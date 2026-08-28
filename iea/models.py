from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class Observation(BaseModel):
    provider: str
    series_id: str
    date: datetime
    value: Optional[float]
    retrieved_at: datetime
    realtime_start: Optional[datetime] = None
    realtime_end: Optional[datetime] = None
    quality: float = Field(ge=0, le=100)
    status: str = 'OK'
