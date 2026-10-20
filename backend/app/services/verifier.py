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


# ---------------------------------------------------------------------------
# Strict checks (verifier v2)
# ---------------------------------------------------------------------------

# Words that mark a sentence as a restriction or a limit, in all three languages
RESTRICTION_RE = re.compile(
    r"\b(not|no|never|avoid|don't|stop|discontinue|without|exceed|maximum|max)\b"
    r"|न करें|मत|न लें|बचें|बंद करें|नहीं|ना |परहेज़|करू नका|घेऊ नका|टाळा|थांबवा|नाही|बंद करा",
    re.IGNORECASE,
)

# Generic words that do not identify what a prohibition is about
CLAUSE_STOPWORDS = {
    "take", "taking", "taken", "medicine", "medicines", "medication", "tablet", "tablets", "doctor", "consult",
    "consulting", "with", "without", "your", "this", "that", "these", "those", "have", "from", "into", "more",
    "than", "when", "after", "before", "while", "completely", "immediately", "during", "should", "must", "also",
    "only", "other", "again", "hours", "days", "daily", "dose", "doses", "times", "about", "avoid", "never",
    "stop", "does", "will", "them", "there", "their", "please", "always", "strictly", "occurs", "occur",
    "develops", "seek", "care", "medical", "emergency", "important",
}

# Unit spellings accepted as the same unit in English, Hindi and Marathi output
UNIT_SYNONYMS = {
    "mg": r"mg|milligrams?|मिलीग्राम|मिग्रॅ|मि\.ग्रा\.?|मिग्रा",
    "mcg": r"mcg|micrograms?|µg|माइक्रोग्राम|मायक्रोग्रॅम",
    "g": r"g|grams?|ग्राम|ग्रॅम",
    "ml": r"ml|millilit(?:er|re)s?|मिली|मिलीलीटर|मि\.ली\.?|मिलि",
    "iu": r"iu|units?|यूनिट|युनिट",
    "unit": r"iu|units?|यूनिट|युनिट",
    "tablet": r"tablets?|tabs?|गोली|गोलियां|गोळी|गोळ्या",
    "capsule": r"capsules?|caps?|कैप्सूल|कॅप्सूल",
    "drop": r"drops?|बूंद|थेंब",
    "puff": r"puffs?|पफ़|पफ",
}


ANY_DOSE_RE = re.compile(
    r"(?<![\d.])(\d+(?:\.\d+)?)\s*(?:" + "|".join(UNIT_SYNONYMS.values()) + r")",
    re.IGNORECASE,
)


def _unit_pattern(unit: str):
    u = (unit or "").lower()
    for key, pattern in UNIT_SYNONYMS.items():
        if u == key or u.startswith(key) or (key == "tablet" and u.startswith("tab")) or (key == "capsule" and u.startswith("cap")):
            return pattern
    return None


def _num_regex(value: float) -> str:
    text = str(int(value)) if float(value).is_integer() else str(value)
    return rf"(?<![\d.]){re.escape(text)}(?![\d.])"


def _segments(simplified_text: str, cards: StructuredCards) -> List[str]:
    """Output split into sentences and list items, so each statement is judged on its own."""
    blocks = [simplified_text, cards.read_aloud_text, " ".join(cards.patient_summary)]
    for card in (cards.dosage, cards.frequency, cards.timing, cards.precautions, cards.warning_signs):
        blocks.append(card.content)
        blocks.extend(card.items or [])
    segments: List[str] = []
    for block in blocks:
        segments.extend(s for s in re.split(r"(?<=[.।!?])\s+|\n", block or "") if s.strip())
    return segments


def _key_terms(clause: str) -> List[str]:
    return [w for w in re.findall(r"[a-z]{4,}", clause.lower()) if w not in CLAUSE_STOPWORDS]


def unbound_doses(entities: ExtractedEntities, output: str) -> List[str]:
    """
    Doses whose number is present but no longer attached to its unit or medicine,
    e.g. two medicines' strengths swapped. Returns human-readable descriptions.
    """
    problems: List[str] = []
    for n in entities.numbers:
        unit_re = _unit_pattern(n.unit)
        if not unit_re or n.unit in ("%",):
            continue
        if not re.search(_num_regex(n.value), output):
            continue  # a missing number is already reported by the basic check
        if not re.search(rf"{_num_regex(n.value)}\s*(?:{unit_re})", output, re.IGNORECASE):
            problems.append(f"{n.raw_str} (unit changed)")
    for med in entities.medications:
        m = re.match(r"(.+?)\s+([\d.]+)\s*(\S+)$", med)
        if not m:
            continue
        name, value, unit = m.group(1).lower(), float(m.group(2)), m.group(3)
        positions = [x.start() for x in re.finditer(re.escape(name), output)]
        if not positions:
            continue  # name translated or transliterated: binding cannot be checked
        # The first dose written after the name is the one a reader attaches to that medicine
        bound = False
        for p in positions:
            nxt = ANY_DOSE_RE.search(output, p + len(name), p + len(name) + 50)
            if nxt and abs(float(nxt.group(1)) - value) < 0.01:
                bound = True
                break
        if not bound:
            problems.append(f"{med} (dose not linked to {m.group(1)})")
    return problems


# True negation markers. "Stop" or "exceed" alone are not enough: "Do not stop abruptly"
# turned into "Stop abruptly" still contains "stop" but now means the opposite.
PROHIBITIVE_RE = re.compile(
    r"\b(not|no|never|avoid|don't|without|maximum|max)\b"
    r"|न करें|मत|न लें|बचें|नहीं|ना |परहेज़|करू नका|घेऊ नका|टाळा|नाही",
    re.IGNORECASE,
)


def uncovered_prohibitions(entities: ExtractedEntities, segments: List[str]) -> List[str]:
    """
    Original prohibitions that no matching statement in the output still covers.
    A clause written as a prohibition ("do not", "avoid", "never") must be matched by an
    output sentence that is itself a prohibition and mentions what the clause is about.
    A conditional stop rule ("Stop if ...") may be matched by any restriction statement.
    """
    prohibitive = [s.lower() for s in segments if PROHIBITIVE_RE.search(s)]
    restrictive = [s.lower() for s in segments if RESTRICTION_RE.search(s)]
    missing: List[str] = []
    for clause in entities.negations:
        terms = _key_terms(clause)
        if not terms:
            continue
        pool = prohibitive if PROHIBITIVE_RE.search(clause) else restrictive
        if not any(any(t in seg for t in terms) for seg in pool):
            missing.append(clause)
    return missing


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
        target_language: str,
        strict: bool = True,
    ) -> VerificationReport:
        """
        strict=True adds the v2 checks: dose-to-unit/medicine binding (all languages) and
        per-prohibition coverage (English output, where the wording can be compared).
        strict=False reproduces the original v1 behaviour and is kept for evaluation.
        """
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

        if strict:
            for problem in unbound_doses(original_entities, combined_output_with_devanagari_norm):
                missing_numbers.append(problem)
                verified_numbers = [v for v in verified_numbers if v not in problem]

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

        uncovered = (
            uncovered_prohibitions(original_entities, _segments(simplified_text, structured_cards))
            if strict and orig_negations and target_language == "en" else []
        )

        if orig_negations:
            if has_output_negation and not uncovered:
                verified_negations = orig_negations
                negation_passed = True
            elif has_output_negation:
                verified_negations = [n for n in orig_negations if n not in uncovered]
                missing_negations = uncovered
                negation_passed = False
                score -= 25
                flags.append(
                    "Prohibition not preserved: the output no longer clearly states: "
                    + "; ".join(f'"{c}"' for c in uncovered)
                )
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
