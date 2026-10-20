"""
Builds a daily medicine timetable (which medicine at which time of day) from the
original prescription. It is rule-based on purpose: the schedule comes straight
from the doctor's text, so it is the same whichever AI wrote the explanation.
"""
import re
from typing import List, Optional

from ..models.schemas import ExtractedEntities, TimetableEntry
from .extractor import ClinicalExtractor

SLOTS = ["morning", "afternoon", "evening", "night"]

FREQ_SLOTS = {
    "Once a day": ["morning"],
    "Twice a day": ["morning", "night"],
    "3 times a day": ["morning", "afternoon", "night"],
    "4 times a day": ["morning", "afternoon", "evening", "night"],
    "Every morning": ["morning"],
    "Every night": ["night"],
    "At bedtime": ["night"],
    "Every morning and night": ["morning", "night"],
}

HOURS_SLOTS = {24: ["morning"], 12: ["morning", "night"], 8: ["morning", "afternoon", "night"],
               6: ["morning", "afternoon", "evening", "night"]}

AMOUNT_RE = re.compile(r"\b(\d+(?:\s*-\s*\d+)?)\s*(puff|tablet|tab|capsule|cap|drop|teaspoon|ml)s?\b", re.IGNORECASE)
FOOD_RE = re.compile(
    r"(\d+\s*(?:minutes?|mins?|hours?)\s+(?:before|after)\s+\w+"
    r"|with\s+(?:food|meals?|milk|breakfast|dinner)(?:\s+and\s+(?:breakfast|lunch|dinner))?"
    r"|after\s+(?:food|meals?|eating)|before\s+(?:food|meals?|eating)|with\s+a\s+full\s+glass\s+of\s+water)",
    re.IGNORECASE,
)
NEGATED = re.compile(r"\b(do\s+not|don't|never|avoid|not)\b", re.IGNORECASE)


def _canonical(entry: str) -> str:
    m = re.search(r"\[(.*)\]", entry)
    label = m.group(1) if m else entry
    return re.sub(r"\s*\([A-Z]+\)\s*$", "", label).strip()


def _slots_for(frequencies: List[str]):
    """Returns (slots, as_needed) for a list of extractor frequency entries."""
    slots: List[str] = []
    as_needed = False
    labels = [_canonical(f) for f in frequencies]
    # Specific times of day beat a bare count ("once a day" + "every morning" = morning)
    specific = [l for l in labels if l in ("Every morning", "Every night", "At bedtime", "Every morning and night")]
    for label in labels:
        if label == "As needed":
            as_needed = True
            continue
        if label == "Once a day" and specific:
            continue
        hours = re.match(r"Every\s+(\d+)(?:-\d+)?\s+hours", label)
        if hours:
            # "every 4-6 hours as needed" is a minimum gap, not a fixed timetable
            if not any(l == "As needed" for l in labels):
                slots += HOURS_SLOTS.get(int(hours.group(1)), [])
            continue
        slots += FREQ_SLOTS.get(label, [])
    ordered = [s for s in SLOTS if s in slots]
    return ordered, as_needed


def _amount(text: str) -> Optional[str]:
    m = AMOUNT_RE.search(text)
    if not m:
        return None
    n = re.sub(r"\s+", "", m.group(1))
    unit = {"tab": "tablet", "cap": "capsule"}.get(m.group(2).lower(), m.group(2).lower())
    return f"{n} {unit}{'' if n == '1' or unit == 'ml' else 's'}"


def _food_note(text: str) -> Optional[str]:
    notes = []
    for clause in re.split(r"[.;]\s*", text):
        if NEGATED.search(clause):
            continue
        notes += [m.group(0) for m in FOOD_RE.finditer(clause)]
    notes = [n for n in notes if not any(n != o and n.lower() in o.lower() for o in notes)]
    return ", ".join(dict.fromkeys(notes)) or None


def _days(durations: List[str]) -> Optional[int]:
    for d in durations:
        num, unit = d.split(" ", 1)
        factor = 1 if unit.startswith("day") else 7 if unit.startswith("week") else 30
        return int(num) * factor
    return None


def build_timetable(raw_text: str, extracted: ExtractedEntities) -> List[TimetableEntry]:
    medicines = extracted.medications
    if not medicines:
        slots, as_needed = _slots_for(extracted.frequencies)
        if not slots and not as_needed:
            return []
        name = extracted.dosages[0] if extracted.dosages else "Your medicine"
        return [TimetableEntry(
            medicine=name, amount=_amount(raw_text), slots=slots, as_needed=as_needed,
            food_note=_food_note(raw_text), duration_days=_days(extracted.durations),
        )]

    found = sorted((raw_text.find(m.split(" ")[0]), m) for m in medicines)
    found = [(pos, m) for pos, m in found if pos >= 0]
    entries: List[TimetableEntry] = []
    for k, (pos, med) in enumerate(found):
        end = found[k + 1][0] if k + 1 < len(found) else len(raw_text)
        segment = raw_text[pos:end]
        slots, as_needed = _slots_for(ClinicalExtractor.extract_frequencies(segment))
        durations = ClinicalExtractor.extract_durations(segment) or (extracted.durations if len(found) == 1 else [])
        entries.append(TimetableEntry(
            medicine=med, amount=_amount(segment), slots=slots, as_needed=as_needed,
            food_note=_food_note(segment), duration_days=_days(durations),
        ))
    return entries
