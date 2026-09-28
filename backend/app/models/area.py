import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Area(Base):
    __tablename__ = "areas"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(300))
    pincode_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("pincodes.id"))
    geometry: Mapped[str] = mapped_column(Geometry("POLYGON", srid=4326))
    selection_method: Mapped[str] = mapped_column(String(20))  # pincode, locality, grid
    h3_cells: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    reports: Mapped[list["AreaReport"]] = relationship(back_populates="area", order_by="AreaReport.created_at.desc()")


class AreaReport(Base):
    __tablename__ = "area_reports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    area_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("areas.id"))
    overall_score: Mapped[float | None]
    sub_scores: Mapped[dict | None] = mapped_column(JSONB)
    raw_data: Mapped[dict | None] = mapped_column(JSONB)
    ai_narrative: Mapped[str | None] = mapped_column(Text)
    scouting_suggestions: Mapped[dict | None] = mapped_column(JSONB)
    data_sources: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, processing, completed, failed
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    area: Mapped["Area"] = relationship(back_populates="reports")
