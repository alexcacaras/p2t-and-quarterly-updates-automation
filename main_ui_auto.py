# main_ui_auto.py
# --- UI automation to disable email notifications in Oracle Fusion ---
import os  # for os features like creating folders
import re  # for regular expressions
import time  # for time related such as timing pauses
import datetime  # for dates and timestamps
import pathlib  # for cleanup paths
from contextlib import suppress  # for suppressing
from urllib.parse import urlparse  # for generating consistent browser
from playwright.sync_api import Playwright, sync_playwright, TimeoutError as PWTimeout  # for browser automation
from login import get_login_page, build_login_config
from crypto_env import load_env_from_encrypted, get_env, _get_env_prefix # dotenv for loading env variables from .env file into python but from the encypted version
load_env_from_encrypted()   # load .env before reading env vars from encrypted version
ENV_PREFIX = _get_env_prefix()

# ----------------- For logging -------------------
import logging  # built in logging
from logging.handlers import RotatingFileHandler  # for preventing too large logs
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

def make_ui_logger():
    log_name = f"UI_AUTO_{ENV_PREFIX}" if ENV_PREFIX else "UI_AUTO"
    log_file = f"UI_AUTO_{ENV_PREFIX}.log" if ENV_PREFIX else "UI_AUTO.log"
    log = logging.getLogger(log_name)
    if log.handlers:
        return log  # already configured
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | UI_AUTO | %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")
    # file handler (rotating)
    from os.path import join
    fh = RotatingFileHandler(join(LOG_DIR, log_file), maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    fh.setFormatter(fmt)
    log.addHandler(fh)
    # console mirror (optional)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    log.addHandler(ch)
    # keep it separate from root / other project loggers
    log.propagate = False
    return log

log = make_ui_logger()

# ---------------- Configuration ----------------
INSTANCE_URL = (get_env("FUSION_BASEURL", ENV_PREFIX) or "").rstrip("/")
HOME_URL = f"{INSTANCE_URL}/fscmUI/faces/AtkHomePageWelcome"

FUSION_USER = get_env("FUSION_USER", ENV_PREFIX)
FUSION_PASS = get_env("FUSION_PASS", ENV_PREFIX)

PAUSE = 3_500            # ms between major steps
CLICK_TIMEOUT = 6_000    # ms for guarded clicks
DRY_RUN = False          # set True to skip the final "Save"

# Categories to check under Security Console → User Categories
NOTIFICATION_CATEGORIES = ["ADMINISTRATORS", "CONTRACTORS", "DEFAULT"]

# Build a unique persistent profile dir per instance (and user)
parsed = urlparse(INSTANCE_URL)
host = (parsed.hostname or "fusion").replace(".", "-")  # e.g., ejvv-test-fa-us6-oraclecloud-com
user = FUSION_USER.split("@")[0] if "@" in FUSION_USER else FUSION_USER or "user"
PROFILE_DIR = f".pw-profile-{host}-{user}"

# ---------- helpers ----------
def snooze(page, ms=PAUSE):
    page.wait_for_timeout(ms)

def try_click(locator, timeout=CLICK_TIMEOUT) -> bool:
    with suppress(PWTimeout):
        locator.wait_for(state="visible", timeout=timeout)
        locator.click(timeout=timeout)
        return True
    return False

def exists(locator, timeout=1_000) -> bool:
    try:
        locator.wait_for(state="visible", timeout=timeout)
        return True
    except PWTimeout:
        return False

def open_notifications(page, pause_ms=PAUSE):
    """
    Open Notifications via:
      1) "Notifications (0 unread)"
      2) "Notifications (N unread)"
      3) generic bell named "Notifications"
    Then click "Show All".
    """
    if try_click(page.get_by_role("link", name=re.compile(r"^Notifications \(0 unread\)$", re.I))):
        snooze(page, pause_ms)
    elif try_click(page.get_by_role("link", name=re.compile(r"^Notifications \(\d+ unread\)$", re.I))):
        snooze(page, pause_ms)
    elif try_click(page.get_by_role("button", name=re.compile(r"^Notifications$", re.I))) or \
         try_click(page.get_by_role("link",  name=re.compile(r"^Notifications$", re.I))):
        snooze(page, pause_ms)
    else:
        raise RuntimeError("Couldn't open Notifications (tried 0 unread, any unread, and bell).")

    if not (try_click(page.get_by_role("button", name=re.compile(r"Show All", re.I))) or
            try_click(page.get_by_role("link",  name=re.compile(r"Show All", re.I)))):  # noqa: E128
        raise RuntimeError("Couldn't find 'Show All' in Notifications.")
    snooze(page, pause_ms)

def take_screenshot(page, label="step"):
    """Takes a screenshot and saves it in /screenshots with timestamp + label."""
    os.makedirs("screenshots", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"screenshots/{timestamp}_{label}.png"
    page.screenshot(path=filename)
    print(f" Screenshot saved: {filename}")
    log.info(f"Screenshot saved: {filename}")

def cleanup_screenshots(folder="screenshots", retain_minutes=None, retain_days=7, keep_latest=200):
    """
    Deletes old screenshots:
      - If retain_days is given, keep files newer than that many days.
      - Else, use retain_minutes (for short-lived test runs).
      - Always keep at most 'keep_latest' most recent files.
    """
    p = pathlib.Path(folder)
    if not p.exists():
        return
    now = time.time()
    files = sorted([f for f in p.glob("*.png") if f.is_file()],
                   key=lambda f: f.stat().st_mtime, reverse=True)

    # age-based delete
    for f in files:
        age_sec = now - f.stat().st_mtime
        if retain_days is not None:
            if age_sec > retain_days * 86400:
                f.unlink(missing_ok=True)
        elif retain_minutes is not None:
            if age_sec > retain_minutes * 60:
                f.unlink(missing_ok=True)

    # cap by count
    files = sorted([f for f in p.glob("*.png") if f.is_file()],
                   key=lambda f: f.stat().st_mtime, reverse=True)
    for f in files[keep_latest:]:
        f.unlink(missing_ok=True)

def log_and_print(message, level="info"):
    if level == "error":
        log.error(message)
    elif level == "warning":
        log.warning(message)
    else:
        log.info(message)
    print(message)

def click_user_categories(sec_page, pause_ms=PAUSE) -> bool:
    """
    Robustly click 'User Categories' in the Security Console left rail.
    Tries role-based, then generic link, then CSS :has-text, then text fallback.
    Scrolls into view before clicking. Returns True if clicked.
    """
    # Give the page a moment and try to find the left nav if present
    with suppress(Exception):
        sec_page.wait_for_load_state("domcontentloaded")

    candidates = []

    # Prefer a left nav region if it exists
    left_nav = None
    with suppress(Exception):
        left_nav = sec_page.get_by_role("navigation")
    if left_nav:
        candidates.append(left_nav.get_by_role("link", name=re.compile(r"^User Categories$", re.I)))

    # Other robust fallbacks
    candidates.extend([
        sec_page.get_by_role("link", name=re.compile(r"^User Categories$", re.I)),
        sec_page.locator("a:has-text('User Categories')"),
        sec_page.locator("span:has-text('User Categories')").locator("xpath=ancestor::a[1]"),
        sec_page.get_by_text(re.compile(r"\bUser Categories\b", re.I)).first,
    ])

    for cand in candidates:
        try:
            cand.scroll_into_view_if_needed()
            if try_click(cand):
                snooze(sec_page, pause_ms)
                take_screenshot(sec_page, "security_user_categories_clicked")
                return True
        except Exception:
            pass

    return False

def ensure_user_categories_list(page, pause_ms=PAUSE):
    """Make sure we're back on the User Categories list before selecting the next name."""
    # Try the robust left-rail opener you already have
    if click_user_categories(page, pause_ms):
        return True
    # Last resort: try any visible 'User Categories' text as a link
    return try_click(page.get_by_text(re.compile(r"\bUser Categories\b", re.I)))

def click_notifications_tab(page, pause_ms=PAUSE) -> bool:
    """
    Click the Notifications tab inside a User Category.
    Uses exact matches and excludes the global bell ('Notifications (N unread)').
    """
    candidates = []

    # Prefer left navigation (the sidebar you screenshotted)
    left_nav = None
    with suppress(Exception):
        left_nav = page.get_by_role("navigation")
    if left_nav:
        # Exact match first
        candidates.append(left_nav.get_by_role("link", name="Notifications", exact=True))
        # Regex fallback
        candidates.append(left_nav.get_by_role("link", name=re.compile(r"^Notifications\b", re.I)))

    # Fallbacks on the whole page, but avoid the svg-glob bell icon
    candidates.extend([
        page.get_by_role("link", name="Notifications", exact=True),
        page.get_by_role("link", name="Notifications Notifications"),
        page.locator("a:has-text('Notifications'):not(.svg-glob)").first,
    ])

    for cand in candidates:
        try:
            cand.scroll_into_view_if_needed()
            if try_click(cand):
                snooze(page, pause_ms)
                take_screenshot(page, "notifications_tab_open")
                return True
        except Exception:
            pass

    return False

def go_security_console(page, pause_ms=PAUSE):
    """Home → Navigator → Tools → Security Console → User Categories (left nav).
       Returns the page object where Security Console lives (same tab)."""

    # Home (idempotent)
    with suppress(Exception):
        try_click(page.get_by_role("link", name="Home", exact=True)); snooze(page)
    take_screenshot(page, "security_home")

    # Navigator
    if not try_click(page.get_by_role("link", name=re.compile(r"^Navigator$", re.I))):
        raise RuntimeError("Navigator not found")
    snooze(page, pause_ms)
    take_screenshot(page, "security_navigator")

    # Tools tile (primary + fallback)
    if not try_click(page.get_by_title("Tools", exact=True).locator("div").nth(1)):
        if not try_click(page.get_by_role("link", name=re.compile(r"^Tools$", re.I))):
            raise RuntimeError("Tools not found")
    snooze(page, pause_ms)
    take_screenshot(page, "security_tools")

    # Security Console — SAME TAB navigation (no popup handling)
    if not (try_click(page.get_by_role("link", name=re.compile(r"^Security Console$", re.I))) or
            try_click(page.get_by_text(re.compile(r"\bSecurity Console\b", re.I)))):
        raise RuntimeError("Security Console link not found")
    page.wait_for_load_state("domcontentloaded")
    snooze(page, pause_ms)
    take_screenshot(page, "security_console_same_tab")

        # --- Reach "User Categories" robustly (same tab) ---
    if click_user_categories(page, pause_ms):
        return page

    raise RuntimeError("Could not find 'User Categories' in Security Console")


def disable_category_notifications(page, category_name: str, pause_ms=PAUSE) -> bool:
    """
    For a given category (e.g., 'ADMINISTRATORS'):
    1. Pre-check the list — if Notification is No, skip entirely
    2. If Yes — open it, go to Notifications tab, Edit, uncheck with 5 fallbacks
    Returns True if category was found, False if not found at all.
    """

    # --- Step 1: Pre-check Yes/No directly from the User Categories list ---
    # Row text looks like "ADMINISTRATORSNotificationYesNext URL"
    yes_row = page.get_by_text(
        re.compile(fr"{re.escape(category_name)}NotificationYes", re.I)
    )
    no_row = page.get_by_text(
        re.compile(fr"{re.escape(category_name)}NotificationNo", re.I)
    )

    if exists(no_row, timeout=2_000):
        log_and_print(f"{category_name}: Notification is No — skipping")
        return True  # already correct, nothing to do

    if not exists(yes_row, timeout=2_000):
        log_and_print(f"{category_name}: not found in list — skipping", level="warning")
        return False  # category not found at all

    log_and_print(f"{category_name}: Notification is Yes — will disable")

    # --- Step 2: Open category ---
    cat_link = page.get_by_role("link", name=re.compile(fr"^{re.escape(category_name)}$", re.I))
    if not exists(cat_link):
        return False

    try_click(cat_link)
    snooze(page, pause_ms)
    take_screenshot(page, f"{category_name.lower()}_category_open")

    # --- Step 3: Notifications tab ---
    if not click_notifications_tab(page, pause_ms):
        return True  # no Notifications tab — skip gracefully
    snooze(page, pause_ms)
    take_screenshot(page, f"{category_name.lower()}_notifications_tab")

    # --- Step 4: Edit ---
    if not try_click(page.get_by_role("button", name=re.compile(r"^Edit$", re.I))):
        return True  # nothing to edit — skip gracefully
    snooze(page, pause_ms)
    take_screenshot(page, f"{category_name.lower()}_edit_open")

    # --- Step 5: Checkbox clicking — 5 fallbacks ---
    # We know it's Yes from the list so we always attempt to uncheck.
    # Each fallback logs which one worked so screenshots + logs tell the story.
    clicked = False

    # Fallback 1 — plain get_by_text (simplest, usually works)
    if not clicked:
        try:
            page.get_by_text("Enable notifications").click()
            clicked = True
            log_and_print(f"{category_name}: clicked checkbox via get_by_text")
        except Exception:
            pass

    # Fallback 2 — scoped to ADF page container
    if not clicked:
        try:
            page.locator('[id="_FOpt1:_UISpageCust"]').get_by_text("Enable notifications").click()
            clicked = True
            log_and_print(f"{category_name}: clicked checkbox via ADF container")
        except Exception:
            pass

    # Fallback 3 — checkbox role with name match
    if not clicked:
        try:
            page.get_by_role("checkbox", name=re.compile(r"Enable notifications", re.I)).click()
            clicked = True
            log_and_print(f"{category_name}: clicked checkbox via checkbox role")
        except Exception:
            pass

    # Fallback 4 — label element containing the text
    if not clicked:
        try:
            page.locator("label").filter(
                has_text=re.compile(r"Enable notifications", re.I)
            ).click()
            clicked = True
            log_and_print(f"{category_name}: clicked checkbox via label")
        except Exception:
            pass

    # Fallback 5 — input[type=checkbox] inside the row containing the text
    if not clicked:
        try:
            page.locator("tr").filter(
                has_text=re.compile(r"Enable notifications", re.I)
            ).locator("input[type='checkbox']").click()
            clicked = True
            log_and_print(f"{category_name}: clicked checkbox via tr > input")
        except Exception:
            pass

    if clicked:
        snooze(page, 400)
        take_screenshot(page, f"{category_name.lower()}_unchecked")
        log_and_print(f"Disabled notifications for: {category_name}")
    else:
        log_and_print(f"All 5 fallbacks failed for {category_name} checkbox", level="warning")

    # --- Step 6: Save (respect DRY_RUN) ---
    if not DRY_RUN:
        with suppress(Exception):
            page.get_by_role("button", name=re.compile(r"^Save$", re.I)).click()
            snooze(page, pause_ms)
            take_screenshot(page, f"{category_name.lower()}_after_save")

    # --- Step 7: Done x2 (Oracle sometimes needs two clicks) ---
    for _ in range(2):
        with suppress(Exception):
            page.get_by_role("button", name=re.compile(r"^Done$", re.I)).click()
            snooze(page, pause_ms)

    take_screenshot(page, f"{category_name.lower()}_done")
    return True

# -----------------------------

def run(playwright: Playwright) -> None:
    context = playwright.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
        args=["--disable-notifications"],
    )

    page = context.new_page()

    # go straight to home
    page.goto(HOME_URL)
    page.wait_for_load_state("domcontentloaded")
    snooze(page)
    take_screenshot(page, "home_loaded")

    # Login (auto-detects standard vs IDCS)
    login = get_login_page(page, build_login_config(ENV_PREFIX), logger=log_and_print)
    login.login()
    if not login.is_logged_in():
        raise RuntimeError(f"Login failed (env={ENV_PREFIX or 'default'})")
    take_screenshot(page, "after_login")

    # Home (idempotent)
    with suppress(Exception):
        page.get_by_role("link", name="Home", exact=True).click()
        snooze(page)
    take_screenshot(page, "home_nav")

    # Notifications flow
    open_notifications(page, PAUSE)
    take_screenshot(page, "notifications_open")

    # Worklist popup
    with page.expect_popup() as page1_info:
        page.get_by_role("button", name="Worklist").click()
    page1 = page1_info.value
    page1.wait_for_load_state("domcontentloaded")
    snooze(page1)
    take_screenshot(page1, "worklist_popup")

        # User menu → Administration
    with suppress(Exception):
        # Try clicking Administration directly first (in case it's already visible)
        if not try_click(page1.get_by_text(re.compile(r"\bAdministration\b", re.I))):
            # Otherwise click the first menuitem (usually the user name), then Administration
            menu_items = page1.get_by_role("menuitem")
            with suppress(Exception):
                menu_items.first.click()
                snooze(page1)
            try_click(page1.get_by_text(re.compile(r"\bAdministration\b", re.I)))
        snooze(page1)
    take_screenshot(page1, "administration_open")

    # --- scroll Notification Mode into view before selecting ---
    mode = page1.get_by_label("Notification Mode")
    mode.scroll_into_view_if_needed()
    snooze(page1, 500)
    take_screenshot(page1, "mode_visible_before_select")

    # Now perform the selection
    mode.select_option("1")
    snooze(page1)
    take_screenshot(page1, "after_select_Notification_mode")

    # --- START OF NOTIFICATION TASK STEPS ---
    # Since Administration is already open from the previous steps:
    page1.get_by_role("link", name="Edit Test Notification Email").click()
    snooze(page1)

    # Handle the Email Textbox
    page1.get_by_role("textbox", name="Test Notification Email").click()
    page1.get_by_role("textbox", name="Test Notification Email").press("ControlOrMeta+a")
    page1.get_by_role("textbox", name="Test Notification Email").fill("Oracle@sunnyvale.ca.gov")
    take_screenshot(page1, "notification_email_filled")

    # Click OK on the email popup
    page1.get_by_role("button", name="OK").click()
    snooze(page1)

   
    take_screenshot(page1, "notification_email_completed")
    # --- END OF NOTIFICATION TASK STEPS ---

    if not DRY_RUN:
        page1.get_by_role("button", name="Save").click()
        snooze(page1)
        take_screenshot(page1, "after_save")

    page1.close()
    snooze(page)

    # back Home
    with suppress(Exception):
        page.get_by_role("link", name="Home", exact=True).click()
        snooze(page)
    take_screenshot(page, "final_home")

        # === Security Console category-level disabler ===
    try:
        sec_page = go_security_console(page, PAUSE)

        processed_any = False
        for cat in NOTIFICATION_CATEGORIES:
            # NEW: always ensure we are back on the list before clicking the next category
            ensure_user_categories_list(sec_page, PAUSE)

            handled = disable_category_notifications(sec_page, cat, PAUSE)
            processed_any = processed_any or handled

        # After processing categories, return Home (from sec_page context)
        with suppress(Exception):
            sec_page.get_by_role("link", name="Home", exact=True).click()
            snooze(sec_page)
        take_screenshot(sec_page, "after_security_console")

        if not processed_any:
            log_and_print(
                "No categories found to process in Security Console (list may be empty or links hidden).",
                level="warning"
            )
    except Exception as e:
        log_and_print(f"Security Console flow skipped due to error: {e}", level="warning")


    # Success + cleanup
    log_and_print("Email notifications successfully disabled (or navigated in dry run mode)!")
    cleanup_screenshots(retain_days=7, keep_latest=200)
    log_and_print("Screenshot cleanup complete.")

    context.close()

# --- main guard (must be top-level, not indented) ---
if __name__ == "__main__":
    with sync_playwright() as p:
        try:
            run(p)
        except Exception as e:
            log_and_print(f"Error occurred: {e}", level="error")
            # Not attempting screenshot here because 'page' is scoped inside run()
            raise