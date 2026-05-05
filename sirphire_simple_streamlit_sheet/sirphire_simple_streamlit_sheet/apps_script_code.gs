/**
 * Sirphire Camera Lens Add-on Checker
 *
 * Google Sheet -> Extensions -> Apps Script
 * Is pure code ko paste karo.
 *
 * Deploy:
 * Deploy -> New deployment -> Web app
 * Execute as: Me
 * Who has access: Anyone
 *
 * Web App URL ko Streamlit me paste karo.
 */

const SHEET_NAME = "products";

const HEADERS = [
  "category_url",
  "url",
  "title",
  "lens_rings",
  "status",
  "checked_at",
  "error"
];

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents || "{}");
    const action = body.action;

    if (action === "setup") return out(setup());
    if (action === "add_products") return out(addProducts(body.category_url || "", body.products || []));
    if (action === "claim_batch") return out(claimBatch(body.category_url || "", Number(body.batch_size || 50)));
    if (action === "update_results") return out(updateResults(body.results || []));
    if (action === "reset_stuck") return out(resetStuck());
    if (action === "stats") return out(stats(body.category_url || ""));
    if (action === "records") return out(records(body.category_url || "", Number(body.limit || 500)));

    return out({ ok: false, error: "Unknown action: " + action });
  } catch (err) {
    return out({ ok: false, error: String(err) });
  }
}

function out(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function getSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) sheet = ss.insertSheet(SHEET_NAME);
  return sheet;
}

function setup() {
  const sheet = getSheet();
  const values = sheet.getRange(1, 1, 1, HEADERS.length).getValues()[0];

  let mismatch = false;
  for (let i = 0; i < HEADERS.length; i++) {
    if (values[i] !== HEADERS[i]) {
      mismatch = true;
      break;
    }
  }

  if (mismatch) {
    sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
    sheet.setFrozenRows(1);
  }

  return { ok: true };
}

function allRows() {
  setup();
  const sheet = getSheet();
  const last = sheet.getLastRow();

  if (last < 2) return [];

  const values = sheet.getRange(2, 1, last - 1, HEADERS.length).getValues();

  return values.map((row, i) => {
    const obj = {};
    HEADERS.forEach((h, idx) => obj[h] = row[idx]);
    obj._row_number = i + 2;
    return obj;
  });
}

function addProducts(categoryUrl, products) {
  setup();
  const sheet = getSheet();
  const rows = allRows();

  const existing = {};
  rows.forEach(r => {
    const key = String(r.category_url || "") + "||" + String(r.url || "");
    existing[key] = true;
  });

  const newRows = [];

  products.forEach(p => {
    const url = String(p.url || "").trim();
    if (!url) return;

    const key = String(categoryUrl || "") + "||" + url;
    if (existing[key]) return;

    existing[key] = true;

    newRows.push([
      categoryUrl,
      url,
      p.title || "",
      "",
      "PENDING",
      "",
      ""
    ]);
  });

  if (newRows.length > 0) {
    sheet.getRange(sheet.getLastRow() + 1, 1, newRows.length, HEADERS.length).setValues(newRows);
  }

  return { ok: true, added: newRows.length };
}

function claimBatch(categoryUrl, batchSize) {
  setup();
  const sheet = getSheet();
  const rows = allRows();
  const claimed = [];
  const rowNumbers = [];

  rows.forEach(r => {
    if (claimed.length >= batchSize) return;

    const sameCategory = String(r.category_url || "") === String(categoryUrl || "");
    const status = String(r.status || "").toUpperCase();
    const hasUrl = String(r.url || "").trim() !== "";

    if (sameCategory && hasUrl && (status === "" || status === "PENDING" || status === "ERROR")) {
      claimed.push(r);
      rowNumbers.push(r._row_number);
    }
  });

  rowNumbers.forEach(rowNum => {
    const statusCol = HEADERS.indexOf("status") + 1;
    const checkedAtCol = HEADERS.indexOf("checked_at") + 1;
    sheet.getRange(rowNum, statusCol).setValue("IN_PROGRESS");
    sheet.getRange(rowNum, checkedAtCol).setValue(new Date());
  });

  return { ok: true, rows: claimed };
}

function updateResults(results) {
  setup();
  const sheet = getSheet();

  results.forEach(r => {
    const rowNum = Number(r._row_number);
    if (!rowNum || rowNum < 2) return;

    const current = sheet.getRange(rowNum, 1, 1, HEADERS.length).getValues()[0];

    Object.keys(r).forEach(key => {
      const idx = HEADERS.indexOf(key);
      if (idx >= 0) {
        current[idx] = r[key];
      }
    });

    sheet.getRange(rowNum, 1, 1, HEADERS.length).setValues([current]);
  });

  return { ok: true, updated: results.length };
}

function resetStuck() {
  setup();
  const sheet = getSheet();
  const rows = allRows();
  const statusCol = HEADERS.indexOf("status") + 1;

  rows.forEach(r => {
    const status = String(r.status || "").toUpperCase();
    if (status === "IN_PROGRESS") {
      sheet.getRange(r._row_number, statusCol).setValue("PENDING");
    }
  });

  return { ok: true };
}

function stats(categoryUrl) {
  const rows = allRows().filter(r => {
    if (!categoryUrl) return true;
    return String(r.category_url || "") === String(categoryUrl || "");
  });

  let total = rows.length;
  let pending = 0;
  let done = 0;
  let found = 0;
  let notFound = 0;
  let errors = 0;
  let inProgress = 0;

  rows.forEach(r => {
    const status = String(r.status || "").toUpperCase();
    const lens = String(r.lens_rings || "").toUpperCase();

    if (status === "" || status === "PENDING") pending++;
    if (status === "DONE") done++;
    if (status === "ERROR") errors++;
    if (status === "IN_PROGRESS") inProgress++;
    if (lens === "FOUND") found++;
    if (lens === "NOT_FOUND") notFound++;
  });

  return {
    ok: true,
    stats: {
      total: total,
      pending: pending,
      done: done,
      found: found,
      not_found: notFound,
      errors: errors,
      in_progress: inProgress
    }
  };
}

function records(categoryUrl, limit) {
  let rows = allRows().filter(r => {
    if (!categoryUrl) return true;
    return String(r.category_url || "") === String(categoryUrl || "");
  });

  rows = rows.slice(Math.max(0, rows.length - limit)).reverse();

  return { ok: true, records: rows };
}
