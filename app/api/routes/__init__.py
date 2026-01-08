from app.api.routes.health import router as health_router
from app.api.routes.voice import router as voice_router

all_routers = [
    health_router,
    voice_router,
]
