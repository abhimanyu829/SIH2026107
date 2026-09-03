"""Document classification: keyword rules first, LLM only when ambiguous.

Categories (spec section 7): CALIBRATION_CERTIFICATE, TEST_REPORT,
FACTORY_DOCUMENT, QC_DOCUMENT, RAW_MATERIAL_DOCUMENT, PROCESS_DOCUMENT,
MACHINERY_DOCUMENT, OTHER.
"""
import re

# Ordered rules: (category, [(strong keywords...), (weak keywords...)])
RULES = [
    ("CALIBRATION_CERTIFICATE",
     ["calibration certificate", "calibration report", "nist traceable",
      "calibrated", "calibration date", "certificate no", "calibration lab"],
     ["calibrat", "traceab"]),
    ("TEST_REPORT",
     ["test report", "test result", "lab report", "tested in accordance",
      "test method", "is 17631", "tested by", "test certificate"],
     ["test", "result", "pass/fail", "laboratory report"]),
    ("RAW_MATERIAL_DOCUMENT",
     ["raw material", "material test certificate", "mtc", "mill certificate",
      "chemical composition", "material grade", "bill of material"],
     ["material", "composition", "grade"]),
    ("MACHINERY_DOCUMENT",
     ["machinery", "machine", "equipment list", "plant and machinery",
      "cnc", "lathe", "press", "instrument list", "equipment register"],
     ["equipment", "machines", "tools"]),
    ("PROCESS_DOCUMENT",
     ["process flow", "process chart", "manufacturing process",
      "process control", "sop", "standard operating procedure",
      "work instruction", "process parameters"],
     ["process", "procedure", "method statement"]),
    ("QC_DOCUMENT",
     ["quality control", "qc plan", "quality manual", "inspection report",
      "quality policy", "in-process inspection", "qc checklist"],
     ["quality", "inspection", "qc"]),
    ("FACTORY_DOCUMENT",
     ["factory license", "factory licence", "layout plan", "gst",
      "manufacturing license", "premises", "factory address",
      "production capacity", "unit registration"],
     ["factory", "premises", "plant address"]),
]


def classify_text(text):
    """(category, confidence, matched_keywords). Deterministic only."""
    low = (text or "").lower()
    best, best_score = "OTHER", 0.0
    matched = []
    for category, strong, weak in RULES:
        score = 0
        cat_matched = []
        for kw in strong:
            if kw in low:
                score += 3
                cat_matched.append(kw)
        for kw in weak:
            if kw in low:
                score += 1
                cat_matched.append(kw)
        if score > best_score:
            best, best_score, matched = category, score, cat_matched
    if best_score == 0:
        return "OTHER", 0.3, []
    conf = min(0.95, 0.5 + 0.1 * best_score)
    return best, round(conf, 2), matched


def classify(document):
    """Classify one extracted document dict.

    Deterministic rules first. When the best rule score is weak (ambiguous),
    ONE LLM call with a short excerpt (300 chars) refines it. The LLM can only
    pick from the fixed category list - it cannot invent types.
    """
    text = "\n".join(p.get("text", "") for p in document.get("pages", []))
    category, confidence, matched = classify_text(text)
    if confidence >= 0.7:
        return {"category": category, "confidence": confidence,
                "method": "rules", "matched_keywords": matched}

    # ambiguous -> one bounded LLM call, fixed vocabulary
    import config as cfg
    excerpt = text[:300].replace("\n", " ").strip()
    prompt = ("Classify this document excerpt into exactly one category from: "
              "%s.\nReply with ONLY the category name, nothing else.\n\nExcerpt: %s"
              % (", ".join(cfg.DOCUMENT_CATEGORIES), excerpt))
    out = cfg.llm_complete_cached("You are a precise document classifier.", prompt,
                                  max_tokens=10)
    if out:
        guess = out.strip().upper().replace(" ", "_").replace("-", "_")
        for c in cfg.DOCUMENT_CATEGORIES:
            if c in guess or guess in c:
                return {"category": c, "confidence": 0.6,
                        "method": "rules+llm", "matched_keywords": matched}
    return {"category": category, "confidence": confidence,
            "method": "rules", "matched_keywords": matched}
