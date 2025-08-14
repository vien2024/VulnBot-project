from fastapi import FastAPI

from server.api.kb_route import kb_router
from server.api.chat_route import chat_router


def create_app():
    app = FastAPI(title="Server")

    app.include_router(kb_router)
    app.include_router(chat_router)

    return app

