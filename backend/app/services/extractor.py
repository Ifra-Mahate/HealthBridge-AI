import re
from typing import List, Dict, Any, Optional
from ..models.schemas import ExtractedEntities, ExtractedNumberUnit


# Common unit regex patterns
UNIT_PATTERNS = [
    r"mg|milligram|milligrams",
    r"mcg|microgram|micrograms",
    r"g|gram|grams",
    r"ml|milliliter|milliliters",
    r"l|liter|liters",
    r"iu|units|unit",
    r"tablets?|tabs?|capsules?|caps?",
    r"drops?",
    r"puffs?",
    r"teaspoons?|tsp",
    r"tablespoons?|tbsp",
    r"sachets?",
    r"ampoules?",
    r"\%|percent"
]
COMBINED_UNITS = "|".join(UNIT_PATTERNS)

# Common clinical frequency terms & Latin abbreviations
FREQUENCY_PATTERNS = [
    (r"\b(once|1\s*time)\s+(a|per)\s+day\b|\b(once\s+daily)\b|\bqd\b|\bq\.d\.\b", "Once a day (QD)"),
    (r"\b(twice|2\s*times)\s+(a|per)\s+day\b|\b(twice\s+daily)\b|\bbid\b|\bb\.i\.d\.\b", "Twice a day (BID)"),
    (r"\b(three|3)\s*times\s+(a|per)\s+day\b|\b(thrice|three\s+times)\s+daily\b|\btid\b|\bt\.i\.d\.\b", "3 times a day (TID)"),
    (r"\b(four|4)\s*times\s+(a|per)\s+day\b|\bfour\s+times\s+daily\b|\bqid\b|\bq\.i\.d\.\b", "4 times a day (QID)"),
    (r"\bevery\s+(\d+(?:\s*-\s*\d+)?)\s+hours?\b|\bq(\d+)h\b", "Every {n} hours"),
    (r"\bas\s+needed\b|\bprn\b|\bp\.r\.n\.\b", "As needed (PRN)"),
    (r"\bat\s+bedtime\b|\bbedtime\b|\bhs\b|\bh\.s\.\b", "At bedtime (HS)"),
    (r"\b(every|each)\s+morning\s+and\s+(night|evening)\b", "Every morning and night"),
    (r"\bevery\s+morning\b(?!\s+and\s+(night|evening))|\bin\s+the\s+morning\b", "Every morning"),
    (r"\bevery\s+night\b|\bin\s+the\s+night\b|\bevening\b", "Every night"),
]

# Treatment course length, e.g. "for 7 days", "x 7 days", "7-day course"
DURATION_PATTERNS = [
    r"\bfor\s+(\d+)\s*(days?|weeks?|months?)\b",
    r"\bx\s*(\d+)\s*(days?|weeks?|months?)\b",
    r"\b(\d+)\s*-\s*(day|week|month)\s+course\b",
]

# Capitalised words that appear before a strength but are not medicine names
NON_MEDICINE_WORDS = {
    "take", "give", "use", "apply", "inhale", "exceed", "than", "below", "above",
    "over", "under", "about", "rx", "dose", "only", "then", "each", "every", "consume",
}

# Timing / Food constraints
TIMING_PATTERNS = [
    r"with\s+(food|meals?|milk|breakfast|lunch|dinner)(\s+and\s+(breakfast|lunch|dinner))?",
    r"after\s+(food|meals?|breakfast|lunch|dinner|eating)",
    r"before\s+(food|meals?|breakfast|lunch|dinner|eating)",
    r"during\s+(food|meals?|breakfast|lunch|dinner)",
    r"on\s+an\s+empty\s+stomach",
    r"\d+\s*(minutes?|mins?|hours?)\s+before\s+(meals?|food|breakfast|lunch|dinner)",
    r"\d+\s*(minutes?|mins?|hours?)\s+after\s+(meals?|food|breakfast|lunch|dinner)",
    r"in\s+the\s+morning",
    r"at\s+bedtime",
    r"with\s+a\s+full\s+glass\s+of\s+water",
]

