from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException
from sqlalchemy import text

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.routers import admin, analytics, auth, student
from app.services.bootstrap import ensure_fixed_session
from app import models  # noqa: F401 - register SQLAlchemy models before create_all


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_settings().require_azure_storage()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        ensure_fixed_session(db)
    yield


app = FastAPI(title="Attendance Saver API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(student.router)
app.include_router(analytics.router)


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(503, "Azure SQL is unavailable. Check the SQL credentials, firewall rule, and ODBC Driver 18 installation.") from exc
    return {"status": "ok", "service": "attendance-saver-api", "database": "azure-sql"}
