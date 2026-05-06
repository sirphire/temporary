import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config import TARGET_TEXT, USER_AGENT


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def normalize_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href).split("?")[0].split("#")[0].rstrip("/")


def get_category_slug(category_url: str) -> str:
    """
    Example:
    https://in.sirphire.com/apple-iphone-16-back-covers
    -> apple-iphone-16-back-covers
    """
    return urlparse(category_url).path.strip("/").lower().rstrip("/")


def get_category_model_keywords(category_url: str) -> list[str]:
    """
    Example:
    apple-iphone-16-back-covers
    -> ["iphone", "16"]

    Ye keywords product URL me hone chahiye.
    """
    slug = get_category_slug(category_url)
    tokens = re.split(r"[^a-z0-9]+", slug)

    stop_words = {
        "apple",
        "mobile",
        "phone",
        "case",
        "cases",
        "cover",
        "covers",
        "back",
        "backcover",
        "backcovers",
        "collection",
        "collections",
    }

    keywords = []
    for token in tokens:
        if not token or token in stop_words:
            continue
        keywords.append(token)

    return keywords


def is_product_url_for_category(url: str, category_url: str) -> bool:
    """
    Sirf current category ke product pages allow karega.

    Allow:
    https://in.sirphire.com/batman-iphone-16-back-cover

    Reject:
    https://in.sirphire.com/apple-iphone-16-back-covers
    https://in.sirphire.com/nothing-phone-3-back-covers
    https://in.sirphire.com/google-pixel-8-back-covers
    """
    low = url.lower().split("?")[0].split("#")[0].rstrip("/")

    # Listing/category pages reject
    if low.endswith("-back-covers"):
        return False

    # Product page must be singular
    if not low.endswith("-back-cover"):
        return False

    # Same domain only
    category_domain = urlparse(category_url).netloc.lower()
    product_domain = urlparse(low).netloc.lower()
    if category_domain and product_domain and category_domain != product_domain:
        return False

    # Product URL me category model keywords hone chahiye
    keywords = get_category_model_keywords(category_url)
    if keywords and not all(keyword in low for keyword in keywords):
        return False

    return True


def fetch_html(url: str, timeout: int = 25) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def extract_links_from_html(category_url: str, html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    products = []
    seen = set()

    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        if not href:
            continue

        url = normalize_url(category_url, href)

        if not is_product_url_for_category(url, category_url):
            continue

        if url in seen:
            continue

        seen.add(url)

        title = clean_text(a.get_text(" "))
        if not title:
            img = a.find("img")
            if img:
                title = clean_text(img.get("alt", ""))

        products.append({
            "url": url,
            "title": title,
        })

    return products


def collect_products_from_sitemap(category_url: str, max_products: int = 1000) -> list[dict]:
    """
    Abhi disabled rakha hai, kyunki sitemap se doosri categories aa rahi thi.
    Sirf category HTML se products collect honge.
    """
    return []


def collect_category_products(category_url: str, max_products: int = 1000, max_rounds: int = 120) -> list[dict]:
    """
    Browser/Playwright use nahi hota.
    Sirf current category page ke HTML se matching product URLs nikalega.
    """
    products = []
    seen = set()

    try:
        html = fetch_html(category_url, timeout=40)
        for product in extract_links_from_html(category_url, html):
            if product["url"] not in seen:
                seen.add(product["url"])
                products.append(product)

            if len(products) >= max_products:
                break
    except Exception:
        pass

    return products[:max_products]


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
