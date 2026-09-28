import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    area_report_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("area_reports.id"))
    location: Mapped[str] = mapped_column(Geometry("POINT", srid=4326))
    address: Mapped[str] = mapped_column(Text)
    pincode: Mapped[str] = mapped_column(String(10))
    rent_monthly: Mapped[float | None] = mapped_column(Float)
    carpet_area_sqft: Mapped[float | None] = mapped_column(Float)
    frontage_ft: Mapped[float | None] = mapped_column(Float)
    floor: Mapped[int | None] = mapped_column(Integer)
    building_type: Mapped[str | None] = mapped_column(String(50))
    contact_name: Mapped[str | None] = mapped_column(String(200))
    contact_phone: Mapped[str | None] = mapped_column(String(20))
    photos: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    stage: Mapped[str] = mapped_column(String(30), default="scouted")
    # stages: scouted, under_review, site_visit, approved, rejected, catchment_requested
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    evaluations: Mapped[list["PropertyEvaluation"]] = relationship(back_populates="property")
    history: Mapped[list["PropertyHistory"]] = relationship(back_populates="property", order_by="PropertyHistory.created_at.desc()")


class PropertyEvaluation(Base):
    __tablename__ = "property_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"))
    overall_score: Mapped[float | None]
    sub_scores: Mapped[dict | None] = mapped_column(JSONB)
    raw_data: Mapped[dict | None] = mapped_column(JSONB)
    ai_narrative: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    property: Mapped["Property"] = relationship(back_populates="evaluations")


class PropertyHistory(Base):
    __tablename__ = "property_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"))
    from_stage: Mapped[str] = mapped_column(String(30))
    to_stage: Mapped[str] = mapped_column(String(30))
    changed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    property: Mapped["Property"] = relationship(back_populates="history")
