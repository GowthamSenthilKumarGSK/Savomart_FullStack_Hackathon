"""Master seed script. Run from the repo root: python data/seed_all.py

Options:
    --force    Force rebuild of OSM data (re-parses the 558MB PBF)
"""
import asyncio
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "backend"))
sys.path.insert(0, str(repo_root))

from data.seed_users import seed_users
from data.seed_stores import seed_stores
from data.seed_pincodes import seed_pincodes
from data.seed_osm import seed_osm


async def main():
    force = "--force" in sys.argv

    print("=" * 60)
    print("Savo SiteScout — Data Seed Pipeline")
    if force:
        print("  (--force: OSM data will be rebuilt from PBF)")
    print("=" * 60)

    await seed_users()
    print()
    await seed_stores()
    print()
    await seed_pincodes()
    print()
    await seed_osm(force=force)

    print()
    print("=" * 60)
    print("Seed complete.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
