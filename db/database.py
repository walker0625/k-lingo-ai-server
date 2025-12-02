import os
from fastapi import FastAPI
from sqlmodel import SQLModel, create_engine, Session
from loguru import logger

## logger
DATABASE_URL = os.environ["DATABASE_URL"]
DATABASE_INIT = os.environ["DATABASE_INIT"]


class DBHandler:
    def __init__(self, app: FastAPI) -> None:
        logger.info("start db handler")
        logger.info(f"DB URL : {DATABASE_URL}")

        # 25.12.02 한글 에러 메시지로 인한 서버 다운 방지 (connect_args 추가)
        engine = create_engine(
            DATABASE_URL, echo=True, connect_args={"client_encoding": "utf8"}
        )

        app.state.engine = engine
        logger.info(f"initialize table : {DATABASE_INIT}")

        # Startup: DB 초기화
        if os.environ["DATABASE_INIT"] == "0":
            logger.info("DATABASE Table initialization start")
            SQLModel.metadata.drop_all(engine)
            SQLModel.metadata.create_all(engine)
            logger.info("DATABASE Table initialization end")

        self.engine = engine
        logger.info("ready for db handler")

    def get_session(self):
        with Session(self.engine) as session:
            yield session

    def dispose(self):
        logger.info("dispose db handler")
        self.engine.dispose()
