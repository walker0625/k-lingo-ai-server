import time, json, sys
from loguru import logger
from fastapi import Request

def set_logger():
    ### logger setting
    logger.remove()
    ### console logger
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        # 콘솔에서는 색상 출력을 활성화합니다.
    )
    ### file logger
    logger.add(
        "logs/api_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level="DEBUG",
        rotation="1 day", retention="7 days", compression="zip",
        enqueue=True
    )
    # ### pipe line
    # logger.enable("uvicorn")

async def fileloger(request: Request, call_next):
    start_time = time.time()
    try:
        if not str(request.url).endswith(".log"):
            content_type = request.headers.get('content-type', '')
            body = await request.body()
            ## check multipart/form-data
            if content_type.startswith('multipart/form-data'):
                logger.info(f"Request: {request.method} {request.url} body={'multipart/form-data' if body else None}")
            else:
                logger.info(f"Request: {request.method} {request.url} body={json.dumps(body.decode('utf-8')) if body else None}")
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        logger.info(
            f"Response: status={response.status_code} completed_in={process_time:.2f}ms"
        )
        return response
    except Exception as e:
        process_time = (time.time() - start_time) * 1000
        logger.info(
            f"{request.method} {request.url.path} - 500 - {process_time:.4f}s - Error: {str(e)}"
        )
        raise e