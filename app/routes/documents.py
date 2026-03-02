from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import Optional
import shutil
import os
from datetime import datetime
from app.utils.email_service import send_approval_email
from app.database import SessionLocal
from app.models.document import Document
from app.models.user import User
from fastapi.responses import StreamingResponse

from app.dependencies.auth import get_current_user, admin_only

from app.services.storage import LocalStorageService
from app.services.cache import (
    get_cached_approved,
    set_cached_approved,
    get_cached_dashboard,
    set_cached_dashboard,
    clear_cache
)

router = APIRouter()
storage = LocalStorageService()

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

    user = db.query(User).filter(User.id == document.uploaded_by).first()

   
    background_tasks.add_task(
        send_approval_email,
        user.email,
        document.filename
    )

    return {"message": "Document approved & email sent"}
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

#---------------------Download---------------------#

@router.get("/{id}/download")
def download_document(id: str, db: Session = Depends(get_db)):

    
    doc = db.query(Document).filter(
        Document.id == id,
        Document.is_deleted == False
    ).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

   
    if doc.status != "approved":
        raise HTTPException(
            status_code=403,
            detail="Document not approved"
        )

    
    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="File not found")

    file = open(doc.file_path, "rb")


    return StreamingResponse(
        file,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={doc.filename}"
        }
    )
#----------------------------Delete----------------------------#

@router.delete("/{id}")
def soft_delete_document(
    id: str,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    doc = db.query(Document).filter(Document.id == id).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

   
    doc.is_deleted = True
    doc.deleted_at = datetime.utcnow()

    db.commit()

    return {"message": "Document soft deleted"}

#=============================================#

@router.post("/upload")
def upload_file(file: UploadFile, db: Session = Depends(get_db)):

    filename = storage.upload(file, file.filename)
    file_url = storage.get_url(filename)

    doc = Document(
        filename=filename,
        url=file_url,
        status="pending"
    )

    db.add(doc)
    db.commit()

    return {"message": "uploaded", "url": file_url}


#============================================#
@router.get("/approved")
def get_approved(db: Session = Depends(get_db)):

    cached = get_cached_approved()
    if cached:
        return cached

    docs = db.query(Document).filter(Document.status == "approved").all()

    result = [{"id": d.id, "file": d.filename} for d in docs]

    set_cached_approved(result)

    return result


#=========================================#
@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):

    cached = get_cached_dashboard()
    if cached:
        return cached

    total = db.query(Document).count()
    approved = db.query(Document).filter(Document.status == "approved").count()
    rejected = db.query(Document).filter(Document.status == "rejected").count()

    data = {
        "total": total,
        "approved": approved,
        "rejected": rejected
    }

    set_cached_dashboard(data)

    return data


#============================================#
@router.put("/status/{doc_id}")
def update_status(doc_id: int, status: str, db: Session = Depends(get_db)):

    doc = db.query(Document).get(doc_id)
    doc.status = status
    db.commit()


    clear_cache()

    return {"message": "updated"}