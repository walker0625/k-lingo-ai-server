import os, logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Field, SQLModel, create_engine, Session, select
from db.session import  SessionDep, get_session
from db.model.character import Character
from db.model.character import CharacterResponse
from db.model.character import CharacterCreate
# from db.model.character import create_character_type_idx

## logger
logger = logging.getLogger("app")
## user router
router = APIRouter()

# Routes
@router.get("/", response_model=list[CharacterResponse])
def get_items(name: str,session : SessionDep):
    statement = select(Character).where(Character.name.contains(name))
    results = session.exec(statement).all()
    return results

@router.post("/post", response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
def add_item(item: CharacterCreate, session: SessionDep):
    """
        Character Type : 1 - AVATAR(외형), 2 -COLOR
    """
    logging.info(f"********** create character : {item}")
    statement = select(Character).where(Character.name == item.name and Character.type_code == item.type_code)
    _item = session.exec(statement).first()
    if _item:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Character already registered"
        )
    # Create new item, select max idx
    statement = select(Character).where(Character.type_code == item.type_code)
    results = session.exec(statement).all()
    logging.info(f"max idx : {results}")
    max_type_idx = max([r.idx for r in results], default=0)
    new_item = Character(
        type_code = item.type_code,
        idx=max_type_idx + 1,
        name = item.name,
        desc = item.desc
    )
    session.add(new_item)
    session.commit()
    session.refresh(new_item)
    return new_item

@router.put("/update/{character_id}", response_model=Character )
def update_item(character_id: int, item: CharacterResponse, session : SessionDep):
    _item = session.get(Character, character_id)
    if not _item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )
    _item.name = item.name
    _item.type_code = item.type_code
    _item.desc = item.desc
    _item.updated_at = datetime.now()
    session.add(_item)
    session.commit()
    session.refresh(_item)
    return _item

@router.delete("/delete/{character_id}")
def delete_item(character_id: int, session: Session = Depends(get_session)):
    item = session.get(Character, character_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )
    session.delete(item)
    session.commit()
    return {"ok": True}