from fastapi import FastAPI

from app.api.routes.image_router import router as images_router
from app.database.connection import Base, engine

app = FastAPI()

app.include_router(images_router)
Base.metadata.create_all(bind=engine)
