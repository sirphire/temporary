import pandas as pd
import streamlit as st

from scraper import check_products_parallel, collect_category_products
from sheet_webapp import SheetWebApp

st.set_page_config(
    page_title="Sirphire Camera Lens Audit",
    layout="wide",
)

st.title("Sirphire Camera Lens Add-on Checker")
st.caption("Category URL do, products check honge, result Google Sheet me save hota jayega.")

with st.sidebar:
    st.header("Google Sheet")
    webapp_url = st.text_input("Google Sheet Web App URL", value="")

    st.header("Input")
    category_url = st.text_input(
        "Category URL",
        value="https://in.sirphire.com/apple-iphone-16-back-covers",
    )

    st.header("Speed")
    max_products = st.number_input("Max products collect from category", min_value=10, max_value=10000, value=1000, step=100)
    batch_size = st.number_input("Products per resume click", min_value=1, max_value=500, value=100, step=10)
    workers = st.number_input("Parallel workers", min_value=1, max_value=30, value=10, step=1)

if not webapp_url:
    st.info("Pehle Google Sheet Web App URL paste karo.")
    st.stop()

if not category_url:
    st.info("Category URL paste karo.")
    st.stop()

sheet = SheetWebApp(webapp_url)

try:
    sheet.setup()
    sheet.reset_stuck()
except Exception as exc:
    st.error(f"Google Sheet connect nahi ho rahi: {exc}")
    st.stop()

try:
    stats = sheet.stats(category_url).get("stats", {})
except Exception as exc:
    st.error(f"Stats load error: {exc}")
    st.stop()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total", stats.get("total", 0))
c2.metric("Pending", stats.get("pending", 0))
c3.metric("Done", stats.get("done", 0))
c4.metric("Found", stats.get("found", 0))
c5.metric("Not Found", stats.get("not_found", 0))

st.divider()

a, b, c = st.columns(3)

with a:
    if st.button("1️⃣ Collect product URLs from category", type="secondary", use_container_width=True):
        with st.spinner("Category open ho rahi hai, JS products load/scroll ho rahe hain..."):
            try:
                products = collect_category_products(category_url, max_products=int(max_products))
                result = sheet.add_products(category_url, products)
                st.success(f"{len(products)} URLs found. {result.get('added', 0)} new URLs sheet me add hue.")
            except Exception as exc:
                st.error(f"Category collect error: {exc}")

with b:
    if st.button("▶️ Resume / Process next batch", type="primary", use_container_width=True):
        try:
            claimed = sheet.claim_batch(category_url, int(batch_size)).get("rows", [])

            if not claimed:
                st.info("Pending products nahi mile. Category complete lag rahi hai.")
            else:
                progress = st.progress(0)
                status_box = st.empty()

                status_box.info(f"{len(claimed)} products claim hue. Parallel checking start...")

                results = check_products_parallel(claimed, workers=int(workers))
                sheet.update_results(results)

                progress.progress(1.0)
                found = sum(1 for r in results if r.get("lens_rings") == "FOUND")
                not_found = sum(1 for r in results if r.get("lens_rings") == "NOT_FOUND")
                errors = sum(1 for r in results if r.get("status") == "ERROR")

                st.success(f"Batch done: FOUND={found}, NOT_FOUND={not_found}, ERROR={errors}")

        except Exception as exc:
            st.error(f"Batch processing error: {exc}")

with c:
    if st.button("⏸️ Pause / Refresh", use_container_width=True):
        st.info("Paused. Resume click karoge to next PENDING/ERROR se continue hoga.")
        st.rerun()

st.divider()

st.subheader("Recent Sheet Records")
try:
    records = sheet.records(category_url, limit=500).get("records", [])
    if records:
        df = pd.DataFrame(records)
        st.dataframe(df, use_container_width=True, height=500)
    else:
        st.info("Is category ke records abhi sheet me nahi hain.")
except Exception as exc:
    st.error(f"Records load error: {exc}")
