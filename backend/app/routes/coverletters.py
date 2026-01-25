from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.coverletter import CoverLetter
from app.routes.auth import get_current_user
from app.schemas.coverletter import (
    GenerateCoverLetterRequest, CoverLetterOut, UpdateEditedFinalRequest
)
from app.services.resume_extract import extract_text_from_pdf, extract_text_from_docx
from app.services.openai_client import generate_cover_letter
from app.services.pdf_export import render_pdf_bytes
from app.main import limiter

router = APIRouter(prefix="/coverletters", tags=["coverletters"])

ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5MB

def require_owner(db: Session, user_id: int, cover_id: int) -> CoverLetter:
    cl = db.query(CoverLetter).filter(CoverLetter.id == cover_id, CoverLetter.user_id == user_id).first()
    if not cl:
        raise HTTPException(status_code=404, detail="Not found")
    return cl

@router.get("", response_model=list[CoverLetterOut])
@limiter.limit("60/minute")
def list_coverletters(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(db, request.headers.get("Authorization"))
    items = (
        db.query(CoverLetter)
        .filter(CoverLetter.user_id == user.id)
        .order_by(CoverLetter.created_at.desc())
        .all()
    )
    return items

@router.get("/{cover_id}", response_model=CoverLetterOut)
@limiter.limit("60/minute")
def get_coverletter(cover_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(db, request.headers.get("Authorization"))
    return require_owner(db, user.id, cover_id)

@router.post("/generate", response_model=CoverLetterOut)
@limiter.limit("3/minute")   # VERY important: cost control + abuse prevention
async def generate(
    request: Request,
    data: GenerateCoverLetterRequest,
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, request.headers.get("Authorization"))

    if resume.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Resume must be a PDF or DOCX")

    raw = await resume.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Resume file too large (max 5MB)")

    kind = ALLOWED_TYPES[resume.content_type]
    if kind == "pdf":
        resume_text = extract_text_from_pdf(raw)
    else:
        resume_text = extract_text_from_docx(raw)

    if not resume_text or len(resume_text) < 50:
        raise HTTPException(status_code=400, detail="Could not extract usable text from resume")

    payload = {
        "input_full_name": data.input_full_name,
        "job_title": data.job_title,
        "company_name": data.company_name,
        "tone": data.tone,
        "job_description": data.job_description,
        "resume_text": resume_text,
        "extra_notes": data.extra_notes,
    }

    ai_draft = generate_cover_letter(payload)

    cl = CoverLetter(
        user_id=user.id,
        input_full_name=data.input_full_name,
        job_title=data.job_title,
        company_name=data.company_name,
        tone=data.tone,
        job_description=data.job_description,
        extra_notes=data.extra_notes,
        resume_text=resume_text,
        ai_draft=ai_draft,
        edited_final=None,
    )
    db.add(cl)
    db.commit()
    db.refresh(cl)
    return cl

@router.put("/{cover_id}/edited", response_model=CoverLetterOut)
@limiter.limit("60/minute")
def update_edited_final(cover_id: int, body: UpdateEditedFinalRequest, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(db, request.headers.get("Authorization"))
    cl = require_owner(db, user.id, cover_id)
    cl.edited_final = body.edited_final
    db.add(cl)
    db.commit()
    db.refresh(cl)
    return cl

@router.delete("/{cover_id}")
@limiter.limit("30/minute")
def delete_coverletter(cover_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(db, request.headers.get("Authorization"))
    cl = require_owner(db, user.id, cover_id)
    db.delete(cl)
    db.commit()
    return {"ok": True}

@router.get("/{cover_id}/pdf")
@limiter.limit("20/minute")  # prevents hammering PDF renderer
def download_pdf(cover_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(db, request.headers.get("Authorization"))
    cl = require_owner(db, user.id, cover_id)

    content = cl.edited_final or cl.ai_draft
    title = f"{cl.input_full_name} — Cover Letter"
    pdf_bytes = render_pdf_bytes(title, content)

    filename = f"Cover_Letter_{cl.company_name}_{cl.job_title}.pdf".replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
