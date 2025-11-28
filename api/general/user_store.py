## Processing user character and equipment purchases
from fastapi import APIRouter, HTTPException, status
from sqlmodel import select
from db.session import  SessionDep, get_user_by_username
from db.model.user import User
from db.model.character import CharacterResponse
from db.model.user_store import UserCharacter, UserCharacterCreate, UserCharacterResponse
## logger
from loguru import logger
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
    for character in _user.user_character:
        result.append(CharacterResponse(
            id = character.id,
            type_code = character.type_code,
            idx = character.idx,
            name = character.name,
            desc = character.desc
        ))
    return result
        
@router.post("/character/change", response_model=UserCharacterResponse, status_code=status.HTTP_201_CREATED)
def add_item(item: UserCharacterCreate, session: SessionDep):
    """
        Character Type : 1 - AVATAR(외형), 2 -COLOR
        캐럭터 변경 처리, 변경시 기본 장착 처리
    """
    ## user checker
    _user = session.get(User,item.user_id)
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
        is_used = True, ## 구매시 기본 장착 처리
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