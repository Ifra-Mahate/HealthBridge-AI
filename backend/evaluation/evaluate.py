"""
HealthBridge AI evaluation.

Measures, on the annotated set in dataset.json:
  1. Clinical extraction quality (precision / recall / F1 per entity type)
  2. Timetable accuracy (correct time slots per medicine)
  3. Information preservation of the rule-based writer in English, Hindi and Marathi
  4. Verifier sensitivity, using fault injection: known errors are inserted into
     correct outputs and we count how many the verifier catches. "Hard" faults are
     included on purpose to document the verifier's blind spots.
  5. Readability: Flesch-Kincaid grade and clinical abbreviations, before vs after
  6. (optional, --llm N) The same preservation checks on live LLM output

Usage (from the backend folder):
    python -m evaluation.evaluate            # offline, deterministic
    python -m evaluation.evaluate --llm 10   # also evaluate 10 items with the configured LLM
"""
import argparse
import asyncio
import copy
import json
import random
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from app.main import _card, _str_list  # noqa: E402
from app.models.schemas import StructuredCards  # noqa: E402
from app.services.extractor import ClinicalExtractor  # noqa: E402
from app.services.fallback import NON_SYMPTOM_WARNINGS, build_rule_based_content  # noqa: E402
from app.services.timetable import build_timetable  # noqa: E402
from app.services.verifier import MULTILINGUAL_NEGATIONS, InformationVerifier  # noqa: E402

LANGS = ["en", "hi", "mr"]
random.seed(7)


# ----------------------------------------------------------------------------- helpers
def norm(s: str) -> str:
    """Lower-case, collapse spaces, and treat '500mg' and '500 mg' as the same."""
    s = re.sub(r"\s+", " ", s.strip().lower())
    return re.sub(r"(\d)\s+(?=(?:mg|mcg|ml|g|iu|units?|%)\b)", r"\1", s)


def canonical_frequency(entry: str) -> str:
    m = re.search(r"\[(.*)\]", entry)
    label = m.group(1) if m else entry
    return re.sub(r"\s*\([A-Z]+\)\s*$", "", label).strip()


def prf(tp: int, n_pred: int, n_gold: int):
    p = tp / n_pred if n_pred else 1.0
    r = tp / n_gold if n_gold else 1.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


def cards_from(data: dict) -> StructuredCards:
    """Same construction the API uses, so the verifier sees exactly what users see."""
    text = str(data.get("simplified_text") or "")
    return StructuredCards(
        dosage=_card(data.get("dosage_card"), "Dosage", "x", "pill"),
        frequency=_card(data.get("frequency_card"), "Frequency", "x", "clock"),
        timing=_card(data.get("timing_card"), "Timing", "x", "utensils"),
        precautions=_card(data.get("precautions_card"), "Precautions", "x", "shield-alert"),
        warning_signs=_card(data.get("warning_signs_card"), "Warning Signs", "x", "alert-triangle"),
        patient_summary=_str_list(data.get("patient_summary")),
        read_aloud_text=str(data.get("read_aloud_text") or text),
    )


def verify(raw: str, extracted, data: dict, lang: str, strict: bool = True):
    return InformationVerifier.verify(raw, extracted, str(data.get("simplified_text") or ""), cards_from(data), lang, strict=strict)


def map_strings(obj, fn):
    """Applies fn to every user-facing string in an LLM-shaped output dict."""
    if isinstance(obj, str):
        return fn(obj)
    if isinstance(obj, list):
        return [map_strings(x, fn) for x in obj]
    if isinstance(obj, dict):
        return {k: (v if k in ("icon", "title") else map_strings(v, fn)) for k, v in obj.items()}
    return obj


