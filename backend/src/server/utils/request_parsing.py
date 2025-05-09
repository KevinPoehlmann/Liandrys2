from fastapi import Request, HTTPException
from pydantic import BaseModel, ValidationError
from typing import Type, TypeVar

T = TypeVar("T", bound=BaseModel)

async def parse_from_request(request: Request, model_cls: Type[T]) -> T:
    try:
        raw = await request.json()
        return model_cls.parse_obj(raw)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())