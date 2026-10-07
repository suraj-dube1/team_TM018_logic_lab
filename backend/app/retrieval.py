import re

SQL = """
WITH vec AS (
  SELECT id, row_number() OVER (ORDER BY embedding <=> %(q)s::vector) AS rk
  FROM chunks ORDER BY embedding <=> %(q)s::vector LIMIT 20
), fts AS (
  SELECT c.id, row_number() OVER (ORDER BY ts_rank_cd(c.tsv, query) DESC) AS rk
  FROM chunks c, to_tsquery('english', %(tsq)s) query
  WHERE c.tsv @@ query LIMIT 20
)
SELECT c.id, c.doc_id, c.source, c.kind, c.page, c.bbox, c.text, d.title,
       1 - (c.embedding <=> %(q)s::vector) AS sim,
       COALESCE(1.0 / (60 + v.rk), 0) + COALESCE(1.0 / (60 + f.rk), 0) AS score
FROM chunks c
JOIN documents d ON d.id = c.doc_id
LEFT JOIN vec v ON v.id = c.id
LEFT JOIN fts f ON f.id = c.id
WHERE v.id IS NOT NULL OR f.id IS NOT NULL
ORDER BY score DESC
LIMIT %(k)s
"""


def _tsquery(question):
    words = [w for w in re.findall(r"[A-Za-z0-9]+", question) if len(w) > 2]
    return " | ".join(words) if words else "xqzxqz"


def search(conn, question, qvec, k=6):
    """Hybrid vector + keyword search fused with RRF. When `conn` is a user connection,
    RLS has already removed every row the user may not see *before* ranking happens."""
    return conn.execute(SQL, {"q": qvec, "tsq": _tsquery(question), "k": k}).fetchall()
