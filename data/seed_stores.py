"""Seed Savomart operational stores from the live API."""
import httpx
from sqlalchemy import text
from app.config import settings
from app.database import async_session


async def seed_stores():
    print("[Stores] Fetching from Savomart API...")
    if not settings.savomart_api_token:
        print("[Stores] ERROR: SAVOMART_API_TOKEN not set in .env — skipping.")
        return

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                settings.savomart_api_url,
                headers={"X-cron-token": settings.savomart_api_token},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        print(f"[Stores] ERROR fetching stores: {e}")
        return

    stores = data if isinstance(data, list) else data.get("data", data.get("results", []))
    if not stores:
        print("[Stores] WARNING: API returned no stores. Response keys:", list(data.keys()) if isinstance(data, dict) else type(data).__name__)
        return

    print(f"[Stores] Got {len(stores)} stores from API.")

    async with async_session() as session:
        inserted = 0
        skipped = 0
        errors = 0
        for s in stores:
            store_id = str(s.get("store_code", s.get("id", s.get("store_id", s.get("code", "")))))
            if not store_id:
                errors += 1
                continue

            geo = s.get("geocoordinates") or {}
            lat = geo.get("latitude") or s.get("latitude") or s.get("lat")
            lon = geo.get("longitude") or s.get("longitude") or s.get("lng") or s.get("lon")
            if not lat or not lon:
                errors += 1
                continue

            try:
                lat, lon = float(lat), float(lon)
            except (ValueError, TypeError):
                errors += 1
                continue

            r = await session.execute(
                text("SELECT 1 FROM savomart_stores WHERE store_id = :sid"),
                {"sid": store_id},
            )
            if r.scalar() is not None:
                skipped += 1
                continue

            name = s.get("name", s.get("store_name", f"Store {store_id}"))
            address = s.get("address", "")

            await session.execute(
                text(
                    "INSERT INTO savomart_stores (id, store_id, name, location, address, operational) "
                    "VALUES (gen_random_uuid(), :sid, :name, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :address, true)"
                ),
                {"sid": store_id, "name": name, "lon": lon, "lat": lat, "address": address},
            )
            inserted += 1

        await session.commit()
    print(f"[Stores] Inserted {inserted}, skipped {skipped} existing, {errors} errors.")
