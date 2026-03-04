from fastapi import FastAPI, Request, Depends
from sqlalchemy.orm import Session

from app.database import Base, engine, SessionLocal
from app.routes import auth, documents
from app.models.user import User
from app.core.logger import logger
from app.database import get_db
from app.core.security import hash_password
import time
from sqlalchemy import text



Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Document Management API",
    description="This API allows users to upload, approve, reject and download documents with authentication.",
    version="1.0.0"
)

app.include_router(auth.router)
app.include_router(documents.router, prefix="/api/v1/docs")



@app.on_event("startup")
def create_admin():
    db: Session = SessionLocal()

    admin_email = "admin@gmail.com"
    admin_password = "admin123"

    existing_admin = db.query(User).filter(User.email == admin_email).first()

    if not existing_admin:
        admin_user = User(
            email=admin_email,
            password=hash_password(admin_password),
            role="admin"
        )
        db.add(admin_user)
        db.commit()
        print("Admin created successfully")
    else:
        print("Admin already exists")

    db.close()


#=======================================#

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()

    response = await call_next(request)

    duration = time.time() - start

    logger.info(f"{request.method} {request.url.path} {response.status_code} {duration:.4f}s")

    return response

start_time = time.time()


#=====================================#
@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute("SELECT 1")
        db_status = "connected"
    except:
        db_status = "failed"

    uptime = time.time() - start_time

    return {
        "status": "running",
        "database": db_status,
        "uptime": round(uptime, 2)
    }


