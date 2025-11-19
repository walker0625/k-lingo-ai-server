import os, logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Field, SQLModel, create_engine, Session, select
from db.session import  SessionDep, get_session
from db.model.item import Item, ItemResponse, ItemCreate

## logger
logger = logging.getLogger("app")
## user router
router = APIRouter()

# Routes
@router.post("/add", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def add_item(item: ItemCreate, session: SessionDep):
    statement = select(Item).where(Item.name == item.name)
    _item = session.exec(statement).first()
    if _item:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Itemname already registered"
        )
    # Create new item
    new_item = Item(
        type=item.type,
        name=item.name,
        desc=item.desc
    )
    session.add(new_item)
    session.commit()
    session.refresh(new_item)
    return new_item

@router.put("/items/{item_id}", response_model=Item )
def update_item(item_id: int, item: ItemResponse, session : SessionDep):
    _item = session.get(Item, item_id)
    if not _item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    _item.name = item.name
    _item.type = item.type
    _item.desc = item.desc
    _item.price = item.price
    _item.updated_at = datetime.now()
    session.add(_item)
    session.commit()
    session.refresh(_item)
    return _item

@router.delete("/{item_id}")
def delete_item(item_id: int, session: Session = Depends(get_session)):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    session.delete(item)
    session.commit()
    return {"ok": True}

@router.get("/items", response_model=list[ItemResponse])
def get_items(name: str,session : SessionDep):
    statement = select(Item).where(Item.name.contains(name))
    results = session.exec(statement).all()
    return results