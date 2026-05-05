import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config import PRODUCT_URL_PATTERNS, TARGET_TEXT, USER_AGENT


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def normalize_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href).split("?")[0].split("#")[0].rstrip("/")


def is_product_url(url: str) -> bool:
    low = url.lower()
    return any(pattern in low for pattern in PRODUCT_URL_PATTERNS)


def ensure_playwright_browser():
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


def click_load_more_if_exists(page) -> bool:
    texts = [
        "Load More",
        "Load more",
        "View More",
        "View more",
        "Show More",
        "Show more",
        "More Products",
        "more products",
    ]

    for text in texts:
        try:
            btn = page.get_by_text(text, exact=False).last
            if btn.is_visible(timeout=700):
                btn.click(timeout=3000)
                return True
        except Exception:
            pass

    try:
        locators = page.locator("button, a, div[role='button']").all()
        for item in locators:
            try:
                txt = clean_text(item.inner_text(timeout=300)).lower()
                if any(x in txt for x in ["load more", "view more", "show more", "more products"]):
                    if item.is_visible(timeout=300):
                        item.click(timeout=3000)
                        return True
            except Exception:
                continue
    except Exception:
        pass

    return False


def collect_category_products(category_url: str, max_products: int = 1000, max_rounds: int = 120) -> list[dict]:
    """
    Category page me sirf 8 products static hote hain, baaki JS/load-more se.
    Ye function browser open karke scroll/click karta hai aur product URLs collect karta hai.
    """
    ensure_playwright_browser()

    from playwright.sync_api import sync_playwright

    products = []
    seen = set()
    stable_rounds = 0
    previous_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 900},
            locale="en-IN",
        )
        page = context.new_page()
        page.goto(category_url, wait_until="networkidle", timeout=90000)

        for _ in range(max_rounds):
            hrefs = page.eval_on_selector_all(
                "a[href]",
                """els => els.map(a => ({
                    href: a.href,
                    text: (a.innerText || a.getAttribute('aria-label') || '').trim()
                }))"""
            )

            for item in hrefs:
                url = normalize_url(category_url, item.get("href", ""))
                if not is_product_url(url):
                    continue
                if url in seen:
                    continue

                seen.add(url)
                products.append({
                    "url": url,
                    "title": clean_text(item.get("text", "")),
                })

            if len(products) >= max_products:
                break

            clicked = click_load_more_if_exists(page)

            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(900)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1200)

            if len(products) == previous_count and not clicked:
                stable_rounds += 1
            else:
                stable_rounds = 0

            previous_count = len(products)

            # Enough stable checks; assume category completed
            if stable_rounds >= 7:
                break

        context.close()
        browser.close()

    return products[:max_products]


def fetch_html(url: str, timeout: int = 25) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def check_one_product(row: dict) -> dict:
    row_number = row.get("_row_number")
    url = str(row.get("url", "")).strip()

    result = {
        "_row_number": row_number,
        "url": url,
        "title": row.get("title", ""),
        "lens_rings": "",
        "status": "ERROR",
        "checked_at": now_utc(),
        "error": "",
    }

    try:
        html = fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        text = clean_text(soup.get_text(" "))

        title = ""
        h1 = soup.find("h1")
        if h1:
            title = clean_text(h1.get_text(" "))
        elif soup.title:
            title = clean_text(soup.title.get_text(" "))

        result["title"] = title or result["title"]
        result["lens_rings"] = "FOUND" if TARGET_TEXT.lower() in text.lower() else "NOT_FOUND"
        result["status"] = "DONE"
        result["error"] = ""

    except Exception as exc:
        result["status"] = "ERROR"
        result["error"] = str(exc)[:500]

    return result


def check_products_parallel(rows: list[dict], workers: int = 8) -> list[dict]:
    if not rows:
        return []

    workers = max(1, min(int(workers), 30))
    results = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(check_one_product, row) for row in rows]
        for future in as_completed(futures):
            results.append(future.result())

    return results
