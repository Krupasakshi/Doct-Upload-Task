from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_path: str
    status: str
    uploaded_by: int
    created_at: datetime
    is_deleted: Optional[bool] = False
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True