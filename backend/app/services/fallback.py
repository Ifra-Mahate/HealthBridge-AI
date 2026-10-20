"""
Rule-based plain-language generator.

Used when no LLM key is configured or the live call fails. It only rephrases
facts found by ClinicalExtractor, so it never invents doses. Any number from the
original text that the templates did not already cover is carried over word for
word, so the verifier never sees a silently dropped number.
"""
import re
from typing import Any, Dict, List

from ..models.schemas import ExtractedEntities
from .extractor import ClinicalExtractor
from .verifier import extract_all_numbers

# Extractor hits that describe an action, not a symptom the patient should watch for
NON_SYMPTOM_WARNINGS = {
    "emergency", "seek immediate medical", "discontinue immediately", "stop taking immediately",
}

FREQ_TEXT = {
    "Once a day": {"en": "once a day", "hi": "दिन में 1 बार", "mr": "दिवसातून 1 वेळा"},
    "Twice a day": {"en": "2 times a day", "hi": "दिन में 2 बार", "mr": "दिवसातून 2 वेळा"},
    "3 times a day": {"en": "3 times a day", "hi": "दिन में 3 बार", "mr": "दिवसातून 3 वेळा"},
    "4 times a day": {"en": "4 times a day", "hi": "दिन में 4 बार", "mr": "दिवसातून 4 वेळा"},
    "As needed": {"en": "only when needed", "hi": "ज़रूरत पड़ने पर", "mr": "गरज असेल तेव्हाच"},
    "At bedtime": {"en": "at bedtime", "hi": "रात को सोने से पहले", "mr": "रात्री झोपण्यापूर्वी"},
    "Every morning": {"en": "every morning", "hi": "हर सुबह", "mr": "दररोज सकाळी"},
    "Every morning and night": {"en": "every morning and night", "hi": "हर सुबह और रात", "mr": "दररोज सकाळी आणि रात्री"},
    "Every night": {"en": "every night", "hi": "हर रात", "mr": "दररोज रात्री"},
}

TIMING_TEXT = [
    (r"with\s+breakfast\s+and\s+dinner", {"en": "with breakfast and dinner", "hi": "नाश्ते और रात के खाने के साथ", "mr": "नाश्ता आणि रात्रीच्या जेवणासोबत"}),
    (r"with\s+(food|meals?)", {"en": "with food", "hi": "खाने के साथ", "mr": "जेवणासोबत"}),
    (r"with\s+milk", {"en": "with milk", "hi": "दूध के साथ", "mr": "दुधासोबत"}),
    (r"with\s+breakfast", {"en": "with breakfast", "hi": "नाश्ते के साथ", "mr": "नाश्त्यासोबत"}),
    (r"with\s+dinner", {"en": "with dinner", "hi": "रात के खाने के साथ", "mr": "रात्रीच्या जेवणासोबत"}),
    (r"after\s+(food|meals?|eating)", {"en": "after eating", "hi": "खाना खाने के बाद", "mr": "जेवणानंतर"}),
    (r"^before\s+(food|meals?|eating)", {"en": "before eating", "hi": "खाना खाने से पहले", "mr": "जेवणापूर्वी"}),
    (r"empty\s+stomach", {"en": "on an empty stomach", "hi": "खाली पेट", "mr": "उपाशीपोटी"}),
    (r"^in\s+the\s+morning", {"en": "in the morning", "hi": "सुबह", "mr": "सकाळी"}),
    (r"^at\s+bedtime", {"en": "at bedtime", "hi": "सोने से पहले", "mr": "झोपण्यापूर्वी"}),
    (r"full\s+glass\s+of\s+water", {"en": "with a full glass of water", "hi": "एक पूरे गिलास पानी के साथ", "mr": "एक पूर्ण ग्लास पाण्यासोबत"}),
]

DURATION_UNITS = {
    "day": {"en": "day", "hi": "दिन", "mr": "दिवस"},
    "days": {"en": "days", "hi": "दिन", "mr": "दिवस"},
    "week": {"en": "week", "hi": "हफ़्ता", "mr": "आठवडा"},
    "weeks": {"en": "weeks", "hi": "हफ़्ते", "mr": "आठवडे"},
    "month": {"en": "month", "hi": "महीना", "mr": "महिना"},
    "months": {"en": "months", "hi": "महीने", "mr": "महिने"},
}

