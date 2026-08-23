from uuid import UUID

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class ImageMetadata(Base):
    __tablename__ = "image_metadata"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True
    )

    blob_storage_provider: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    blob_key: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    content_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )