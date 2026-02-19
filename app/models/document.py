from sqlalchemy import Column, String, ForeignKey
from app.database import Base
import uuid

class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String)
    file_path = Column(String)
    status = Column(String, default="pending")
    uploaded_by = Column(String, ForeignKey("users.id"))
