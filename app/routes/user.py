from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session
from datetime import timedelta

from app.schemas.user import OTPVerify, LoginRequest, UserResponse
from app.database import SessionLocale
from app.model.user import User
from app.service.user_service import (
    generate_otp,
    send_otp,
    create_accesss_token,
    decode_access_token
)

router = APIRouter(
    prefix="/v1/user",
    tags=["V1 USER API"],
)

# Dependency to get DB session


def get_db():
    db = SessionLocale()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(decode_access_token)]


@router.post('/register/', status_code=status.HTTP_201_CREATED)
async def register_user(
    db: db_dependency,
    name: str = Form(...),
    email: str = Form(...),
    phone_number: str = Form(...),
    fcm_token: str = Form(None)

):
    # Check for existing user
    existing_user = db.query(User).filter(
        User.phone_number == phone_number).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this phone number already exists."
        )

    otp = generate_otp()

    try:
        send_otp(otp=otp, mobile_number=phone_number)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to send OTP: {str(e)}"
        )

    new_user = User(
        name=name,
        email=email,
        phone_number=phone_number,
        otp=otp,
        fcm_token=fcm_token,
        is_active=False  # Wait for OTP verification
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return {"message": "OTP sent successfully. Please verify your phone number."}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register user: {str(e)}"
        )


@router.post("/login/", status_code=status.HTTP_200_OK)
async def login_user(login_request: LoginRequest, db: db_dependency):
    user = db.query(User).filter(User.phone_number ==
                                 login_request.phone_number).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not activated. Please verify your phone number."
        )

    otp = generate_otp()
    user.otp = otp

    try:
        send_otp(otp=otp, mobile_number=login_request.phone_number)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to send OTP: {str(e)}"
        )

    db.commit()
    return {"message": "OTP sent successfully. Please verify to proceed."}


@router.post("/verify/", status_code=status.HTTP_200_OK)
async def verify_user_otp(verify_request: OTPVerify, db: db_dependency):
    user = db.query(User).filter(User.phone_number ==
                                 verify_request.phone_number).first()

    print(
        f"Verifying OTP for phone number: {verify_request.phone_number}, provided OTP: {verify_request.otp}")
    print(user.otp)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    if str(user.otp) != str(verify_request.otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP."
        )

    user.is_active = True
    user.otp = None

    db.commit()

    access_token = create_accesss_token(
        name=user.name,
        user_id=user.id,
        expiry=timedelta(days=90)
    )

    return {
        "message": "Phone number verified successfully.",
        "access_token": access_token
    }


@router.get("/profile/", response_model=UserResponse)
async def get_user_profile(user: user_dependency, db: db_dependency):
    db_user = db.query(User).filter(User.id == user['user_id']).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
    return db_user
