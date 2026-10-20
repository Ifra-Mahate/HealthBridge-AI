from typing import List
from ..models.schemas import SamplePreset


SAMPLE_PRESETS: List[SamplePreset] = [
    SamplePreset(
        id="sample_amoxicillin",
        title="Amoxicillin 500mg (Antibiotic Course)",
        category="Infection / Antibiotic",
        description="Prescription for bacterial infection with strict course duration, food instructions, and allergy red flags.",
        raw_text=(
            "Rx: Amoxicillin 500 mg PO TID x 7 days with meals. "
            "Do NOT take if allergic to penicillin. "
            "Complete the entire 7-day course even if symptoms improve early. "
            "Discontinue immediately and seek emergency medical care if severe skin rash, "
            "facial swelling, or difficulty breathing develops."
        )
    ),
    SamplePreset(
        id="sample_metformin",
        title="Metformin & Glimepiride (Diabetes Management)",
        category="Endocrine / Diabetes",
        description="Dual medication for blood sugar control with specific meal timings, alcohol warning, and hypoglycemia signs.",
        raw_text=(
            "Rx: Metformin 500 mg tab PO BID with breakfast and dinner. "
            "Glimepiride 1 mg tab PO QD 15 minutes before breakfast. "
            "Avoid alcohol completely due to risk of lactic acidosis. "
            "Do not skip meals. If you feel shaky, cold sweats, or dizzy (blood sugar below 70 mg/dL), "
            "consume 15 g of fast-acting glucose immediately and call your clinic."
        )
    ),
    SamplePreset(
        id="sample_lisinopril",
        title="Lisinopril & Furosemide (Hypertension & Fluid)",
        category="Cardiovascular / Blood Pressure",
        description="Blood pressure and diuretic regimen with morning scheduling, hydration guidelines, and orthostatic dizziness warning.",
        raw_text=(
            "Rx: Lisinopril 10 mg PO QD in the morning. "
            "Furosemide 40 mg PO QD in the morning with a full glass of water. "
            "Avoid potassium supplements. Do NOT stop taking abruptly without consulting doctor. "
            "Get up slowly from sitting or lying down to prevent dizziness. "
            "Report sudden swelling of legs or weight gain over 2 kg in 48 hours to physician."
        )
    ),
    SamplePreset(
        id="sample_asthma",
        title="Budesonide & Salbutamol (Asthma Regimen)",
        category="Respiratory / Inhalers",
        description="Steroid inhaler maintenance combined with rescue inhaler, mouth rinsing advice, and shortness of breath warning.",
        raw_text=(
            "Rx: Budesonide 200 mcg inhaler: 2 puffs BID every morning and night. "
            "Rinse mouth thoroughly with water and spit out after each use to prevent thrush. "
            "Salbutamol 100 mcg inhaler: 1-2 puffs PRN every 4-6 hours for acute wheezing. "
            "Do not exceed 8 puffs in 24 hours. Seek immediate emergency room attention if breathing difficulty does not improve within 15 minutes."
        )
    ),
    SamplePreset(
        id="sample_ibuprofen",
        title="Ibuprofen 400mg (Anti-inflammatory / Pain)",
        category="Musculoskeletal / Pain",
        description="NSAID pain relief with strict 24-hour ceiling dose, stomach protection, and gastrointestinal red-flag indicators.",
        raw_text=(
            "Rx: Ibuprofen 400 mg tab PO TID PRN for severe knee inflammation. "
            "Always take with food or milk. Do NOT take on an empty stomach. "
            "Do not exceed 1200 mg in 24 hours. Avoid taking with other aspirin or NSAIDs. "
            "Stop medication immediately and consult doctor if black tarry stools or persistent stomach burning occurs."
        )
    )
]
