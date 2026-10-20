from app.data.sample_data import SAMPLE_PRESETS
from app.services.extractor import ClinicalExtractor
from app.services.fallback import build_rule_based_content
from app.main import _card
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_extracts_medicines_and_duration():
    e = ClinicalExtractor.extract_all("Rx: Amoxicillin 500 mg PO TID x 7 days with meals.")
    assert e.medications == ["Amoxicillin 500 mg"]
    assert e.durations == ["7 days"]


def test_every_n_hours_label_keeps_number():
    e = ClinicalExtractor.extract_all("Salbutamol 100 mcg 1-2 puffs every 4-6 hours.")
    assert any("Every 4-6 hours" in f for f in e.frequencies)


def test_fallback_has_no_raw_abbreviation_brackets():
    text = SAMPLE_PRESETS[0].raw_text
    data = build_rule_based_content(text, "en", ClinicalExtractor.extract_all(text))
    assert "[" not in data["frequency_card"]["content"]
    assert "3 times a day" in data["frequency_card"]["content"]
    assert "7 days" in data["frequency_card"]["content"]
    assert all("emergency" != w.lower().rstrip(".") for w in data["warning_signs_card"]["items"])


def test_all_samples_keep_every_number_in_every_language():
    for sample in SAMPLE_PRESETS:
        for lang in ("en", "hi", "mr"):
            res = client.post("/api/simplify", json={"raw_text": sample.raw_text, "target_language": lang})
            assert res.status_code == 200
            check = res.json()["verification"]["numeric_check"]
            assert check["passed"], (sample.id, lang, check["items_missing"])


def test_card_defaults_fill_missing_llm_fields():
    card = _card({"content": "Take 1 tablet", "items": "single string"}, "Dosage", "x", "pill")
    assert card.title == "Dosage"
    assert card.icon == "pill"
    assert card.items == ["single string"]
    assert _card(None, "T", "C", "clock").content == "C"


def test_prohibited_timing_is_never_shown_as_a_direction():
    text = "Rx: Ibuprofen 400 mg tab PO TID with food. Do NOT take on an empty stomach."
    data = build_rule_based_content(text, "en", ClinicalExtractor.extract_all(text))
    assert "empty stomach" not in data["timing_card"]["content"].lower()
    assert "empty stomach" not in data["simplified_text"].lower()
    assert any("empty stomach" in p.lower() for p in data["precautions_card"]["items"])


def test_morning_and_night_kept_together():
    e = ClinicalExtractor.extract_all("Budesonide 200 mcg: 2 puffs BID every morning and night.")
    assert any("Every morning and night" in f for f in e.frequencies)
    assert not any(f.endswith("[Every morning]") for f in e.frequencies)


def test_frequency_written_in_words():
    for text, label in [("three times a day", "3 times a day"), ("four times a day", "4 times a day"),
                        ("twice a day", "Twice a day"), ("once a day", "Once a day")]:
        e = ClinicalExtractor.extract_all(f"Paracetamol 500 mg {text}.")
        assert any(label in f for f in e.frequencies), text


def test_timetable_slots_for_samples():
    from app.services.timetable import build_timetable
    by_id = {s.id: s.raw_text for s in SAMPLE_PRESETS}
    amox = build_timetable(by_id["sample_amoxicillin"], ClinicalExtractor.extract_all(by_id["sample_amoxicillin"]))
    assert amox[0].slots == ["morning", "afternoon", "night"]
    assert amox[0].duration_days == 7
    asthma = build_timetable(by_id["sample_asthma"], ClinicalExtractor.extract_all(by_id["sample_asthma"]))
    assert asthma[0].slots == ["morning", "night"] and asthma[0].amount == "2 puffs"
    assert asthma[1].as_needed and asthma[1].slots == []
    metformin = build_timetable(by_id["sample_metformin"], ClinicalExtractor.extract_all(by_id["sample_metformin"]))
    assert metformin[0].food_note == "with breakfast and dinner"


def test_timetable_without_medicine_name():
    from app.services.timetable import build_timetable
    text = "Take 1 tablet three times a day after food for 5 days."
    entries = build_timetable(text, ClinicalExtractor.extract_all(text))
    assert entries[0].slots == ["morning", "afternoon", "night"]
    assert entries[0].amount == "1 tablet" and entries[0].duration_days == 5


def test_simplify_returns_timetable():
    res = client.post("/api/simplify", json={"raw_text": SAMPLE_PRESETS[0].raw_text, "target_language": "en"})
    assert res.json()["timetable"][0]["medicine"] == "Amoxicillin 500 mg"


