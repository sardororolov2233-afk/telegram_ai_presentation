from pydantic import BaseModel, ConfigDict
from enum import Enum
from typing import Optional
from datetime import datetime

class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"

class User(BaseModel):
    id: Optional[int] = None
    telegram_id: int
    username: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    phone: Optional[str] = None
    language_code: Optional[str] = "uz"
    is_active: bool = True
    is_premium: bool = False
    role: UserRole = UserRole.USER
    balance: float = 0.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
