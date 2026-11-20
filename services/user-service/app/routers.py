from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import EmailStr
from tortoise.exceptions import IntegrityError

from app.config import Settings, get_settings
from app.models import User
from app.passwords import hash_password, verify_password
from app.schemas import LoginRequest, TokenResponse, UserCreate, UserRead, UserUpdate
from app.security import AuthenticatedUser, create_access_token

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])
users_router = APIRouter(prefix="/api/users", tags=["users"])


@auth_router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate) -> User:
    email = payload.email.lower()
    if await User.exists(email=email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    try:
        return await User.create(
            email=email,
            full_name=payload.full_name.strip(),
            password_hash=hash_password(payload.password),
        )
    except IntegrityError as exc:  # concurrent registration with the same email
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from exc


@auth_router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, settings: Annotated[Settings, Depends(get_settings)]
) -> TokenResponse:
    user = await User.get_or_none(email=payload.email.lower())
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    token, expires_in = create_access_token(
        user_id=user.id, email=user.email, full_name=user.full_name, settings=settings
    )
    return TokenResponse(
        access_token=token, expires_in=expires_in, user=UserRead.model_validate(user)
    )


@users_router.get("/me", response_model=UserRead)
async def read_me(current: AuthenticatedUser) -> User:
    user = await User.get_or_none(id=current.id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@users_router.patch("/me", response_model=UserRead)
async def update_me(payload: UserUpdate, current: AuthenticatedUser) -> User:
    user = await User.get_or_none(id=current.id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
    await user.save()
    return user


@users_router.get("/lookup", response_model=UserRead)
async def lookup_by_email(email: Annotated[EmailStr, Query()], _current: AuthenticatedUser) -> User:
    """Used by WorkspaceService to resolve an email into a user when inviting a member."""
    user = await User.get_or_none(email=email.lower())
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@users_router.get("/{user_id}", response_model=UserRead)
async def read_user(user_id: int, _current: AuthenticatedUser) -> User:
    user = await User.get_or_none(id=user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user
