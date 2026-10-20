import asyncio
import json
import logging
import httpx
from typing import Dict, Any, Optional
from ..config import settings
from .fallback import build_rule_based_content
from ..models.schemas import (
    StructuredCards,
    InstructionCard,
    ExtractedEntities
)

logger = logging.getLogger("healthbridge.ai")

SYSTEM_PROMPT = """You are HealthBridge AI, a clinical plain-language specialist helping patients and caregivers understand medical instructions safely.

GOAL:
Convert the provided medical instruction or prescription into clear, accurate, reassuring plain language that any patient or caregiver can follow,
regardless of education level, age, health condition or familiarity with medical terms. Plain language benefits everyone: keep sentences short and
explain every abbreviation (including Indian prescription notation such as OD, BD, TDS, SOS, AC, PC and dose patterns like 1-0-1).
You will output your response in the requested target language:
- 'en': Plain English (short sentences, everyday words, warm and clear)
- 'hi': Simple Hindi (हिन्दी) (Devanagari script, everyday colloquial spoken Hindi, avoid archaic or difficult vocabulary)
- 'mr': Simple Marathi (मराठी) (Devanagari script, clear everyday spoken Marathi, warm and polite)

SAFETY & MEDICAL FIDELITY RULES:
1. NEVER alter, round, or hallucinate numbers, dosages, durations, or frequencies. If raw text says '500 mg', you MUST state '500 mg' (or 500 मिलीग्राम / 500 मिग्रॅ).
2. NEVER remove warnings, allergies, or contraindications. Highlight them prominently.
3. If an instruction says 'do not crush' or 'avoid alcohol', preserve it explicitly as a strict prohibition.
4. If an instruction is ambiguous (e.g. 'take as needed' without maximum limit), explicitly advise the patient to ask their doctor or pharmacist.
5. Provide a 'read_aloud_text' field specifically written for smooth, natural speech synthesis (expand clinical abbreviations: mg -> milligrams, PO -> by mouth, TID -> three times a day, etc.).

YOU MUST RETURN VALID JSON ONLY with this exact structure:
{
  "simplified_text": "Overall clear summary paragraph in simple language.",
  "dosage_card": {
    "title": "Language-appropriate title for Dosage",
    "content": "Clear instruction on how much medicine to take at once",
    "badge": "e.g., 500 mg / 1 tablet",
    "icon": "pill"
  },
  "frequency_card": {
    "title": "Language-appropriate title for Frequency & Schedule",
    "content": "Clear explanation of how many times a day and when to take it",
    "badge": "e.g., 3 times daily",
    "icon": "clock"
  },
  "timing_card": {
    "title": "Language-appropriate title for Food & Timing",
    "content": "Clear instruction regarding relation to meals (with food, after meals, empty stomach, etc.)",
    "badge": "e.g., With meals",
    "icon": "utensils"
  },
  "precautions_card": {
    "title": "Language-appropriate title for Things to Avoid (Precautions)",
    "content": "Brief overview of what not to do",
    "items": ["List of strict prohibitions and do-nots, e.g. Do not stop early, Avoid alcohol"],
    "icon": "shield-alert"
  },
  "warning_signs_card": {
    "title": "Language-appropriate title for Danger Signs (When to Contact Doctor)",
    "content": "When to seek urgent doctor or hospital help",
    "items": ["Specific red flags like rash, difficulty breathing, facial swelling, chest pain"],
    "icon": "alert-triangle"
  },
  "patient_summary": [
    "Simple bullet 1 (What medicine is for / main action)",
    "Simple bullet 2 (Exact daily routine)",
    "Simple bullet 3 (Most important safety rule)"
  ],
  "read_aloud_text": "Text to be spoken aloud by text-to-speech engine in the target language."
}
"""


