from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., description="Message sender role: 'user' or 'assistant'")
    content: str = Field(..., description="Message text content")


class RAGQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000, description="Natural language question")
    top_k: int = Field(default=4, ge=1, le=10, description="Number of context chunks to retrieve")
    search_mode: Literal["hybrid", "dense", "bm25"] = Field(
        default="hybrid", description="Search strategy: 'hybrid' (RRF), 'dense' (FAISS), or 'bm25' (lexical)"
    )
    history: list[ChatMessage] = Field(
        default_factory=list, description="Recent conversation history for multi-turn context"
    )


class CitationItem(BaseModel):
    source_number: int
    document_id: str
    document_title: str
    page_number: int
    security_level: str
    chunk_id: str
    quote_excerpt: str


class RAGQueryResponse(BaseModel):
    question: str
    answer: str
    user_role: str
    allowed_security_levels: list[str]
    citations: list[CitationItem]
    has_sufficient_context: bool
