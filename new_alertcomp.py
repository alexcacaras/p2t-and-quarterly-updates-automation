import os
import re
import requests # HTTP library for sending SOAP POST requests to Oracle BI Publisher
import xml.etree.ElementTree as ET # parses SOAP XML response to extract Base64 report bytes
import base64 # decodes Base64 string from SOAP response into raw Excel bytes
import pandas as pd # reads Excel bytes into DataFrame, filters rows needing correction
from io import BytesIO # wraps decoded bytes in file-like object so pandas can read without saving to disk
from datetime import datetime # generates timestamps for screenshot and report filenames
from pathlib import Path # object-oriented file path handling for cleanup functions
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError # browser automation for Oracle Fusion UI
import time # compares file modification times during cleanup
import pathlib # used alongside Path for glob-based file scanning in cleanup
from login import get_login_page, build_login_config
from crypto_env import load_env_from_encrypted, get_env, _get_env_prefix # dotenv for loading env variables from .env file into python but from the encypted version
load_env_from_encrypted()   # load .env before reading env vars from encrypted version
ENV_PREFIX = _get_env_prefix()
# ---------------------------
# SOAP CONFIG (for report)
# ---------------------------
SOAP_URL      = f"{(get_env('FUSION_BASEURL', ENV_PREFIX) or '').rstrip('/').rstrip(':443')}:443/xmlpserver/services/v2/ReportService"
SOAP_USERNAME = get_env("SOAP_USERNAME", ENV_PREFIX)
SOAP_PASSWORD = get_env("SOAP_PASSWORD", ENV_PREFIX)
REPORT_PATH   = get_env("REPORT_PATH", ENV_PREFIX)

# ---------------------------
# PLAYWRIGHT CONFIG (for UI)
# ---------------------------
INSTANCE_URL = (get_env("FUSION_BASEURL", ENV_PREFIX) or "").rstrip("/")

HOME_URL = f"{INSTANCE_URL}/fscmUI/faces/AtkHomePageWelcome"

#can change the user just set as FUSION_USER
FUSION_USER = get_env("FUSION_USER", ENV_PREFIX)
FUSION_PASS = get_env("FUSION_PASS", ENV_PREFIX)

# ---------------------------
# GENERAL CONFIG
# ---------------------------
DRY_RUN = False #set false if you want to save
REPORTS_DIR = "alert_composer_reports"

PAUSE = 3_500            # ms between major steps 
PAUSE_AFTER_CLICK = 1_000
PAUSE_AFTER_FILL = 800
PAUSE_BEFORE_DIALOG = 2_000
PAUSE_AFTER_DIALOG_CLICK = 2_000
REPORTS_KEEP_DAYS = 7
REPORTS_KEEP_MAX  = 200
SCREENSHOTS_KEEP_DAYS = 7
SCREENSHOTS_KEEP_MAX  = 200
FORCE_XPATH = False  # Set True to skip regex runs and go straight to xpath mode
#------------------------------------
#HELPERS
#------------------------------------
# Added some of the helpers from main_ui_auto
from contextlib import suppress # suppresses PWTimeoutError inside try_click() so optional clicks don't crash the script

def snooze(page, ms=PAUSE):
    page.wait_for_timeout(ms)

def try_click(locator, timeout=6_000) -> bool:
    with suppress(PWTimeoutError):
        locator.wait_for(state="visible", timeout=timeout)
        locator.click(timeout=timeout)
        return True
    return False
SCREENSHOTS_DIR = "screenshots_alert_composer"
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

#Add to helpers for screenshots
def take_screenshot(page, label="step"):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{SCREENSHOTS_DIR}/{timestamp}_{label}.png"
    page.screenshot(path=filename)
    log_print(f" Screenshot: {filename}")
