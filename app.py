import os
from dotenv import load_dotenv

## Load .env file
load_dotenv()

import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager

## DB Handler
from db.database import DBHandler
# from db.vectordb import milvus_service
## Redis Handler
from db.redis import StateStore
## logger
from loguru import logger
from loguru_config import set_logger, fileloger

## router
# from api.general.general_router import mount_router

from api.general.user import router as user_router
from api.general.character import router as character_router
from api.general.user_store import router as user_store_router
from api.general.scenario import router as scenario_router
from api.general.interview import router as interview_router
from api.general.logviewer import router as log_router
from api.general.upload import router as upload_router
from api.general.retrieve import router as retrieve_router

from api.chat.chat_router import router as chat_router
from api.listening.listening_router import router as listening_router
from api.write.write_routers import router as write_router
from api.speaking.speaking_router import router as speaking_router
from api.evaluation.evaluation_router import router as evaluation_router

set_logger()

# lifespan 정의
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("lifespan start")
    dbhandler = DBHandler(app)
    # milvus_service.connect()
    logger.info("lifespan start")
    yield
    logger.info("liefspan end")
    dbhandler.dispose()
    # milvus_service.disconnect()
    logger.info("liefspan end")

## main app
logger.info('')
app = FastAPI(lifespan=lifespan)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    return await fileloger(request, call_next)

## router
# mount_router(app)
# speaking_router.py:30 - 듣기 응답 실패: [WinError 127] 지정된 프로시저를  찾을 수 없습니다. 
# Error loading "C:\walker\code\k-lingo-ai-server\.venv\Lib\site-packages\torch\lib\shm.dll" or one of its dependencies.

### general_router
app.include_router(user_router, prefix="/users", tags=["user"])
app.include_router(interview_router, prefix="/interview", tags=["interview"])
app.include_router(scenario_router, prefix="/scenario", tags=["scenario"])
app.include_router(character_router, prefix="/character", tags=["character"])
app.include_router(user_store_router, prefix="/store", tags=["store"])
app.include_router(log_router, prefix="/logs", tags=["logs"])
app.include_router(upload_router, prefix="/upload", tags=["upload"])

### ai_router
app.include_router(chat_router, prefix="/chats", tags=["chat"])
app.include_router(listening_router, prefix="/listenings", tags=["listening"])
app.include_router(write_router, prefix="/writes", tags=["write"])
app.include_router(speaking_router, prefix="/speakings", tags=["speaking"])
app.include_router(evaluation_router, prefix="/evaluations", tags=["evaluation"])

## index page
@app.get("/")
def home():
    return RedirectResponse(url="/index.html")

logger.info("static folder")
os.makedirs("static", exist_ok=True)
app.mount("/", StaticFiles(directory="static"), name="static")
logger.info("ready to service[port 8104]")

if __name__ == "__main__":
    # Render는 PORT 환경변수를 제공
    port = int(os.environ.get("PORT", 8104))
    uvicorn.run(app, host="0.0.0.0", port=port)