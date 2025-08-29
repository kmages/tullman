# /home/kmages/backend/kenifier_lite.py  (complete file)

import re

# Basic banned phrases / filler to tighten tone
BANNED = [
    "as an ai", "as a large language model", "in conclusion",
    "it depends", "hopefully", "furthermore", "moreover", "additionally",
    "basically", "actually", "honestly", "frankly", "literally",
    "sort of", "kind of", "i mean", "you know",
]

def _kill_em_dashes(text: str) -> str:
    text = text.replace("—", ". ").replace("---", ". ")
    return re.sub(r"\s+\.\s+", ". ", text)

def _ban_phrases(text: str) -> str:
    low = text.lower()
    for p in BANNED:
        if p in low:
            text = re.sub(re.escape(p), "", text, flags=re.IGNORECASE)
            low  = text.lower()
    # collapse whitespace
    return re.sub(r"\s{2,}", " ", text).strip()

def _tighten(text: str) -> str:
    # remove leading fillers
    text = re.sub(r"^(Well|So|Also)[, ]+\b", "", text, flags=re.IGNORECASE)
    # avoid run-ons
    text = re.sub(r", and ", ". ", text)
    text = re.sub(r"; ", ". ", text)
    return text.strip()

def rewrite(raw_text: str) -> str:
    """
    Rule-based cleanup to make the draft concise and direct.
    Does not invent content; it tightens what's given.
    """
    if not raw_text:
        return raw_text
    x = raw_text
    # drop explicit placeholders like "(draft) "
    x = re.sub(r"^\(draft\)\s*", "", x, flags=re.IGNORECASE)
    x = _kill_em_dashes(x)
    x = _ban_phrases(x)
    x = _tighten(x)
    return x
