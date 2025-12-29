from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    phone_number: str = Field(..., min_length=10, max_length=10)


class OTPVerify(BaseModel):
    phone_number: str = Field(..., min_length=10, max_length=10)
    otp: int


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    phone_number: str
    fcm_token: str = None
    is_active: bool

    class Config:
        orm_mode = True