# Every user-facing sentence, per language. {placeholders} are filled below.
T = {
    "en": {
        "dose_title": "How much to take",
        "dose_one": "Take {dose} each time.",
        "dose_many": "Your medicines and how much of each to take:",
        "dose_unknown": "Take the amount written on your prescription label.",
        "dose_tip": "Do not take extra or skip doses unless your doctor says so.",
        "freq_title": "How often",
        "freq": "Take it {freq}.",
        "freq_unknown": "Follow the schedule your doctor gave you.",
        "freq_tip": "Try to take it at the same times every day.",
        "duration": "Keep taking it for {dur}, even if you feel better.",
        "time_title": "Food and timing",
        "time": "Take it {timing}.",
        "time_unknown": "No special food rule was found. Take it with a glass of water.",
        "avoid_title": "Things to avoid",
        "avoid": "Please follow these rules carefully:",
        "avoid_default": ["Do not change the dose on your own.", "Do not share this medicine with anyone."],
        "warn_title": "Get help right away if",
        "warn": "Stop the medicine and contact a doctor or hospital immediately if you notice:",
        "warn_default": ["Rash, itching or swelling of the face", "Trouble breathing", "Feeling very unwell"],
        "summary_dose": "Take {dose}.",
        "summary_freq": "Take it {freq}.",
        "summary_safety": "If something feels wrong, call your doctor.",
        "extra": "Exact words from your prescription: {extra}",
        "intro": "Here are your medicine instructions in simple words.",
        "outro": "Do not change your dose without asking your doctor.",
        "freq_many": "Each medicine has its own schedule:",
        "time_many": "Food and time rules for each medicine:",
        "med_line": "Take {med} {when}.",
        "original_words": "",
    },
    "hi": {
        "dose_title": "कितनी दवा लेनी है",
        "dose_one": "हर बार {dose} लें।",
        "dose_many": "आपकी दवाएं और हर दवा की मात्रा:",
        "dose_unknown": "पर्चे पर लिखी मात्रा के अनुसार दवा लें।",
        "dose_tip": "डॉक्टर से पूछे बिना ज़्यादा दवा न लें और कोई खुराक न छोड़ें।",
        "freq_title": "कितनी बार",
        "freq": "यह दवा {freq} लें।",
        "freq_unknown": "डॉक्टर के बताए समय पर दवा लें।",
        "freq_tip": "हर दिन एक ही समय पर दवा लेने की कोशिश करें।",
        "duration": "यह दवा {dur} तक लें, भले ही आप बेहतर महसूस करें।",
        "time_title": "खाना और समय",
        "time": "दवा {timing} लें।",
        "time_unknown": "खाने का कोई खास नियम नहीं मिला। दवा एक गिलास पानी के साथ लें।",
        "avoid_title": "क्या न करें",
        "avoid": "इन नियमों का ध्यान से पालन करें:",
        "avoid_default": ["अपने आप दवा की मात्रा न बदलें।", "यह दवा किसी और को न दें।"],
        "warn_title": "तुरंत मदद लें अगर",
        "warn": "इनमें से कुछ भी हो तो दवा बंद करें और तुरंत डॉक्टर या अस्पताल से संपर्क करें:",
        "warn_default": ["चेहरे पर सूजन, खुजली या दाने", "सांस लेने में तकलीफ़", "बहुत ज़्यादा तबीयत खराब लगना"],
        "summary_dose": "{dose} लें।",
        "summary_freq": "दवा {freq} लें।",
        "summary_safety": "कुछ भी गलत लगे तो डॉक्टर को फ़ोन करें।",
        "extra": "आपके पर्चे के मूल शब्द: {extra}",
        "intro": "आपकी दवा की जानकारी आसान शब्दों में।",
        "outro": "डॉक्टर से पूछे बिना दवा की मात्रा न बदलें।",
        "freq_many": "हर दवा का अपना समय है:",
        "time_many": "हर दवा के लिए खाने और समय के नियम:",
        "med_line": "{med} {when} लें।",
        "original_words": " (पर्चे के मूल शब्दों में)",
    },
    "mr": {
        "dose_title": "किती औषध घ्यायचे",
        "dose_one": "प्रत्येक वेळी {dose} घ्या.",
        "dose_many": "तुमची औषधे आणि प्रत्येकाचे प्रमाण:",
        "dose_unknown": "प्रिस्क्रिप्शनवर लिहिलेल्या प्रमाणानुसार औषध घ्या.",
        "dose_tip": "डॉक्टरांना विचारल्याशिवाय जास्त औषध घेऊ नका किंवा डोस चुकवू नका.",
        "freq_title": "किती वेळा",
        "freq": "हे औषध {freq} घ्या.",
        "freq_unknown": "डॉक्टरांनी सांगितलेल्या वेळेनुसार औषध घ्या.",
        "freq_tip": "दररोज एकाच वेळी औषध घेण्याचा प्रयत्न करा.",
        "duration": "बरे वाटले तरीही हे औषध {dur} घ्या.",
        "time_title": "जेवण आणि वेळ",
        "time": "औषध {timing} घ्या.",
        "time_unknown": "जेवणाचा कोणताही विशेष नियम सापडला नाही. औषध एक ग्लास पाण्यासोबत घ्या.",
        "avoid_title": "काय करू नये",
        "avoid": "हे नियम काळजीपूर्वक पाळा:",
        "avoid_default": ["स्वतःहून औषधाचे प्रमाण बदलू नका.", "हे औषध इतरांना देऊ नका."],
        "warn_title": "लगेच मदत घ्या जर",
        "warn": "यापैकी काहीही जाणवल्यास औषध थांबवा आणि ताबडतोब डॉक्टर किंवा रुग्णालयाशी संपर्क साधा:",
        "warn_default": ["चेहऱ्यावर सूज, खाज किंवा पुरळ", "श्वास घेण्यास त्रास", "खूप अस्वस्थ वाटणे"],
        "summary_dose": "{dose} घ्या.",
        "summary_freq": "औषध {freq} घ्या.",
        "summary_safety": "काहीही चुकीचे वाटल्यास डॉक्टरांना फोन करा.",
        "extra": "तुमच्या प्रिस्क्रिप्शनमधील मूळ शब्द: {extra}",
        "intro": "तुमच्या औषधाची माहिती सोप्या शब्दांत.",
        "outro": "डॉक्टरांना विचारल्याशिवाय डोस बदलू नका.",
        "freq_many": "प्रत्येक औषधाची वेळ वेगळी आहे:",
        "time_many": "प्रत्येक औषधासाठी जेवण आणि वेळेचे नियम:",
        "med_line": "{med} {when} घ्या.",
        "original_words": " (प्रिस्क्रिप्शनमधील मूळ शब्दांत)",
    },
}

