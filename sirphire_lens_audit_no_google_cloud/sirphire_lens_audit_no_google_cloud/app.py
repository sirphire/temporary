import pandas as pd
import streamlit as st

from scraper import extract_product_links_from_category_js, run_batch
from sheet_api import SheetAPI

st.set_page_config(page_title="Sirphire Lens Rings Audit", layout="wide")

st.title("Sirphire Product Audit — Camera Lens Protector Rings")
st.caption("No Google Cloud setup. Streamlit talks to Google Sheet using Apps Script Web App.")

with st.sidebar:
    st.header("Google Sheet API")
    webapp_url = st.text_input("Apps Script Web App URL", value="")
    api_key = st.text_input("API key/password", value="", type="password")

    st.divider()
    st.header("Scraper Settings")
    batch_size = st.number_input("Products per run", min_value=1, max_value=100, value=10)
    delay_seconds = st.number_input("Delay between product pages / seconds", min_value=0.5, max_value=20.0, value=1.5, step=0.5)
    max_products_per_category = st.number_input("Max products per category", min_value=8, max_value=2000, value=500, step=50)

    st.divider()
    st.subheader("Import category URLs")
    category_urls_text = st.text_area(
        "One category URL per line",
        value="https://in.sirphire.com/iphone-17-back-covers",
        height=120,
    )

if not webapp_url:
    st.info("Apps Script Web App URL paste karo.")
    st.stop()

sheet = SheetAPI(webapp_url=webapp_url, api_key=api_key)

try:
    sheet.setup()
except Exception as exc:
    st.error(f"Sheet API connect nahi ho paayi: {exc}")
    st.stop()

try:
    s = sheet.stats().get("stats", {})
except Exception as exc:
    st.error(f"Stats read error: {exc}")
    st.stop()

col_a, col_b, col_c, col_d = st.columns(4)
col_a.metric("Total URLs", s.get("total", 0))
col_b.metric("Done", s.get("done", 0))
col_c.metric("Found", s.get("found", 0))
col_d.metric("Not Found", s.get("not_found", 0))

err_col, pend_col = st.columns(2)
err_col.metric("Errors", s.get("errors", 0))
pend_col.metric("Pending", s.get("pending", 0))

st.divider()

left, right = st.columns([1, 1])

with left:
    if st.button("Import products from category URLs", type="secondary"):
        category_urls = [u.strip() for u in category_urls_text.splitlines() if u.strip()]
        total_added = 0
        progress = st.progress(0)

        for idx, category_url in enumerate(category_urls, start=1):
            try:
                with st.spinner(f"Importing category {idx}/{len(category_urls)}: {category_url}"):
                    rows = extract_product_links_from_category_js(
                        category_url=category_url,
                        max_products=int(max_products_per_category),
                    )
                    result = sheet.append_urls(rows)
                    added = result.get("added", 0)
                    total_added += added

                st.success(f"{category_url}: {len(rows)} product URLs found, {added} new URLs added")
            except Exception as exc:
                st.error(f"{category_url}: import error: {exc}")

            progress.progress(idx / len(category_urls))

        st.info(f"Total new URLs added: {total_added}")

with right:
    uploaded = st.file_uploader("Optional: product URLs CSV upload", type=["csv"])
    if uploaded and st.button("Import CSV URLs"):
        df = pd.read_csv(uploaded)
        if "url" not in df.columns:
            st.error("CSV me `url` column required hai.")
        else:
            rows = []
            for _, r in df.iterrows():
                rows.append({
                    "url": str(r.get("url", "")).strip(),
                    "category": str(r.get("category", "")),
                    "title": str(r.get("title", "")),
                    "status": "PENDING",
                })
            result = sheet.append_urls(rows)
            st.success(f"{result.get('added', 0)} new URLs added from CSV")

st.divider()

c1, c2, c3 = st.columns(3)

if c1.button("▶️ Resume / Run next batch", type="primary"):
    try:
        processed, last_url = run_batch(
            sheet_api=sheet,
            batch_size=int(batch_size),
            delay_seconds=float(delay_seconds),
        )
        if processed:
            st.success(f"{processed} products checked. Last URL: {last_url}")
        else:
            st.info("Pending URL nahi mila. Kaam complete lag raha hai.")
    except Exception as exc:
        st.error(f"Batch error: {exc}")

if c2.button("⏸️ Pause"):
    st.warning("Paused. Resume karne par next PENDING/ERROR row se continue hoga.")

if c3.button("Refresh stats/table"):
    st.rerun()

st.subheader("Sheet preview")
try:
    records = sheet.get_records(limit=500).get("records", [])
    if records:
        st.dataframe(pd.DataFrame(records), use_container_width=True, height=450)
    else:
        st.info("Abhi sheet me koi product URL nahi hai.")
except Exception as exc:
    st.error(f"Preview read error: {exc}")
