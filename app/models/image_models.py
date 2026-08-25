from uuid import UUID

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class StoredImageMetadata(Base):
    __tablename__ = "stored_image_metadata"

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
    
    filename: Mapped[str] = mapped_column(
        String,
        nullable=True,
    )

    size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    
    height: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    width: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    image_format: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )