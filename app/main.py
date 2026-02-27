from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.database import Base, engine, SessionLocal
from app.routes import auth, documents
from app.models.user import User
from app.core.security import hash_password



Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(auth.router)
app.include_router(documents.router)



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





