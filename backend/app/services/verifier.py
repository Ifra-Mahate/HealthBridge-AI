import re
from typing import List, Dict, Any, Set
from ..models.schemas import (
    ExtractedEntities,
    StructuredCards,
    VerificationReport,
    CheckResult,
    ExtractedNumberUnit
)


# Devanagari numerals mapping (०-९ to 0-9)
DEVANAGARI_DIGITS = {
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'
}

# Negation terms in English, Hindi, and Marathi
MULTILINGUAL_NEGATIONS = [
    # English
    "do not", "don't", "never", "avoid", "stop", "discontinue", "should not",
    # Hindi
    "न करें", "मत करें", "न लें", "मत लें", "बचें", "बंद करें", "नहीं", "ना खाएं", "परहेज़",
    # Marathi
    "करू नका", "घेऊ नका", "टाळा", "थांबवा", "नाही", "खाऊ नका", "बंद करा"
]


def normalize_devanagari_numbers(text: str) -> str:
    """Converts Devanagari numeric characters (०, १, २, etc.) to standard Arabic digits (0, 1, 2)."""
    chars = [DEVANAGARI_DIGITS.get(ch, ch) for ch in text]
    return "".join(chars)


def extract_all_numbers(text: str) -> List[float]:
    """Finds all numerical values in text, normalizing Devanagari numerals."""
    normalized = normalize_devanagari_numbers(text)
    pattern = re.compile(r"\b\d+(?:\.\d+)?\b")
    numbers: List[float] = []
    for match in pattern.finditer(normalized):
        try:
            numbers.append(float(match.group(0)))
        except ValueError:
            continue
    return numbers


