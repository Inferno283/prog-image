from fastapi import FastAPI

from app.api.routes.images import router as images_router

app = FastAPI()

app.include_router(images_router)
