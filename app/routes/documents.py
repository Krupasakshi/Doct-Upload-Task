from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import Optional
import os
from datetime import datetime
from fastapi.responses import StreamingResponse

from app.database import SessionLocal
from app.models.document import Document
from app.models.user import User
from app.dependencies.auth import get_current_user, admin_only
from app.utils.email_service import send_approval_email

from app.services.cache import (
    get_cached_approved,
    set_cached_approved,
    get_cached_dashboard,
    set_cached_dashboard,
    clear_cache
)

router = APIRouter(prefix="/documents", tags=["Documents"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_FILE_SIZE = 5 * 1024 * 1024
ALLOWED_TYPES = ["application/pdf", "image/jpeg", "image/png"]


# ---------------- DB Dependency ---------------- #

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------- Upload Document ---------------- #

@router.post(
    "/upload",
    summary="Upload document",
    description="Upload PDF or image (max 5MB)"
)
def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only PDF/JPG/PNG allowed")

    contents = file.file.read()

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Max size 5MB exceeded")

    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as f:
        f.write(contents)

    doc = Document(
        filename=file.filename,
        file_path=file_path,
        status="pending",
        uploaded_by=current_user.id
    )

    db.add(doc)
    db.commit()
    db.refresh(doc)

    return {"message": "Uploaded", "id": doc.id}


# ---------------- My Documents ---------------- #

@router.get(
    "/my-documents",
    summary="Get my documents"
)
def my_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    docs = db.query(Document).filter(
        Document.uploaded_by == current_user.id,
        Document.is_deleted == False
    ).all()

    return [{"id": d.id, "file": d.filename, "status": d.status} for d in docs]


# ---------------- Admin All Documents ---------------- #

@router.get("/all", summary="Admin: View all documents")
def all_documents(
    status_filter: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 10,
    current_admin: User = Depends(admin_only),
    db: Session = Depends(get_db)
):
    query = db.query(Document).filter(Document.is_deleted == False)

    if status_filter:
        query = query.filter(Document.status == status_filter)

    docs = query.offset(skip).limit(limit).all()

    return [{"id": d.id, "file": d.filename, "status": d.status} for d in docs]


# ---------------- Approve ---------------- #

@router.put("/approve/{doc_id}", summary="Approve document")
def approve_document(
    doc_id: int,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(admin_only),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == doc_id).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Not found")

    doc.status = "approved"
    db.commit()

    user = db.query(User).filter(User.id == doc.uploaded_by).first()

    background_tasks.add_task(
        send_approval_email,
        user.email,
        doc.filename
    )

    clear_cache()

    return {"message": "Approved"}


# ---------------- Reject ---------------- #

@router.put("/reject/{doc_id}", summary="Reject document")
def reject_document(
    doc_id: int,
    current_admin: User = Depends(admin_only),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == doc_id).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Not found")

    doc.status = "rejected"
    db.commit()

    clear_cache()

    return {"message": "Rejected"}


# ---------------- Download ---------------- #

@router.get("/{id}/download", summary="Download document")
def download_document(id: int, db: Session = Depends(get_db)):

    doc = db.query(Document).filter(
        Document.id == id,
        Document.is_deleted == False
    ).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Not found")

    if doc.status != "approved":
        raise HTTPException(status_code=403, detail="Not approved")

    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="File missing")

    file = open(doc.file_path, "rb")

    return StreamingResponse(
        file,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={doc.filename}"}
    )


# ---------------- Soft Delete ---------------- #

@router.delete("/{id}", summary="Soft delete document")
def soft_delete(
    id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == id).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Not found")

    doc.is_deleted = True
    doc.deleted_at = datetime.utcnow()

    db.commit()
    clear_cache()

    return {"message": "Deleted"}


# ---------------- Approved (Cache) ---------------- #

@router.get("/approved", summary="Get approved docs")
def get_approved(db: Session = Depends(get_db)):

    cached = get_cached_approved()
    if cached:
        return cached

    docs = db.query(Document).filter(
        Document.status == "approved",
        Document.is_deleted == False
    ).all()

    result = [{"id": d.id, "file": d.filename} for d in docs]

    set_cached_approved(result)
    return result


# ---------------- Dashboard ---------------- #

@router.get("/dashboard", summary="Dashboard stats")
def dashboard(db: Session = Depends(get_db)):

    cached = get_cached_dashboard()
    if cached:
        return cached

    data = {
        "total": db.query(Document).count(),
        "approved": db.query(Document).filter(Document.status == "approved").count(),
        "rejected": db.query(Document).filter(Document.status == "rejected").count()
    }

    set_cached_dashboard(data)
    return data


# ---------------- Update Status ---------------- #

@router.put("/status/{doc_id}", summary="Update status")
def update_status(doc_id: int, status: str, db: Session = Depends(get_db)):

    doc = db.query(Document).filter(Document.id == doc_id).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Not found")

    doc.status = status
    db.commit()

    clear_cache()

    return {"message": "Updated"}