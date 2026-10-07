import os

from . import llm, verify
from .db import admin_conn, user_conn
from .embed import embed_query
from .retrieval import search

K = 6
NO_ANSWER = "I couldn't find anything you're authorised to see that answers that."


def _blocked_count(question, qvec, visible_ids):
    """Diagnostic only: how many chunks would have ranked in the top-k with NO access control but were
    withheld by RLS. Returns a number, never content. Disable with SHOW_BLOCKED_COUNT=0."""
    with admin_conn() as conn:
        unrestricted = {r["id"] for r in search(conn, question, qvec, K)}
    return len(unrestricted - set(visible_ids))


def run(user, question, k=K):
    qvec = embed_query(question)
    with user_conn(user) as conn:                      # <- RLS applies to everything fetched here
        rows = search(conn, question, qvec, k)
    blocked = _blocked_count(question, qvec, [r["id"] for r in rows]) if os.getenv("SHOW_BLOCKED_COUNT", "1") == "1" else 0

    claims, mode, kept, dropped = [], "none", [], []
    if rows:
        claims, mode = llm.generate(question, rows)
        kept, dropped = verify.check(claims, rows)

    cited = sorted({s for c in kept for s in c["sources"]})
    remap = {old: new for new, old in enumerate(cited, 1)}
    sources = [{
        "n": remap[i], "chunk_id": rows[i - 1]["id"], "title": rows[i - 1]["title"],
        "source": rows[i - 1]["source"], "page": rows[i - 1]["page"], "kind": rows[i - 1]["kind"],
        "snippet": rows[i - 1]["text"][:260],
    } for i in cited]
    out_claims = [{"text": c["text"], "sources": [remap[s] for s in c["sources"]], "grounding": c["grounding"]} for c in kept]

    with admin_conn() as conn:
        conn.execute("INSERT INTO audit_log(username, question, chunk_ids, blocked, dropped) VALUES (%s,%s,%s,%s,%s)",
                     (user["username"], question, [r["id"] for r in rows], blocked, len(dropped)))
    return {
        "user": user["username"], "mode": mode, "claims": out_claims, "sources": sources,
        "answer": " ".join(f"{c['text']} " + "".join(f"[{s}]" for s in c["sources"]) for c in out_claims) or NO_ANSWER,
        "blocked": blocked, "dropped": len(dropped), "retrieved": len(rows),
        "_retrieved_text": " ".join(r["text"] for r in rows),   # stripped before leaving the API
    }
