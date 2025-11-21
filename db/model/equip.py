from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, UniqueConstraint, Session, select
from enum import Enum

class EquipType(Enum):
    TOP = 1
    BOTTOM = 2
    SHOES = 3
    GLOVES = 4
    HAT = 5    

class Equip(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    type_code: EquipType
    idx: int
    name: str
    desc: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    __table_args__ = (
        UniqueConstraint("type_code", "idx", name="equip_type_index"),
    )

class EquipCreate(BaseModel):
    type_code: EquipType
    name: str
    desc: str

class EquipResponse(BaseModel):
    id: int
    username: str
    fullname: str
    is_active: bool

def create_equip_type_idx(session: Session, new_equip: EquipCreate):
    # 해당 type의 최대 idx 조회
    statement = select(Equip).where(Equip.type_code == new_equip.type_code)
    results = session.exec(statement).all()
    max_type_idx = max([r.idx for r in results], default=0)
    new_item = Equip(
        type_code = new_equip.type_code,
        idx=max_type_idx,
        name = new_equip.name,
        desc = new_equip.desc
    )
    session.add(new_item)
    session.commit()
    session.refresh(new_item)
    return new_item


