import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config import DEFAULT_DELAY_SECONDS, TARGET_TEXT, USER_AGENT


PRODUCT_URL_PATTERNS = (
    "-back-cover",
    "/products/",
)


def fetch_html(url: str, timeout: int = 30) -> str:
    """
    Fetch a public page politely. If the website blocks scraping with 403,
    this function raises an error instead of bypassing protection.
    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def looks_like_product_url(url: str) -> bool:
    url_l = url.lower()
    return any(pattern in url_l for pattern in PRODUCT_URL_PATTERNS)


def normalize_url(base_url: str, href: str) -> str:
    full_url = urljoin(base_url, href).split("?")[0].split("#")[0].rstrip("/")
    return full_url


def extract_product_links_from_html(category_url: str, html: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")

    rows = []
    seen = set()

    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        if not href:
            continue

        full_url = normalize_url(category_url, href)

        if not looks_like_product_url(full_url):
            continue

        title = clean_text(a.get_text(" "))
        if not title:
            img = a.find("img")
            title = clean_text(img.get("alt", "")) if img else ""

        if full_url not in seen:
            seen.add(full_url)
            rows.append({
                "url": full_url,
                "category": category_url,
                "title": title,
                "status": "PENDING",
            })

    return rows


def extract_product_links_from_category_static(category_url: str) -> List[Dict[str, str]]:
    html = fetch_html(category_url)
    return extract_product_links_from_html(category_url, html)


def _ensure_playwright_browser():
    """
    Streamlit Cloud/local machines sometimes have Playwright installed but not Chromium.
    This tries to install Chromium once when missing. If installation is blocked,
    the caller will receive the original error.
    """
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return
    except Exception:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _click_possible_load_more(page) -> bool:
    """
    Tries common load-more button text. Returns True if a visible button was clicked.
    """
    button_texts = [
        "Load More",
        "Load more",
        "Show More",
        "Show more",
        "View More",
        "View more",
        "More Products",
        "more products",
    ]

    for text in button_texts:
        try:
            locator = page.get_by_text(text, exact=False).last
            if locator and locator.is_visible(timeout=800):
                locator.click(timeout=3000)
                return True
        except Exception:
            pass

    # Generic button/link selectors that sometimes contain the text inside spans
    try:
        candidates = page.locator("button, a, div[role='button']").all()
        for c in candidates:
            try:
                txt = clean_text(c.inner_text(timeout=300)).lower()
                if any(x in txt for x in ["load more", "show more", "view more", "more products"]):
                    if c.is_visible(timeout=300):
                        c.click(timeout=3000)
                        return True
            except Exception:
                continue
    except Exception:
        pass

    return False


def extract_product_links_from_category_js(
    category_url: str,
    max_products: int = 500,
    max_rounds: int = 80,
    wait_ms: int = 1500,
) -> List[Dict[str, str]]:
    """
    JS-rendered category scraper:
    - opens the category in headless Chromium
    - scrolls down
    - clicks common "Load more/View more" controls
    - stops after product count stays stable for several rounds
    """
    _ensure_playwright_browser()

    from playwright.sync_api import sync_playwright

    seen = set()
    rows = []
    stable_rounds = 0
    last_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 900},
            locale="en-IN",
        )
        page = context.new_page()
        page.goto(category_url, wait_until="networkidle", timeout=60000)

        for _ in range(max_rounds):
            # Collect links visible/loaded so far
            hrefs = page.eval_on_selector_all(
                "a[href]",
                """els => els.map(a => ({
                    href: a.href,
                    text: (a.innerText || a.getAttribute('aria-label') || '').trim()
                }))"""
            )

            for item in hrefs:
                full_url = normalize_url(category_url, item.get("href", ""))
                if not looks_like_product_url(full_url):
                    continue
                if full_url in seen:
                    continue
                seen.add(full_url)
                rows.append({
                    "url": full_url,
                    "category": category_url,
                    "title": clean_text(item.get("text", "")),
                    "status": "PENDING",
                })

            if len(rows) >= max_products:
                break

            clicked = _click_possible_load_more(page)

            # Scroll to bottom to trigger lazy/infinite loading
            page.mouse.wheel(0, 2500)
            page.wait_for_timeout(wait_ms)

            # Also jump close to bottom; some themes trigger on scroll position
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(wait_ms)

            if len(rows) == last_count and not clicked:
                stable_rounds += 1
            else:
                stable_rounds = 0

            last_count = len(rows)

            # Stop only after multiple stable rounds so slow JS has time
            if stable_rounds >= 6:
                break

        context.close()
        browser.close()

    return rows


def extract_product_links_from_category(
    category_url: str,
    use_js: bool = True,
    max_products: int = 500,
) -> List[Dict[str, str]]:
    """
    Main category import function. For Sirphire, use_js=True is recommended
    because category pages may initially show only ~8 products and load the rest via JS.
    """
    if use_js:
        return extract_product_links_from_category_js(
            category_url=category_url,
            max_products=max_products,
        )

    return extract_product_links_from_category_static(category_url)


def check_product_page(product_url: str) -> Dict[str, str]:
    """
    Checks whether the product page contains the exact add-on text:
    Add Camera Lens Protector Rings

    Product pages are usually server-rendered enough for this text check.
    If product pages also become JS-only, this can be extended with Playwright too.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    try:
        html = fetch_html(product_url)
        soup = BeautifulSoup(html, "lxml")
        page_text = clean_text(soup.get_text(" "))

        title = ""
        h1 = soup.find("h1")
        if h1:
            title = clean_text(h1.get_text(" "))
        if not title and soup.title:
            title = clean_text(soup.title.get_text(" "))

        found = TARGET_TEXT.lower() in page_text.lower()

        return {
            "title": title,
            "lens_rings": "FOUND" if found else "NOT_FOUND",
            "status": "DONE",
            "checked_at": now,
            "error": "",
        }
    except Exception as exc:
        return {
            "lens_rings": "",
            "status": "ERROR",
            "checked_at": now,
            "error": str(exc)[:500],
        }


def run_batch(ws, next_pending_row_func, update_result_func, batch_size: int = 10, delay_seconds: float = DEFAULT_DELAY_SECONDS):
    processed = 0
    last_url = ""

    for _ in range(batch_size):
        item = next_pending_row_func(ws)
        if not item:
            break

        row_number, record = item
        url = str(record.get("url", "")).strip()
        if not url:
            break

        result = check_product_page(url)
        update_result_func(ws, row_number, result)

        processed += 1
        last_url = url
        time.sleep(delay_seconds)

    return processed, last_url