def num_str(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else str(v)


def num_re(s: str):
    return re.compile(rf"(?<![\d.]){re.escape(s)}(?![\d.])")


# ----------------------------------------------------------------------------- 1. extraction
def evaluate_extraction(items):
    totals = {k: [0, 0, 0] for k in ("medications", "frequencies", "durations", "warnings")}
    prohibition = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    errors = []
    for it in items:
        e = ClinicalExtractor.extract_all(it["text"])
        g = it["gold"]
        pred = {
            "medications": {norm(m) for m in e.medications},
            "frequencies": {canonical_frequency(f) for f in e.frequencies},
            "durations": {norm(d) for d in e.durations},
        }
        gold = {
            "medications": {norm(m) for m in g["medications"]},
            "frequencies": set(g["frequencies"]),
            "durations": {norm(d) for d in g["durations"]},
        }
        for key in pred:
            tp = len(pred[key] & gold[key])
            totals[key][0] += tp
            totals[key][1] += len(pred[key])
            totals[key][2] += len(gold[key])
            for miss in gold[key] - pred[key]:
                errors.append((it["id"], key, "missed", miss))
            for extra in pred[key] - gold[key]:
                errors.append((it["id"], key, "spurious", extra))

        # Warning signs: fuzzy phrase match, after removing non-symptom triggers (as the app does)
        pw = [norm(w) for w in e.warnings if norm(w) not in NON_SYMPTOM_WARNINGS]
        gw = [norm(w) for w in g["warnings"]]
        matched_gold = sum(any(p in gg or gg in p for p in pw) for gg in gw)
        matched_pred = sum(any(p in gg or gg in p for gg in gw) for p in pw)
        totals["warnings"][0] += matched_gold
        totals["warnings"][1] += len(pw)
        totals["warnings"][2] += len(gw)
        totals.setdefault("_warn_pred_tp", 0)
        totals["_warn_pred_tp"] += matched_pred
        for gg in gw:
            if not any(p in gg or gg in p for p in pw):
                errors.append((it["id"], "warnings", "missed", gg))
        for p in pw:
            if not any(p in gg or gg in p for gg in gw):
                errors.append((it["id"], "warnings", "spurious", p))

        has_pred = bool(e.negations)
        key = ("tp" if g["has_prohibition"] else "fp") if has_pred else ("fn" if g["has_prohibition"] else "tn")
        prohibition[key] += 1

    results = {}
    for key in ("medications", "frequencies", "durations"):
        tp, n_pred, n_gold = totals[key]
        results[key] = prf(tp, n_pred, n_gold) + (n_gold,)
    # warnings: precision from matched predictions, recall from matched gold
    _, n_pred, n_gold = totals["warnings"]
    p = totals["_warn_pred_tp"] / n_pred if n_pred else 1.0
    r = totals["warnings"][0] / n_gold if n_gold else 1.0
    results["warnings"] = (p, r, 2 * p * r / (p + r) if p + r else 0.0, n_gold)
    t = prohibition
    results["prohibitions"] = prf(t["tp"], t["tp"] + t["fp"], t["tp"] + t["fn"]) + (t["tp"] + t["fn"],)
    return results, errors


# ----------------------------------------------------------------------------- 2. timetable
def evaluate_timetable(items):
    total = recognised = correct = correct_given_recognised = 0
    errors = []
    for it in items:
        gold_tt = it["gold"]["timetable"]
        if not gold_tt:
            continue
        pred = {norm(x.medicine): x for x in build_timetable(it["text"], ClinicalExtractor.extract_all(it["text"]))}
        for med, exp in gold_tt.items():
            total += 1
            got = pred.get(norm(med))
            if got is None:
                errors.append((it["id"], med, "medicine not recognised"))
                continue
            recognised += 1
            ok = list(got.slots) == exp["slots"] and got.as_needed == exp["as_needed"]
            if ok:
                correct += 1
                correct_given_recognised += 1
            else:
                errors.append((it["id"], med, f"expected {exp['slots']}{' +PRN' if exp['as_needed'] else ''}, "
                                              f"got {list(got.slots)}{' +PRN' if got.as_needed else ''}"))
    return {
        "entries": total,
        "accuracy": correct / total if total else 0,
        "recognised": recognised / total if total else 0,
        "accuracy_when_recognised": correct_given_recognised / recognised if recognised else 0,
    }, errors


# ----------------------------------------------------------------------------- 3. preservation
def evaluate_preservation(items):
    out = {}
    for lang in LANGS:
        scores, verified, numeric_ok, numbers_total, numbers_kept = [], 0, 0, 0, 0
        for it in items:
            e = ClinicalExtractor.extract_all(it["text"])
            data = build_rule_based_content(it["text"], lang, e)
            rep = verify(it["text"], e, data, lang)
            scores.append(rep.score)
            verified += rep.status == "VERIFIED"
            numeric_ok += rep.numeric_check.passed
            numbers_total += len(rep.numeric_check.items_original)
            numbers_kept += len(rep.numeric_check.items_verified)
        out[lang] = {
            "mean_score": statistics.mean(scores),
            "verified_rate": verified / len(items),
            "all_numbers_kept_rate": numeric_ok / len(items),
            "number_preservation": numbers_kept / numbers_total if numbers_total else 1,
        }
    return out


# ----------------------------------------------------------------------------- 4. fault injection
def _negation_sentence(s: str) -> bool:
    low = s.lower()
    return any(n in low for n in MULTILINGUAL_NEGATIONS)


def drop_negation_sentences(text: str) -> str:
    parts = re.split(r"(?<=[.।!?])\s+", text)
    return " ".join(p for p in parts if not _negation_sentence(p))


def faults_for(raw, e, data):
    """Yields (fault_name, is_hard, mutated_data, check_name) for one clean output."""
    out_numbers = {num_str(n.value) for n in e.numbers
                   if num_re(num_str(n.value)).search(json.dumps(data, ensure_ascii=False))}
    nums = sorted(out_numbers, key=lambda s: -float(s))

    if nums:
        target = nums[0]
        new = str(int(float(target) * 2)) if float(target) else "1"
        yield "Dose number altered", False, map_strings(copy.deepcopy(data), lambda s: num_re(target).sub(new, s)), "numeric_check"
        yield "Dose number deleted", False, map_strings(copy.deepcopy(data), lambda s: num_re(target).sub("", s)), "numeric_check"

    if e.negations:
        d = map_strings(copy.deepcopy(data), drop_negation_sentences)
        d["precautions_card"]["items"] = []
        d["precautions_card"]["content"] = "Follow your doctor's advice."
        yield "All prohibitions removed", False, d, "negation_check"

    if e.warnings:
        d = copy.deepcopy(data)
        d["warning_signs_card"]["items"] = []
        d["warning_signs_card"]["content"] = ""
        yield "Warning signs removed", False, d, "warning_check"

    if e.frequencies:
        d = copy.deepcopy(data)
        d["frequency_card"]["content"] = ""
        d["frequency_card"]["items"] = None
        yield "Schedule removed", False, d, "frequency_check"

    # ---- hard faults: expected to expose verifier limitations
    if len(nums) >= 2:
        a, b = nums[0], nums[1]

        def swap_values(s, a=a, b=b):
            s = num_re(a).sub("\u0000A", s)
            s = num_re(b).sub(a, s)
            return s.replace("\u0000A", b)
        yield "Two dose numbers swapped", True, map_strings(copy.deepcopy(data), swap_values), "numeric_check"

    # Only prohibitions that come from the prescription itself are valid targets.
    # The writer's generic advice ("Do not share this medicine") is not source content.
    items = data["precautions_card"].get("items") or []
    source = [n.lower().rstrip(".") for n in e.negations]
    from_source = [i for i in items if i.lower().rstrip(".") in source]
    if len(from_source) >= 2:
        d = copy.deepcopy(data)
        dropped = from_source[0]
        d["precautions_card"]["items"] = [i for i in items if i != dropped]
        d = map_strings(d, lambda s: s.replace(dropped, ""))
        yield "One of several prohibitions removed", True, d, "negation_check"

    neg_items = [i for i in from_source if re.match(r"(?i)\s*(do not|avoid|never)\b", i)]
    if neg_items:
        d = copy.deepcopy(data)
        first = neg_items[0]
        flipped = re.sub(r"(?i)^\s*(do not|avoid|never)\s+", "", first)
        flipped = flipped[:1].upper() + flipped[1:]
        d["precautions_card"]["items"] = [flipped if i == first else i for i in items]
        yield "Prohibition inverted (\"Do not X\" -> \"X\")", True, d, "negation_check"


def evaluate_faults(items, lang="en"):
    """Runs every fault against verifier v1 (strict=False) and v2 (strict=True)."""
    stats = {}
    clean_flagged = {"v1": 0, "v2": 0}
    for it in items:
        e = ClinicalExtractor.extract_all(it["text"])
        data = build_rule_based_content(it["text"], lang, e)
        for version, strict in (("v1", False), ("v2", True)):
            clean_flagged[version] += verify(it["text"], e, data, lang, strict).status != "VERIFIED"
        for name, hard, mutated, check in faults_for(it["text"], e, data):
            s = stats.setdefault(name, {"hard": hard, "n": 0, "v1": 0, "v2": 0})
            s["n"] += 1
            for version, strict in (("v1", False), ("v2", True)):
                s[version] += not getattr(verify(it["text"], e, mutated, lang, strict), check).passed
    return stats, {k: v / len(items) for k, v in clean_flagged.items()}


# ----------------------------------------------------------------------------- 5. readability
ABBREVIATIONS = re.compile(
    r"\b(PO|QD|OD|BID|BD|TID|TDS|QID|QDS|PRN|SOS|HS|AC|PC|Rx|STAT|Tab|Cap|Syp)\b|\bq\d+h\b|\bx\s*\d+\s*(?:days?|weeks?)\b"
)


def syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups)
    if w.endswith("e") and not w.endswith(("le", "ee")) and n > 1:
        n -= 1
    return max(1, n)


