from __future__ import annotations
import asyncio
import time
from typing import Optional


class BrowserSession:
    def __init__(self, channel: str, headless: bool, user_data_dir: str):
        self.channel = channel
        self.headless = headless
        self.user_data_dir = user_data_dir.strip() if user_data_dir else ""
        self._playwright = None
        self._browser = None
        self._context = None
        self.page = None
        self.last_used = time.monotonic()

    async def start(self) -> None:
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()

        if self.user_data_dir:
            # Persistent context — uses real Chrome profile (already logged in)
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                channel=self.channel if self.channel != "chromium" else None,
                headless=self.headless,
                args=["--no-first-run", "--no-default-browser-check"],
            )
            self._browser = None
            self.page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        else:
            kwargs = {"headless": self.headless}
            if self.channel and self.channel != "chromium":
                kwargs["channel"] = self.channel
            self._browser = await self._playwright.chromium.launch(**kwargs)
            self._context = await self._browser.new_context()
            self.page = await self._context.new_page()

    async def close(self) -> None:
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        finally:
            self._playwright = None
            self._browser = None
            self._context = None
            self.page = None

    def touch(self) -> None:
        self.last_used = time.monotonic()

    def idle_seconds(self) -> float:
        return time.monotonic() - self.last_used

    @property
    def alive(self) -> bool:
        return self.page is not None

    async def ensure_alive(self) -> None:
        if not self.alive:
            await self.start()
        self.touch()
