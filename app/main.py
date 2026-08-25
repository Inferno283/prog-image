from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.image_router import router as images_router
from app.connections.db_connection import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all) # Not for use in production, for local development only

    yield

    await engine.dispose()


app = FastAPI(lifespan=lifespan)

app.include_router(images_router)