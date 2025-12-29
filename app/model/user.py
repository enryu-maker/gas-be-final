from app.database import Base
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
import datetime


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String)
    fcm_token = Column(String, nullable=True)
    phone_number = Column(String(10), nullable=False, unique=True)
    otp = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_active = Column(Boolean, default=False)

    # One user → many rooms
    rooms = relationship("Room", back_populates="owner",
                         cascade="all, delete-orphan")
