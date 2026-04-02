"""Browser tools — Playwright-based web automation."""

import asyncio
from urllib.parse import urlparse

_playwright = _browser = _page = _loop = _thread = None
_browser_lock = asyncio.Lock()

_GET_LINKS_JS = """
Array.from(document.querySelectorAll(
  'a[href], button, input, textarea, select, [role="button"], [role="link"], [role="tab"]'
)).filter(el => el.offsetParent !== null).slice(0, 50).map((el, i) => {
  const tag = el.tagName.toLowerCase();
  const text = (el.innerText || el.getAttribute('aria-label')
    || el.getAttribute('placeholder') || el.name || '').trim().substring(0, 60);
  const href = el.href || '', type = el.type || '';
  return `[${i}] <${tag}${type ? ' type='+type : ''}> ${text}${href ? ' > '+href.substring(0,80) : ''}`;
}).join('\\n')
"""

def _get_loop():
    """Get or create a dedicated event loop for browser ops."""
    global _loop, _thread
    if _loop is None or _loop.is_closed():
        import threading
        _loop = asyncio.new_event_loop()
        _thread = threading.Thread(target=_loop.run_forever, daemon=True)
        _thread.start()
    return _loop


def _run(coro):
    """Run an async coroutine on the dedicated browser event loop."""
    return asyncio.run_coroutine_threadsafe(coro, _get_loop()).result(timeout=30)


def _read_cdp_ws_url() -> str:
    """Read the WebSocket URL from Chrome's DevToolsActivePort file."""
    import os
    port_file = os.path.expanduser(
        "~/Library/Application Support/Google/Chrome/DevToolsActivePort"
    )
    try:
        with open(port_file) as f:
            lines = f.read().strip().split("\n")
        return f"ws://127.0.0.1:{lines[0]}{lines[1]}"
    except (FileNotFoundError, IndexError):
        return ""


async def _ensure_browser():
    """Connect to user's Chrome via CDP, or launch standalone Chromium as fallback."""
    from playwright.async_api import async_playwright
    global _playwright, _browser, _page
    async with _browser_lock:
        if _browser is None or not _browser.is_connected():
            _playwright = await async_playwright().start()
            # Try connecting to user's Chrome first (requires remote debugging toggle)
            ws_url = _read_cdp_ws_url()
            if not ws_url:
                return None  # No browser available
            _browser = await _playwright.chromium.connect_over_cdp(ws_url, timeout=5000)
            ctx = _browser.contexts[0] if _browser.contexts else await _browser.new_context()
            _page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            print("[Browser] Connected to Chrome via CDP")
        if _page.is_closed():
            ctx = _browser.contexts[0] if _browser.contexts else await _browser.new_context()
            _page = await ctx.new_page()
        return _page


def _validate_url(url: str) -> str | None:
    """Return an error string if the URL scheme is not http/https."""
    if urlparse(url).scheme not in ("http", "https"):
        return f"Blocked URL '{url}': only http and https schemes are allowed."
    return None


# ── Async implementations ─────────────────────────────────────────

async def _browse(url: str) -> str:
    err = _validate_url(url)
    if err:
        return err
    page = await _ensure_browser()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2000)
        text = await page.evaluate("document.body.innerText.substring(0, 3000)")
        return f"Title: {await page.title()}\n{text}"
    except Exception as e:
        return f"Error navigating to {url}: {e}"

async def _click_selector(selector: str) -> str:
    page = await _ensure_browser()
    try:
        await page.click(selector, timeout=5000)
        await page.wait_for_timeout(1000)
        return f"Clicked '{selector}'. Page: {await page.title()}"
    except Exception as e:
        return f"Error clicking '{selector}': {e}"

async def _type_in(selector: str, text: str) -> str:
    page = await _ensure_browser()
    try:
        await page.fill(selector, text, timeout=5000)
        return f"Typed '{text[:40]}' into '{selector}'."
    except Exception as e:
        return f"Error typing into '{selector}': {e}"

async def _read_page() -> str:
    page = await _ensure_browser()
    try:
        text = await page.evaluate("document.body.innerText.substring(0, 4000)")
        return f"URL: {page.url}\nTitle: {await page.title()}\n{text}"
    except Exception as e:
        return f"Error reading page: {e}"

async def _chrome_js(code: str) -> str:
    page = await _ensure_browser()
    try:
        result = await page.evaluate(code)
        return str(result)[:2000] if result else "OK"
    except Exception as e:
        return f"Error: {e}"

async def _get_links() -> str:
    page = await _ensure_browser()
    try:
        links = await page.evaluate(_GET_LINKS_JS)
        return f"Interactive elements on page:\n{links}"
    except Exception as e:
        return f"Error: {e}"

async def _click_text(text: str) -> str:
    page = await _ensure_browser()
    try:
        await page.get_by_text(text, exact=False).first.click(timeout=5000)
        await page.wait_for_timeout(1000)
        return f"Clicked text '{text}'. Page: {await page.title()}"
    except Exception as e:
        return f"Error clicking text '{text}': {e}"

async def _search(query: str) -> str:
    """Search Google and return top 5 results."""
    from urllib.parse import quote_plus
    page = await _ensure_browser()
    try:
        url = f"https://www.google.com/search?q={quote_plus(query)}"
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2000)
        results = await page.evaluate("""
            Array.from(document.querySelectorAll('div.g')).slice(0, 5).map(el => {
                const a = el.querySelector('a');
                const h3 = el.querySelector('h3');
                const snippet = el.querySelector('[data-sncf], .VwiC3b, [style*="-webkit-line-clamp"]');
                return {
                    title: h3 ? h3.innerText.trim() : '',
                    url: a ? a.href : '',
                    snippet: snippet ? snippet.innerText.trim() : ''
                };
            }).filter(r => r.title)
        """)
        if not results:
            return f"No results found for '{query}'."
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}\n   {r['snippet']}\n   {r['url']}")
        return f"Search results for '{query}':\n\n" + "\n\n".join(lines)
    except Exception as e:
        return f"Error searching for '{query}': {e}"


# ── Sync wrappers (called by TOOL_DISPATCH) ──────────────────────

def tool_browse(url: str) -> str:          return _run(_browse(url))
def tool_browser_click(s: str) -> str:     return _run(_click_selector(s))
def tool_browser_type(s: str, t: str):     return _run(_type_in(s, t))
def tool_read_page() -> str:               return _run(_read_page())
def tool_chrome_js(code: str) -> str:      return _run(_chrome_js(code))
def tool_get_links() -> str:               return _run(_get_links())
def tool_click_text(text: str) -> str:     return _run(_click_text(text))
def tool_search(query: str) -> str:        return _run(_search(query))

async def _cleanup_browser():
    """Close browser and Playwright instance."""
    global _playwright, _browser, _page
    if _browser:
        try: await _browser.close()
        except Exception: pass
        _browser = _page = None
    if _playwright:
        try: await _playwright.stop()
        except Exception: pass
        _playwright = None

def cleanup_browser():
    """Sync wrapper to close browser resources."""
    if _loop and not _loop.is_closed():
        try: asyncio.run_coroutine_threadsafe(_cleanup_browser(), _loop).result(timeout=5)
        except Exception: pass