#screenshot cleaner helper
def cleanup_screenshots():
    p = pathlib.Path(SCREENSHOTS_DIR)
    if not p.exists():
        return
    now = time.time()
    files = sorted([f for f in p.glob("*.png") if f.is_file()],
                   key=lambda f: f.stat().st_mtime, reverse=True)
    for f in files:
        if now - f.stat().st_mtime > SCREENSHOTS_KEEP_DAYS * 86400:
            try:
                f.unlink(missing_ok=True)
            except PermissionError:
                log_print(f"Skipped (file in use): {f.name}", level="warning")
    files = sorted([f for f in p.glob("*.png") if f.is_file()],
                   key=lambda f: f.stat().st_mtime, reverse=True)
    for f in files[SCREENSHOTS_KEEP_MAX:]:
        try:
            f.unlink(missing_ok=True)
        except PermissionError:
            log_print(f"Skipped (file in use): {f.name}", level="warning")
#reports cleanup helper
def cleanup_reports():
    p = pathlib.Path(REPORTS_DIR)
    if not p.exists():
        return
    now = time.time()
    files = sorted([f for f in p.glob("*.xlsx") if f.is_file()],
                   key=lambda f: f.stat().st_mtime, reverse=True)
    for f in files:
        if now - f.stat().st_mtime > REPORTS_KEEP_DAYS * 86400:
            try:
                f.unlink(missing_ok=True)
            except PermissionError:
                log_print(f"Skipped (file in use): {f.name}", level="warning")
    files = sorted([f for f in p.glob("*.xlsx") if f.is_file()],
                   key=lambda f: f.stat().st_mtime, reverse=True)
    for f in files[REPORTS_KEEP_MAX:]:
        try:
            f.unlink(missing_ok=True)
        except PermissionError:
            log_print(f"Skipped (file in use): {f.name}", level="warning")
# ---------------------------
# LOGGING SETUP
# ---------------------------
import logging # built-in logging framework for rotating log file and console output
from logging.handlers import RotatingFileHandler  # rotates log file at 5MB

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

