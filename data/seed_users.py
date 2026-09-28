"""Seed four demo users for the four personas."""
import uuid
from sqlalchemy import text
from app.database import async_session

DEMO_USERS = [
    {"id": "00000000-0000-0000-0000-000000000001", "name": "Priya Sharma", "email": "priya@demo.sitescout", "role": "bd_manager"},
    {"id": "00000000-0000-0000-0000-000000000002", "name": "Arjun Patel", "email": "arjun@demo.sitescout", "role": "bd_executive"},
    {"id": "00000000-0000-0000-0000-000000000003", "name": "Meena Krishnan", "email": "meena@demo.sitescout", "role": "survey_manager"},
    {"id": "00000000-0000-0000-0000-000000000004", "name": "Ravi Kumar", "email": "ravi@demo.sitescout", "role": "survey_executive"},
]


async def seed_users():
    print("[Users] Seeding demo users...")
    async with async_session() as session:
        r = await session.execute(text("SELECT COUNT(*) FROM users"))
        existing = r.scalar()
        if existing >= len(DEMO_USERS):
            print(f"[Users] Already {existing} users in DB, skipping.")
            return

        inserted = 0
        for u in DEMO_USERS:
            r = await session.execute(
                text("SELECT 1 FROM users WHERE id = :id"), {"id": u["id"]}
            )
            if r.scalar() is None:
                await session.execute(
                    text(
                        "INSERT INTO users (id, name, email, role) "
                        "VALUES (:id, :name, :email, :role)"
                    ),
                    u,
                )
                inserted += 1
        await session.commit()
    print(f"[Users] Inserted {inserted}, total {existing + inserted}.")
