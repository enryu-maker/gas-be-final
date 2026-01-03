from app.database import Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, UniqueConstraint, Float
from sqlalchemy.orm import relationship
import datetime


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    space_name = Column(String)
    space_type = Column(String)
    emegency_contact = Column(String)
    date_added = Column(DateTime, default=datetime.datetime.utcnow)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    owner = relationship("User", back_populates="rooms")
    safety_status = relationship(
        "RoomSafetyStatus",
        back_populates="room",
        uselist=False,
        cascade="all, delete"
    )
    gas_logs = relationship(
        "RoomGasHourlyLog",
        back_populates="room",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class RoomSafetyStatus(Base):
    __tablename__ = "room_safety_status"

    id = Column(Integer, primary_key=True, index=True)

    fire_detected = Column(Boolean, default=False)
    gas_detected = Column(Boolean, default=False)
    valve_on = Column(Boolean, default=True)

    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)

    room_id = Column(Integer, ForeignKey("rooms.id"),
                     unique=True, nullable=False)

    room = relationship("Room", back_populates="safety_status")


class RoomGasHourlyLog(Base):
    __tablename__ = "room_gas_hourly_logs"

    id = Column(Integer, primary_key=True, index=True)

    gas_level = Column(
        Float,
        nullable=False,
        comment="Gas concentration in PPM"
    )

    recorded_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.datetime.utcnow()
        .replace(minute=0, second=0, microsecond=0)
    )

    room_id = Column(
        Integer,
        ForeignKey("rooms.id"),
        nullable=False
    )

    room = relationship("Room", back_populates="gas_logs")

    __table_args__ = (
        UniqueConstraint(
            "room_id",
            "recorded_at",
            name="uq_room_hourly_gas"
        ),
    )
