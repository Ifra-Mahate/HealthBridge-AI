import pytest
from app.services.extractor import ClinicalExtractor
from app.services.verifier import InformationVerifier
from app.models.schemas import StructuredCards, InstructionCard


def test_verifier_passes_on_preserved_information():
    orig_text = "Take Amoxicillin 500 mg TID with meals for 7 days. Avoid alcohol."
    extracted = ClinicalExtractor.extract_all(orig_text)

    # Output that preserves 500 mg, TID, 7 days, and avoidance
    cards = StructuredCards(
        dosage=InstructionCard(
            title="Dosage",
            content="Take 500 mg per dose.",
            badge="500 mg",
            icon="pill"
        ),
        frequency=InstructionCard(
            title="Frequency",
            content="Take 3 times daily (TID) for 7 days.",
            badge="3 times daily",
            icon="clock"
        ),
        timing=InstructionCard(
            title="Timing",
            content="Always take with meals.",
            badge="With food",
            icon="utensils"
        ),
        precautions=InstructionCard(
            title="Precautions",
            content="Avoid alcohol while taking this medicine.",
            items=["Avoid alcohol"],
            icon="shield-alert"
        ),
        warning_signs=InstructionCard(
            title="Warning Signs",
            content="Call doctor if allergy occurs.",
            items=["Allergic reaction"],
            icon="alert-triangle"
        ),
        patient_summary=["Take 500 mg", "3 times a day for 7 days"],
        read_aloud_text="Take 500 milligrams 3 times daily with meals for 7 days. Avoid alcohol."
    )

    report = InformationVerifier.verify(
        original_text=orig_text,
        original_entities=extracted,
        simplified_text="Take 500 mg 3 times daily with food for 7 days.",
        structured_cards=cards,
        target_language="en"
    )

    assert report.score >= 85
    assert report.status == "VERIFIED"
    assert report.numeric_check.passed is True
    assert report.negation_check.passed is True


def test_verifier_flags_missing_or_altered_numbers():
    orig_text = "Take 500 mg tablets."
    extracted = ClinicalExtractor.extract_all(orig_text)

    # Output that drops 500 mg completely or has only 250 mg
    cards = StructuredCards(
        dosage=InstructionCard(
            title="Dosage",
            content="Take 250 mg.",
            badge="250 mg",
            icon="pill"
        ),
        frequency=InstructionCard(
            title="Frequency",
            content="Daily",
            badge="Daily",
            icon="clock"
        ),
        timing=InstructionCard(
            title="Timing",
            content="With water",
            badge="Water",
            icon="utensils"
        ),
        precautions=InstructionCard(
            title="Precautions",
            content="None",
            items=[],
            icon="shield-alert"
        ),
        warning_signs=InstructionCard(
            title="Warning Signs",
            content="None",
            items=[],
            icon="alert-triangle"
        ),
        patient_summary=["Take medication"],
        read_aloud_text="Take 250 milligrams daily."
    )

    report = InformationVerifier.verify(
        original_text=orig_text,
        original_entities=extracted,
        simplified_text="Take 250 mg daily.",
        structured_cards=cards,
        target_language="en"
    )

    # 500 was missing!
    assert report.numeric_check.passed is False
    assert any("500" in missing for missing in report.numeric_check.items_missing)
    assert report.score < 85
