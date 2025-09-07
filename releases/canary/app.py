from flask import Flask, jsonify, request
app = Flask(__name__)

def curated_answer(q):
    p = (q or "").lower()
    if "who is" in p or "about" in p:
        return ("Hi — I’m Howard Tullman. I’m a Chicago-based entrepreneur, operator, and investor. "
                "I led 1871, helped build Tribeca Flashpoint Academy, and turned around Kendall College. "
                "Earlier I founded or ran CCC Information Services, Tunes.com, and The Cobalt Group. "
                "I mentor founders, invest in scrappy teams, and I believe AI is now table stakes for every business and for individuals.")
    if "ai strategy" in p or ("ai" in p and "strategy" in p):
        return ("AI is how you compound advantage—speed, coverage, consistency, and a learning loop from your own work. "
                "Start with one painful process, ship a small assist this quarter, measure, and scale what works. "
                "Keep humans in the loop early, cite your sources, and protect data.")
    if "proud" in p:
        return ("I’m proudest of the people and platforms we built—1871; the turnarounds at Kendall and Tribeca Flashpoint; "
                "and the founders I’ve mentored. The impact—careers, customers, execution—outlasts me.")
    return ("Hi — I’m Howard Tullman. Tell me the outcome you want and the constraint in your way—"
            "we’ll ship one small win this quarter and scale the ones that work.")

@app.get("/health")
def health():
    return jsonify({"ok": True})

@app.post("/chat")
def chat():
    j = request.get_json(force=True, silent=True) or {}
    q = (j.get("prompt") or "").strip()
    ans = curated_answer(q)
    links = []
    if "who is" in (q or "").lower():
        links = [{"title":"Wikipedia: Howard Tullman","url":"https://en.wikipedia.org/wiki/Howard_Tullman"}]
    return jsonify({"session_id": j.get("session_id"), "answer": ans, "sources": links})
