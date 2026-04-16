from fastapi import APIRouter

from app.api.v1.consumer import router as consumer_router
from app.api.v1.health import router as health_router
from app.api.v1.merchant import router as merchant_router
from app.api.v1.pos import router as pos_router
from app.api.v1.public import router as public_router
from app.api.v1.webhooks import router as webhooks_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(public_router, prefix="/public", tags=["public"])
api_router.include_router(consumer_router, prefix="/me", tags=["consumer"])
api_router.include_router(merchant_router, prefix="/merchant", tags=["merchant"])
api_router.include_router(pos_router, prefix="/pos", tags=["pos"])
api_router.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
