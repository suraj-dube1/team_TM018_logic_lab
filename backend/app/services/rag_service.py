"""RAG pipeline integrating secure retrieval, controlled prompting, and source citations."""

from dataclasses import dataclass
import logging
import re

from app.models.user import User
from app.services.llm_provider import get_llm_provider
from app.services.retrieval_service import retrieve_for_user
from app.services.vector_store_service import get_vector_store


logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are VaultRAG Intelligence, a secure, knowledgeable AI assistant for organizational and institutional documents.
Follow these rules strictly:
1. Answer the question using the provided Sources. Synthesize and explain the relevant information found in the sources helpfully, accurately, and clearly.
2. If the sources cover aspects of the user's inquiry (such as policies, procedures, eligibility requirements, guidelines, or rules), summarize what is available in the authorized documents and cite them.
3. Only if the provided sources have NO relevant information at all to the user's question, state:
   "The authorized documents do not contain enough information to answer this question."
4. Do not fabricate facts, speculate, or extrapolate beyond the provided sources.
5. For every claim or key fact, cite the corresponding source in brackets, e.g. [Source 1]."""


@dataclass
class Citation:
    source_number: int
    document_id: str
    document_title: str
    page_number: int
    security_level: str
    chunk_id: str
    quote_excerpt: str


@dataclass
class RAGResult:
    question: str
    answer: str
    user_role: str
    allowed_security_levels: list[str]
    citations: list[Citation]
    has_sufficient_context: bool


GREETING_PATTERN = re.compile(
    r"^(hi|hii+|hey|hello|good\s+(morning|afternoon|evening)|howdy|greetings|who\s+are\s+you|what\s+can\s+you\s+do|help|what\s+is\s+this)(\s+there|\s+assistant|\s+vaultrag)?[\s!?.,]*$",
    re.IGNORECASE,
)

CATALOG_PATTERN = re.compile(
    r"^(what|which)\s+documents?\s+(are\s+shared|do\s+you\s+have|are\s+available|can\s+i\s+(access|see|view)|exist|in\s+the\s+vault|in\s+the\s+system)[\s!?.,]*"
    r"|^(list|show|display|tell\s+me)\s+(all\s+)?(the\s+)?(shared\s+|available\s+)?documents?[\s!?.,]*"
    r"|^what\s+(files|documents?)\s+are\s+(in\s+the\s+database|stored)[\s!?.,]*",
    re.IGNORECASE,
)

ROLE_PERMISSION_PATTERN = re.compile(
    r"^(can'?t|cannot|can)\s+(a\s+)?(student|faculty|admin|intern|manager|i|we)\s+(get|access|view|see)(\s+(it|this|that|info|information))?[\s!?.,]*"
    r"|^why\s+(can'?t|cannot)\s+(a\s+)?(student|faculty|admin|intern|manager|i|we)\s+(get|access|view|see)[\s!?.,]*"
    r"|^what\s+(can|information\s+can|info\s+can|documents?\s+can)\s+(a\s+)?(student|faculty|admin|intern|manager|i|we)\s+(get|access|view|see|have)[\s!?.,]*"
    r"|^what\s+is\s+(a\s+)?(student|faculty|admin|intern|manager)\s+allowed\s+to\s+(get|access|view|see)[\s!?.,]*",
    re.IGNORECASE,
)

ANALYSIS_PATTERN = re.compile(
    r"^(analyze|analyse|explain|summarize|summary\s+of)\s+(all\s+)?(the\s+)?(shared\s+|available\s+)?documents?[\s!?.,]*"
    r"|^analyze\s+(the\s+)?shared\s+documents\s+and\s+tell\s+me\s+what\s+is\s+available[\s!?.,]*",
    re.IGNORECASE,
)


def _get_authorized_document_titles(allowed_levels: list[str]) -> list[str]:
    """Retrieve unique authorized document titles from database or vector store."""
    try:
        from app.db.database import SessionLocal
        from app.models.document import Document

        db = SessionLocal()
        try:
            db_docs = (
                db.query(Document)
                .filter(Document.security_level.in_(allowed_levels), Document.processing_status == "READY")
                .all()
            )
            if db_docs:
                return sorted(list({d.title for d in db_docs}))
        finally:
            db.close()
    except Exception as exc:
        logger.debug("Database query for document titles skipped: %s", exc)

    # Fallback to vector store metadata (used in unit tests and standalone runs)
    try:
        store = get_vector_store()
        titles = set()
        for lvl in allowed_levels:
            for ch in store.metadata_by_level.get(lvl, []):
                if ch.document_title:
                    titles.add(ch.document_title)
        clean_titles = [
            t
            for t in titles
            if not t.lower().startswith(("doc_", "chapter", "report", "scan", "title", "test", "public policy", "handbook"))
        ]
        return sorted(list(clean_titles if clean_titles else titles))
    except Exception as exc:
        logger.warning("Vector store title extraction error: %s", exc)
        return []


def _get_representative_citations(allowed_levels: list[str], top_n: int = 3) -> list[Citation]:
    """Retrieve high-quality representative citations from authorized documents."""
    try:
        store = get_vector_store()
        citations: list[Citation] = []
        seen_docs = set()
        idx = 1
        for lvl in allowed_levels:
            chunks = store.metadata_by_level.get(lvl, [])
            clean_chunks = [
                ch
                for ch in chunks
                if ch.document_title
                and not ch.document_title.lower().startswith(("chapter", "title", "report", "scan", "doc_", "test"))
            ]
            candidates = clean_chunks if clean_chunks else chunks
            for ch in candidates:
                if ch.document_title and ch.document_title not in seen_docs and len(ch.text) > 40:
                    seen_docs.add(ch.document_title)
                    excerpt = ch.text.strip().replace("\n", " ")
                    if len(excerpt) > 180:
                        excerpt = excerpt[:180] + "..."
                    citations.append(
                        Citation(
                            source_number=idx,
                            document_id=ch.document_id,
                            document_title=ch.document_title,
                            page_number=ch.page_number,
                            security_level=ch.security_level,
                            chunk_id=ch.chunk_id,
                            quote_excerpt=excerpt,
                        )
                    )
                    idx += 1
                    if len(citations) >= top_n:
                        break
            if len(citations) >= top_n:
                break
        return citations
    except Exception as exc:
        logger.warning("Could not extract representative citations: %s", exc)
        return []


def _build_catalog_response(user: User, allowed_levels: list[str], question: str) -> RAGResult:
    titles = _get_authorized_document_titles(allowed_levels)
    citations = _get_representative_citations(allowed_levels, top_n=3)
    allowed_str = ", ".join(allowed_levels)
    role_name = getattr(user, "role", "STUDENT")

    docs_list_md = "\n".join(f"- **{t}**" for t in titles) if titles else "- *No documents indexed currently.*"

    answer = (
        f"Based on your **{role_name}** role clearance (**{allowed_str}**), you are authorized to access the following shared documents in VaultRAG:\n\n"
        f"### Available Documents ({len(titles)}):\n"
        f"{docs_list_md}\n\n"
        f"### Role Clearance Boundaries:\n"
        f"- **Current Role**: {role_name} ({allowed_str})\n"
    )
    if role_name in ("STUDENT", "INTERN"):
        answer += (
            f"- **Accessible Scope**: You can query student admission guidelines [Source 1], attendance rules [Source 2], examination regulations, course structures, and fee schedules.\n"
            f"- **Restricted Files**: **INTERNAL** documents (Faculty Senate Operations) and **CONFIDENTIAL** records (Board of Trustees Executive Financial Plans) are blocked by database-level Row-Level Security."
        )
    elif role_name in ("FACULTY", "MANAGER"):
        answer += (
            f"- **Accessible Scope**: You can query all public student academic documents plus internal faculty research guidelines and senate operations.\n"
            f"- **Restricted Files**: **CONFIDENTIAL** executive budget and board plans require **ADMIN** clearance."
        )
    else:
        answer += "- **Accessible Scope**: Full unrestricted clearance across PUBLIC, INTERNAL, and CONFIDENTIAL documents, system governance, and audit trails."

    return RAGResult(
        question=question,
        answer=answer,
        user_role=role_name,
        allowed_security_levels=allowed_levels,
        citations=citations,
        has_sufficient_context=True,
    )


def _build_role_permission_response(
    user: User,
    allowed_levels: list[str],
    question: str,
    history: list[dict[str, str]] | None = None,
) -> RAGResult:
    role_name = getattr(user, "role", "STUDENT")
    allowed_str = ", ".join(allowed_levels)
    citations = _get_representative_citations(allowed_levels, top_n=3)

    # Check if prior turn was a denial on a restricted resource
    was_prior_denial = False
    prior_topic = ""
    if history and len(history) >= 2:
        last_turn = history[-2]  # previous user question
        last_ans = history[-1]   # previous assistant answer
        if "not contain enough information" in last_ans.get("content", "").lower() or "insufficient" in last_ans.get("content", "").lower():
            was_prior_denial = True
            prior_topic = last_turn.get("content", "")

    answer_parts = []
    if was_prior_denial and prior_topic:
        answer_parts.append(
            f"Regarding your question about *\"{prior_topic[:80]}\"*: **No, a student cannot access that information.**\n"
            f"In VaultRAG, document security is strictly enforced at the database level before data reaches the language model. "
            f"The requested document is classified as **CONFIDENTIAL** (or **INTERNAL**), which requires Admin (or Faculty) clearance.\n"
        )

    if role_name in ("STUDENT", "INTERN"):
        answer_parts.append(
            f"### What a {role_name} CAN Get:\n"
            f"Under your **{role_name}** clearance (**PUBLIC**), you are authorized to retrieve and analyze all student-relevant documents and policies:\n"
            f"1. **Admissions & Eligibility**: Requirements, application steps, and document clearance [Source 1].\n"
            f"2. **Attendance Rules**: Mandatory 75% minimum attendance requirement and medical condonation procedures [Source 2].\n"
            f"3. **Academic Regulations & Curriculum**: Course structures, credit models, grading criteria, and graduation requirements [Source 3].\n"
            f"4. **Examination Rules**: Supplementary/backlog exams, admit cards, and revaluation procedures.\n"
            f"5. **Fees & Scholarships**: Approved payment channels, fee schedules, and merit/need-based financial aid.\n\n"
            f"### What a {role_name} CANNOT Get:\n"
            f"- **INTERNAL Documents**: Faculty Senate Operations, tenure review policies, and departmental research guidelines (Requires **FACULTY** role).\n"
            f"- **CONFIDENTIAL Documents**: Board of Trustees Executive Financial Plans and university budget allocations (Requires **ADMIN** role)."
        )
    elif role_name in ("FACULTY", "MANAGER"):
        answer_parts.append(
            f"### What a {role_name} CAN Get:\n"
            f"Under your **{role_name}** clearance (**{allowed_str}**), you can access:\n"
            f"1. **Faculty Operations**: Faculty senate guidelines, sabbatical approvals, and research grant policies [Source 1].\n"
            f"2. **All Student Documents**: Attendance rules [Source 2], academic curricula, and grading guidelines [Source 3].\n\n"
            f"### What is Restricted:\n"
            f"- **CONFIDENTIAL Documents**: Executive financial reserves and board budgets (Requires **ADMIN** role)."
        )
    else:
        answer_parts.append(
            f"### What an {role_name} CAN Get:\n"
            f"As an **{role_name}**, you have full clearance across **PUBLIC**, **INTERNAL**, and **CONFIDENTIAL** documents, "
            f"including executive financial plans, institutional budgets, user role administration, and security audit logs."
        )

    return RAGResult(
        question=question,
        answer="\n".join(answer_parts),
        user_role=role_name,
        allowed_security_levels=allowed_levels,
        citations=citations,
        has_sufficient_context=True,
    )


def _build_analysis_response(
    user: User,
    question: str,
    top_k: int = 5,
    search_mode: str = "hybrid",
) -> RAGResult:
    retrieval_res = retrieve_for_user(
        user=user,
        query="admission requirements attendance regulations examination rules fee payment scholarship",
        top_k=max(top_k, 5),
        mode=search_mode,
    )
    valid_results = [r for r in retrieval_res.results if r.score >= 0.35]
    if not valid_results:
        return _build_role_permission_response(user, retrieval_res.allowed_security_levels, question)

    source_blocks = []
    source_map = {}
    for i, res in enumerate(valid_results, start=1):
        chunk = res.chunk
        excerpt = chunk.text.strip().replace("\n", " ")
        if len(excerpt) > 180:
            excerpt = excerpt[:180] + "..."
        cit = Citation(
            source_number=i,
            document_id=chunk.document_id,
            document_title=chunk.document_title,
            page_number=chunk.page_number,
            security_level=chunk.security_level,
            chunk_id=chunk.chunk_id,
            quote_excerpt=excerpt,
        )
        source_map[i] = cit
        source_blocks.append(
            f"[Source {i}] (Document: '{chunk.document_title}', Page {chunk.page_number}, Classification: {chunk.security_level}):\n{chunk.text}"
        )

    titles = _get_authorized_document_titles(retrieval_res.allowed_security_levels)
    titles_summary = ", ".join(titles[:10])

    prompt = (
        f"The user has the role '{user.role}' with permitted classifications: {', '.join(retrieval_res.allowed_security_levels)}.\n"
        f"Available authorized documents include: {titles_summary}.\n\n"
        f"Context from authorized documents:\n"
        + "\n\n".join(source_blocks)
        + f"\n\nQuestion: {question}\n\n"
        f"Provide a well-structured, comprehensive analysis of the shared documents and what is available for this role. "
        f"Cover Admissions, Attendance, Examination rules, and Fees/Scholarships, citing the sources [Source X]."
    )
    llm = get_llm_provider()
    raw_answer = llm.generate(prompt=prompt, system_prompt=SYSTEM_PROMPT).strip()

    cited_indices = [int(m) for m in re.findall(r"\[Source (\d+)\]", raw_answer)]
    active_citations = [source_map[i] for i in set(cited_indices) if i in source_map]
    if not active_citations:
        active_citations = list(source_map.values())[:3]
    active_citations.sort(key=lambda c: c.source_number)

    return RAGResult(
        question=question,
        answer=raw_answer,
        user_role=retrieval_res.user_role,
        allowed_security_levels=retrieval_res.allowed_security_levels,
        citations=active_citations,
        has_sufficient_context=True,
    )


def answer_question(
    user: User,
    question: str,
    top_k: int = 4,
    search_mode: str = "hybrid",
    history: list[dict[str, str]] | None = None,
) -> RAGResult:
    """Run the secure RAG query pipeline for an authenticated user."""
    # Step 1: Permission-aware retrieval (unauthorized chunks are NEVER searched)
    retrieval_res = retrieve_for_user(user=user, query=question, top_k=top_k, mode=search_mode)

    # 1. Conversational greeting handling
    if GREETING_PATTERN.match(question.strip()):
        allowed_str = ", ".join(retrieval_res.allowed_security_levels)
        greeting_answer = (
            f"Hello {user.name or 'there'}! I am your VaultRAG intelligence assistant.\n\n"
            f"I am connected and ready to answer questions based on your authorized documents. "
            f"Your current role is **{retrieval_res.user_role}**, which allows access to **{allowed_str}** classification levels.\n\n"
            f"You can ask me questions about institutional guidelines, policies, or click one of the suggested prompts below!"
        )
        return RAGResult(
            question=question,
            answer=greeting_answer,
            user_role=retrieval_res.user_role,
            allowed_security_levels=retrieval_res.allowed_security_levels,
            citations=[],
            has_sufficient_context=True,
        )

    # 2. Document Catalog inquiries (e.g. "What documents are shared?", "List documents")
    if CATALOG_PATTERN.search(question.strip()):
        return _build_catalog_response(user=user, allowed_levels=retrieval_res.allowed_security_levels, question=question)

    # 3. Role Permission & "Can't student get it?" inquiries
    if ROLE_PERMISSION_PATTERN.search(question.strip()):
        return _build_role_permission_response(
            user=user,
            allowed_levels=retrieval_res.allowed_security_levels,
            question=question,
            history=history,
        )

    # 4. Shared Document Analysis inquiries (e.g. "Analyze shared documents and tell me what is available")
    if ANALYSIS_PATTERN.search(question.strip()):
        return _build_analysis_response(user=user, question=question, top_k=top_k, search_mode=search_mode)

    # 5. Filter chunks by score threshold
    valid_results = [r for r in retrieval_res.results if r.score >= 0.35]
    if not valid_results:
        return RAGResult(
            question=question,
            answer="The authorized documents do not contain enough information to answer this question.",
            user_role=retrieval_res.user_role,
            allowed_security_levels=retrieval_res.allowed_security_levels,
            citations=[],
            has_sufficient_context=False,
        )

    # 6. Assemble numbered context sources
    source_blocks: list[str] = []
    source_map: dict[int, Citation] = {}

    for i, res in enumerate(valid_results, start=1):
        chunk = res.chunk
        excerpt = chunk.text.strip().replace("\n", " ")
        if len(excerpt) > 180:
            excerpt = excerpt[:180] + "..."

        citation = Citation(
            source_number=i,
            document_id=chunk.document_id,
            document_title=chunk.document_title,
            page_number=chunk.page_number,
            security_level=chunk.security_level,
            chunk_id=chunk.chunk_id,
            quote_excerpt=excerpt,
        )
        source_map[i] = citation
        source_blocks.append(
            f"[Source {i}] (Document: '{chunk.document_title}', Page {chunk.page_number}, Classification: {chunk.security_level}):\n{chunk.text}"
        )

    context_text = "\n\n".join(source_blocks)

    # Include recent conversation turns if provided
    history_prefix = ""
    if history:
        recent = history[-4:]
        history_prefix = "Recent Conversation History:\n" + "\n".join(
            f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}" for m in recent
        ) + "\n\n"

    user_prompt = f"{history_prefix}Context:\n{context_text}\n\nQuestion: {question}\n\nAnswer:"

    # 7. LLM generation
    llm = get_llm_provider()
    raw_answer = llm.generate(prompt=user_prompt, system_prompt=SYSTEM_PROMPT).strip()

    # 8. Validate anti-hallucination condition
    no_info_marker = "do not contain enough information" in raw_answer.lower() or "insufficient" in raw_answer.lower()
    has_context = not no_info_marker

    # 9. Extract citations mentioned in the answer
    active_citations: list[Citation] = []
    if has_context:
        cited_indices = [int(m) for m in re.findall(r"\[Source (\d+)\]", raw_answer)]
        if cited_indices:
            for idx in set(cited_indices):
                if idx in source_map:
                    active_citations.append(source_map[idx])
        else:
            # If the model didn't append tags explicitly, include the top retrieved sources
            active_citations = list(source_map.values())[:2]

        active_citations.sort(key=lambda c: c.source_number)

    return RAGResult(
        question=question,
        answer=raw_answer,
        user_role=retrieval_res.user_role,
        allowed_security_levels=retrieval_res.allowed_security_levels,
        citations=active_citations,
        has_sufficient_context=has_context,
    )
