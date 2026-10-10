"""Automated seed script for VaultRAG hackathon demo.

Provisions demo accounts, tiered multi-page sample documents,
computes vector embeddings, indexes FAISS partitioned stores,
and seeds initial audit events for a complete turn-key presentation.

Users Created:
- student@example.com / StudentPass123! (STUDENT: PUBLIC only)
- faculty@example.com / FacultyPass123! (FACULTY: PUBLIC + INTERNAL)
- admin@example.com   / AdminPass123!   (ADMIN: PUBLIC + INTERNAL + CONFIDENTIAL)

Documents Ingested:
- Undergraduate Student Handbook 2026 (PUBLIC)
- Faculty Senate Operations & Research Guidelines (INTERNAL)
- Board of Trustees Executive Financial Plan 2026 (CONFIDENTIAL)
"""

from io import BytesIO
import logging
from pathlib import Path
import sys

# Ensure backend root is in python path
backend_root = Path(__file__).resolve().parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import pymupdf
from sqlalchemy import select

from app.core.config import get_settings
from app.db.database import Base, SessionLocal, engine
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_extraction import DocumentExtraction
from app.models.user import Role, User
from app.services.auth_service import hash_password, normalize_email
from app.services.chunking_service import chunk_pages
from app.services.document_extraction_service import extract_document
from app.services.file_storage_service import store_upload
from app.services.vector_store_service import get_vector_store
from app.services.audit_service import (
    ACTION_ACCESS_DENIED,
    ACTION_ADMIN_ROLE_CHANGE,
    ACTION_DOCUMENT_QUERY,
    ACTION_DOCUMENT_UPLOAD,
    ACTION_LOGIN_SUCCESS,
    STATUS_DENIED,
    STATUS_SUCCESS,
    record_audit_event,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("demo_seed")


DEMO_USERS = [
    {
        "name": "Sarah Connor (Student)",
        "email": "student@example.com",
        "password": "StudentPass123!",
        "role": Role.STUDENT,
    },
    {
        "name": "Dr. Alan Grant (Faculty)",
        "email": "faculty@example.com",
        "password": "FacultyPass123!",
        "role": Role.FACULTY,
    },
    {
        "name": "Director Ellen Ripley (Admin)",
        "email": "admin@example.com",
        "password": "AdminPass123!",
        "role": Role.ADMIN,
    },
]


DEMO_DOCUMENTS = [
    {
        "title": "Undergraduate Student Handbook 2026",
        "filename": "student-handbook-2026.pdf",
        "security_level": "PUBLIC",
        "uploader_email": "admin@example.com",
        "pages": [
            (
                "UNDERGRADUATE STUDENT HANDBOOK 2026\n"
                "SECTION 1: ACADEMIC REGULATIONS & ATTENDANCE\n\n"
                "1.1 Attendance Requirements:\n"
                "Undergraduate students enrolled in all degree programs must maintain a minimum of 80% physical "
                "or verified virtual attendance across all scheduled lectures, seminars, and laboratory sessions. "
                "Students failing to maintain the mandatory 80% attendance threshold will be ineligible to sit for "
                "final semester examinations without an official medical or extenuating circumstance waiver.\n\n"
                "1.2 Grading and Academic Standing:\n"
                "Undergraduate GPA is calculated on a 4.0 scale. A cumulative GPA below 2.0 places the student on "
                "academic probation for the subsequent semester. Dean's List honors require a semester GPA of 3.75 "
                "with at least 15 graded credits."
            ),
            (
                "UNDERGRADUATE STUDENT HANDBOOK 2026\n"
                "SECTION 2: CAMPUS FACILITIES & LIBRARY OPERATIONS\n\n"
                "2.1 Central University Library:\n"
                "The university library operates standard academic hours from 8:00 AM to 12:00 Midnight, Monday through "
                "Saturday. During midterm review weeks and final examination periods, the facility remains open 24 hours "
                "a day with active security presence, unrestricted study commons, private collaborative study cubicles, "
                "and complimentary tutoring support.\n\n"
                "2.2 Student Recreation and Dining:\n"
                "The Campus Recreation Center is open daily from 6:00 AM to 10:00 PM. All meal plan balances roll over "
                "from Fall to Spring semester within the same academic year."
            ),
            (
                "UNDERGRADUATE STUDENT HANDBOOK 2026\n"
                "SECTION 3: PARKING, HEALTH & WELLNESS SERVICES\n\n"
                "3.1 Parking Permits:\n"
                "Standard undergraduate campus parking permits cost $120 per academic semester and allow parking "
                "in designated Blue and Green campus commuter lots. Overnight parking requires a Gold permit ($180).\n\n"
                "3.2 Health and Counseling Center:\n"
                "The Student Health Center offers outpatient clinical care, preventative vaccinations, and free walk-in "
                "mental health counseling. A 24/7 student crisis telehealth helpline is accessible to all enrolled students "
                "via extension 4357 (HELP)."
            ),
        ],
    },
    {
        "title": "Faculty Senate Operations & Research Guidelines",
        "filename": "faculty-senate-guidelines.pdf",
        "security_level": "INTERNAL",
        "uploader_email": "faculty@example.com",
        "pages": [
            (
                "FACULTY SENATE OPERATIONS MANUAL & GUIDELINES\n"
                "CONFIDENTIAL TO FACULTY & STAFF - INTERNAL USE ONLY\n\n"
                "SECTION 1: SABBATICAL LEAVE POLICY\n"
                "1.1 Sabbatical Eligibility:\n"
                "Tenured faculty members are eligible to apply for academic sabbatical leave after completing six consecutive "
                "semesters of full-time teaching and research service. Sabbatical leave may be taken as either one semester "
                "at 100% regular base salary, or one full academic year at 75% regular salary.\n\n"
                "1.2 Application Procedures:\n"
                "Sabbatical applications must include a detailed scholarly research proposal and be submitted to the "
                "Department Chair at least eight months prior to the proposed leave semester. Formal endorsement from "
                "both the Department Chair and the Academic Dean is mandatory."
            ),
            (
                "FACULTY SENATE OPERATIONS MANUAL & GUIDELINES\n"
                "CONFIDENTIAL TO FACULTY & STAFF - INTERNAL USE ONLY\n\n"
                "SECTION 2: COMPETITIVE RESEARCH GRANT AWARDS\n"
                "2.1 Internal Grant Funding:\n"
                "The University Research Council awards competitive internal research grants of up to $75,000 per academic "
                "cycle for faculty-led investigations. Allowable expenditures include specialized laboratory equipment, "
                "graduate research assistant stipends, computational cloud credits, and travel to peer-reviewed conferences.\n\n"
                "2.2 Overhead and Indirect Costs:\n"
                "Internal grant awards are exempt from standard facilities and administrative overhead deductions."
            ),
            (
                "FACULTY SENATE OPERATIONS MANUAL & GUIDELINES\n"
                "CONFIDENTIAL TO FACULTY & STAFF - INTERNAL USE ONLY\n\n"
                "SECTION 3: FINAL GRADE SUBMISSIONS & COMMITTEE SERVICE\n"
                "3.1 Grade Submission Deadlines:\n"
                "All faculty instructors must submit final course letter grades through the faculty web portal within "
                "exactly 72 hours of the conclusion of their course final examination. Late grade submissions cause "
                "immediate graduation clearance disruptions and require written explanation to the Provost.\n\n"
                "3.2 Departmental Committee Service:\n"
                "Full-time faculty members are expected to contribute at least four hours weekly to departmental "
                "standing committees and curriculum evaluation panels."
            ),
        ],
    },
    {
        "title": "Board of Trustees Executive Financial Plan 2026",
        "filename": "board-executive-financial-plan.pdf",
        "security_level": "CONFIDENTIAL",
        "uploader_email": "admin@example.com",
        "pages": [
            (
                "BOARD OF TRUSTEES EXECUTIVE FINANCIAL PLAN 2026\n"
                "SECURITY CLASSIFICATION: CONFIDENTIAL - RESTRICTED ACCESS\n\n"
                "SECTION 1: INSTITUTIONAL EMERGENCY RESERVE ENDOWMENT\n"
                "1.1 Reserve Fund Allocation:\n"
                "The institutional emergency reserve fund endowment maintains a designated liquidity balance of "
                "forty-two point five million dollars ($42.5M) for campus expansion, high-security facilities, "
                "and crisis contingency stabilization for fiscal year 2026.\n\n"
                "1.2 Investment Strategy & Oversight:\n"
                "The investment portfolio is managed under the conservative fiduciary oversight of the Board Finance "
                "Subcommittee, maintaining 60% fixed income treasuries and 40% diversified blue-chip assets."
            ),
            (
                "BOARD OF TRUSTEES EXECUTIVE FINANCIAL PLAN 2026\n"
                "SECURITY CLASSIFICATION: CONFIDENTIAL - RESTRICTED ACCESS\n\n"
                "SECTION 2: EXECUTIVE COMPENSATION & RETENTION POOL\n"
                "2.1 Senior Leadership Incentive Compensation:\n"
                "The confidential executive leadership retention pool is capped at $4.8 million for the 2026-2028 "
                "governance triennium. Disbursements are strictly tied to institutional accreditation outcomes, "
                "endowment growth targets, and national research ranking metrics.\n\n"
                "2.2 Key Personnel Succession Planning:\n"
                "Confidential leadership succession protocols have been established for the University President, "
                "Chief Financial Officer, and Vice Chancellor of Research."
            ),
            (
                "BOARD OF TRUSTEES EXECUTIVE FINANCIAL PLAN 2026\n"
                "SECURITY CLASSIFICATION: CONFIDENTIAL - RESTRICTED ACCESS\n\n"
                "SECTION 3: PROJECT SILICON ANNEX - PROPERTY ACQUISITION\n"
                "3.1 Strategic Downtown Land Purchase:\n"
                "Under 'Project Silicon Annex', the university is executing a confidential option to purchase "
                "commercial parcel 104-B in the downtown innovation district for eighteen million dollars ($18.0M).\n\n"
                "3.2 Planned Facility Purpose:\n"
                "The site will house the future Institute for Artificial Intelligence and Quantum Systems, "
                "co-financed by private philanthropic donations and municipal technology innovation grants."
            ),
        ],
    },
]


def create_pdf_bytes(pages: list[str]) -> bytes:
    """Generate a clean, multi-page PDF document using PyMuPDF."""
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page(width=595, height=842)  # Standard A4 size
        # Margin: left 50, top 50, right 545, bottom 792
        page.insert_textbox(pymupdf.Rect(50, 50, 545, 792), text, fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def seed_database():
    """Seed users, documents, vector embeddings, and audit logs."""
    settings = get_settings()
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 1. Seed or update Users
        logger.info("--- Seeding Demo Users ---")
        user_records: dict[str, User] = {}
        for user_data in DEMO_USERS:
            email_norm = normalize_email(user_data["email"])
            existing_user = db.scalar(select(User).where(User.email == email_norm))
            if existing_user:
                logger.info("User '%s' (%s) already exists.", existing_user.email, existing_user.role)
                existing_user.name = user_data["name"]
                existing_user.role = user_data["role"].value
                existing_user.password_hash = hash_password(user_data["password"])
                existing_user.is_active = True
                db.commit()
                db.refresh(existing_user)
                user_records[email_norm] = existing_user
            else:
                new_user = User(
                    name=user_data["name"],
                    email=email_norm,
                    password_hash=hash_password(user_data["password"]),
                    role=user_data["role"].value,
                    is_active=True,
                )
                db.add(new_user)
                db.commit()
                db.refresh(new_user)
                logger.info("Created user: %s (Role: %s)", new_user.email, new_user.role)
                user_records[email_norm] = new_user

        # 2. Seed Documents into database, filesystem, and vector store
        logger.info("--- Seeding Demo Documents & FAISS Embeddings ---")
        vector_store = get_vector_store()
        upload_dir = settings.upload_dir
        upload_dir.mkdir(parents=True, exist_ok=True)

        for doc_def in DEMO_DOCUMENTS:
            existing_doc = db.scalar(select(Document).where(Document.title == doc_def["title"]))
            if existing_doc:
                logger.info("Document '%s' already exists (ID: %s).", existing_doc.title, existing_doc.id)
                continue

            uploader = user_records[normalize_email(doc_def["uploader_email"])]
            pdf_bytes = create_pdf_bytes(doc_def["pages"])
            stream = BytesIO(pdf_bytes)

            stored = store_upload(
                stream,
                original_filename=doc_def["filename"],
                upload_dir=upload_dir,
                max_size_bytes=settings.max_upload_size_bytes,
            )

            extraction_result = extract_document(stored.path, source_type=stored.source_type)
            if not extraction_result or not extraction_result.pages:
                logger.error("Failed to extract pages from %s", doc_def["title"])
                continue

            doc_record = Document(
                title=doc_def["title"],
                original_filename=doc_def["filename"],
                stored_filename=stored.stored_filename,
                source_type=stored.source_type,
                security_level=doc_def["security_level"],
                processing_status="READY",
                file_size_bytes=stored.file_size_bytes,
                sha256=stored.sha256,
                uploaded_by=uploader.id,
            )
            db.add(doc_record)
            db.flush()

            chunks = chunk_pages(
                extraction_result.pages,
                document_id=doc_record.id,
                document_title=doc_record.title,
                source_type=doc_record.source_type,
                security_level=doc_record.security_level,
                uploaded_by=doc_record.uploaded_by,
            )

            db.add(
                DocumentExtraction(
                    document_id=doc_record.id,
                    extracted_text=extraction_result.extracted_text,
                    pages=[{"page_number": p.page_number, "text": p.text} for p in extraction_result.pages],
                    page_count=extraction_result.page_count,
                    extraction_method=extraction_result.extraction_method,
                    error_code=None,
                )
            )

            for chunk in chunks:
                db.add(
                    DocumentChunk(
                        id=chunk.id,
                        document_id=chunk.document_id,
                        chunk_index=chunk.chunk_index,
                        page_number=chunk.page_number,
                        text=chunk.text,
                        document_title=chunk.document_title,
                        source_type=chunk.source_type,
                        security_level=chunk.security_level,
                        uploaded_by=chunk.uploaded_by,
                    )
                )

            db.commit()
            db.refresh(doc_record)

            # Index into FAISS partitioned store
            vector_store.add_chunks(chunks)
            logger.info(
                "Indexed '%s' [%s] (%d pages, %d chunks) into FAISS sub-index.",
                doc_record.title,
                doc_record.security_level,
                extraction_result.page_count,
                len(chunks),
            )

            record_audit_event(
                db=db,
                action=ACTION_DOCUMENT_UPLOAD,
                status=STATUS_SUCCESS,
                user=uploader,
                resource_type="DOCUMENT",
                resource_id=doc_record.id,
                details=f"Uploaded '{doc_record.title}' ({doc_record.security_level})",
            )

        # 3. Seed Realistic Audit Trail Events
        logger.info("--- Seeding Initial Audit Trail ---")
        student_user = user_records["student@example.com"]
        faculty_user = user_records["faculty@example.com"]
        admin_user = user_records["admin@example.com"]

        sample_events = [
            (ACTION_LOGIN_SUCCESS, STATUS_SUCCESS, admin_user, "Admin console session authenticated"),
            (ACTION_LOGIN_SUCCESS, STATUS_SUCCESS, faculty_user, "Faculty web dashboard login"),
            (ACTION_LOGIN_SUCCESS, STATUS_SUCCESS, student_user, "Student portal login"),
            (
                ACTION_DOCUMENT_QUERY,
                STATUS_SUCCESS,
                student_user,
                "Query: 'What are the campus library hours during final exams?' returned 1 citation",
            ),
            (
                ACTION_DOCUMENT_QUERY,
                STATUS_SUCCESS,
                faculty_user,
                "Query: 'What is the maximum internal competitive research grant award?' returned 1 citation",
            ),
            (
                ACTION_ACCESS_DENIED,
                STATUS_DENIED,
                student_user,
                "Query: 'What is the emergency reserve endowment fund balance?' failed closed (no authorized context)",
            ),
            (
                ACTION_DOCUMENT_QUERY,
                STATUS_SUCCESS,
                admin_user,
                "Query: 'What is the purchase price for Project Silicon Annex?' returned 1 citation",
            ),
            (
                ACTION_ADMIN_ROLE_CHANGE,
                STATUS_SUCCESS,
                admin_user,
                "Audited and confirmed security clearance levels for campus faculty senate",
            ),
        ]

        for action, status, user, details in sample_events:
            record_audit_event(
                db=db,
                action=action,
                status=status,
                user=user,
                details=details,
            )

        db.commit()
        logger.info("Successfully seeded audit events.")

        # Summary telemetry printout
        logger.info("==================================================")
        logger.info("           VAULTRAG DEMO SEED COMPLETED!          ")
        logger.info("==================================================")
        logger.info("Demo User Logins:")
        logger.info("  1. Student: student@example.com / StudentPass123! [PUBLIC only]")
        logger.info("  2. Faculty: faculty@example.com / FacultyPass123! [PUBLIC + INTERNAL]")
        logger.info("  3. Admin:   admin@example.com   / AdminPass123!   [FULL ACCESS]")
        logger.info("Vector Index Partition Counts:")
        for lvl in ("PUBLIC", "INTERNAL", "CONFIDENTIAL"):
            logger.info("  - Index [%s]: %d vectors", lvl, vector_store.indices[lvl].ntotal)
        logger.info("==================================================")

    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
