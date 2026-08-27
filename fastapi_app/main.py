"""FastAPI utilities mounted at /fastapi when served through Uvicorn."""

from fastapi import FastAPI


app = FastAPI(
    title="Madrasa Management FastAPI",
    description="High-performance utility endpoints for the Madrasa Management System.",
    version="1.0.0",
)


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok", "service": "fastapi"}
