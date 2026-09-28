import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CatchmentStudy(Base):
    __tablename__ = "catchment_studies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("properties.id"))
    area_report_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("area_reports.id"))
    boundary: Mapped[str] = mapped_column(Geometry("POLYGON", srid=4326))
    radius_m: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="requested")
    # statuses: requested, planning, in_progress, completed
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    assignments: Mapped[list["SurveyAssignment"]] = relationship(back_populates="study")
    insights: Mapped[list["CatchmentInsight"]] = relationship(back_populates="study")


class SurveyAssignment(Base):
    __tablename__ = "survey_assignments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    study_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("catchment_studies.id"))
    assigned_to: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    zone_h3_cells: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    zone_boundary: Mapped[str] = mapped_column(Geometry("POLYGON", srid=4326))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # statuses: pending, in_progress, completed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    study: Mapped["CatchmentStudy"] = relationship(back_populates="assignments")
    surveys: Mapped[list["LaneSurvey"]] = relationship(back_populates="assignment")


class LaneSurvey(Base):
    __tablename__ = "lane_surveys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("survey_assignments.id"))
    road_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("osm_roads.id"))
    road_segment: Mapped[str | None] = mapped_column(Geometry("LINESTRING", srid=4326))
    household_type: Mapped[str | None] = mapped_column(String(50))  # apartments, individual, mixed
    household_count_range: Mapped[str | None] = mapped_column(String(20))  # <20, 20-50, 50-100, 100+
    shop_count: Mapped[int | None] = mapped_column(Integer)
    shop_types: Mapped[dict | None] = mapped_column(JSONB)
    road_condition: Mapped[str | None] = mapped_column(String(50))
    foot_traffic: Mapped[str | None] = mapped_column(String(20))  # low, medium, high
    photos: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    notes: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Geometry("POINT", srid=4326))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    assignment: Mapped["SurveyAssignment"] = relationship(back_populates="surveys")


class CatchmentInsight(Base):
    __tablename__ = "catchment_insights"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    study_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("catchment_studies.id"))
    total_roads_surveyed: Mapped[int] = mapped_column(Integer, default=0)
    total_roads_in_area: Mapped[int] = mapped_column(Integer, default=0)
    completion_pct: Mapped[float] = mapped_column(Float, default=0.0)
    aggregated_data: Mapped[dict | None] = mapped_column(JSONB)
    ai_narrative: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    study: Mapped["CatchmentStudy"] = relationship(back_populates="insights")
