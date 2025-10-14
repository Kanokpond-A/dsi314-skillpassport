from fastapi import FastAPI
from .api.v1.routes import router as v1_router

app = FastAPI(title="UCB Backend", version="0.1.0")
app.include_router(v1_router)
