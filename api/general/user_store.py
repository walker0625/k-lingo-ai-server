## Processing user character and equipment purchases
from fastapi import APIRouter, HTTPException, status
from sqlmodel import select, update
from db.session import  SessionDep, get_user_by_username
from db.model.user_store import UserCharacter, UserCharacterCreate, UserCharacterResponse
from db.model.user import User
from db.model.character import CharacterResponse
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    statement = select(UserCharacter).\
                where(UserCharacter.user_id == item.user_id,
                      UserCharacter.character_id == item.character_id)
    _item = session.exec(statement).first()
    if _item:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have that character equipped"
        )
    ## 아이템 장착 처리
    new_item = UserCharacter(
        user_id = item.user_id,
        # username = _user.username,
        character_id = item.character_id,
        is_used = True, ## 구매시 기본 장착 처리
        desc = item.desc
    )
    session.add(new_item)
    session.commit()
    session.refresh(new_item)
    ## 동일 타입 장착 해제 처리
     ## user의 user_character에서 동일 타입이 장착되어 있으면 해제 처리    
    user_characters = _user.user_character
    for uc in user_characters:
        if uc.id == new_item.id:
            continue
        if uc.is_used and uc.character.type_code == new_item.character.type_code:
            uc.is_used = False
            session.add(uc)
    session.commit()
    
    return UserCharacterResponse(
        id = new_item.id,
        user_id = new_item.user_id,
        username = new_item.user.username,
        character_id = new_item.character_id,
        character_name = new_item.character.name,
        is_used = new_item.is_used,
        desc = new_item.desc
    )