from fastapi import FastAPI
from app.api import router
# uv run uvicorn app.main:app --reload
# http://127.0.0.1:8000/
# http://127.0.0.1:8000/docs

app = FastAPI()
app.include_router(router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Hello OfferAI!"}


@app.get("/health")
def health() -> dict[str, str]:
    return{"status": "OK!"}
