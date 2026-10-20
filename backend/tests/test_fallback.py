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
