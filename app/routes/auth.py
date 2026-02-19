from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from jose import jwt, JWTError
from app.schemas.user import UserCreate, UserResponse, TokenResponse
from app.database import SessionLocal
from app.models.user import User
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    SECRET_KEY,
    ALGORITHM
)

router = APIRouter(prefix="/auth", tags=["Auth"])


# ---------------- DB Dependency ---------------- #

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------- Register ---------------- #

@router.post("/register", response_model=UserResponse)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(User.email == user_data.email).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    new_user = User(
        email=user_data.email,
        password=hash_password(user_data.password),
        role="user"
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


# ---------------- Login ---------------- #

@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    access_token = create_access_token(
        data={"sub": user.id, "role": user.role}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


# ---------------- Refresh Token ---------------- #

@router.post("/refresh")
def refresh_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        role = payload.get("role")

        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        new_access_token = create_access_token(
            data={"sub": user_id, "role": role}
        )

        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token"
        )