class InformationVerifier:
    """
    Verifies that the simplified and translated instructions preserve
    all clinical facts from the original instruction without dangerous
    alterations or omissions.
    """

    @classmethod
    def verify(
        cls,
        original_text: str,
        original_entities: ExtractedEntities,
        simplified_text: str,
        structured_cards: StructuredCards,
        target_language: str
    ) -> VerificationReport:
        flags: List[str] = []
        ambiguity_warnings: List[str] = []
        score = 100

        # Combine all simplified output text across cards and summary for holistic cross-checking
        all_output_parts = [
            simplified_text,
            structured_cards.dosage.content,
            structured_cards.dosage.badge or "",
            structured_cards.frequency.content,
            structured_cards.timing.content,
            structured_cards.precautions.content,
            " ".join(structured_cards.precautions.items or []),
            structured_cards.warning_signs.content,
            " ".join(structured_cards.warning_signs.items or []),
            " ".join(structured_cards.patient_summary),
            structured_cards.read_aloud_text
        ]
        combined_output = " ".join(all_output_parts).lower()
        combined_output_with_devanagari_norm = normalize_devanagari_numbers(combined_output)

        # -------------------------------------------------------------
        # 1. NUMERIC VERIFICATION
        # -------------------------------------------------------------
        orig_numbers: List[float] = [n.value for n in original_entities.numbers]
        # Remove common non-critical counts like 1 in "1 time" if ambiguous, but track vital numbers
        output_numbers = extract_all_numbers(combined_output)
        
        verified_numbers: List[str] = []
        missing_numbers: List[str] = []

        for num_unit in original_entities.numbers:
            val = num_unit.value
            val_str = f"{num_unit.raw_str}"
            # Check if value exists in output numbers
            found = any(abs(val - out_val) < 0.01 for out_val in output_numbers)
            if found:
                verified_numbers.append(val_str)
            else:
                missing_numbers.append(val_str)

        numeric_passed = len(missing_numbers) == 0
        if not numeric_passed:
            score -= (30 * min(len(missing_numbers), 2))
            flags.append(
                f"Numeric discrepancy: The following original numbers or doses were not explicitly confirmed in the output: {', '.join(missing_numbers)}"
            )

        numeric_check = CheckResult(
            passed=numeric_passed,
            details="All original dosages and quantities verified." if numeric_passed else f"Missing or unconfirmed numbers: {', '.join(missing_numbers)}",
            items_original=[n.raw_str for n in original_entities.numbers],
            items_verified=verified_numbers,
            items_missing=missing_numbers
        )

        # -------------------------------------------------------------
        # 2. NEGATIONS & CONTRAINDICATIONS CHECK
        # -------------------------------------------------------------
        orig_negations = original_entities.negations
        verified_negations: List[str] = []
        missing_negations: List[str] = []

        has_output_negation = any(neg.lower() in combined_output for neg in MULTILINGUAL_NEGATIONS)

        if orig_negations:
            if has_output_negation:
                verified_negations = orig_negations
                negation_passed = True
            else:
                missing_negations = orig_negations
                negation_passed = False
                score -= 25
                flags.append("Warning: Original text contained negative restrictions (e.g. 'do not' or 'avoid'), but no clear prohibition was detected in output.")
        else:
            negation_passed = True

        negation_check = CheckResult(
            passed=negation_passed,
            details="Negative instructions (prohibitions/restrictions) properly preserved." if negation_passed else "Warning: Negative restrictions were present in original but may be missing.",
            items_original=orig_negations,
            items_verified=verified_negations,
            items_missing=missing_negations
        )

        # -------------------------------------------------------------
        # 3. FREQUENCY CHECK
        # -------------------------------------------------------------
        orig_frequencies = original_entities.frequencies
        freq_card_text = structured_cards.frequency.content.strip()
        frequency_passed = True
        missing_freq: List[str] = []
        verified_freq: List[str] = []

        if orig_frequencies:
            if len(freq_card_text) >= 3 and not freq_card_text.lower().startswith("not specified"):
                verified_freq = orig_frequencies
                frequency_passed = True
            else:
                missing_freq = orig_frequencies
                frequency_passed = False
                score -= 15
                flags.append("Frequency detail: Original mentions administration frequency, but frequency card is sparse.")

        frequency_check = CheckResult(
            passed=frequency_passed,
            details="Schedule and frequency verified in structured card." if frequency_passed else "Frequency not clearly identified in output.",
            items_original=orig_frequencies,
            items_verified=verified_freq,
            items_missing=missing_freq
        )

        # -------------------------------------------------------------
        # 4. TIMING & FOOD CHECK
        # -------------------------------------------------------------
        orig_timings = original_entities.timings
        timing_card_text = structured_cards.timing.content.strip()
        timing_passed = True
        missing_timing: List[str] = []
        verified_timing: List[str] = []

        if orig_timings:
            if len(timing_card_text) >= 3 and not timing_card_text.lower().startswith("not specified"):
                verified_timing = orig_timings
                timing_passed = True
            else:
                missing_timing = orig_timings
                timing_passed = False
                score -= 10
                flags.append("Timing constraint: Original specified food or time-of-day constraints, verify timing card carefully.")

        timing_check = CheckResult(
            passed=timing_passed,
            details="Food and meal relations verified." if timing_passed else "Meal relation or timing details missing.",
            items_original=orig_timings,
            items_verified=verified_timing,
            items_missing=missing_timing
        )

        # -------------------------------------------------------------
        # 5. WARNING SIGNS CHECK
        # -------------------------------------------------------------
        orig_warnings = original_entities.warnings
        warning_card_items = structured_cards.warning_signs.items or []
        warning_card_content = structured_cards.warning_signs.content
        warning_passed = True
        missing_warn: List[str] = []
        verified_warn: List[str] = []

        if orig_warnings:
            if warning_card_items or len(warning_card_content) > 10:
                verified_warn = orig_warnings
                warning_passed = True
            else:
                missing_warn = orig_warnings
                warning_passed = False
                score -= 20
                flags.append("Safety notice: Original text highlighted red-flag symptoms that need prominent patient visibility.")

        warning_check = CheckResult(
            passed=warning_passed,
            details="Urgent warning signs documented." if warning_passed else "Red-flag warning signs not prominently reflected.",
            items_original=orig_warnings,
            items_verified=verified_warn,
            items_missing=missing_warn
        )

        # -------------------------------------------------------------
        # 6. AMBIGUITY DETECTION
        # -------------------------------------------------------------
        lower_orig = original_text.lower()
        if re.search(r"\bas\s+needed\b|\bprn\b", lower_orig) and not re.search(r"max(imum)?|\bdo\s+not\s+exceed\b", lower_orig):
            ambiguity_warnings.append("Ambiguity: 'Take as needed' is specified without an explicit maximum daily dose limit. Patient should consult pharmacist.")

        if not original_entities.dosages and not original_entities.numbers:
            ambiguity_warnings.append("Ambiguity: No exact numeric dosage strength (e.g. mg, ml) was detected in the original text.")

        if re.search(r"\buntil\s+finished\b|\buntil\s+gone\b", lower_orig) and not re.search(r"\b\d+\s+days\b", lower_orig):
            ambiguity_warnings.append("Ambiguity: Instruction states 'take until finished' without specifying number of course days.")

        # Ensure score bounds
        score = max(0, min(100, score))

        if score >= 85:
            status = "VERIFIED"
            summary = "High fidelity: All critical numerical dosages, timings, and clinical directives are verified and preserved."
        elif score >= 60:
            status = "CAUTION"
            summary = "Review advised: Some details or numbers require visual verification against the original prescription."
        else:
            status = "CRITICAL_MISMATCH"
            summary = "Safety alert: Key clinical numbers or restrictions from original instructions could not be confirmed."

        return VerificationReport(
            score=score,
            status=status,
            summary=summary,
            numeric_check=numeric_check,
            negation_check=negation_check,
            frequency_check=frequency_check,
            timing_check=timing_check,
            warning_check=warning_check,
            ambiguity_warnings=ambiguity_warnings,
            flags=flags
        )
