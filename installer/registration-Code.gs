/**
 * Code.gs — Google Apps Script web app that receives GRFP Scorer
 * registration and usage events, appends them to a Google Sheet, and
 * emails you a daily digest (or per-install, if you prefer).
 *
 * SETUP (about 10 minutes):
 *  1. Create a new Google Sheet. Rename the first tab "installs" and add a
 *     second tab named "usage".
 *  2. Extensions → Apps Script. Replace the default code with this file, and put the
 *     Sheet's ID (from its URL, between /d/ and /edit) in SHEET_ID below.
 *  3. APP_TOKEN must match register.py (it already does). It is not a secret —
 *     the app is open source — it only keeps accidental junk out of the sheet.
 *  4. NOTIFY_EMAIL is the address that receives the digest.
 *  5. Deploy → New deployment → Type: Web app.
 *        Execute as: Me
 *        Who has access: Anyone
 *     Copy the Web app URL into ENDPOINT in register.py.
 *  6. Run installDigestTrigger() once from the editor (authorize when
 *     prompted) to get a daily 8am summary email. If you'd rather get an
 *     email on every install, set EMAIL_PER_INSTALL = true instead.
 *
 * Re-deploy ("Manage deployments → Edit → New version") after any edit.
 */

// The ID of the Google Sheet that receives rows: the long string in its URL between /d/ and /edit.
// Required if this script is a standalone project; harmless if it is bound to the Sheet.
const SHEET_ID = "17k-XNJXDGIm3cZikA9xcin5js3v3TkdYd0SWf5LzEsU";
const APP_TOKEN = "grfp-scorer-public";   // must match APP_TOKEN in register.py (not a secret: the code is public)
const NOTIFY_EMAIL = "atsocvd@gmail.com";  // personal, non-institutional address
const EMAIL_PER_INSTALL = false;
const MAX_ROWS_PER_DAY = 500;              // crude flood guard; raise if a workshop legitimately exceeds it

const INSTALL_HEADERS = [
  "timestamp_utc", "install_id", "name", "email", "institution",
  "usage_opt_in", "os", "os_version", "arch", "app_version", "country"
];
const USAGE_HEADERS = [
  "timestamp_utc", "install_id", "statement_type", "backend", "model", "words",
  "total", "four_item", "disease", "app_version"
];

/** Visiting the URL in a browser: a plain health check, so the deployment can be tested. */
function doGet(e) {
  let sheetOk = false;
  try { ss_(); sheetOk = true; } catch (err) {}
  return respond_(200, "GRFP Scorer registration endpoint is up" + (sheetOk ? "" : " — but SHEET_ID is wrong or not set"));
}

function doPost(e) {
  let body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (err) {
    return respond_(400, "bad json");
  }
  if (body.token !== APP_TOKEN) return respond_(403, "forbidden");
  if (typeof body.install_id !== "string" || !/^[0-9a-f-]{36}$/.test(body.install_id)) return respond_(400, "bad install_id");

  const ss = ss_();
  if (floodGuard_(ss)) return respond_(429, "too many rows today");

  if (body.event === "install") {
    const sh = sheet_(ss, "installs", INSTALL_HEADERS);
    // Dedupe: if this install_id already registered, don't add a second row.
    const ids = sh.getRange(2, 2, Math.max(sh.getLastRow() - 1, 1), 1).getValues().flat();
    if (ids.indexOf(body.install_id) === -1) {
      sh.appendRow([
        body.ts || new Date().toISOString(),
        body.install_id, str_(body.name), str_(body.email), str_(body.institution),
        body.usage_opt_in ? "yes" : "no",
        body.os, body.os_version, body.arch, body.app_version,
        ""  // country: fill by hand or via a lookup on institution later
      ]);
      if (EMAIL_PER_INSTALL) {
        MailApp.sendEmail(
          NOTIFY_EMAIL,
          "GRFP Scorer: new install — " + (body.institution || "unknown institution"),
          body.name + " <" + body.email + ">\n" + body.institution + "\n" +
          body.os + " " + body.os_version + " (" + body.arch + ")  v" + body.app_version +
          "\nTotal installs: " + (sh.getLastRow() - 1)
        );
      }
    }
    return respond_(200, "ok");
  }

  if (body.event === "score") {
    const sh = sheet_(ss, "usage", USAGE_HEADERS);
    const num = v => (v == null || v === "") ? "" : Number(v);
    sh.appendRow([
      body.ts || new Date().toISOString(),
      body.install_id, str_(body.statement_type), str_(body.backend), str_(body.model), num(body.words),
      num(body.total), num(body.four), num(body.disease), body.app_version
    ]);
    return respond_(200, "ok");
  }

  return respond_(400, "unknown event");
}