def make_logger():
    log_name = f"ALERT_COMPOSER_{ENV_PREFIX}" if ENV_PREFIX else "ALERT_COMPOSER"
    log_file = f"ALERT_COMPOSER_{ENV_PREFIX}.log" if ENV_PREFIX else "ALERT_COMPOSER.log"
    log = logging.getLogger(log_name)
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")
    fh = RotatingFileHandler(os.path.join(LOG_DIR, log_file),
                             maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    fh.setFormatter(fmt)
    log.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    log.addHandler(ch)
    log.propagate = False
    return log

log = make_logger()

def log_print(msg, level="info"):
    """Print and log at the same time."""
    if level == "error":
        log.error(msg)
    elif level == "warning":
        log.warning(msg)
    else:
        log.info(msg)

# ---------------------------
# SOAP - GET REPORT DATA
# ---------------------------
def fetch_alert_report():
    """Call SOAP API, decode Base64, save Excel log, return dataframe."""

    soap_body = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:v2="http://xmlns.oracle.com/oxp/service/v2">
       <soapenv:Header/>
       <soapenv:Body>
          <v2:runReport>
             <v2:reportRequest>
                <v2:attributeFormat>xlsx</v2:attributeFormat>
                <v2:reportAbsolutePath>{REPORT_PATH}</v2:reportAbsolutePath>
                <v2:sizeOfDataChunkDownload>-1</v2:sizeOfDataChunkDownload>
             </v2:reportRequest>
             <v2:userID>{SOAP_USERNAME}</v2:userID>
             <v2:password>{SOAP_PASSWORD}</v2:password>
          </v2:runReport>
       </soapenv:Body>
    </soapenv:Envelope>"""

    headers = {"Content-Type": "text/xml; charset=utf-8"}
    
    log_print("=" * 60)
    log_print("STEP 1: Calling SOAP API to fetch alert report...")
    response = requests.post(SOAP_URL, data=soap_body, headers=headers)
    log_print(f"SOAP Response Status: {response.status_code}")

   # Extract Base64
    log_print("STEP 2: Extracting Base64 from response...")
    if response.status_code != 200:
        log_print(f"SOAP call failed ({response.status_code}). Response body:\n{response.text[:1500]}", level="error")
        raise RuntimeError(f"SOAP report request failed with HTTP {response.status_code}")
    root = ET.fromstring(response.text)
    node = root.find(".//{http://xmlns.oracle.com/oxp/service/v2}reportBytes")
    if node is None:
        log_print(f"No reportBytes in response. Body:\n{response.text[:1500]}", level="error")
        raise RuntimeError("SOAP response contained no reportBytes (see body above)")
    report_bytes_b64 = node.text

    # Decode
    log_print("STEP 3: Decoding Base64 to Excel...")
    excel_bytes = base64.b64decode(report_bytes_b64)

    # Save to log folder
    os.makedirs(REPORTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_path = os.path.join(REPORTS_DIR, f"alert_report_{timestamp}.xlsx")
    with open(output_path, "wb") as f:
        f.write(excel_bytes)
    log_print(f"Report saved to: {output_path}")

    # Read into pandas
    df = pd.read_excel(BytesIO(excel_bytes), engine="openpyxl", header=1)
    df = df.dropna(subset=["ALERT_NAME"])
    log_print(f"Columns: {df.columns.tolist()}")
    log_print(f"Rows: {len(df)}")

    return df


def get_alerts_to_fix(df):
    """Filter dataframe to only rows that need fixing and build corrected expressions."""

    log_print("=" * 60)
    log_print("STEP 4: Finding alerts that need fixing...")

    if df.empty:
        log_print("Report is empty - no alerts need fixing.")
        return pd.DataFrame()

    needs_fix = df[df["VALUE_EXPRESSION"].str.contains(".UserName}", na=False, regex=False)].copy()

    if needs_fix.empty:
        log_print("No alerts need fixing right now.")
        return pd.DataFrame()

    needs_fix["CORRECTED_EXPRESSION"] = needs_fix["VALUE_EXPRESSION"].str.replace(
        ".UserName}", ".WorkEmail}", regex=False
    )

    log_print(f"Found {len(needs_fix)} templates that need fixing:")
    log_print(needs_fix[["ALERT_NAME", "NAME1", "VALUE_EXPRESSION"]].to_string())

    log_print("\nWhat will be changed:")
    for _, row in needs_fix.iterrows():
        log_print(f"  Alert:    {row['ALERT_NAME']}")
        log_print(f"  Template: {row['NAME1']}")
        log_print(f"  FROM:     {row['VALUE_EXPRESSION']}")
        log_print(f"  TO:       {row['CORRECTED_EXPRESSION']}")

    return needs_fix
# ---------------------------
# PLAYWRIGHT HELPERS
# ---------------------------


def safe_click(locator, desc: str, timeout=20000, pause_after=PAUSE_AFTER_CLICK):
    try:
        locator.click(timeout=timeout)
        log_print(f"✓ CLICK: {desc}")
        if pause_after > 0:
            locator.page.wait_for_timeout(pause_after)
    except PWTimeoutError:
        raise RuntimeError(f"Timed out clicking: {desc}")
    
#fill field using javascript injection
def fill_force(locator, value: str, pause_after=PAUSE_AFTER_FILL): 
    locator.click()
    locator.page.wait_for_timeout(200)
    locator.evaluate(
        """(el, v) => {
            el.focus();
            el.value = v;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""",
        value
    )
    if pause_after > 0:
        locator.page.wait_for_timeout(pause_after)

def ensure_logged_in(page):
    login = get_login_page(page, build_login_config(ENV_PREFIX), logger=log_print)
    login.login()
    if not login.is_logged_in():
        raise RuntimeError(f"Login failed (env={ENV_PREFIX or 'default'})")
    log_print("Logged in.")

def open_alerts_composer(page):
    safe_click(page.get_by_role("link", name="Navigator"), "Navigator")
    page.wait_for_timeout(PAUSE_BEFORE_DIALOG)
    safe_click(page.get_by_title("Tools", exact=True), "Tools")
    page.wait_for_timeout(PAUSE_BEFORE_DIALOG)
    safe_click(page.get_by_role("link", name="Alerts Composer"), "Alerts Composer")
    page.wait_for_load_state("networkidle", timeout=60000)

def open_alert_by_search(page, alert_name: str):
    log_print(f"Searching for alert: {alert_name}")
    
    search = page.get_by_role("textbox", name=re.compile(r"Enter the alert name or code", re.I))
    try_click(search)
    snooze(page, PAUSE_BEFORE_DIALOG)
    
    search.fill(alert_name)
    take_screenshot(page, f"search_{alert_name[:30].replace(' ', '_')}")
    snooze(page, PAUSE_BEFORE_DIALOG)  # wait for autocomplete to appear
    
    # Click the autocomplete suggestion
    page.locator('[id="_FOpt1:_UISpageCust"] tr') \
        .filter(has_text=re.compile(r"^Enter the alert name or code$")) \
        .get_by_role("link").click()
    snooze(page, PAUSE)  # wait for results to load
    
    # Click the alert link in results
    alert_link = page.get_by_role("link", name=re.compile(re.escape(alert_name), re.I))
    if not try_click(alert_link):
        raise RuntimeError(f"Alert link not found: {alert_name}")
    log_print(f" Opened alert: {alert_name}")
    page.wait_for_load_state("networkidle", timeout=60000)
    snooze(page, PAUSE)  # wait for alert page to fully load

def open_template_by_name(page, template_name: str):
    safe_click(
        page.get_by_role("cell", name=re.compile(re.escape(template_name), re.I)),
        f"Template row: {template_name}"
    )
    page.wait_for_timeout(400)
    if page.get_by_role("link", name=re.compile(re.escape(template_name), re.I)).is_visible(timeout=2000):
        safe_click(
            page.get_by_role("link", name=re.compile(re.escape(template_name), re.I)),
            f"Template link: {template_name}"
        )
    page.wait_for_load_state("networkidle", timeout=60000)

def set_mail_expr(page, desired_expr: str):
    row = page.get_by_role("row", name=re.compile(r"^Mail\b", re.I))
    expr_input = row.get_by_role("textbox").first
    page.wait_for_timeout(300)
    current = expr_input.input_value()
    log_print(f"  Current Mail expr: {current!r}")
    log_print(f"  Desired Mail expr: {desired_expr!r}")
    if current.strip() == desired_expr.strip():
        log_print("  Already correct, no change needed")
        return False
    if DRY_RUN:
        log_print("  DRY_RUN: would update Mail expr")
        return True
    fill_force(expr_input, desired_expr)
    page.wait_for_timeout(300)
    new_value = expr_input.input_value()
    if new_value.strip() == desired_expr.strip():
        log_print(f"  Updated successfully! New value: {new_value!r}")
        return True
    else:
        log_print(f"  Update FAILED! Expected: {desired_expr!r}, Got: {new_value!r}", level="error")
        return False

def click_apply_if_needed(page):
    if DRY_RUN:
        log_print("  DRY_RUN: would click Apply")
        return
    safe_click(page.get_by_role("button", name=re.compile(r"^Apply$", re.I)), "Apply")
    page.wait_for_timeout(1500)

def click_save_and_close(page):
    if DRY_RUN:
        log_print("DRY_RUN: would click Save and Close")
        return
    btn = page.get_by_role("button", name=re.compile(r"Save and Close", re.I))
    # scroll it into view first so ADF registers it
    with suppress(Exception):
        btn.scroll_into_view_if_needed()
        snooze(page, 500)
    # first click to focus / activate the button area
    try_click(btn, timeout=10_000)
    snooze(page, 1_000)
    # second click in case ADF swallowed the first one
    try_click(btn, timeout=5_000)
    page.wait_for_load_state("networkidle", timeout=60000)
    snooze(page, PAUSE)
    log_print(" Save and Close clicked")

def navigate_back(page):
    if page.get_by_role("link", name=re.compile("Back", re.I)).is_visible(timeout=2000):
        safe_click(page.get_by_role("link", name=re.compile("Back", re.I)), "Back")
    else:
        page.go_back()
    page.wait_for_load_state("networkidle", timeout=60000)

def recover_to_alerts_composer(page):
    log_print("Recovering - navigating back to Alerts Composer...")
    try:
        page.goto(HOME_URL, wait_until="domcontentloaded")
        snooze(page, PAUSE)
        safe_click(page.get_by_role("link", name="Navigator"), "Navigator")
        snooze(page, PAUSE_BEFORE_DIALOG)
        # Tools already expanded from earlier - click Alerts Composer directly
        safe_click(page.get_by_role("link", name="Alerts Composer"), "Alerts Composer")
        page.wait_for_load_state("networkidle", timeout=60000)
        snooze(page, PAUSE)
        log_print("✓ Recovered to Alerts Composer")
    except Exception as e:
        log_print(f" Recovery itself failed: {e}", level="error")

def open_manage_recipients_dialog(page, template_name: str, use_xpath: bool = False):
    log_print(f"Opening Manage Recipients for: {template_name}" + (" [xpath mode]" if use_xpath else ""))

    if use_xpath:
        input_loc = page.locator(f'input[value="{template_name}"]').first
        cell_locator = input_loc.locator("xpath=ancestor::td[1]")
        row_locator = None  # find Edit by Y position instead
    
    elif "/" in template_name:
        cell_locator = page.get_by_role("cell", name=template_name, exact=False).first
        row_locator = page.get_by_role("row", name=template_name, exact=False).first
    else:
        cell_locator = page.get_by_role("cell", name=re.compile(r"^" + re.escape(template_name) + r"\b", re.I)).first
        row_locator = page.get_by_role("row", name=re.compile(r"^" + re.escape(template_name) + r"\b", re.I)).first

    # Step 1: Scroll the ADF table's scroller div to expose all rows
    with suppress(Exception):
        page.evaluate("""() => {
            const scroller = document.querySelector('[id$="t1::scroller"]');
            if (scroller) {
                scroller.scrollTop = scroller.scrollHeight;
            }
        }""")
        snooze(page, 500)

    # Step 2: Scroll into view and click the cell
    cell_locator.scroll_into_view_if_needed()
    snooze(page, 300)
    if not try_click(cell_locator):
        raise RuntimeError(f"Could not click cell for template: {template_name}")
    snooze(page, 300)
    log_print(f"✓ Clicked template cell")

    # Step 3: Click Edit button
    if use_xpath and row_locator is None:
        # Get Y position of the cell we just clicked
        cell_box = cell_locator.bounding_box()
        edit_btn = None
        if cell_box:
            log_print(f"  Cell Y position: {cell_box['y']:.0f}")
            for btn in page.locator('[title="Edit"]').all():
                btn_box = btn.bounding_box()
                if btn_box and abs(btn_box['y'] - cell_box['y']) < 20:
                    log_print(f"  Found Edit button at Y: {btn_box['y']:.0f}")
                    edit_btn = btn
                    break
        if not edit_btn:
            raise RuntimeError(f"Could not find Edit button for template: {template_name}")
        edit_btn.scroll_into_view_if_needed()
        snooze(page, 300)
        if not try_click(edit_btn):
            raise RuntimeError(f"Could not click Edit button for template: {template_name}")
        snooze(page, PAUSE_BEFORE_DIALOG)
        log_print("✓ Clicked Edit button")
    else:
        edit_btn = row_locator.get_by_title("Edit", exact=True).first
        edit_btn.scroll_into_view_if_needed()
        snooze(page, 300)
        if not try_click(edit_btn):
            raise RuntimeError(f"Could not click Edit button for template: {template_name}")
        snooze(page, PAUSE_BEFORE_DIALOG)
        log_print("✓ Clicked Edit button")

    # Step 4: Click Manage Recipients in the popup
    menu_item = page.locator('[id="__af_Z_window"]').get_by_text("Manage Recipients and Message", exact=False)
    if not try_click(menu_item, timeout=10_000):
        raise RuntimeError(f"Menu item not visible for template: {template_name}")
    log_print("✓ Clicked Manage Recipients and Message")

    page.wait_for_load_state("domcontentloaded", timeout=30000)
    snooze(page, PAUSE)

# ---------------------------
# MAIN RUN
# ---------------------------
def run(use_xpath: bool = False):
    if use_xpath:
        log_print("*** XPATH MODE — using exact input[value] matching for all templates ***")

    # --- SOAP PART ---
    df = fetch_alert_report()
    needs_fix = get_alerts_to_fix(df)

    if needs_fix.empty:
        log_print("Nothing to fix, exiting.")
        cleanup_screenshots()  
        cleanup_reports()
        return

    # --- PLAYWRIGHT PART ---
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto(HOME_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(1000)
            ensure_logged_in(page)
            open_alerts_composer(page)

            for alert_name, group in needs_fix.groupby("ALERT_NAME"):
                log_print("=" * 60)
                log_print(f"STEP 5: Processing alert: {alert_name}")
                log_print(f"  Templates to fix: {len(group)}")

                try:  # outer soft-fail per alert
                    open_alert_by_search(page, alert_name)
                    snooze(page, PAUSE)
                    page.wait_for_timeout(1000)

                    # Loop through each template in this alert
                    for _, row in group.iterrows():
                        template_name = row["NAME1"]
                        corrected_expr = row["CORRECTED_EXPRESSION"]

                        log_print(f"\n  Template: {template_name}")
                        try:  # inner soft-fail per template
                            snooze(page, PAUSE)
                            open_manage_recipients_dialog(page, template_name, use_xpath=use_xpath)
                            take_screenshot(page, f"before_{template_name[:30].replace(' ', '_')}")
                            snooze(page, PAUSE)

                            changed = set_mail_expr(page, corrected_expr)
                            if changed:
                                take_screenshot(page, f"after_{template_name[:30].replace(' ', '_')}")
                                snooze(page, PAUSE)
                                click_apply_if_needed(page)
                                page.wait_for_timeout(500)
                            else:
                                # already correct — cancel out of open dialog
                                log_print(f"  Already correct — cancelling dialog")
                                with suppress(Exception):
                                    page.get_by_role("button", name="Cancel").click()
                                    snooze(page, 500)

                        except (PWTimeoutError, RuntimeError) as e:
                            take_screenshot(page, f"FAILED_{template_name[:30].replace(' ', '_')}")
                            log_print(f"!!!!! Template SKIPPED: {template_name} — {e}", level="warning")
                            err_msg = str(e).lower()
                            dialog_was_opened = (
                                "menu item not visible" not in err_msg
                                and "could not click" not in err_msg
                                and "scroll_into_view" not in err_msg
                            )
                            if dialog_was_opened:
                                with suppress(Exception):
                                    page.get_by_role("button", name="Cancel").click()
                                    snooze(page, 500)
                            else:
                                log_print("  (dialog never opened — skipping without Cancel)")
                            continue

                    # Save and close after ALL templates done (runs even if some were skipped)
                    snooze(page, PAUSE)
                    click_save_and_close(page)
                    snooze(page, PAUSE)

                    # Go back to alerts composer only if more alerts remain
                    if alert_name != list(needs_fix["ALERT_NAME"].unique())[-1]:
                        search = page.get_by_role("textbox", name=re.compile(r"Enter the alert name or code", re.I))
                        try_click(search)
                        page.keyboard.press("Control+a")
                        page.keyboard.press("Delete")
                        snooze(page, PAUSE_BEFORE_DIALOG)
                        log_print("✓ Ready for next alert search")

                except PWTimeoutError as e:  # outer soft-fail — skip entire alert
                    take_screenshot(page, f"FAILED_alert_{alert_name[:30].replace(' ', '_')}")
                    log_print(f"!!!!! Alert SKIPPED (timeout): {alert_name}", level="warning")
                    recover_to_alerts_composer(page)
                    continue  # next alert ✓

            log_print("=" * 60)
            log_print(" DONE - All alerts processed!")
            log_print("=" * 60)

        except Exception as e:
            log_print(f" ERROR: {e}", level="error")
            import traceback
            traceback.print_exc()
        finally:
            cleanup_screenshots()
            cleanup_reports()
            context.close()
            browser.close()


if __name__ == "__main__":
    MAX_RERUNS = 3
    for attempt in range(MAX_RERUNS):
        log_print(f"=== RUN ATTEMPT {attempt + 1} of {MAX_RERUNS} ===")
        run(use_xpath=FORCE_XPATH or (attempt == 2))
        log_print(f"=== ATTEMPT {attempt + 1} COMPLETE ===")