LIST_JOIN = {"en": " and ", "hi": " और ", "mr": " आणि "}


def _join(items: List[str], lang: str) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + LIST_JOIN[lang] + items[-1]


def _canonical_frequency(entry: str) -> str:
    """'TID [3 times a day (TID)]' -> '3 times a day'."""
    match = re.search(r"\[(.*)\]", entry)
    label = match.group(1) if match else entry
    return re.sub(r"\s*\([A-Z]+\)\s*$", "", label).strip()


def _frequency_text(entry: str, lang: str) -> str:
    label = _canonical_frequency(entry)
    if label in FREQ_TEXT:
        return FREQ_TEXT[label][lang]
    hours = re.match(r"Every\s+([\d-]+)\s+hours", label)
    if hours:
        n = hours.group(1)
        return {"en": f"every {n} hours", "hi": f"हर {n} घंटे में", "mr": f"दर {n} तासांनी"}[lang]
    return label


MEAL_WORDS = {
    # meal: (hindi, marathi genitive)
    "breakfast": ("नाश्ते", "नाश्त्याच्या"),
    "lunch": ("दोपहर के खाने", "दुपारच्या जेवणाच्या"),
    "dinner": ("रात के खाने", "रात्रीच्या जेवणाच्या"),
    "meal": ("खाने", "जेवणाच्या"),
    "meals": ("खाने", "जेवणाच्या"),
    "food": ("खाने", "जेवणाच्या"),
}

