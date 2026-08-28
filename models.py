from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class Observation(BaseModel):
    provider: str
    series_id: str
    date: datetime
    value: Optional[float]
    retrieved_at: datetime
    unit: Optional[str] = None
    frequency: Optional[str] = None
    quality: float = Field(default=0, ge=0, le=100)
    status: str = 'OK'
