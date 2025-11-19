import os, logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, Annotated
from passlib.context import CryptContext
from db.model.user import User, UserCreate, UserResponse, Token, TokenData
from db.session import  SessionDep, get_user_by_username, get_password_hash
from db.session import authenticate_user, create_access_token, get_current_active_user

## logger
logger = logging.getLogger("app")
## user router
router = APIRouter()

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"])

# Routes
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, session: SessionDep):
    # Check if user exists
    existing_user = get_user_by_username(session, user.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

@router.post("/token", response_model=Token)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep
):
    user = authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    return current_user

@router.get("/protected")
def protected_route(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    return {
        "message": f"Hello {current_user.username}! This is a protected route.",
        "user_id": current_user.id
    }
