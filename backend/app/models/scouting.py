import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ScoutingTask(Base):
    __tablename__ = "scouting_tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    area_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("areas.id"))
    area_report_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("area_reports.id"))
    pincode_code: Mapped[str] = mapped_column(String(10))
    hotspot_rank: Mapped[int] = mapped_column(Integer)
    hotspot_geometry: Mapped[str] = mapped_column(Geometry("POLYGON", srid=4326))
    hotspot_centroid: Mapped[str] = mapped_column(Geometry("POINT", srid=4326))
    hotspot_score: Mapped[int] = mapped_column(Integer)
    hotspot_signals: Mapped[dict | None] = mapped_column(JSONB)

    assigned_to: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    assigned_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="assigned")
    notes: Mapped[str | None] = mapped_column(Text)

    property_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("properties.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
