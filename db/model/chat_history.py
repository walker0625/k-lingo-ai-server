from sqlmodel import SQLModel, Field, Relationship
from pgvector.sqlalchemy import Vector
from typing import Optional
from datetime import datetime
from sqlalchemy import Column, Index

class ChatHistory(SQLModel, table=True):
    __tablename__ = "chat_history"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    question: str
    # SQLModel에서 vector 타입 사용 시 sa_column 필요
    embedding: list[float] = Field(sa_column=Column(Vector(1536))) 
    created_at: datetime = Field(default_factory=datetime.now)
    
    __table_args__ = (
        # 1. user_id에 대한 B-Tree 인덱스 (기본 인덱스)
        Index("ix_chat_history_user_id", "user_id"),

        # 2. embedding 컬럼에 대한 HNSW 인덱스 (코사인 거리)
        Index(
            "ix_chat_history_embedding", # 인덱스 이름 (임의 지정 가능)
            "embedding",                 # 대상 컬럼
            postgresql_using="hnsw",     # 알고리즘: HNSW
            postgresql_ops={"embedding": "vector_cosine_ops"} # 연산자: 코사인 거리
        ),
    )