def fk_grade(text: str) -> float:
    sentences = max(1, len(re.findall(r"[.!?]+", text)))
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    if not words:
        return 0.0
    syl = sum(syllables(w) for w in words)
    return 0.39 * (len(words) / sentences) + 11.8 * (syl / len(words)) - 15.59


def evaluate_readability(items):
    before_fk, after_fk, before_ab, after_ab = [], [], 0, 0
    for it in items:
        data = build_rule_based_content(it["text"], "en", ClinicalExtractor.extract_all(it["text"]))
        out = data["simplified_text"].split("Exact words from your prescription:")[0]
        before_fk.append(fk_grade(it["text"]))
        after_fk.append(fk_grade(out))
        before_ab += len(ABBREVIATIONS.findall(it["text"]))
        after_ab += len(ABBREVIATIONS.findall(out))
    return {
        "fk_before": statistics.mean(before_fk), "fk_after": statistics.mean(after_fk),
        "abbr_before": before_ab, "abbr_after": after_ab,
    }


# ----------------------------------------------------------------------------- 6. optional LLM
async def evaluate_llm(items, n):
    from app.services.ai_service import AISimplificationService
    rows = []
    for it in items[:n]:
        e = ClinicalExtractor.extract_all(it["text"])
        t0 = time.time()
        res = await AISimplificationService.simplify(it["text"], "en", e)
        latency = time.time() - t0
        rep = verify(it["text"], e, res["data"], "en")
        rows.append({
            "id": it["id"], "live": res["ai_configured"], "provider": res["ai_provider"],
            "score": rep.score, "status": rep.status, "numbers_ok": rep.numeric_check.passed,
            "missing": rep.numeric_check.items_missing, "latency": latency,
        })
        print(f"  {it['id']}: {rep.status} {rep.score} ({latency:.0f}s, live={res['ai_configured']})", flush=True)
    return rows


