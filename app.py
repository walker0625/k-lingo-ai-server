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
## router
from api.general.general_router import mount_router
## logger
from loguru import logger
from loguru_config import set_logger, fileloger
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
mount_router(app)

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