def test_indian_notation_dose_patterns_and_abbreviations():
    from app.services.timetable import build_timetable
    text = "Tab Pantoprazole 40 mg 1-0-0 AC for 14 days. Tab Metformin 500 mg BD PC. Tab Paracetamol 650 mg SOS."
    e = ClinicalExtractor.extract_all(text)
    labels = " ".join(e.frequencies)
    assert "Pattern 1-0-0" in labels and "Twice a day" in labels and "As needed" in labels
    plan = {x.medicine: x for x in build_timetable(text, e)}
    assert plan["Pantoprazole 40 mg"].slots == ["morning"]
    assert plan["Metformin 500 mg"].slots == ["morning", "night"]
    assert plan["Paracetamol 650 mg"].as_needed and not plan["Paracetamol 650 mg"].slots


def test_dose_pattern_does_not_match_dates_or_ranges():
    e = ClinicalExtractor.extract_all("Review on 20-10-2026. Take 1-2 puffs every 4-6 hours.")
    assert not any("Pattern" in f for f in e.frequencies)


def test_glossary_explains_abbreviations_in_each_language():
    from app.services.glossary import build_glossary
    text = "Rx: Tab Amoxicillin 500 mg PO TDS x 5 days. Tab Paracetamol 650 mg SOS."
    terms = {g.term for g in build_glossary(text, "en")}
    assert {"Rx", "PO", "TDS / TID", "SOS", "x N days", "Tab", "mg"} <= terms
    hindi = build_glossary(text, "hi")
    assert any("तीन" in g.meaning for g in hindi)


def test_daily_maximum_is_never_read_as_a_dose():
    text = "Tab Paracetamol 650 mg SOS for fever, not more than 3 tablets in 24 hours."
    e = ClinicalExtractor.extract_all(text)
    data = build_rule_based_content(text, "en", e)
    assert "650 mg 3 tablets" not in data["simplified_text"]
    assert any("not more than 3 tablets in 24 hours" in p.lower() for p in data["precautions_card"]["items"])
    assert ClinicalExtractor.per_dose_count("Take 2 tablets twice a day. Do not exceed 8 tablets.") == ("2", "tablet")
    assert ClinicalExtractor.per_dose_count("Maximum 4 tablets a day.") is None


def test_dose_pattern_at_end_of_sentence():
    e = ClinicalExtractor.extract_all("Rx: Tab Pantoprazole 40 mg 1-0-0.")
    assert any("Pattern 1-0-0" in f for f in e.frequencies)


def test_digits_inside_names_are_not_doses_and_weekly_is_kept():
    from app.services.timetable import build_timetable
    text = "Vitamin D3 60000 IU once a week for 8 weeks with milk."
    e = ClinicalExtractor.extract_all(text)
    assert e.medications == ["Vitamin D3 60000 IU"]
    assert [n.raw_str for n in e.numbers] == ["60000 IU", "8"]
    data = build_rule_based_content(text, "en", e)
    assert "once a week" in data["simplified_text"]
    assert build_timetable(text, e)[0].weekly


def test_verifier_v2_catches_swapped_doses_and_inverted_prohibitions():
    from app.services.verifier import InformationVerifier
    from app.main import _card
    from app.models.schemas import StructuredCards
    text = "Metformin 500 mg BID. Glimepiride 1 mg OD. Do not skip meals."
    e = ClinicalExtractor.extract_all(text)

    def check(simplified, avoid):
        cards = StructuredCards(
            dosage=_card({"content": simplified}, "D", "x", "pill"),
            frequency=_card({"content": "Twice a day and once a day."}, "F", "x", "clock"),
            timing=_card({"content": "Any time."}, "T", "x", "utensils"),
            precautions=_card({"content": "Rules:", "items": [avoid]}, "P", "x", "shield-alert"),
            warning_signs=_card({"content": "Call a doctor if unwell.", "items": []}, "W", "x", "alert-triangle"),
            patient_summary=[], read_aloud_text=simplified,
        )
        return InformationVerifier.verify(text, e, simplified, cards, "en")

    good = check("Take Metformin 500 mg twice a day. Take Glimepiride 1 mg once a day.", "Do not skip meals.")
    swapped = check("Take Metformin 1 mg twice a day. Take Glimepiride 500 mg once a day.", "Do not skip meals.")
    inverted = check("Take Metformin 500 mg twice a day. Take Glimepiride 1 mg once a day.", "Skip meals.")
    assert good.status == "VERIFIED"
    assert not swapped.numeric_check.passed
    assert not inverted.negation_check.passed