# ----------------------------------------------------------------------------- report
def pct(x):
    return f"{100 * x:.1f}%"


def write_report(path, dev, test, pres, faults, clean_fp, read, llm):
    n_dev, n_test = dev["n"], test["n"]
    L = []
    L.append("# Evaluation Report\n")
    L.append(f"Generated by `backend/evaluation/evaluate.py` on {time.strftime('%Y-%m-%d')}. "
             "All sections except the optional live-LLM section are deterministic and reproducible offline.\n")
    L.append("## Data\n")
    L.append(f"- **Development set** (`dataset.json`, {n_dev} prescriptions): used while building and debugging the system. "
             "Scores on this set are optimistic.")
    L.append(f"- **Held-out test set** (`heldout.json`, {n_test} prescriptions): written after development was frozen, "
             "in phrasing styles the rules were not tuned for. The code was not changed after these results were first computed.")
    L.append("- All prescriptions are fictional and were annotated by the project author.\n")

    L.append("## 1. Clinical Information Extraction\n")
    L.append("| Entity | Dev F1 | Test precision | Test recall | Test F1 | Test gold items |\n| --- | --- | --- | --- | --- | --- |")
    names = {"medications": "Medicine name and strength", "frequencies": "Dosing frequency",
             "durations": "Course duration", "warnings": "Warning signs", "prohibitions": "Prohibition present"}
    for k, label in names.items():
        p, r, f, n = test["ext"][k]
        L.append(f"| {label} | {pct(dev['ext'][k][2])} | {pct(p)} | {pct(r)} | {pct(f)} | {n} |")
    L.append("")

    L.append("## 2. Medicine Timetable\n")
    L.append("| Metric | Dev | Test |\n| --- | --- | --- |")
    L.append(f"| Entries evaluated | {dev['tt']['entries']} | {test['tt']['entries']} |")
    L.append(f"| Exact slot accuracy | {pct(dev['tt']['accuracy'])} | {pct(test['tt']['accuracy'])} |")
    L.append(f"| Medicine recognised | {pct(dev['tt']['recognised'])} | {pct(test['tt']['recognised'])} |")
    L.append(f"| Slot accuracy when recognised | {pct(dev['tt']['accuracy_when_recognised'])} | {pct(test['tt']['accuracy_when_recognised'])} |\n")

    n_all = n_dev + n_test
    L.append(f"## 3. Information Preservation (rule-based writer, all {n_all} prescriptions)\n")
    L.append("| Language | Mean safety score | Rated VERIFIED | All numbers kept | Numbers kept |\n| --- | --- | --- | --- | --- |")
    for lang, name in (("en", "English"), ("hi", "Hindi"), ("mr", "Marathi")):
        r = pres[lang]
        L.append(f"| {name} | {r['mean_score']:.1f} | {pct(r['verified_rate'])} | {pct(r['all_numbers_kept_rate'])} | {pct(r['number_preservation'])} |")
    L.append("")

    L.append(f"## 4. Verifier Sensitivity (fault injection, all {n_all} prescriptions)\n")
    L.append("A known error is inserted into an otherwise correct English output, and we record whether the relevant safety check fails. "
             "Standard faults are errors the original verifier (v1) was designed to catch. Subtle faults probe its blind spots. "
             "Verifier v2 adds dose-to-unit and dose-to-medicine binding, and per-prohibition coverage.\n")
    L.append("| Fault | Type | Cases | Detected by v1 | Detected by v2 |\n| --- | --- | --- | --- | --- |")
    for name, s in sorted(faults.items(), key=lambda kv: (kv[1]["hard"], kv[0])):
        L.append(f"| {name} | {'Subtle' if s['hard'] else 'Standard'} | {s['n']} | {pct(s['v1'] / s['n'])} | {pct(s['v2'] / s['n'])} |")
    L.append(f"\nFalse alarm rate on unmodified outputs: v1 {pct(clean_fp['v1'])}, v2 {pct(clean_fp['v2'])}.\n")

    L.append(f"## 5. Readability (English, all {n_all} prescriptions)\n")
    L.append("| Metric | Original prescription | HealthBridge output |\n| --- | --- | --- |")
    L.append(f"| Clinical abbreviations (total) | {read['abbr_before']} | {read['abbr_after']} |")
    L.append(f"| Flesch-Kincaid grade (mean) | {read['fk_before']:.1f} | {read['fk_after']:.1f} |")
    L.append("\nThe Flesch-Kincaid formula treats abbreviations such as \"PO\" or \"TID\" as short, easy words, so it under-estimates how hard "
             "the original prescriptions are. The abbreviation count is the more meaningful measure here.\n")

    if llm:
        live = [r for r in llm if r["live"]]
        L.append("## 6. Live LLM Output\n")
        if live:
            L.append(f"Provider: {live[0]['provider']}. Items: {len(live)} from the development set, English output, checked by verifier v2.\n")
            L.append("| Metric | Value |\n| --- | --- |")
            L.append(f"| Mean safety score | {statistics.mean(r['score'] for r in live):.1f} |")
            L.append(f"| Rated VERIFIED | {pct(sum(r['status'] == 'VERIFIED' for r in live) / len(live))} |")
            L.append(f"| All numbers kept | {pct(sum(r['numbers_ok'] for r in live) / len(live))} |")
            L.append(f"| Median latency | {statistics.median(r['latency'] for r in live):.0f} s |")
            flagged = [r for r in live if r["status"] != "VERIFIED"]
            if flagged:
                L.append("\nOutputs the verifier flagged: " + "; ".join(
                    f"{r['id']} (score {r['score']}{': ' + ', '.join(r['missing']) if r['missing'] else ''})" for r in flagged) + ".")
        fell_back = [r for r in llm if not r["live"]]
        if fell_back:
            L.append(f"\n{len(fell_back)} request(s) fell back to the rule engine because the AI call failed or timed out.")
        L.append("")

    L.append("## Error Analysis (held-out test set)\n")
    L.append("| Item | Field | Error |\n| --- | --- | --- |")
    for item_id, field, kind, value in test["ext_err"]:
        L.append(f"| {item_id} | {field} | {kind}: `{value}` |")
    for item_id, med, msg in test["tt_err"]:
        L.append(f"| {item_id} | timetable ({med}) | {msg} |")
    L.append("\nRemaining development-set errors:\n")
    L.append("| Item | Field | Error |\n| --- | --- | --- |")
    for item_id, field, kind, value in dev["ext_err"]:
        L.append(f"| {item_id} | {field} | {kind}: `{value}` |")
    for item_id, med, msg in dev["tt_err"]:
        L.append(f"| {item_id} | timetable ({med}) | {msg} |")
    L.append("")

    L.append("## Limitations of This Evaluation\n")
    L.append(f"- The data is small ({n_all} items), fictional and annotated by the project author, so results indicate behaviour rather than clinical accuracy.")
    L.append("- Warning-sign matching uses phrase overlap, which can be lenient for partial matches.")
    L.append("- Fault injection tests the verifier against synthetic errors. Real model errors can be subtler.")
    L.append("- Per-prohibition coverage is checked for English output only. Hindi and Marathi rely on the v1 negation check plus dose binding.")
    L.append("- No patient comprehension study was performed.")
    Path(path).write_text("\n".join(L) + "\n", encoding="utf-8")


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))["items"]


