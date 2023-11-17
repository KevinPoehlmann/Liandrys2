import aiohttp
import asyncio
import functools
import json
import logging

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable

from src.server.models.json_validation import (
    InfoJson,
    RuneJson
)


logger = logging.getLogger("patch_loader")
debugger = logging.getLogger("debugger")



def info_loader() -> InfoJson:
    """Loads information from the info.json file

        Parameters:
            info: describing the information part of the file

        Returns:
            information as dict
    """
    with open("src/server/loader/info.json") as info_file:
        info_dict = json.load(info_file)
    return InfoJson(**info_dict)





class TodoType(str, Enum):
    LOAD="Load"
    HOTFIX="Hotfix"
    PATCH="Patch"



@dataclass
class Todo():
    todo_type: TodoType
    patch: str
    hotfix: datetime = None



@dataclass
class RuneClass():
    """Class to gather Rune information"""
    rune: RuneJson
    tree: str
    tree_id: int
    row: int

    def __str__(self) -> str:
        return self.rune.name


class SafeSession():
        def __init__(self, session) -> None:
            self.session: aiohttp.ClientSession = session

        def retry(method: Callable) -> Callable:
            """Decorator to load data from url and retry on exceptions"""
            @functools.wraps(method)
            async def wrapper(ref, url):
                i = 1
                while True:
                    try:
                        async with ref.session.get(url) as response:
                            m = await method(ref, response)
                            #debugger.info(f"{i} tries to load '{url}'.")
                            return m
                    except (asyncio.TimeoutError, aiohttp.ServerDisconnectedError) as e:
                        if i == 5:
                            raise e
                        i += 1
                        if i == 5:
                            logger.warning(f"Last retry for url '{url}'.")
            return wrapper

        @retry
        async def json(self, response: aiohttp.ClientResponse) -> dict:
            """Turns json reponse into dict.
            
                Parameters:
                    response: json response
                    
                Returns:
                    dict with json data
            """
            return await response.json()
        
        @retry
        async def html(self, response: aiohttp.ClientResponse) -> str:
            """Turns reponse into html string.
            
                Parameters:
                    response: html string
                    
                Returns:
                    html from the response
            """
            return await response.text()
        
        @retry
        async def read(self, response: aiohttp.ClientResponse) -> bytes:
            """Turns reponse into bytes.
            
                Parameters:
                    response: response
                    
                Returns:
                    bytes with data from response
            """
            return await response.read()