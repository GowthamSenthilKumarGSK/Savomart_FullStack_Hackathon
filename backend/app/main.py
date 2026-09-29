from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import pincodes, stores, fitness, hotspots, scouting

app = FastAPI(title="Savo SiteScout", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pincodes.router)
app.include_router(stores.router)
app.include_router(fitness.router)
app.include_router(hotspots.router)
app.include_router(scouting.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
