from typing import Literal

from pydantic import BaseModel, Field


class RetrievalQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Semantic search query")
    top_k: int = Field(default=5, ge=1, le=20, description="Maximum number of chunks to retrieve")
    search_mode: Literal["hybrid", "dense", "bm25"] = Field(
        default="hybrid", description="Search strategy: 'hybrid' (RRF), 'dense' (FAISS), or 'bm25' (lexical)"
    )


class RetrievalChunkItem(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    page_number: int
    text: str
    security_level: str
    score: float


class RetrievalResponse(BaseModel):
    query: str
    user_role: str
    allowed_security_levels: list[str]
    total_retrieved: int
    chunks: list[RetrievalChunkItem]
