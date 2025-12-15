from loguru import logger
from fastapi import FastAPI
def mount_router(app:FastAPI):
    logger.info("mount general routers")
    from api.general.user import router as user_router
    from api.general.character import router as character_router
    from api.general.user_store import router as user_store_router
    from api.general.scenario import router as scenario_router
    from api.general.interview import router as interview_router
    from api.general.logviewer import router as log_router
    from api.general.upload import router as upload_router
    # from api.general.retrieve import router as retrieve_router

    ## router
    app.include_router(user_router, prefix="/users", tags=["user"])
    app.include_router(character_router, prefix="/character", tags=["character"])
    app.include_router(user_store_router, prefix="/store", tags=["store"])
    app.include_router(scenario_router, prefix="/scenario", tags=["scenario"])
    app.include_router(interview_router, prefix="/interview", tags=["interview"])
    app.include_router(log_router, prefix="/logs", tags=["logs"])
    app.include_router(upload_router, prefix="/upload", tags=["upload"])
    # app.include_router(retrieve_router, prefix="/vector", tags=["vector"])