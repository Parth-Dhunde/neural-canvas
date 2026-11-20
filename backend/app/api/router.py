"""Aggregate API routers."""

from fastapi import APIRouter

from app.api import dashboard, hardware, jobs, system

api_router = APIRouter()
api_router.include_router(jobs.router)
api_router.include_router(dashboard.router)
api_router.include_router(hardware.router)
api_router.include_router(system.router)