# Clinical warnings / red-flags
WARNING_TRIGGERS = [
    r"rash(es)?",
    r"hives",
    r"difficulty\s+breathing",
    r"shortness\s+of\s+breath",
    r"(facial\s+)?swelling(\s+of\s+(the\s+)?(face|lips|tongue|throat|legs))?",
    r"breathing\s+difficulty",
    r"black\s+tarry\s+stools?",
    r"(persistent\s+)?stomach\s+burning",
    r"weight\s+gain",
    r"cold\s+sweats?",
    r"shaky",
    r"chest\s+pain",
    r"severe\s+(dizziness|headache|pain|vomiting|diarrhea)",
    r"fever",
    r"yellowing\s+of\s+skin|jaundice",
    r"blood\s+in\s+stool|dark\s+urine",
    r"allergic\s+reaction",
    r"emergency|seek\s+immediate\s+medical",
    r"discontinue\s+immediately|stop\s+taking\s+immediately"
]

# Clinical precautions
PRECAUTION_PATTERNS = [
    r"avoid\s+alcohol",
    r"do\s+not\s+(crush|chew|break|split|cut)\b",
    r"swallow\s+whole",
    r"do\s+not\s+drive",
    r"complete\s+the\s+(entire|full)?\s*course",
    r"do\s+not\s+stop\s+(taking\s+)?abruptly",
    r"keep\s+hydrated|drink\s+plenty\s+of\s+water",
    r"avoid\s+direct\s+sunlight",
    r"store\s+in\s+a\s+cool|store\s+in\s+refrigerator",
    r"do\s+not\s+take\s+double\s+dose",
    r"shake\s+well\s+before\s+use"
]

# Negation terms
NEGATION_WORDS = [
    r"\bdo\s+not\b",
    r"\bdon't\b",
    r"\bnever\b",
    r"\bavoid\b",
    r"\bdiscontinue\b",
    r"\bstop\b",
    r"\bnot\b",
    r"\bno\b",
    r"\bwithout\b",
    r"\bcannot\b",
    r"\bshouldn't\b",
]


def _dedupe_ci(items: List[str]) -> List[str]:
    """Removes case-insensitive duplicates while keeping the first spelling."""
    seen = set()
    out: List[str] = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


