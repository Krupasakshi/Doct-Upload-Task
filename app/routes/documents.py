from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import Optional
import shutil
import os
from datetime import datetime

from app.database import SessionLocal
from app.models.document import Document
from app.models.user import User
from app.dependencies.auth import get_current_user, admin_only

router = APIRouter(prefix="/documents", tags=["Documents"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_TYPES = ["application/pdf", "image/jpeg", "image/png"]


# ---------------- DB Dependency ---------------- #

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------- Background Task ---------------- #

def log_approval(filename: str):
    with open("approval_log.txt", "a") as f:
        f.write(f"{filename} approved at {datetime.utcnow()}\n")


# ---------------- Upload Document ---------------- #

@router.post("/upload")
def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only PDF or Image allowed")

    contents = file.file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 5MB limit")

    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as buffer:
        buffer.write(contents)

    new_doc = Document(
        filename=file.filename,
        file_path=file_path,
        status="pending",
        uploaded_by=current_user.id
    )

    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    return {
        "message": "File uploaded successfully",
        "document_id": new_doc.id,
        "status": new_doc.status
    }


# ---------------- View My Documents ---------------- #

@router.get("/my-documents")
def my_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    docs = db.query(Document).filter(
        Document.uploaded_by == current_user.id
    ).all()

    return docs


# ---------------- Admin View All Documents ---------------- #

@router.get("/all")
def all_documents(
    status_filter: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 10,
    current_admin: User = Depends(admin_only),
    db: Session = Depends(get_db)
):
    query = db.query(Document)

    if status_filter:
        query = query.filter(Document.status == status_filter)

    documents = query.offset(skip).limit(limit).all()

    return documents


# ---------------- Approve Document ---------------- #

@router.put("/approve/{doc_id}")
def approve_document(
    doc_id: str,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(admin_only),
    db: Session = Depends(get_db)
):
    document = db.query(Document).filter(Document.id == doc_id).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    document.status = "approved"
    db.commit()

    background_tasks.add_task(log_approval, document.filename)

    return {"message": "Document approved successfully"}


# ---------------- Reject Document ---------------- #

@router.put("/reject/{doc_id}")
def reject_document(
    doc_id: str,
    current_admin: User = Depends(admin_only),
    db: Session = Depends(get_db)
):
    document = db.query(Document).filter(Document.id == doc_id).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    document.status = "rejected"
    db.commit()

    return {"message": "Document rejected successfully"}
