import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List

from .config import settings
from .models.schemas import (
    SimplificationRequest,
    SimplificationResponse,
    HealthStatus,
    SamplePreset,
    ExtractedEntities,
    StructuredCards,
    InstructionCard
)
from .services.extractor import ClinicalExtractor
from .services.verifier import InformationVerifier
from .services.ai_service import AISimplificationService
from .services.timetable import build_timetable
from .data.sample_data import SAMPLE_PRESETS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("healthbridge.main")

app = FastAPI(
    title="HealthBridge AI - Clinical Simplification & Verification API",
    description="Backend API for converting complex medical instructions into accessible English, Hindi, and Marathi for low-literacy patients with automated safety & verification checks.",
    version="1.0.0"
)

# CORS Middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


DISCLAIMER_TEXT = (
    "DISCLAIMER: HealthBridge AI is an informational tool created for academic and research demonstration. "
    "It does NOT provide medical advice, diagnosis, or clinical treatment plans. It does not replace consultation "
    "with a licensed physician, clinical pharmacist, or healthcare provider. Always confirm medical decisions "
    "with qualified healthcare personnel."
)

LANGUAGE_NAMES = {
    "en": "Simple English",
    "hi": "Hindi (हिन्दी)",
    "mr": "Marathi (मराठी)"
}


def _str_list(value) -> List[str]:
    """Coerces an LLM field into a list of non-empty strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(v) for v in value if v is not None and str(v).strip()]


def _card(raw, title: str, content: str, icon: str) -> InstructionCard:
    raw = raw if isinstance(raw, dict) else {}
    items = _str_list(raw.get("items")) if raw.get("items") is not None else None
    badge = raw.get("badge")
    return InstructionCard(
        title=str(raw.get("title") or title),
        content=str(raw.get("content") or content),
        badge=str(badge) if badge else None,
        items=items,
        icon=str(raw.get("icon") or icon),
    )


@app.get("/api", tags=["Health"])
def root():
    return {
        "project": "HealthBridge AI",
        "description": "Medical Instructions Simplification & Verification Engine",
        "version": "1.0.0",
        "status": "online"
    }


@app.get("/api/health", response_model=HealthStatus, tags=["Health"])
def health_check():
    """Returns application status and AI provider configuration health."""
    provider_status = AISimplificationService.get_provider_status()
    return HealthStatus(
        status="healthy",
        ai_configured=provider_status["is_configured"],
        ai_provider=provider_status["provider"],
        gemini_key_present=provider_status["gemini_ready"],
        groq_key_present=provider_status["groq_ready"],
        openai_key_present=provider_status["openai_ready"],
        message=(
            "AI Provider active and ready."
            if provider_status["is_configured"]
            else "AI API key not detected in backend/.env. Running with Clinical Rule-Based Parser. Configure GEMINI_API_KEY for live LLM translation."
        )
    )


@app.get("/api/samples", response_model=List[SamplePreset], tags=["Samples"])
def get_sample_presets():
    """Returns curated clinical prescription samples for quick testing."""
    return SAMPLE_PRESETS


@app.post("/api/extract", response_model=ExtractedEntities, tags=["Clinical Extraction"])
def extract_clinical_entities(payload: SimplificationRequest):
    """Direct endpoint to test rule-based entity extraction on raw medical instructions."""
    try:
        return ClinicalExtractor.extract_all(payload.raw_text)
    except Exception as e:
        logger.error(f"Error during entity extraction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/simplify", response_model=SimplificationResponse, tags=["Simplification"])
async def simplify_instructions(payload: SimplificationRequest):
    """
    Main pipeline:
    1. Extracts structured clinical entities from original text.
    2. Simplifies and translates content using AI model or rule-based parser.
    3. Runs rigorous Information-Preservation verification check.
    4. Returns structured cards, audit report, and safety flags.
    """
    try:
        target_lang = payload.target_language.lower().strip()
        if target_lang not in ["en", "hi", "mr"]:
            target_lang = "en"

        # Step 1: Rule-based clinical entity extraction
        extracted = ClinicalExtractor.extract_all(payload.raw_text)

        # Step 2: AI simplification & translation
        ai_result = await AISimplificationService.simplify(
            raw_text=payload.raw_text,
            target_language=target_lang,
            extracted=extracted
        )

        data = ai_result["data"]
        simplified_text = str(data.get("simplified_text") or "")

        # Format cards. LLM output can miss fields, so every card is merged onto safe defaults.
        structured_cards = StructuredCards(
            dosage=_card(data.get("dosage_card"), "Dosage", "Follow your prescription label.", "pill"),
            frequency=_card(data.get("frequency_card"), "Frequency", "As directed by your doctor.", "clock"),
            timing=_card(data.get("timing_card"), "Timing", "Take with water.", "utensils"),
            precautions=_card(data.get("precautions_card"), "Precautions", "Safety rules", "shield-alert"),
            warning_signs=_card(data.get("warning_signs_card"), "Warning Signs", "Get urgent help if you notice:", "alert-triangle"),
            patient_summary=_str_list(data.get("patient_summary")),
            read_aloud_text=str(data.get("read_aloud_text") or simplified_text)
        )

        # Step 3: Information-Preservation verification
        verification = InformationVerifier.verify(
            original_text=payload.raw_text,
            original_entities=extracted,
            simplified_text=simplified_text,
            structured_cards=structured_cards,
            target_language=target_lang
        )

        return SimplificationResponse(
            success=True,
            target_language=target_lang,
            target_language_name=LANGUAGE_NAMES.get(target_lang, "Simple English"),
            simplified_text=simplified_text,
            structured_cards=structured_cards,
            extracted_from_original=extracted,
            verification=verification,
            timetable=build_timetable(payload.raw_text, extracted),
            ai_provider=ai_result.get("ai_provider", "HealthBridge Engine"),
            ai_model=ai_result.get("ai_model", "Default"),
            ai_configured=ai_result.get("ai_configured", False),
            setup_guidance=ai_result.get("setup_guidance"),
            disclaimer=DISCLAIMER_TEXT
        )

    except Exception as e:
        logger.error(f"Error in simplify_instructions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process instructions: {str(e)}")


# Serve the built React app (frontend/dist) so `python run.py` hosts the whole project.
# During development, Vite on port 5173 serves the frontend and proxies /api here instead.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str):
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (FRONTEND_DIST / full_path).resolve()
        if full_path and candidate.is_file() and FRONTEND_DIST in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def root_info():
        return root()
