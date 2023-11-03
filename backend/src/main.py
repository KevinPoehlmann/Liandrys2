from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware





def add_middleware(app: FastAPI) -> None:
    origins = ["http://localhost:5173"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )

def start_application() -> FastAPI:
    app = FastAPI()
    add_middleware(app)
    return app

app = start_application()

@app.get("/")
async def root():
    return {"message": "Just the beginning!"}