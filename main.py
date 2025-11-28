# ===== 2025.11.24 paddlex 호환 패치 (이건 기능이라 둠) =====
import sys
from types import ModuleType
import langchain
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

docstore_module = ModuleType("langchain.docstore")
document_module = ModuleType("langchain.docstore.document")
document_module.Document = Document
docstore_module.document = document_module
text_splitter_module = ModuleType("langchain.text_splitter")
text_splitter_module.RecursiveCharacterTextSplitter = RecursiveCharacterTextSplitter
sys.modules["langchain.docstore"] = docstore_module
sys.modules["langchain.docstore.document"] = document_module
sys.modules["langchain.text_splitter"] = text_splitter_module
langchain.docstore = docstore_module
langchain.text_splitter = text_splitter_module
# ===== 패치 끝 =====

import os, logging, time, json
from dotenv import load_dotenv

## 설정 파일
load_dotenv()
import uvicorn
from ipynb.logging_config import setup_logging
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

## DB Session
from db.session import create_db_and_tables  # ,engine
from sqlmodel import SQLModel, create_engine

## Milvus Connection
# from pymilvus import connections
from db.vectordb import milvus_service

# from db.vector import set_connection

## Router
from api.general.user import router as user_router

# from api.general.item import router as item_router
from api.general.character import router as character_router
from api.general.user_store import router as user_store_router
from api.general.scenario import router as scenario_router
from api.general.upload import router as upload_router

from api.chat.chat_router import router as chat_router
from api.listening.listening_router import router as listening_router
from api.write.write_routers import router as write_router
from api.speaking.speaking_router import router as speaking_router

from api.general.retrieve import router as retrieve_router
from api.general.logviewer import router as log_router

## file logger
from loguru import logger as file_logger


## 로깅 설정 적용 및 로거 생성
setup_logging()
logger = logging.getLogger("app")


# lifespan 정의
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("LIFESPAN START")
    ###### Database setup ######
    logger.info("DATABASE SETUP")
    DATABASE_URL = os.environ["DATABASE_URL"]
    engine = create_engine(DATABASE_URL, echo=True)
    app.state.engine = engine
    # Startup: DB 초기화
    if os.environ["DATABASE_INIT"] == "0":
        logger.info("DATABASE Table initialization start")
        SQLModel.metadata.drop_all(engine)
        create_db_and_tables(engine)
        logger.info("DATABASE Table initialization end")

    ## Milvus Connection
    # set_connection()
    milvus_service.connect()
    yield
    engine.dispose()
    # connections.disconnect("default")
    milvus_service.disconnect()
    logger.info("LIFESPAN END")


logger.info("start k-lingo api")
app = FastAPI(title="K Lingo API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)


## 로그 미들 웨어
file_logger.add(
    "logs/api_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    level="INFO",
    rotation="1 day",
    retention="7 days",
    compression="zip",
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    try:
        ## skip log api call
        skip_body_url = [":8104/files", ":8104/speaking", ":8104/write"]
        if not str(request.url).endswith(".log"):
            body = await request.body()
            if any([skip_url in str(request.url) for skip_url in skip_body_url]):
                file_logger.info(
                    f"Request: {request.method} {request.url} body={'multipark/form-data' if body else None}"
                )
            else:
                file_logger.info(
                    f"Request: {request.method} {request.url} body={json.dumps(body.decode('utf-8')) if body else None}"
                )

        response = await call_next(request)

        process_time = (time.time() - start_time) * 1000
        file_logger.info(
            f"Response: status={response.status_code} completed_in={process_time:.2f}ms"
        )
        return response
    except Exception as e:
        process_time = (time.time() - start_time) * 1000
        file_logger.info(
            f"{request.method} {request.url.path} - 500 - {process_time:.4f}s - Error: {str(e)}"
        )
        raise e


@app.get("/")
def home():
    return RedirectResponse(url="/index.html")


logger.info("load routers")
app.include_router(user_router, prefix="/users", tags=["user"])
app.include_router(character_router, prefix="/characters", tags=["character"])
app.include_router(user_store_router, prefix="/store", tags=["store"])
app.include_router(scenario_router, prefix="/scenario", tags=["scenario"])
app.include_router(upload_router, prefix="/files", tags=["files"])
app.include_router(chat_router, prefix="/chats", tags=["chat"])
app.include_router(listening_router, prefix="/listenings", tags=["listening"])
app.include_router(write_router, prefix="/writes", tags=["write"])
app.include_router(speaking_router, prefix="/speakings", tags=["speaking"])
app.include_router(retrieve_router, prefix="/vector", tags=["vector"])
app.include_router(log_router, prefix="/logs", tags=["logs"])


logger.info("static folder")
os.makedirs("static", exist_ok=True)
app.mount("/", StaticFiles(directory="static"), name="static")
logger.info("ready to service[port 8104]")
if __name__ == "__main__":
    # Render는 PORT 환경변수를 제공
    port = int(os.environ.get("PORT", 8104))
    uvicorn.run(app, host="0.0.0.0", port=port)