SYMPTOM_TEXT = {
    "rash": ("दाने या चकत्ते", "अंगावर पुरळ"),
    "rashes": ("दाने या चकत्ते", "अंगावर पुरळ"),
    "hives": ("पित्ती (खुजली वाले चकत्ते)", "अंगावर पित्त उठणे"),
    "difficulty breathing": ("सांस लेने में तकलीफ़", "श्वास घेण्यास त्रास"),
    "breathing difficulty": ("सांस लेने में तकलीफ़", "श्वास घेण्यास त्रास"),
    "shortness of breath": ("सांस फूलना", "धाप लागणे"),
    "facial swelling": ("चेहरे पर सूजन", "चेहऱ्यावर सूज"),
    "swelling": ("सूजन", "सूज"),
    "swelling of legs": ("पैरों में सूजन", "पायांना सूज"),
    "swelling of the face": ("चेहरे पर सूजन", "चेहऱ्यावर सूज"),
    "chest pain": ("सीने में दर्द", "छातीत दुखणे"),
    "fever": ("बुखार", "ताप"),
    "jaundice": ("पीलिया (त्वचा पीली होना)", "कावीळ (त्वचा पिवळी होणे)"),
    "dark urine": ("गहरे रंग का पेशाब", "गडद रंगाची लघवी"),
    "allergic reaction": ("एलर्जी", "ॲलर्जी"),
    "weight gain": ("अचानक वज़न बढ़ना", "अचानक वजन वाढणे"),
    "cold sweats": ("ठंडा पसीना", "थंड घाम"),
    "shaky": ("कांपना", "थरथर कापणे"),
    "black tarry stools": ("काला, चिपचिपा मल", "काळी, डांबरासारखी शौच"),
    "persistent stomach burning": ("पेट में लगातार जलन", "पोटात सतत जळजळ"),
    "stomach burning": ("पेट में जलन", "पोटात जळजळ"),
}


def _symptom_text(entry: str, lang: str) -> str:
    if lang == "en":
        return entry
    pair = SYMPTOM_TEXT.get(entry.lower())
    return pair[0 if lang == "hi" else 1] if pair else entry


def _timing_text(entry: str, lang: str) -> str:
    low = entry.lower()
    gap = re.search(r"(\d+)\s*(minutes?|mins?|hours?)\s+(before|after)\s+(\w+)", low)
    if gap:
        n, unit, rel, meal = gap.groups()
        is_hour = unit.startswith("hour")
        if lang == "en":
            return f"{n} {'hours' if is_hour else 'minutes'} {rel} {meal}"
        hi_meal, mr_meal = MEAL_WORDS.get(meal, (meal, meal))
        if lang == "hi":
            return f"{hi_meal} से {n} {'घंटे' if is_hour else 'मिनट'} {'पहले' if rel == 'before' else 'बाद'}"
        return f"{mr_meal} {n} {'तास' if is_hour else 'मिनिटे'} {'आधी' if rel == 'before' else 'नंतर'}"
    for pattern, texts in TIMING_TEXT:
        if re.search(pattern, low):
            return texts[lang]
    return entry


def _duration_text(entry: str, lang: str) -> str:
    num, unit = entry.split(" ", 1)
    return f"{num} {DURATION_UNITS.get(unit, {}).get(lang, unit)}"


def _sentence(text: str) -> str:
    text = text.strip().rstrip(".")
    return text[:1].upper() + text[1:] + "." if text else text


def _dedupe(items: List[str]) -> List[str]:
    seen, out = set(), []
    for item in items:
        if item and item.lower() not in seen:
            seen.add(item.lower())
            out.append(item)
    return out


def _drop_contained(items: List[str]) -> List[str]:
    """Drops entries that are part of a longer entry ('before breakfast' vs '15 minutes before breakfast')."""
    low = [i.lower() for i in items]
    return [i for i, l in zip(items, low) if not any(l != o and l in o for o in low)]


COUNT_UNITS = {
    "puff": ("पफ़", "पफ"), "tablet": ("गोली", "गोळी"), "tab": ("गोली", "गोळी"),
    "capsule": ("कैप्सूल", "कॅप्सूल"), "cap": ("कैप्सूल", "कॅप्सूल"), "drop": ("बूंद", "थेंब"),
}

