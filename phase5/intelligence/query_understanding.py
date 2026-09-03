"""Query understanding: language, entities, intent, mode - deterministic first,
LLM optional. Same regex/tokenizer as Phase 4 so behaviour stays predictable
and free; the LLM only refines when configured.
"""
import re

# --- entity extraction -------------------------------------------------------
IS_RE = re.compile(r"\bIS\s*[:\-]?\s*(\d{2,6})(?:\s*[:\-]\s*(\d{4}))?", re.I)
QCO_RE = re.compile(r"\bQCO[ \-:]*(\d{1,4})\b", re.I)
SCHEME_WORDS = ("scheme i", "scheme ii", "scheme iii", "scheme iv", "fmcs",
                "isi mark", "registration scheme", "hallmarking scheme",
                "conformity assessment")
TEST_WORDS = ("test", "tests", "testing", "lab", "laboratory", "laboratories")
PRODUCT_HINTS = ("manufactur", "make", "produce", "product", "chair", "cooker",
                 "pressure cooker", "cement", "steel", "paint", "toy", "led",
                 "household", "furniture")

STOPWORDS = {"what", "which", "who", "where", "when", "is", "are", "the", "a",
             "an", "of", "for", "to", "and", "apply", "applies", "required",
             "require", "relevant", "can", "perform", "do", "them", "my",
             "me", "tell", "show", "give", "this", "that", "these", "those"}


def detect_language(text):
    """en by default; Devanagari -> hi (script detection, not a model call)."""
    if re.search(r"[\u0900-\u097F]", text or ""):
        return "hi"
    return "en"


def extract_entities(text):
    """Deterministic entity extraction. LLM never invents these later."""
    ents = {"is_number": None, "is_year": None, "is_numbers": [], "qco_number": None,
            "scheme": None, "wants_tests": False, "wants_labs": False,
            "product_text": None, "comparison": False, "identifier": None}
    nums = []
    for m in IS_RE.finditer(text or ""):
        nums.append(m.group(1))
        if not ents["is_number"]:
            ents["is_number"], ents["is_year"] = m.group(1), m.group(2)
    ents["is_numbers"] = nums
    ents["comparison"] = len(nums) >= 2 or bool(
        re.search(r"\bcompar\w+\b", text or "", re.I))
    mq = QCO_RE.search(text or "")
    ents["qco_number"] = mq.group(1) if mq else None
    low = (text or "").lower()
    for w in SCHEME_WORDS:
        if w in low:
            ents["scheme"] = w
            break
    ents["wants_tests"] = any(w in low for w in TEST_WORDS[:4])
    ents["wants_labs"] = any(w in low for w in TEST_WORDS[4:]) or "lab" in low
    if any(h in low for h in PRODUCT_HINTS) or not nums:
        toks = [t for t in re.findall(r"[a-z0-9\-]+", low)
                if len(t) >= 3 and t not in STOPWORDS]
        # drop pure test/lab words AND BIS-domain boilerplate from product
        # text ('indian' matched 'Indian Language' in IS 16333 live - the
        # product text must stay a product description, not a query echo)
        toks = [t for t in toks if t not in
                ("tests", "test", "testing", "laboratory", "laboratories",
                 "labs", "indian", "standard", "bis", "certification",
                 "mandatory", "scheme", "quality", "control", "order",
                 "licence", "license", "applicable", "supporting", "evidence")]
        ents["product_text"] = " ".join(toks[:6]) or None
    return ents


def classify_task(text, entities=None):
    """Prefer the simplest valid route (spec). Deterministic; LLM may refine
    downstream but classification itself stays free and stable."""
    e = entities or extract_entities(text)
    low = (text or "").lower()
    if e["comparison"] and len(e["is_numbers"]) >= 2:
        return "COMPARISON"
    ident = re.search(r"\b(?:verify|licence|license|cml|huid|registration no)\b",
                      low)
    if ident:
        return "VERIFICATION"
    product_hint = any(h in low for h in PRODUCT_HINTS)
    complex_markers = sum(1 for m in (
        "manufactur", "requirements", "compliance", "pathway", "which scheme",
        "mandatory", "labs or laboratories", "and show", "all bis") if m in low)
    if complex_markers >= 2 or (product_hint and complex_markers >= 1) or (
            any(h in low for h in ("manufactur",)) and e["wants_tests"]):
        return "COMPLIANCE_WORKFLOW"
    if e["wants_labs"] and not e["wants_tests"]:
        return "LAB_LOOKUP"
    if e["wants_tests"]:
        return "TEST_LOOKUP"
    if e["qco_number"]:
        return "QCO_LOOKUP"
    if e["scheme"]:
        return "SCHEME_LOOKUP"
    if e["is_number"] and not e["product_text"]:
        return "SIMPLE_LOOKUP"
    if e["product_text"] and not e["is_number"]:
        return "STANDARD_DISCOVERY" if any(
            w in low for w in ("standard", "apply", "applies", "which")) \
            else "PRODUCT_DISCOVERY"
    if "compare" in low:
        return "COMPARISON"
    if "document" in low or "manual" in low:
        return "DOCUMENT_RESEARCH"
    if "certif" in low and e["product_text"]:
        return "CERTIFICATION_GUIDANCE"
    return "GENERAL_BIS"


AGENT_TASKS = {"COMPLIANCE_WORKFLOW", "COMPARISON", "VERIFICATION",
               "CERTIFICATION_GUIDANCE", "DOCUMENT_RESEARCH",
               "STANDARD_DISCOVERY"}


def execution_mode(task, force_agent=False, entities=None):
    """SIMPLE chat when one tool family answers it; AGENT for multi-step work."""
    if force_agent:
        return "AGENT"
    return "AGENT" if task in AGENT_TASKS else "SIMPLE"
