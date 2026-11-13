from fastapi import FastAPI

app = FastAPI(title="Recipe Assistant")


@app.get("/health")
async def health():
    return {"status": "ok"}