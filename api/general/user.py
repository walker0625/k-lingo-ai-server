import os
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from typing import Annotated
from db.model.user import User, UserCreate, UserResponse, Token
from db.model.character import CharacterType
from db.session import  SessionDep, get_user_by_username, get_password_hash
from db.session import authenticate_user, create_access_token, get_current_active_user
## logger
from loguru import logger
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
        fullname=user.fullname,
        password=hashed_password
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return UserResponse(
        id = db_user.id,
        username = db_user.username,
        fullname = db_user.fullname,
        is_active = db_user.is_active,
        my_avatar = None,
        my_color = None
    )

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
    _user = UserResponse(
        id = current_user.id,
        username = current_user.username,
        fullname = current_user.fullname,
        is_active = current_user.is_active,
        my_avatar = None,
        my_color = None
    )
    user_characters = current_user.user_character
    for _char in user_characters:
        if _char.is_used:
            if _char.character.type_code == CharacterType.AVATAR:
                _user.my_avatar = _char.character.name
            elif _char.character.type_code == CharacterType.COLOR:
                _user.my_color = _char.character.name
    
    return _user

# @router.get("/host")
# def protected_route(
#     current_user: Annotated[User, Depends(get_current_active_user)]
# ):
#     ## how to check host user.
#     return {
#         "message": f"Hello host player, {current_user.username}!",
#         "user_id": current_user.id
#     }
