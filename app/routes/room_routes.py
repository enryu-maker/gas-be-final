from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form, Query
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import SessionLocale
from app.model.room import Room, RoomSafetyStatus, RoomGasHourlyLog
from app.schemas.room_schema import (
    RoomCreate,
    RoomResponse,
    SafetyStatusResponse,
)
from app.service.user_service import decode_access_token
from app.service.notification import send_push_notification


router = APIRouter(
    prefix="/v1/room",
    tags=["V1 ROOM API"],
)


# =========================
# Dependencies
# =========================

def get_db():
    db = SessionLocale()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(decode_access_token)]


# =========================
# Room CRUD
# =========================

@router.post("/", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    db: db_dependency,
    user: user_dependency,
    space_name: str = Form(...),
    space_type: str = Form(None),
    emegency_contact: str = Form(None),
):
    new_room = Room(
        space_name=space_name,
        space_type=space_type,
        user_id=user["user_id"],
        emegency_contact=emegency_contact,
        date_added=datetime.utcnow(),
    )

    new_room.safety_status = RoomSafetyStatus(
        fire_detected=False,
        gas_detected=False,
        valve_on=True,
    )

    try:
        db.add(new_room)
        db.commit()
        db.refresh(new_room)
        return new_room
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create room: {str(e)}",
        )


@router.get("/", response_model=List[RoomResponse])
async def list_user_rooms(db: db_dependency, user: user_dependency):
    return db.query(Room).filter(Room.user_id == user["user_id"]).all()


@router.delete("/{room_id}/", status_code=status.HTTP_200_OK)
async def delete_room(room_id: int, db: db_dependency, user: user_dependency):
    room = db.query(Room).filter(
        Room.id == room_id,
        Room.user_id == user["user_id"],
    ).first()

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    db.delete(room)
    db.commit()
    return {"message": "Room deleted successfully"}


# =========================
# Room Safety Status
# =========================

@router.get("/{room_id}/status")
def get_room_status(room_id: int, db: db_dependency):
    room = db.query(Room).filter(Room.id == room_id).first()

    if not room or not room.safety_status:
        raise HTTPException(status_code=404, detail="Room not found")

    status = room.safety_status
    return {
        "room_id": room.id,
        "fire_detected": status.fire_detected,
        "gas_detected": status.gas_detected,
        "valve_on": status.valve_on,
        "updated_at": status.updated_at,
    }


@router.patch("/{room_id}/toggle-fire")
def toggle_fire(room_id: int, db: db_dependency):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if not room.safety_status:
        room.safety_status = RoomSafetyStatus(
            fire_detected=False,
            gas_detected=False,
            valve_on=True,
        )
        db.add(room.safety_status)

    status = room.safety_status
    status.fire_detected = not status.fire_detected
    db.commit()

    if status.fire_detected:
        send_push_notification(
            room.owner.fcm_token,
            "🔥 Fire Alert",
            f"Fire detected in {room.space_name}",
        )

    return {"fire_detected": status.fire_detected}


@router.patch("/{room_id}/toggle-gas")
def toggle_gas(room_id: int, db: db_dependency):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if not room.safety_status:
        room.safety_status = RoomSafetyStatus(
            fire_detected=False,
            gas_detected=False,
            valve_on=True,
        )
        db.add(room.safety_status)

    status = room.safety_status
    status.gas_detected = not status.gas_detected

    if status.gas_detected:
        status.valve_on = False
        send_push_notification(
            room.owner.fcm_token,
            "⚠️ Gas Leak Detected",
            f"Gas leak detected in {room.space_name}. Valve turned OFF.",
        )

    db.commit()
    return {
        "gas_detected": status.gas_detected,
        "valve_on": status.valve_on,
    }


@router.patch("/{room_id}/toggle-valve")
def toggle_valve(room_id: int, db: db_dependency):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room or not room.safety_status:
        raise HTTPException(status_code=404, detail="Room not found")

    status = room.safety_status
    status.valve_on = not status.valve_on
    db.commit()
    return {"valve_on": status.valve_on}


# =========================
# 🔓 OPEN API – GAS LEVEL INGEST (NO AUTH)
# =========================

@router.post("/{room_id}/gas-level", status_code=status.HTTP_201_CREATED)
def submit_gas_level(
    db: db_dependency,
    room_id: int,
    gas_level: float = Query(..., description="Gas level in PPM"),
):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # ⏱ Exact timestamp (append-only)
    now = datetime.utcnow()

    # ✅ ALWAYS INSERT
    log = RoomGasHourlyLog(
        room_id=room_id,
        gas_level=gas_level,
        recorded_at=now,
    )
    db.add(log)

    # Safety status init
    if not room.safety_status:
        room.safety_status = RoomSafetyStatus(
            fire_detected=False,
            gas_detected=False,
            valve_on=True,
        )
        db.add(room.safety_status)

    # 🚨 Threshold Logic
    if gas_level > 300:
        room.safety_status.gas_detected = True
        room.safety_status.valve_on = False

        send_push_notification(
            room.owner.fcm_token,
            "⚠️ Gas Alert",
            f"High gas level detected in {room.space_name}",
        )
    else:
        room.safety_status.gas_detected = False

    db.commit()

    return {
        "room_id": room_id,
        "gas_level": gas_level,
        "recorded_at": now,
    }


@router.get("/{room_id}/gas-levels", status_code=200)
def get_gas_levels(
    room_id: int,
    db: db_dependency,
    start_time: Optional[datetime] = Query(
        None, description="Start datetime (UTC)"
    ),
    end_time: Optional[datetime] = Query(
        None, description="End datetime (UTC)"
    ),
    limit: int = Query(
        24, ge=1, le=720, description="Number of records (default: last 24 hours)"
    ),
):
    """
    🔓 OPEN API
    Returns gas level history for a room
    """

    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    query = db.query(RoomGasHourlyLog).filter(
        RoomGasHourlyLog.room_id == room_id
    )

    if start_time:
        query = query.filter(RoomGasHourlyLog.recorded_at >= start_time)

    if end_time:
        query = query.filter(RoomGasHourlyLog.recorded_at <= end_time)

    gas_logs = (
        query.order_by(RoomGasHourlyLog.recorded_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "room_id": room_id,
        "count": len(gas_logs),
        "data": [
            {
                "gas_level": log.gas_level,
                "recorded_at": log.recorded_at,
            }
            for log in gas_logs
        ],
    }
