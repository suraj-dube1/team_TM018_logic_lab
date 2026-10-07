import numpy as np

_model = None


def _m():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding("BAAI/bge-small-en-v1.5")  # 384-dim, ONNX, CPU friendly
    return _model


def embed_docs(texts):
    return [np.asarray(v, dtype=np.float32) for v in _m().embed(list(texts))]


def embed_query(text):
    return np.asarray(next(iter(_m().query_embed([text]))), dtype=np.float32)
