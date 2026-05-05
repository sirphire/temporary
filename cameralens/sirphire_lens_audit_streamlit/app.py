import pandas as pd
import streamlit as st

from google_sheets import (
    append_urls,
    get_records,
    next_pending_row,
    open_sheet,
    stats,
    update_result,
)
from scraper import extract_product_links_from_category, run_batch

st.set_page_config(page_title="Sirphire Lens Rings Audit", layout="wide")

st.title("Sirphire Product Audit — Camera Lens Protector Rings")
st.caption("Resume/Pause friendly scraper using Google Sheets as the source of truth.")

if "paused" not in st.session_state:
    st.session_state.paused = True

with st.sidebar:
    st.header("Settings")
    sheet_url = st.text_input("Google Sheet URL or ID", value="")
    worksheet_name = st.text_input("Worksheet name", value="products")
    batch_size = st.number_input("Products per run", min_value=1, max_value=100, value=10)
    delay_seconds = st.number_input("Delay between product pages / seconds", min_value=0.5, max_value=20.0, value=1.5, step=0.5)

    st.divider()
    st.subheader("Import category URLs")
    category_urls_text = st.text_area(
        "One category URL per line",
        value="https://in.sirphire.com/iphone-17-back-covers",
        height=120,
    )
    use_js = st.checkbox("Use JS browser import for categories", value=True)
    max_products_per_category = st.number_input("Max products per category", min_value=8, max_value=2000, value=500, step=50)

if not sheet_url:
    st.info("Google Sheet URL/ID add karo. Sheet service-account email ke saath share honi chahiye.")
    st.stop()

try:
    ws = open_sheet(sheet_url, worksheet_name)
except Exception as exc:
    st.error(f"Google Sheet open nahi ho paayi: {exc}")
    st.stop()

col_a, col_b, col_c, col_d = st.columns(4)

s = stats(ws)
col_a.metric("Total URLs", s["total"])
col_b.metric("Done", s["done"])
col_c.metric("Found", s["found"])
col_d.metric("Not Found", s["not_found"])

err_col, pend_col = st.columns(2)
err_col.metric("Errors", s["errors"])
pend_col.metric("Pending", s["pending"])

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
                    rows = extract_product_links_from_category(
                        category_url,
                        use_js=use_js,
                        max_products=int(max_products_per_category),
                    )
                    added = append_urls(ws, rows)
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
            added = append_urls(ws, rows)
            st.success(f"{added} new URLs added from CSV")

st.divider()

c1, c2, c3 = st.columns(3)

if c1.button("▶️ Resume / Run next batch", type="primary"):
    st.session_state.paused = False
    processed, last_url = run_batch(
        ws=ws,
        next_pending_row_func=next_pending_row,
        update_result_func=update_result,
        batch_size=int(batch_size),
        delay_seconds=float(delay_seconds),
    )
    st.session_state.paused = True
    if processed:
        st.success(f"{processed} products checked. Last URL: {last_url}")
    else:
        st.info("Pending URL nahi mila. Kaam complete lag raha hai.")

if c2.button("⏸️ Pause"):
    st.session_state.paused = True
    st.warning("Paused. Resume karne par next PENDING/ERROR row se continue hoga.")

if c3.button("Refresh stats/table"):
    st.rerun()

st.subheader("Sheet preview")
records = get_records(ws)
if records:
    df = pd.DataFrame(records)
    st.dataframe(df, use_container_width=True, height=450)
else:
    st.info("Abhi sheet me koi product URL nahi hai.")
