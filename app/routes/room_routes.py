from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import SessionLocale
from app.model.room import Room, RoomSafetyStatus
from app.schemas.room_schema import RoomCreate, RoomResponse, SafetyStatusResponse
from app.service.user_service import decode_access_token
from app.service.notification import send_push_notification

router = APIRouter(
    prefix="/v1/room",
    tags=["V1 ROOM API"],
)


# Dependency
def get_db():
    db = SessionLocale()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(decode_access_token)]


@router.post("/", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    db: db_dependency,
    user: user_dependency,
    space_name: str = Form(...),
    space_type: str = Form(None),
    emegency_contact: str = Form(None)
):
    """Create a room for the logged-in user and initialize safety status"""

    print("Creating room for user:", user["user_id"])

    new_room = Room(
        space_name=space_name,
        space_type=space_type,
        user_id=user["user_id"],
        emegency_contact=emegency_contact,
        date_added=datetime.utcnow()
    )

    # ✅ Create default safety status
    new_room.safety_status = RoomSafetyStatus(
        fire_detected=False,
        gas_detected=False,
        valve_on=True
    )

    try:
        db.add(new_room)
        db.commit()
        db.refresh(new_room)
        return new_room

    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create room: {str(e)}"
        )


@router.get("/", response_model=List[RoomResponse])
async def list_user_rooms(db: db_dependency, user: user_dependency):
    """List all rooms created by the logged-in user"""
    rooms = db.query(Room).filter(Room.user_id == user["user_id"]).all()
    return rooms


@router.delete("/{room_id}/", status_code=status.HTTP_200_OK)
async def delete_room(room_id: int, db: db_dependency, user: user_dependency):
    """Delete a specific room (only if owned by the user)"""
    room = db.query(Room).filter(
        Room.id == room_id, Room.user_id == user["user_id"]).first()

    if not room:
        raise HTTPException(
            status_code=404, detail="Room not found or not yours.")

    db.delete(room)
    db.commit()
    return {"message": "Room deleted successfully."}


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
        "updated_at": status.updated_at
    }


@router.patch("/{room_id}/toggle-fire")
def toggle_fire(room_id: int, db: db_dependency):

    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # ✅ Create safety status if missing
    if not room.safety_status:
        room.safety_status = RoomSafetyStatus(
            fire_detected=False,
            gas_detected=False,
            valve_on=True
        )
        db.add(room.safety_status)
        db.commit()
        db.refresh(room)

    status = room.safety_status

    # 🔁 Toggle fire
    status.fire_detected = not status.fire_detected
    db.commit()

    # 🔔 Notify only when fire = TRUE
    if status.fire_detected:
        send_push_notification(
            room.owner.fcm_token,
            "🔥 Fire Alert",
            f"Fire detected in {room.space_name}"
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
            valve_on=True
        )
        db.add(room.safety_status)
        db.commit()
        db.refresh(room)

    status = room.safety_status

    # 🔁 Toggle gas
    status.gas_detected = not status.gas_detected

    if status.gas_detected:
        status.valve_on = False

        send_push_notification(
            room.owner.fcm_token,
            "⚠️ Gas Leak Detected",
            f"Gas leak detected in {room.space_name}. Valve turned OFF."
        )

    db.commit()

    return {
        "gas_detected": status.gas_detected,
        "valve_on": status.valve_on
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
