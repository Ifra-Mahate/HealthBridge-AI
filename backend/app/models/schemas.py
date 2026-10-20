from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SimplificationRequest(BaseModel):
    raw_text: str = Field(..., min_length=5, max_length=4000, description="Raw prescription or medical instruction text")
    target_language: str = Field(default="en", description="Target language: 'en' (Simple English), 'hi' (Hindi), or 'mr' (Marathi)")


class ExtractedNumberUnit(BaseModel):
    value: float
    raw_str: str
    unit: Optional[str] = None
    context: Optional[str] = None


class ExtractedEntities(BaseModel):
    medications: List[str] = Field(default_factory=list)
    dosages: List[str] = Field(default_factory=list)
    durations: List[str] = Field(default_factory=list)
    numbers: List[ExtractedNumberUnit] = Field(default_factory=list)
    frequencies: List[str] = Field(default_factory=list)
    timings: List[str] = Field(default_factory=list)
    precautions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    negations: List[str] = Field(default_factory=list)


class CheckResult(BaseModel):
    passed: bool
    details: str
    items_original: List[str] = Field(default_factory=list)
    items_verified: List[str] = Field(default_factory=list)
    items_missing: List[str] = Field(default_factory=list)


class VerificationReport(BaseModel):
    score: int = Field(..., description="Preservation safety score from 0 to 100")
    status: str = Field(..., description="'VERIFIED' | 'CAUTION' | 'CRITICAL_MISMATCH'")
    summary: str = Field(..., description="Human-readable verification summary")
    numeric_check: CheckResult
    negation_check: CheckResult
    frequency_check: CheckResult
    timing_check: CheckResult
    warning_check: CheckResult
    ambiguity_warnings: List[str] = Field(default_factory=list)
    flags: List[str] = Field(default_factory=list)


class InstructionCard(BaseModel):
    title: str
    content: str
    badge: Optional[str] = None
    items: Optional[List[str]] = None
    icon: str


class StructuredCards(BaseModel):
    dosage: InstructionCard
    frequency: InstructionCard
    timing: InstructionCard
    precautions: InstructionCard
    warning_signs: InstructionCard
    patient_summary: List[str] = Field(default_factory=list)
    read_aloud_text: str


class TimetableEntry(BaseModel):
    medicine: str
    amount: Optional[str] = None
    slots: List[str] = Field(default_factory=list, description="Any of: morning, afternoon, evening, night")
    as_needed: bool = False
    weekly: bool = False
    food_note: Optional[str] = None
    duration_days: Optional[int] = None


class GlossaryTerm(BaseModel):
    term: str
    found_as: str
    meaning: str


class SimplificationResponse(BaseModel):
    success: bool
    target_language: str
    target_language_name: str
    simplified_text: str
    structured_cards: StructuredCards
    extracted_from_original: ExtractedEntities
    verification: VerificationReport
    timetable: List[TimetableEntry] = Field(default_factory=list)
    glossary: List[GlossaryTerm] = Field(default_factory=list)
    ai_provider: str
    ai_model: str
    ai_configured: bool
    setup_guidance: Optional[str] = None
    disclaimer: str


class HealthStatus(BaseModel):
    status: str
    ai_configured: bool
    ai_provider: str
    gemini_key_present: bool
    groq_key_present: bool
    openai_key_present: bool
    message: str


class SamplePreset(BaseModel):
    id: str
    title: str
    category: str
    description: str
    raw_text: str
