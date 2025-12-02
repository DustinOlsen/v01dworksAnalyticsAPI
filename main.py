from fastapi import FastAPI
from app.api import router
from app.database import init_db

app = FastAPI(title="Privacy Visitor Tracker")

@app.on_event("startup")
def on_startup():
    init_db()

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
