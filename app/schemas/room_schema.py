from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class SafetyStatusResponse(BaseModel):
    room_id: int
    fire_detected: bool
    gas_detected: bool
    valve_on: bool

    class Config:
        orm_mode = True


class RoomBase(BaseModel):
    space_name: str
    space_type: Optional[str] = None,
    emegency_contact: Optional[str] = None


class RoomCreate(RoomBase):
    user_id: int  # Link room to user


class RoomResponse(RoomBase):
    id: int
    date_added: datetime
    user_id: int
    safety_status: SafetyStatusResponse | None

    class Config:
        from_attributes = True