def split_results(items):
    ext, ext_err = evaluate_extraction(items)
    tt, tt_err = evaluate_timetable(items)
    return {"n": len(items), "ext": ext, "ext_err": ext_err, "tt": tt, "tt_err": tt_err}


def main():
    parser = argparse.ArgumentParser(description="Evaluate HealthBridge AI")
    parser.add_argument("--llm", type=int, default=0, help="also evaluate N development items with the configured LLM (slow, uses API quota)")
    args = parser.parse_args()

    dev_items, test_items = load("dataset.json"), load("heldout.json")
    dev, test = split_results(dev_items), split_results(test_items)
    everything = dev_items + test_items
    pres = evaluate_preservation(everything)
    faults, clean_fp = evaluate_faults(everything)
    read = evaluate_readability(everything)
    llm = asyncio.run(evaluate_llm(dev_items, args.llm)) if args.llm else []

    report = ROOT.parent.parent / "docs" / "EVALUATION.md"
    report.parent.mkdir(exist_ok=True)
    write_report(report, dev, test, pres, faults, clean_fp, read, llm)

    def ext_json(ext):
        return {k: dict(zip(("precision", "recall", "f1", "gold"), v)) for k, v in ext.items()}

    (ROOT / "results.json").write_text(json.dumps({
        "development": {"extraction": ext_json(dev["ext"]), "timetable": dev["tt"]},
        "heldout": {"extraction": ext_json(test["ext"]), "timetable": test["tt"]},
        "preservation": pres, "fault_injection": faults, "clean_false_alarm_rate": clean_fp,
        "readability": read, "llm": llm,
    }, indent=2), encoding="utf-8")
    print(report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