NEGATED_CLAUSE = re.compile(r"\b(do\s+not|don't|never|avoid|must\s+not|should\s+not|not)\b", re.IGNORECASE)

# A timing that only repeats a frequency already shown ("in the morning" vs "Every morning")
TIMING_COVERED_BY = {"in the morning": "Every morning", "at bedtime": "At bedtime"}


def _amount(text: str, lang: str) -> str:
    """First per-dose count in the text, such as '2 puffs' or '1-2 tablets'."""
    m = re.search(r"\b(\d+(?:\s*-\s*\d+)?)\s*(puff|tablet|tab|capsule|cap|drop)s?\b", text, re.IGNORECASE)
    if not m:
        return ""
    n, unit = re.sub(r"\s+", "", m.group(1)), m.group(2).lower()
    if lang == "en":
        unit = {"tab": "tablet", "cap": "capsule"}.get(unit, unit)
        return f"{n} {unit}{'' if n == '1' else 's'}"
    return f"{n} {COUNT_UNITS[unit][0 if lang == 'hi' else 1]}"


def _schedule(text: str, lang: str):
    """Plain-language frequencies and timings found in a piece of prescription text."""
    raw_freqs = ClinicalExtractor.extract_frequencies(text)
    canon = {_canonical_frequency(f) for f in raw_freqs}
    # Timings inside a prohibition ("Do NOT take on an empty stomach") are rules, not
    # directions, and stay on the precautions card. Showing them here would invert them.
    allowed: List[str] = []
    for clause in re.split(r"[.;]\s*", text):
        if not NEGATED_CLAUSE.search(clause):
            allowed.extend(ClinicalExtractor.extract_timings(clause))
    raw_timings = [
        x for x in _drop_contained(_dedupe(allowed))
        if TIMING_COVERED_BY.get(x.lower()) not in canon
    ]
    freqs = _dedupe([_frequency_text(f, lang) for f in raw_freqs])
    timings = _dedupe([_timing_text(x, lang) for x in raw_timings])
    return freqs, timings


def _medicine_plans(raw_text: str, medicines: List[str], lang: str):
    """Splits the text at each medicine name so every medicine keeps its own schedule."""
    found = [(raw_text.find(m.split(" ")[0]), m) for m in medicines]
    found = sorted((pos, m) for pos, m in found if pos >= 0)
    plans = []
    for k, (pos, med) in enumerate(found):
        end = found[k + 1][0] if k + 1 < len(found) else len(raw_text)
        segment = raw_text[pos:end]
        freqs, timings = _schedule(segment, lang)
        amount = _amount(segment, lang)
        plans.append({
            "medicine": med, "name": med.split(" ")[0], "freqs": freqs, "timings": timings,
            "when": ([amount] if amount else []) + freqs + timings,
        })
    return plans


