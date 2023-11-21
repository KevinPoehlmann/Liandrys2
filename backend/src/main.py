from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


from src.server.routes.patch import router as patchesRouter
from src.server.routes.champion import router as championsRouter
from src.server.routes.item import router as itemsRouter
from src.server.routes.rune import router as runesRouter
from src.server.routes.summonerspell import router as summonerspellsRouter




def add_middleware(app: FastAPI) -> None:
    origins = ["http://localhost:5173"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )
    

def include_routers(app: FastAPI) -> None:
    app.include_router(patchesRouter, tags=["Patch"], prefix="/patch")
    app.include_router(championsRouter, tags=["Champion"], prefix="/champion")
    app.include_router(itemsRouter, tags=["Item"], prefix="/item")
    app.include_router(runesRouter, tags=["Rune"], prefix="/rune")
    app.include_router(summonerspellsRouter, tags=["Summonerspell"], prefix="/summonerspell")


def add_static_files(app: FastAPI) -> None:
    app.mount("/images", StaticFiles(directory="src/images"), name="images")
    app.mount("/logs", StaticFiles(directory="src/logs"), name="logs")


def start_application() -> FastAPI:
    app = FastAPI()
    add_middleware(app)
    include_routers(app)
    add_static_files(app)
    return app

app = start_application()

@app.get("/")
async def root():
    return {"message": "Just the beginning!"}