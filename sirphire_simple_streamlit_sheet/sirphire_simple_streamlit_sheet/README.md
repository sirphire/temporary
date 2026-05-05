# Sirphire Camera Lens Add-on Checker

Simple setup:

```text
GitHub + Streamlit + Google Sheet
```

No Google Cloud. No service account. No secret JSON.

Google Sheet me save karne ke liye Sheet ke andar Apps Script Web App use hota hai.

## Work flow

1. Streamlit app me category URL paste karo.
2. App category page open karega.
3. JS/load-more products collect karega.
4. Products Google Sheet me PENDING save honge.
5. Resume button se products parallel check honge.
6. Result Google Sheet me save hoga:
   - FOUND
   - NOT_FOUND
   - ERROR
7. Pause karna ho to bas next batch mat chalana.
8. Resume karoge to next PENDING/ERROR se continue hoga.

## Google Sheet setup

Sheet open karo:

```text
Extensions -> Apps Script
```

`apps_script_code.gs` ka code paste karo.

Deploy:

```text
Deploy -> New deployment -> Web app
Execute as: Me
Who has access: Anyone
```

Deploy ke baad Web App URL copy karo.

## Streamlit setup

Streamlit app me paste karo:

```text
Google Sheet Web App URL
```

Category URL example:

```text
https://in.sirphire.com/apple-iphone-16-back-covers
```

## Streamlit Cloud

Repo me ye files honi chahiye:

```text
app.py
scraper.py
sheet_webapp.py
config.py
requirements.txt
packages.txt
apps_script_code.gs
```

Main file path:

```text
app.py
```

Agar subfolder me rakha hai, e.g.

```text
cameralens/sirphire_simple_streamlit_sheet/app.py
```

to Streamlit Cloud me wahi full path dena.

## Speed

Default:

```text
Products per resume click: 100
Parallel workers: 10
```

Agar site apni hai aur load handle kar sakti hai:

```text
Products per resume click: 200
Parallel workers: 20
```

Bahut high workers mat rakhna warna timeout/error badh sakte hain.