def build_rule_based_content(raw_text: str, lang: str, extracted: ExtractedEntities) -> Dict[str, Any]:
    """Builds the same JSON shape the LLM prompt asks for, using only extracted facts."""
    if lang not in T:
        lang = "en"
    t = T[lang]
    medicines = extracted.medications
    durations = [_duration_text(d, lang) for d in extracted.durations]
    duration_line = t["duration"].format(dur=_join(durations, lang)) if durations else ""

    freqs, timings = _schedule(raw_text, lang)
    plans = _medicine_plans(raw_text, medicines, lang) if len(medicines) > 1 else []

    if plans:
        # Several medicines: one line per medicine on each card
        dose_content = t["dose_many"]
        dose_items = medicines
        dose_badge = {"en": f"{len(medicines)} medicines", "hi": f"{len(medicines)} दवाएं", "mr": f"{len(medicines)} औषधे"}[lang]
        freq_items = [f"{p['name']}: {_join(p['freqs'], lang)}" for p in plans if p["freqs"]] or None
        time_items = [f"{p['name']}: {_join(p['timings'], lang)}" for p in plans if p["timings"]] or None
        freq_content = t["freq_many"] if freq_items else t["freq_unknown"]
        if duration_line:
            freq_content += " " + duration_line
        time_content = t["time_many"] if time_items else t["time_unknown"]
        freq_badge = time_badge = None
        med_lines = [
            t["med_line"].format(med=p["medicine"], when=", ".join(p["when"]))
            if p["when"] else t["summary_dose"].format(dose=p["medicine"])
            for p in plans
        ]
        summary = med_lines + [t["summary_safety"]]
        body = list(med_lines)
    else:
        dose = medicines[0] if medicines else (extracted.dosages[0] if extracted.dosages else "")
        dose_items = None
        dose_badge = (extracted.dosages or [dose])[0] if dose else None
        dose_content = (t["dose_one"].format(dose=dose) if dose else t["dose_unknown"]) + " " + t["dose_tip"]
        freq_items = time_items = None
        freq_content = t["freq"].format(freq=_join(freqs, lang)) if freqs else t["freq_unknown"]
        if duration_line:
            freq_content += " " + duration_line
        time_content = t["time"].format(timing=_join(timings, lang)) if timings else t["time_unknown"]
        freq_badge = freqs[0] if freqs else None
        time_badge = timings[0] if timings else None
        summary = []
        if dose:
            summary.append(t["summary_dose"].format(dose=dose))
        if freqs:
            summary.append(t["summary_freq"].format(freq=_join(freqs, lang)))
        body = list(summary) + ([time_content] if timings else [])
        summary.append(t["summary_safety"])
    freq_content += " " + t["freq_tip"]

    # Precautions: every prohibition from the source, without near-duplicates
    negations = [_sentence(n) for n in extracted.negations]
    extra_precautions = [
        _sentence(p) for p in extracted.precautions
        if not any(p.lower() in n.lower() for n in negations)
    ]
    precaution_items = _dedupe(negations + extra_precautions)
    precaution_content = t["avoid"] + (t["original_words"] if precaution_items else "")
    precaution_items = precaution_items or t["avoid_default"]

    # Warning symptoms, translated where a known phrase exists
    symptoms = _dedupe([w for w in extracted.warnings if w.lower() not in NON_SYMPTOM_WARNINGS])
    warning_items = [_sentence(_symptom_text(s, lang)) for s in symptoms] or t["warn_default"]

    simplified_parts = [t["intro"]] + body
    if duration_line:
        simplified_parts.append(duration_line)
    simplified_parts.append(t["outro"])
    simplified_text = " ".join(simplified_parts)

    # Carry over any number the templates above did not mention, in the original words
    produced = " ".join([
        simplified_text, dose_content, " ".join(dose_items or []), freq_content, " ".join(freq_items or []),
        time_content, " ".join(time_items or []), " ".join(precaution_items), " ".join(warning_items),
    ])
    produced_numbers = extract_all_numbers(produced)
    missing = [n for n in extracted.numbers if not any(abs(n.value - v) < 0.01 for v in produced_numbers)]
    if missing:
        sentences = re.split(r"(?<=[.;])\s+", raw_text)
        extra = _dedupe([
            s.strip() for s in sentences
            if any(re.search(rf"(?<![\d.]){re.escape(n.raw_str.split()[0])}(?![\d.])", s) for n in missing)
        ])
        if extra:
            simplified_text += " " + t["extra"].format(extra=" ".join(extra))

    read_aloud = " ".join([simplified_text, t["warn"]] + warning_items)

    return {
        "simplified_text": simplified_text,
        "dosage_card": {"title": t["dose_title"], "content": dose_content, "badge": dose_badge, "items": dose_items, "icon": "pill"},
        "frequency_card": {"title": t["freq_title"], "content": freq_content, "badge": freq_badge, "items": freq_items, "icon": "clock"},
        "timing_card": {"title": t["time_title"], "content": time_content, "badge": time_badge, "items": time_items, "icon": "utensils"},
        "precautions_card": {"title": t["avoid_title"], "content": precaution_content, "items": precaution_items, "icon": "shield-alert"},
        "warning_signs_card": {"title": t["warn_title"], "content": t["warn"], "items": warning_items, "icon": "alert-triangle"},
        "patient_summary": summary,
        "read_aloud_text": read_aloud,
    }
