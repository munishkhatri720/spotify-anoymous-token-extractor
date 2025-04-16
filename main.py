import nodriver
import asyncio
from typing import Optional
from nodriver import cdp
import httpx
from rich import print

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
            if resp.status_code == 200:
                self.future.set_result(resp.json())
            else:
                self.future.set_result({'error' : resp.text})    
        else:
            self.loop.create_task(
                self.tab.feed_cdp(
                    cdp.fetch.continue_request(request_id=event.request_id)
                )
            )

    async def execute(self) -> None:
        self.browser = await nodriver.start(browser_args=["--headless=true"])
        self.tab = self.browser.main_tab
        self.tab.add_handler(cdp.fetch.RequestPaused, self.request_paused_handler)
        self.tab = await self.browser.get("https://open.spotify.com/")
        await asyncio.sleep(20)

    async def main(self):
        self.browser_task = self.loop.create_task(self.execute())
        try:
            result = await asyncio.wait_for(self.future, timeout=15.0)
            print(result)
        except asyncio.TimeoutError:
            print("Timed out for token extraction !")
        finally:
            self.browser_task.cancel()


if __name__ == "__main__":
    ex = SpotifyTokenExtractor()
    ex.loop.run_until_complete(ex.main())
