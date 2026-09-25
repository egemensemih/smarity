"""Başsız (headless) Chrome ile HTML → görsel.

Kapaklar, Instagram post/story görselleri ve yedek 3D görseller burada üretilir.
GitHub'ın Ubuntu makinelerinde Google Chrome hazır gelir; yoksa Playwright'ın
Chromium'u bir kez indirilir.
"""
from __future__ import annotations

import base64
import io
import subprocess
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image

from .config import ROOT
from .util import log

GL_ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
           "--font-render-hinting=none", "--disable-lcd-text"]


class RenderError(RuntimeError):
    pass


class Renderer:
    def __init__(self, cache_dir: Path):
        self.cache = cache_dir
        self.cache.mkdir(parents=True, exist_ok=True)
        self._pw = None
        self._browser = None
        self.env = Environment(loader=FileSystemLoader(str(ROOT / "templates" / "cards")),
                               autoescape=select_autoescape(["html"]))
        self.env.globals["font_dir"] = (ROOT / "assets" / "fonts").as_uri()
        # Marka logosu (kartlarda): renkli, koyu zemin için açık renkli; maske olarak da kullanılabilsin diye data URI
        for key, name in (("logo_uri", "logo.svg"), ("logo_light_uri", "logo-light.svg")):
            f = ROOT / "static" / name
            self.env.globals[key] = ("data:image/svg+xml;base64," + base64.b64encode(f.read_bytes()).decode()) if f.exists() else ""

    # ── tarayıcı ────────────────────────────────────────────
    def _launch(self):
        if self._browser:
            return self._browser
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        attempts = [dict(), dict(channel="chrome")]
        for i, kw in enumerate(attempts + [None]):
            if kw is None:
                log.info("Chromium indiriliyor (tek seferlik)…")
                subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
                kw = dict()
            try:
                self._browser = self._pw.chromium.launch(args=GL_ARGS, **kw)
                return self._browser
            except Exception as e:  # noqa: BLE001
                log.debug("Tarayıcı açılamadı (%s): %s", kw, e)
        raise RenderError("Tarayıcı başlatılamadı")

    def close(self):
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:  # noqa: BLE001
            pass
        self._browser = self._pw = None

    def _page(self, w: int, h: int):
        b = self._launch()
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1)
        return ctx, ctx.new_page()

    # ── HTML şablonu → JPEG ─────────────────────────────────
    def html_to_image(self, template: str, ctx: dict, size: tuple[int, int], out: Path,
                      quality: int = 88) -> Path:
        w, h = size
        html = self.env.get_template(template).render(**ctx, W=w, H=h)
        page_file = self.cache / f"_render_{w}x{h}.html"
        page_file.write_text(html, encoding="utf-8")
        bctx, page = self._page(w, h)
        try:
            page.goto(page_file.as_uri(), wait_until="load", timeout=45000)
            page.evaluate("document.fonts.ready.then(() => true)")
            page.wait_for_function("window.__ready === true", timeout=20000)
            png = page.screenshot(type="png", clip={"x": 0, "y": 0, "width": w, "height": h})
        finally:
            bctx.close()
        out.parent.mkdir(parents=True, exist_ok=True)
        img = Image.open(io.BytesIO(png)).convert("RGB")
        img.save(out, "JPEG", quality=quality, optimize=True, progressive=True)
        return out

    # ── yedek 3D stüdyo görseli ────────────────────────────
    def studio_art(self, seed: float, comp: int, colors: dict, size: tuple[int, int]) -> Image.Image:
        w, h = size
        html = self.env.get_template("studio.html").render(w=w, h=h, seed=f"{seed:.3f}", comp=comp, **colors)
        page_file = self.cache / "_studio.html"
        page_file.write_text(html, encoding="utf-8")
        bctx, page = self._page(w, h)
        try:
            page.goto(page_file.as_uri(), wait_until="load", timeout=120000)
            page.wait_for_function("document.title !== ''", timeout=180000)
            title = page.title()
            if title != "done":
                raise RenderError(f"3D görsel üretilemedi: {title[:200]}")
            data = page.evaluate("window.__png")
        finally:
            bctx.close()
        raw = base64.b64decode(data.split(",", 1)[1])
        return Image.open(io.BytesIO(raw)).convert("RGB")
