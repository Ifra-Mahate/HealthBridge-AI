import pytest
from app.services.extractor import ClinicalExtractor


def test_extract_dosages_and_numbers():
    text = "Amoxicillin 500 mg PO TID x 7 days with meals. Take 2 tablets."
    extracted = ClinicalExtractor.extract_all(text)

    # Check dosages
    assert any("500 mg" in d for d in extracted.dosages)
    assert any("2 tablet" in d.lower() for d in extracted.dosages)

    # Check extracted numbers
    values = [n.value for n in extracted.numbers]
    assert 500.0 in values
    assert 7.0 in values
    assert 2.0 in values


def test_extract_frequencies_and_timings():
    text = "Take Metformin 500 mg BID with breakfast and dinner. Glimepiride 1 mg QD."
    extracted = ClinicalExtractor.extract_all(text)

    # Check frequencies
    freq_text = " ".join(extracted.frequencies).lower()
    assert "bid" in freq_text or "twice" in freq_text
    assert "qd" in freq_text or "once" in freq_text

    # Check timings
    timing_text = " ".join(extracted.timings).lower()
    assert "breakfast" in timing_text


def test_extract_precautions_and_warnings():
    text = (
        "Rx: Ibuprofen 400 mg. Avoid alcohol. Do NOT crush. "
        "Stop immediately if difficulty breathing or severe rash occurs."
    )
    extracted = ClinicalExtractor.extract_all(text)

    precautions_str = " ".join(extracted.precautions).lower()
    assert "alcohol" in precautions_str
    assert "crush" in precautions_str

    warnings_str = " ".join(extracted.warnings).lower()
    assert "breathing" in warnings_str
    assert "rash" in warnings_str

    assert len(extracted.negations) >= 1
