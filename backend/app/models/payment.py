from pydantic import BaseModel, ConfigDict
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime

class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"

class PaymentProvider(str, Enum):
    PAYME = "payme"
    CLICK = "click"

class Payment(BaseModel):
    id: Optional[int] = None
    user_id: int
    amount: float
    currency: str = "UZS"
    provider: PaymentProvider
    status: PaymentStatus = PaymentStatus.PENDING
    external_id: Optional[str] = None
    description: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
