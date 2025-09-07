def is_strategy(q: str) -> bool:
    q=(q or "").lower()
    if any(k in q for k in ("who is","about","bio","profile","background")): return False
    has_ai = ("ai" in q) or ("artificial intelligence" in q)
    has_plan = any(k in q for k in ("strategy","roadmap","plan","playbook","table stakes","table-stakes"))
    explicit = any(k in q for k in ("need an ai strategy","why do i need an ai"))
    return (has_ai and has_plan) or explicit

def is_bio(q: str) -> bool:
    q=(q or "").lower()
    return any(k in q for k in ("who is","about","bio","profile","background"))

def is_kendall(q: str) -> bool:
    q=(q or "").lower()
    # match any mention of Kendall plus 
    # allow specific signals to keep precision if needed
    return "kendall" in q

def is_reflective(q: str) -> bool:
    q=(q or "").lower()
    keys=(
      "define success","success",
      "forget when chasing goals","chasing goals",
      "kindness","boldest opinion","bold opinion",
      "fear of death","fear death","afterlife",
      "free will","misunderstood about you","misunderstand about you",
      "irrational belief","stay grounded","secret fuel",
      "unshakable belief","core trait","need to hear more often","solitude",
      "true love","chemistry"
    )
    return any(k in q for k in keys)

def is_opinion_israel(q: str) -> bool:
    q=(q or "").lower()
    keys=("israel","gaza","hamas","idf","west bank","antisemitism","two-state","two state")
    return any(k in q for k in keys)

ROUTES = [
    (is_strategy,       "strategy"),
    (is_kendall,        "kendall"),
    (is_opinion_israel, "opinion_israel"),
    (is_reflective,     "reflective"),
    (is_bio,            "bio"),
]
