# Sirphire Lens Rings Audit

Streamlit + Python scraper jo Sirphire product pages check karta hai ki page me **Add Camera Lens Protector Rings** add-on present hai ya nahi. Result Google Sheet me save hota hai:

- `FOUND`
- `NOT_FOUND`
- `ERROR`
- `PENDING`

Google Sheet hi resume state hai, isliye app band hone ke baad bhi next run wahi se continue karega.

## Important for Sirphire category pages

Sirphire category pages me kuch products static HTML me dikhte hain, aur baaki products JavaScript / lazy loading / load-more se aate hain. Is project me category import ke liye Playwright headless Chromium support add hai:

- page open karta hai
- scroll karta hai
- `Load More`, `View More`, `Show More` buttons click karne ki koshish karta hai
- jab product count stable ho jaye tab URLs Google Sheet me add karta hai

App me checkbox hai:

```text
Use JS browser import for categories
```

Isko ON rakho.

## 1. Google Sheet setup

Create a Google Sheet with worksheet name:

```text
products
```

Sheet headers app khud bana dega:

```text
url | category | title | lens_rings | status | checked_at | error
```

## 2. Google Cloud service account

1. Google Cloud Console me project banao.
2. Google Sheets API aur Google Drive API enable karo.
3. Service Account banao.
4. JSON key download karo.
5. Apni Google Sheet ko service account ke `client_email` ke saath **Editor** access me share karo.

## 3. Local install

```bash
git clone https://github.com/YOUR_USERNAME/sirphire-lens-audit.git
cd sirphire-lens-audit
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

Create `.streamlit/secrets.toml`:

```toml
[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\nYOUR_KEY\n-----END PRIVATE KEY-----\n"
client_email = "your-service-account@your-project.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

Run:

```bash
streamlit run app.py
```

## 4. Streamlit Cloud deploy

1. Code GitHub repo me push karo.
2. Streamlit Cloud me New App select karo.
3. `app.py` choose karo.
4. App secrets me same `secrets.toml` content paste karo.
5. `packages.txt` repo me included hai for Playwright Linux dependencies.
6. Deploy.

Note: first category import par app Playwright Chromium install karne ki koshish karega if missing. Agar Streamlit Cloud environment me browser install fail ho, local machine/VPS deployment recommended hai.

## 5. Kaise use karna hai

1. App me Google Sheet URL paste karo.
2. Category URLs add karo, e.g.

```text
https://in.sirphire.com/iphone-17-back-covers
https://in.sirphire.com/iphone-17-pro-max-back-covers
```

3. `Use JS browser import for categories` ON rakho.
4. `Max products per category` 500 ya 1000 set karo.
5. **Import products from category URLs** click karo.
6. **Resume / Run next batch** click karo.
7. App next pending rows process karega.
8. Ruk gaya to dobara same button click karo. Starting se nahi chalega.

## 6. Google Sheet as resume state

Every product URL has a `status`.

- blank / `PENDING`: not checked yet
- `DONE`: checked
- `ERROR`: failed, retryable

Resume button next `PENDING` or `ERROR` row se continue karta hai.

## 7. If product pages are also JS-only

Current product check normal HTML text fetch se karta hai. Agar product pages par lens option JavaScript ke baad hi show hota hai, then `check_product_page()` ko bhi Playwright mode me convert karna hoga. Structure already ready hai; category import Playwright se ho raha hai.

## Important notes

- Yeh scraper public page content check karta hai.
- Website protection bypass nahi karta.
- Delay ko high rakho, e.g. 1.5–3 seconds, taaki website par load kam rahe.
- Agar category import incomplete aaye, `Max products per category` badhao aur phir import dubara run karo; duplicate URLs add nahi honge.
