from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class SafetyStatusResponse(BaseModel):
    room_id: int
    fire_detected: bool
    gas_detected: bool
    valve_on: bool
    updated_at: datetime

    class Config:
        from_attributes = True


class RoomGasHourlyLogResponse(BaseModel):
    id: int
    gas_level: float
    recorded_at: datetime

    class Config:
        from_attributes = True


class RoomBase(BaseModel):
    space_name: str
    space_type: Optional[str] = None
    emegency_contact: Optional[str] = None


class RoomCreate(RoomBase):
    user_id: int


class RoomUpdate(BaseModel):
    space_name: Optional[str] = None
    space_type: Optional[str] = None
    emegency_contact: Optional[str] = None


class RoomResponse(RoomBase):
    id: int
    date_added: datetime
    user_id: int
    safety_status: Optional[SafetyStatusResponse] = None
    gas_logs: Optional[List[RoomGasHourlyLogResponse]] = []

    class Config:
        from_attributes = True
