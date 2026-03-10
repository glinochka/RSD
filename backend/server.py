from fastapi import FastAPI

from app.logger_config import setup_logger
setup_logger()

from fastapi.middleware.cors import CORSMiddleware
from app.router_users import router as users_router
from app.router_agents import router as agents_router
from app.router_documents import router as documents_router
from app.origins import origins
import uvicorn



app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins = origins,
    allow_methods = ['*'],
    allow_headers = ['*'],
    allow_credentials = True
)

app.include_router(users_router.router)
app.include_router(agents_router.router)
app.include_router(documents_router.router)


if __name__ == "__main__":

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True 
    )