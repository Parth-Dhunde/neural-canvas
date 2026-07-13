"""Aggregate API routers."""

from fastapi import APIRouter

from app.api import engines, hardware, jobs, system, viewer

api_router = APIRouter()
api_router.include_router(jobs.router)
api_router.include_router(engines.router)
api_router.include_router(hardware.router)
api_router.include_router(system.router)
api_router.include_router(viewer.router)
