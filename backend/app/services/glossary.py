"""
Explains the medical abbreviations and shorthand found in a prescription.
Includes the Latin-derived terms used internationally and the notation common
in Indian prescriptions (OD, BD, TDS, SOS, 1-0-1).
"""
import re
from typing import List

from ..models.schemas import GlossaryTerm

# (regex, term shown, English, Hindi, Marathi)
TERMS = [
    (r"\bRx\b", "Rx", "Prescription: the medicines your doctor has ordered.",
     "पर्चा: डॉक्टर द्वारा लिखी गई दवाएं।", "प्रिस्क्रिप्शन: डॉक्टरांनी लिहून दिलेली औषधे."),
    (r"\bPO\b|\bp\.o\.", "PO", "By mouth (Latin: per os). Swallow the medicine.",
     "मुंह से (लैटिन: per os)। दवा निगलनी है।", "तोंडाने (लॅटिन: per os). औषध गिळायचे आहे."),
    (r"\bQD\b|\bOD\b", "OD / QD", "Once a day (Latin: omne in die / quaque die).",
     "दिन में एक बार।", "दिवसातून एकदा."),
    (r"\bBID\b|\bBD\b|\bb\.i\.d\.", "BD / BID", "Twice a day (Latin: bis in die).",
     "दिन में दो बार।", "दिवसातून दोनदा."),
    (r"\bTID\b|\bTDS\b|\bt\.i\.d\.", "TDS / TID", "Three times a day (Latin: ter in die / ter die sumendum).",
     "दिन में तीन बार।", "दिवसातून तीन वेळा."),
    (r"\bQID\b|\bQDS\b|\bq\.i\.d\.", "QDS / QID", "Four times a day (Latin: quater in die).",
     "दिन में चार बार।", "दिवसातून चार वेळा."),
    (r"\bq(\d+)h\b", "qNh", "Every N hours, for example q6h means every 6 hours.",
     "हर N घंटे में, जैसे q6h का मतलब हर 6 घंटे।", "दर N तासांनी, उदा. q6h म्हणजे दर 6 तासांनी."),
    (r"\bPRN\b|\bp\.r\.n\.", "PRN", "Only when needed (Latin: pro re nata).",
     "सिर्फ़ ज़रूरत पड़ने पर।", "फक्त गरज असेल तेव्हा."),
    (r"\bSOS\b", "SOS", "Only if needed, for example when symptoms appear.",
     "सिर्फ़ ज़रूरत होने पर, जैसे लक्षण दिखने पर।", "फक्त गरज असल्यास, उदा. लक्षणे दिसल्यावर."),
    (r"\bHS\b|\bh\.s\.", "HS", "At bedtime (Latin: hora somni).",
     "रात को सोने से पहले।", "रात्री झोपण्यापूर्वी."),
    (r"\bAC\b", "AC", "Before meals (Latin: ante cibum).",
     "खाना खाने से पहले।", "जेवणापूर्वी."),
    (r"\bPC\b", "PC", "After meals (Latin: post cibum).",
     "खाना खाने के बाद।", "जेवणानंतर."),
    (r"\bSTAT\b", "STAT", "Immediately, right now (Latin: statim).",
     "तुरंत।", "ताबडतोब."),
    (r"(?<![\d.\-/])[0-2](?:\.5)?\s*-\s*[0-2](?:\.5)?\s*-\s*[0-2](?:\.5)?(?![\d\-/]|\.\d)", "1-0-1",
     "Dose pattern: morning, afternoon, night. 1-0-1 means one in the morning, none in the afternoon, one at night.",
     "खुराक का क्रम: सुबह-दोपहर-रात। 1-0-1 का मतलब सुबह एक, दोपहर कोई नहीं, रात एक।",
     "डोसचा क्रम: सकाळ-दुपार-रात्र. 1-0-1 म्हणजे सकाळी एक, दुपारी नाही, रात्री एक."),
    (r"\bx\s*\d+\s*(days?|weeks?)\b", "x N days", "For N days, the length of the treatment course.",
     "N दिनों तक, यानी इलाज कितने दिन चलेगा।", "N दिवस, म्हणजे उपचार किती दिवस चालेल."),
    (r"\bTab\b|\btab\b", "Tab", "Tablet.", "गोली (टैबलेट)।", "गोळी (टॅबलेट)."),
    (r"\bCap\b|\bcap\b", "Cap", "Capsule.", "कैप्सूल।", "कॅप्सूल."),
    (r"\bSyp\b|\bsyp\b", "Syp", "Syrup (liquid medicine).", "सिरप (तरल दवा)।", "सिरप (पातळ औषध)."),
    (r"\bmg\b", "mg", "Milligram, a unit of medicine strength.", "मिलीग्राम, दवा की ताकत की इकाई।", "मिलिग्रॅम, औषधाच्या ताकदीचे एकक."),
    (r"\bmcg\b", "mcg", "Microgram, one-thousandth of a milligram.", "माइक्रोग्राम, मिलीग्राम का हज़ारवां हिस्सा।", "मायक्रोग्रॅम, मिलिग्रॅमचा हजारावा भाग."),
    (r"\bml\b", "ml", "Millilitre, a unit of liquid volume. A teaspoon is about 5 ml.",
     "मिलीलीटर, तरल की मात्रा। एक चम्मच लगभग 5 ml होता है।", "मिलिलिटर, द्रवाचे प्रमाण. एक चमचा सुमारे 5 ml असतो."),
    (r"\bmg/dL\b", "mg/dL", "Milligrams per decilitre, used for blood sugar readings.",
     "मिलीग्राम प्रति डेसीलीटर, ब्लड शुगर मापने की इकाई।", "मिलिग्रॅम प्रति डेसिलिटर, रक्तातील साखर मोजण्याचे एकक."),
    (r"\bNSAIDs?\b", "NSAIDs", "Non-steroidal anti-inflammatory drugs, such as ibuprofen and aspirin.",
     "दर्द और सूजन की दवाएं, जैसे आइबुप्रोफ़ेन और एस्पिरिन।", "वेदना आणि सूज कमी करणारी औषधे, उदा. आयबुप्रोफेन आणि ॲस्पिरिन."),
]

LANG_INDEX = {"en": 2, "hi": 3, "mr": 4}


def build_glossary(raw_text: str, lang: str = "en") -> List[GlossaryTerm]:
    idx = LANG_INDEX.get(lang, 2)
    found: List[GlossaryTerm] = []
    for row in TERMS:
        match = re.search(row[0], raw_text)
        if match:
            found.append(GlossaryTerm(term=row[1], found_as=match.group(0).strip(), meaning=row[idx]))
    return found
