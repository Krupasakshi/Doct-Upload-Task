from sqlalchemy import Column, String, ForeignKey, Boolean, DateTime
from app.database import Base
import uuid
from datetime import datetime

class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)

   
    status = Column(String, default="pending")

    uploaded_by = Column(String, ForeignKey("users.id"))

   
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

 
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)