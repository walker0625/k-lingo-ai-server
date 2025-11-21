## Processing user character and equipment purchases

import os, logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Field, SQLModel, create_engine, Session, select
from db.session import  SessionDep, get_session, get_user_by_username
from db.model.user import User, get_user_by_id
from db.model.character import Character, CharacterResponse
from db.model.user_store import UserCharacter, UserCharacterCreate, UserCharacterResponse


## logger
logger = logging.getLogger("app")
## user router
router = APIRouter()

# Routes
@router.get("/characters", response_model=list[CharacterResponse])
def get_characters(username:str, session : SessionDep):
    _user = get_user_by_username(session, username)
    if not _user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    result = []
    for character in _user.characters:
        result.append(CharacterResponse(
            id = character.id,
            type_code = character.type_code,
            idx = character.idx,
            name = character.name,
            desc = character.desc
        ))
    return result
        
@router.post("/buy/character", response_model=UserCharacterResponse, status_code=status.HTTP_201_CREATED)
def add_item(item: UserCharacterCreate, session: SessionDep):
    """
        Character Type : 1 - AVATAR(외형), 2 -COLOR
        캐럭터 구매 처리, 구매시 장착 여부는 확인 필요
    """
    ## user checker
    _user = get_user_by_id(session, item.user_id)
    if not _user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )
    statement = select(UserCharacter).\
                where(UserCharacter.user_id == item.user_id and UserCharacter.character_id == item.character_id)
    _item = session.exec(statement).first()
    if _item:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already buyed that Character"
        )
    # Create new item
    new_item = UserCharacter(
        user_id = item.user_id,
        username = _user.username,
        character_id = item.character_id,
        is_used = False, ## 구매시 기본 장차 처리 여부??
        desc = item.desc
    )
    session.add(new_item)
    session.commit()
    session.refresh(new_item)
    return UserCharacterResponse(
        id = new_item.id,
        user_id = new_item.user_id,
        username = new_item.user.username,
        character_id = new_item.character_id,
        character_name = new_item.character.name,
        is_used = new_item.is_used,
        desc = new_item.desc
    )