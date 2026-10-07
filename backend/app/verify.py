"""Claim verifier: a claim survives only if it cites a retrieved chunk AND is grounded in it
(every number appears in the cited text, and enough of its content words do too)."""
import os
import re

STOP = set("the and for are was were has have had that this with from into your their its not but can will would should "
           "about which what when where who whom how than then also been being them they there these those such any all "
           "each per via our out use used using over under more most other some may might could does did".split())


def _words(t):
    return [w for w in re.findall(r"[a-z0-9]+", t.lower()) if len(w) > 2 and w not in STOP]


def _stem(w):
    return w[:5]


def _nums(t):
    t = re.sub(r"\[\d+\]", " ", t)
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", t)}


def support(claim, source_texts):
    src = " ".join(source_texts)
    src_stems = {_stem(w) for w in _words(src)}
    src_nums = {n for n in _nums(src)} | {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", src)}
    nums_ok = all(n in src_nums or n.rstrip("0").rstrip(".") in src_nums for n in _nums(claim))
    cw = [_stem(w) for w in _words(claim)]
    lex = (sum(1 for w in cw if w in src_stems) / len(cw)) if cw else 0.0
    return nums_ok, lex


def check(claims, rows):
    """claims: [{'text', 'sources': [1-based idx into rows]}] -> (kept, dropped)"""
    lex_min = float(os.getenv("VERIFY_LEX_MIN", "0.5"))
    kept, dropped = [], []
    for c in claims:
        idx = [i for i in c.get("sources", []) if isinstance(i, int) and 1 <= i <= len(rows)]
        if not idx or not c.get("text", "").strip():
            dropped.append({**c, "why": "no valid citation"})
            continue
        nums_ok, lex = support(c["text"], [rows[i - 1]["text"] for i in idx])
        if nums_ok and lex >= lex_min:
            kept.append({"text": c["text"].strip(), "sources": idx, "grounding": round(lex, 2)})
        else:
            dropped.append({**c, "why": "numbers not in source" if not nums_ok else f"weak grounding ({lex:.2f})"})
    return kept, dropped
