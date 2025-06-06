import asyncio
from src.server.loader.helper import SafeSession
import aiohttp
from pathlib import Path

# List of champions you want to download
CHAMPIONS = ["V25.S1.1"]

BASE_URL = "https://wiki.leagueoflegends.com/en-us/"

DEST_DIR = Path("src/tests/static/html")
DEST_DIR.mkdir(parents=True, exist_ok=True)

async def download_html_pages():
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as aio_session:
        session = SafeSession(aio_session)

        for champ in CHAMPIONS:
            url = f"{BASE_URL}{champ}"
            try:
                html = await session.get_html(url)
                filepath = DEST_DIR / f"{champ.lower()}.html"
                filepath.write_text(html, encoding="utf-8")
                print(f"Saved: {filepath}")
            except Exception as e:
                print(f"Failed to download {champ}: {e}")

if __name__ == "__main__":
    asyncio.run(download_html_pages())