class ClinicalExtractor:
    """
    Extracts structured clinical facts from raw instructions:
    dosages, numbers with units, frequencies, food timings,
    precautions, warnings, and negations.
    """

    @classmethod
    def extract_numbers_and_units(cls, text: str) -> List[ExtractedNumberUnit]:
        """Finds all occurrences of numbers associated with medical units or standalone count numbers."""
        results: List[ExtractedNumberUnit] = []
        pattern = re.compile(
            rf"(?P<val>\d+(?:\.\d+)?|\d+/\d+)\s*(?P<unit>{COMBINED_UNITS})?",
            re.IGNORECASE
        )
        for match in pattern.finditer(text):
            val_str = match.group("val")
            unit_str = match.group("unit")
            try:
                if "/" in val_str:
                    num, denom = val_str.split("/")
                    num_val = float(num) / float(denom)
                else:
                    num_val = float(val_str)
            except ValueError:
                continue

            start = max(0, match.start() - 25)
            end = min(len(text), match.end() + 25)
            context = text[start:end].strip()

            results.append(
                ExtractedNumberUnit(
                    value=num_val,
                    raw_str=match.group(0).strip(),
                    unit=unit_str.lower() if unit_str else None,
                    context=context
                )
            )
        return results

    @classmethod
    def extract_dosages(cls, text: str) -> List[str]:
        """Extracts recognizable dosage phrases like '500 mg', '2 tablets', '1-2 puffs'."""
        pattern = re.compile(
            rf"\b\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?\s*(?:{COMBINED_UNITS})\b",
            re.IGNORECASE
        )
        matches = [m.group(0).strip() for m in pattern.finditer(text)]
        return list(dict.fromkeys(matches))

    @classmethod
    def extract_frequencies(cls, text: str) -> List[str]:
        """Extracts frequency mentions."""
        found: List[str] = []
        for pat, canonical in FREQUENCY_PATTERNS:
            matches = re.finditer(pat, text, re.IGNORECASE)
            for m in matches:
                label = canonical
                if "{n}" in canonical:
                    n = next((g for g in m.groups() if g), "")
                    label = canonical.replace("{n}", re.sub(r"\s+", "", n))
                found.append(f"{m.group(0).strip()} [{label}]")
        return list(dict.fromkeys(found))

    @classmethod
    def extract_durations(cls, text: str) -> List[str]:
        """Extracts treatment course lengths, normalised to e.g. '7 days'."""
        found: List[str] = []
        for pat in DURATION_PATTERNS:
            for m in re.finditer(pat, text, re.IGNORECASE):
                num, unit = m.group(1), m.group(2).lower()
                if not unit.endswith("s") and num != "1":
                    unit += "s"
                found.append(f"{num} {unit}")
        return list(dict.fromkeys(found))

    @classmethod
    def extract_medications(cls, text: str) -> List[str]:
        """Finds 'Name strength' pairs such as 'Metformin 500 mg'."""
        pattern = re.compile(
            r"\b([A-Z][a-zA-Z]{3,})\s+(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|iu|units?))\b"
        )
        found: List[str] = []
        for m in pattern.finditer(text):
            if m.group(1).lower() in NON_MEDICINE_WORDS:
                continue
            found.append(f"{m.group(1)} {m.group(2)}")
        return list(dict.fromkeys(found))

    @classmethod
    def extract_timings(cls, text: str) -> List[str]:
        """Extracts food or time-of-day constraints."""
        found: List[str] = []
        for pat in TIMING_PATTERNS:
            for m in re.finditer(pat, text, re.IGNORECASE):
                found.append(m.group(0).strip())
        return list(dict.fromkeys(found))

    @classmethod
    def extract_precautions(cls, text: str) -> List[str]:
        """Extracts clinical precautions."""
        found: List[str] = []
        for pat in PRECAUTION_PATTERNS:
            for m in re.finditer(pat, text, re.IGNORECASE):
                found.append(m.group(0).strip())
        return list(dict.fromkeys(found))

    @classmethod
    def extract_warnings(cls, text: str) -> List[str]:
        """Extracts red-flag symptom warnings."""
        found: List[str] = []
        for pat in WARNING_TRIGGERS:
            for m in re.finditer(pat, text, re.IGNORECASE):
                found.append(m.group(0).strip())
        return _dedupe_ci(found)

    @classmethod
    def extract_negations(cls, text: str) -> List[str]:
        """Extracts negative clauses (e.g., 'do not crush', 'avoid alcohol')."""
        clauses: List[str] = []
        sentence_parts = re.split(r"[.;,]\s*", text)
        for part in sentence_parts:
            for neg in NEGATION_WORDS:
                if re.search(neg, part, re.IGNORECASE):
                    cleaned = part.strip()
                    if cleaned and len(cleaned) > 3:
                        clauses.append(cleaned)
                    break
        return list(dict.fromkeys(clauses))

    @classmethod
    def extract_all(cls, text: str) -> ExtractedEntities:
        """Runs full extraction pipeline on given text."""
        return ExtractedEntities(
            medications=cls.extract_medications(text),
            dosages=cls.extract_dosages(text),
            durations=cls.extract_durations(text),
            numbers=cls.extract_numbers_and_units(text),
            frequencies=cls.extract_frequencies(text),
            timings=cls.extract_timings(text),
            precautions=cls.extract_precautions(text),
            warnings=cls.extract_warnings(text),
            negations=cls.extract_negations(text)
        )
