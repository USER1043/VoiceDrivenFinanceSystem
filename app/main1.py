from fastapi import FastAPI
from app.api.routes import all_routers

app = FastAPI(
    title="Voice Driven Finance System",
    version="1.0.0"
)

@app.get("/")
def root():
    return {"message": "Voice Driven Finance System API is running"}

for router in all_routers:
    app.include_router(router)
