from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


from server.routes.patch import router as patchesRouter




def add_middleware(app: FastAPI) -> None:
    origins = ["http://localhost:5174"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )


def include_routers(app: FastAPI) -> None:
    app.include_router(patchesRouter, tags=["Patch"], prefix="/patch")


def add_static_files(app: FastAPI) -> None:
    app.mount("/images", StaticFiles(directory="images"), name="images")
    app.mount("/logs", StaticFiles(directory="logs"), name="logs")


def start_application() -> FastAPI:
    app = FastAPI()
    add_middleware(app)
    include_routers(app)
    add_static_files(app)
    return app

app = start_application()

@app.get("/")
async def root():
    return {"msg": "ADMIN!"}












def something(a):
    return a