class AISimplificationService:
    @classmethod
    def get_provider_status(cls) -> Dict[str, Any]:
        """Checks which AI credentials are configured in the environment."""
        has_gemini = bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip() and settings.GEMINI_API_KEY != "your_gemini_api_key_here")
        has_groq = bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip())
        has_openai = bool(settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip())

        active_provider = settings.AI_PROVIDER.lower()
        is_configured = False

        if active_provider == "gemini" and has_gemini:
            is_configured = True
        elif active_provider == "groq" and has_groq:
            is_configured = True
        elif active_provider == "openai" and has_openai:
            is_configured = True
        elif has_gemini or has_groq or has_openai:
            is_configured = True

        return {
            "is_configured": is_configured,
            "provider": active_provider,
            "gemini_ready": has_gemini,
            "groq_ready": has_groq,
            "openai_ready": has_openai,
        }

    @classmethod
    async def simplify(
        cls,
        raw_text: str,
        target_language: str,
        extracted: ExtractedEntities
    ) -> Dict[str, Any]:
        """
        Processes medical text through configured AI provider.
        If credentials are absent, falls back transparently to intelligent rule-based templating
        with explicit notification so the student and user know exact AI status.
        """
        status = cls.get_provider_status()

        if status["is_configured"]:
            try:
                if (settings.AI_PROVIDER == "gemini" and status["gemini_ready"]) or (status["gemini_ready"] and not status["groq_ready"] and not status["openai_ready"]):
                    return await cls._call_gemini(raw_text, target_language)
                elif settings.AI_PROVIDER == "groq" and status["groq_ready"]:
                    return await cls._call_groq(raw_text, target_language)
                elif settings.AI_PROVIDER == "openai" and status["openai_ready"]:
                    return await cls._call_openai(raw_text, target_language)
            except Exception as e:
                logger.error(f"Error calling live LLM: {e}", exc_info=True)
                # Fall back gracefully to rule-based generation with honest error note
                return cls._generate_rule_based_fallback(
                    raw_text, target_language, extracted,
                    ai_error=f"Live AI model call failed: {str(e)}. Using verified clinical rule-based engine."
                )

        # Honest state when no API key is configured
        return cls._generate_rule_based_fallback(
            raw_text, target_language, extracted,
            ai_error=None
        )

    @classmethod
    async def _call_gemini(cls, raw_text: str, target_language: str) -> Dict[str, Any]:
        """Calls Google Gemini API using google-genai or direct REST."""
        lang_names = {"en": "Simple English", "hi": "Simple Hindi (हिन्दी)", "mr": "Simple Marathi (मराठी)"}
        target_name = lang_names.get(target_language, "Simple English")

        user_prompt = f"""Target Language: {target_name} ({target_language})

Original Medical Prescription / Instruction:
\"\"\"
{raw_text}
\"\"\"

Please convert this into clear patient instructions following all instructions and the JSON schema."""

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            response = await asyncio.wait_for(client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=f"{SYSTEM_PROMPT}\n\n{user_prompt}")
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                )
            ), timeout=settings.AI_TIMEOUT_SECONDS)
            raw_content = response.text
            parsed = json.loads(raw_content)
            return {
                "success": True,
                "ai_provider": "Google Gemini",
                "ai_model": settings.GEMINI_MODEL,
                "ai_configured": True,
                "data": parsed,
                "setup_guidance": None
            }
        except Exception as e:
            # A timeout means Gemini itself is slow; retrying over REST would only double the wait
            if isinstance(e, asyncio.TimeoutError):
                raise RuntimeError(f"Gemini did not answer within {settings.AI_TIMEOUT_SECONDS} seconds") from e
            # Try REST fallback if SDK initialization has specific version issue
            logger.warning(f"Google GenAI SDK error, attempting direct REST fallback: {e}")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": f"{SYSTEM_PROMPT}\n\n{user_prompt}"}
                        ]
                    }
                ],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.2
                }
            }
            async with httpx.AsyncClient(timeout=float(settings.AI_TIMEOUT_SECONDS)) as http_client:
                res = await http_client.post(url, json=payload)
                res.raise_for_status()
                res_data = res.json()
                text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text)
                return {
                    "success": True,
                    "ai_provider": "Google Gemini (REST API)",
                    "ai_model": settings.GEMINI_MODEL,
                    "ai_configured": True,
                    "data": parsed,
                    "setup_guidance": None
                }

    @classmethod
    async def _call_groq(cls, raw_text: str, target_language: str) -> Dict[str, Any]:
        """Calls Groq API (ultra-fast Llama 3.3)."""
        lang_names = {"en": "Simple English", "hi": "Simple Hindi (हिन्दी)", "mr": "Simple Marathi (मराठी)"}
        target_name = lang_names.get(target_language, "Simple English")

        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Target Language: {target_name} ({target_language})\n\nPrescription:\n{raw_text}"}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }
        async with httpx.AsyncClient(timeout=25.0) as http_client:
            res = await http_client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return {
                "success": True,
                "ai_provider": "Groq Cloud",
                "ai_model": settings.GROQ_MODEL,
                "ai_configured": True,
                "data": parsed,
                "setup_guidance": None
            }

    @classmethod
    async def _call_openai(cls, raw_text: str, target_language: str) -> Dict[str, Any]:
        """Calls OpenAI API."""
        lang_names = {"en": "Simple English", "hi": "Simple Hindi (हिन्दी)", "mr": "Simple Marathi (मराठी)"}
        target_name = lang_names.get(target_language, "Simple English")

        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Target Language: {target_name} ({target_language})\n\nPrescription:\n{raw_text}"}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }
        async with httpx.AsyncClient(timeout=25.0) as http_client:
            res = await http_client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return {
                "success": True,
                "ai_provider": "OpenAI",
                "ai_model": settings.OPENAI_MODEL,
                "ai_configured": True,
                "data": parsed,
                "setup_guidance": None
            }

    @classmethod
    def _generate_rule_based_fallback(
        cls,
        raw_text: str,
        target_language: str,
        extracted: ExtractedEntities,
        ai_error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Rule-based generator used when no external AI key is configured, or when the
        live call fails. It only rephrases facts found by the extractor, so it never
        invents doses.
        """
        guidance = (
            ai_error if ai_error else
            "No AI key (GEMINI_API_KEY, GROQ_API_KEY or OPENAI_API_KEY) is set in backend/.env, "
            "so these instructions were written by the built-in rule-based engine. Add a free "
            "GEMINI_API_KEY to backend/.env for more natural AI wording."
        )

        return {
            "success": True,
            "ai_provider": "Built-in rule-based engine",
            "ai_model": "Rule-Based Clinical Parser v1.1",
            "ai_configured": False,
            "data": build_rule_based_content(raw_text, target_language, extracted),
            "setup_guidance": guidance
        }
