import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Pincode(Base):
    __tablename__ = "pincodes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    geometry: Mapped[str] = mapped_column(Geometry("MULTIPOLYGON", srid=4326))


class OsmPoi(Base):
    __tablename__ = "osm_pois"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    osm_id: Mapped[int] = mapped_column(BigInteger, index=True)
    osm_type: Mapped[str] = mapped_column(String(10))  # node, way, relation
    category: Mapped[str] = mapped_column(String(50), index=True)  # shop, amenity, office, building
    subcategory: Mapped[str] = mapped_column(String(100), index=True)  # supermarket, school, hospital, etc.
    name: Mapped[str | None] = mapped_column(String(500))
    location: Mapped[str] = mapped_column(Geometry("POINT", srid=4326))
    tags: Mapped[dict | None] = mapped_column(JSONB)


class OsmRoad(Base):
    __tablename__ = "osm_roads"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    osm_id: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str | None] = mapped_column(String(500))
    road_type: Mapped[str] = mapped_column(String(50), index=True)  # primary, secondary, residential, etc.
    geometry: Mapped[str] = mapped_column(Geometry("LINESTRING", srid=4326))
    tags: Mapped[dict | None] = mapped_column(JSONB)


class SavomartStore(Base):
    __tablename__ = "savomart_stores"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    store_id: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(300))
    location: Mapped[str] = mapped_column(Geometry("POINT", srid=4326))
    address: Mapped[str | None] = mapped_column(Text)
    operational: Mapped[bool] = mapped_column(default=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GeocodeCache(Base):
    __tablename__ = "geocode_cache"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    query_text: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    lat: Mapped[float]
    lon: Mapped[float]
    display_name: Mapped[str] = mapped_column(String(500), default="")
    bbox: Mapped[dict | None] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