/** Daily summary: totals, new installs in the last 24h, institution count. */
function sendDigest() {
  const ss = ss_();
  const inst = sheet_(ss, "installs", INSTALL_HEADERS);
  const usage = sheet_(ss, "usage", USAGE_HEADERS);
  const rows = inst.getLastRow() > 1
    ? inst.getRange(2, 1, inst.getLastRow() - 1, INSTALL_HEADERS.length).getValues()
    : [];
  const cutoff = Date.now() - 24 * 3600 * 1000;
  const recent = rows.filter(r => new Date(r[0]).getTime() > cutoff);
  if (recent.length === 0 && rows.length === 0) return;

  const institutions = new Set(rows.map(r => String(r[4]).trim().toLowerCase()).filter(Boolean));
  const scored = Math.max(usage.getLastRow() - 1, 0);

  let msg = "GRFP Scorer — daily summary\n\n";
  msg += "Total installs: " + rows.length + "\n";
  msg += "Distinct institutions: " + institutions.size + "\n";
  msg += "Statements scored (opted-in users): " + scored + "\n";
  msg += "New installs, last 24h: " + recent.length + "\n\n";
  recent.forEach(r => { msg += "  " + r[2] + " — " + r[4] + " (" + r[6] + ")\n"; });
  msg += "\nSheet: " + ss.getUrl();

  MailApp.sendEmail(NOTIFY_EMAIL, "GRFP Scorer: " + recent.length + " new install(s), " + rows.length + " total", msg);
}

/** Run once from the editor to schedule sendDigest() every morning. */
function installDigestTrigger() {
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger("sendDigest").timeBased().everyDays(1).atHour(8).create();
}

// ----------------------------------------------------------------- helpers

/** The receiving spreadsheet: by ID if set, else the Sheet this script is bound to. */
function ss_() {
  if (SHEET_ID && SHEET_ID !== "PASTE_SHEET_ID") return SpreadsheetApp.openById(SHEET_ID);
  const active = SpreadsheetApp.getActiveSpreadsheet();
  if (!active) throw new Error("No bound spreadsheet: set SHEET_ID at the top of this script.");
  return active;
}

function str_(v) { return String(v == null ? "" : v).slice(0, 200); }

/** True if more than MAX_ROWS_PER_DAY rows were added across both tabs in the last 24 h. */
function floodGuard_(ss) {
  const cache = CacheService.getScriptCache();
  const key = "rows_" + new Date().toISOString().slice(0, 10);
  const n = Number(cache.get(key) || 0) + 1;
  cache.put(key, String(n), 86400);
  return n > MAX_ROWS_PER_DAY;
}

function sheet_(ss, name, headers) {
  let sh = ss.getSheetByName(name);
  if (!sh) sh = ss.insertSheet(name);
  if (sh.getLastRow() === 0) {
    sh.appendRow(headers);
    sh.setFrozenRows(1);
  }
  return sh;
}

function respond_(code, text) {
  // Apps Script can't set HTTP status codes; clients check the body instead.
  return ContentService.createTextOutput(JSON.stringify({ status: code, msg: text }))
    .setMimeType(ContentService.MimeType.JSON);
}
