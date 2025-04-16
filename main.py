import nodriver
import asyncio
from typing import Optional
from nodriver import cdp
import httpx
from rich.logging import RichHandler
from rich.console import Console
from rich.theme import Theme
import logging

console = Console(
    theme=Theme(
        {
            "logging.level.error": "bold red",
            "logging.level.warning": "yellow",
            "logging.level.info": "green",
        }
    )
)
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="%X",
    handlers=[
        RichHandler(
            rich_tracebacks=True,
            show_level=True,
            show_path=True,
            show_time=True,
            console=console,
        )
    ],
)
log: logging.Logger = logging.getLogger(__name__)

class SpotifyTokenExtractor:
    def __init__(self):
        self.loop = nodriver.loop()
        self.tab: Optional[nodriver.Tab] = None
        self.browser: Optional[nodriver.Browser] = None
        self.client: httpx.AsyncClient = httpx.AsyncClient()
        self.future: asyncio.Future[dict[str, str | int | bool]] = (
            self.loop.create_future()
        )
        self.browser_task: Optional[asyncio.Task[None]] = None

    async def request_paused_handler(self, event: cdp.fetch.RequestPaused) -> None:
        if "/get_access_token" in event.request.url:
            resp = await self.client.get(event.request.url)
            log.info(f"Response Status Code : {resp.status_code}")
            if resp.status_code == 200:
                self.future.set_result(resp.json())
            else:
                self.future.set_result({'error' : resp.text})    
        else:
            log.info(f'Skipping request : {event.request.url}')
            self.loop.create_task(
                self.tab.feed_cdp(
                    cdp.fetch.continue_request(request_id=event.request_id)
                )
            )

    async def execute(self) -> None:
        log.info("Starting webbrowser in headless mode...")
        self.browser = await nodriver.start(browser_args=["--headless=true" , "--disable-gpu=true" , "--no-sandbox=True"] , browser_executable_path="/usr/bin/google-chrome")
        self.tab = self.browser.main_tab
        self.tab.add_handler(cdp.fetch.RequestPaused, self.request_paused_handler)
        log.info('Opening : https://open.spotify.com')
        self.tab = await self.browser.get("https://open.spotify.com/")
        log.info("Waiting for the page to fully load...")
        await asyncio.sleep(20)

    async def main(self):
        self.browser_task = self.loop.create_task(self.execute())
        try:
            result = await asyncio.wait_for(self.future, timeout=25.0)
            log.info(f'Result : {result}')
        except asyncio.TimeoutError as e:
            log.error(f"Timed out for token extraction : {e}")
        finally:
            log.info('Cancelled the browser task and closed the browser.')
            self.browser_task.cancel()


if __name__ == "__main__":
    ex = SpotifyTokenExtractor()
    ex.loop.run_until_complete(ex.main())
