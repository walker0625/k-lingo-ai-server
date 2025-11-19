import os, logging
from dotenv import load_dotenv
## 설정 파일
load_dotenv()
import uvicorn
from logging_config import setup_logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
## DB Session
from db.session import create_db_and_tables #,engine
from sqlmodel import SQLModel, create_engine
## Router
from api.general.user import router as user_router
from api.general.item import router as item_router

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
        logger.info("ATABASE Table initialization end")
    yield
    engine.dispose()
    logger.info("LIFESPAN END")

logger.info("start k-lingo api")
app = FastAPI(title="K Lingo API",lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

@app.get("/")
def home():
    return RedirectResponse(url="/index.html")
logger.info('load routers')
app.include_router(user_router, prefix="/users", tags=["user"])
app.include_router(item_router, prefix="/items", tags=["item"])

logger.info('static folder')
os.makedirs("static", exist_ok=True)
app.mount("/", StaticFiles(directory="static"), name="static")
logger.info('ready to service[port 8104]')
if __name__ == "__main__":
    # Render는 PORT 환경변수를 제공
    port = int(os.environ.get("PORT", 8104))
    uvicorn.run(app, host="0.0.0.0", port=port)