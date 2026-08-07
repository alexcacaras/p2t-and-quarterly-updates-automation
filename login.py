"""
Sunnyvale ESS — UI login handling.

Consolidated from the multi-client login page objects and flattened for this
project's flat layout. Supports the standard Oracle Cloud login and IDCS, with
optional auto-detect. 
"""

import re
from contextlib import suppress
from crypto_env import get_env


# --------------------------------------------------------------------------
# Config builder — bridges the project's get_env(prefix) scheme to a config dict
# --------------------------------------------------------------------------
def build_login_config(env_prefix: str = "") -> dict:
    base = (get_env("FUSION_BASEURL", env_prefix) or "").rstrip("/")
    return {
        "base_url": f"{base}/fscmUI/faces/AtkHomePageWelcome",
        "login_type": (get_env("LOGIN_TYPE", env_prefix) or "auto").lower(),
        "credentials": {
            "username": get_env("FUSION_USER", env_prefix),
            "password": get_env("FUSION_PASS", env_prefix),
        },
        "browser": {"slow_mo": int(get_env("UI_SLOW_MO", env_prefix) or 3500)},
    }


# --------------------------------------------------------------------------
# Standard Oracle Cloud login (User ID / Password / Sign In on one screen)
# --------------------------------------------------------------------------
class LoginPage:
    USERNAME_NAME = re.compile(r"User\s*ID", re.I)
    PASSWORD_NAME = re.compile(r"Password", re.I)
    SIGN_IN_NAME  = re.compile(r"Sign\s*In", re.I)

    def __init__(self, page, config):
        self.page = page
        self.config = config
        self.base_url = config["base_url"]
        self.credentials = config["credentials"]
        self.pause = config.get("browser", {}).get("slow_mo", 3500)

    def _do(self, fn, desc: str = ""):
        fn()
        return True

    def snooze(self, ms: int = None):
        self.page.wait_for_timeout(ms or self.pause)

    def _user_box(self):
        return self.page.get_by_role("textbox", name=self.USERNAME_NAME)

    def _pass_box(self):
        return self.page.get_by_role("textbox", name=self.PASSWORD_NAME)

    def _sign_in_btn(self):
        return self.page.get_by_role("button", name=self.SIGN_IN_NAME)

    def navigate(self):
        self.page.goto(self.base_url)
        self.page.wait_for_load_state("domcontentloaded")
        self.snooze(600)

    def is_already_logged_in(self) -> bool:
        try:
            self.page.get_by_role("link", name="Home", exact=True).wait_for(
                state="visible", timeout=4000
            )
            return True
        except Exception:
            return False

    # overridable hook — standard uses fill(), IDCS overrides to type()
    def _enter_password(self, box, pwd: str):
        self._do(lambda: box.fill(pwd), "Fill password")

    def login(self, username: str = None, password: str = None):
        self.navigate()
        if self.is_already_logged_in():
            self.go_home()
            return

        user = username or self.credentials["username"]
        pwd  = password or self.credentials["password"]
        ubox = self._user_box()
        pbox = self._pass_box()

        self._do(lambda: ubox.click(), "Click username field"); self.snooze(500)
        self._do(lambda: ubox.fill(user), f"Fill username: {user}"); self.snooze(1000)
        self._do(lambda: pbox.click(), "Click password field"); self.snooze(500)
        self._enter_password(pbox, pwd); self.snooze(1000)

        self._do(lambda: self._sign_in_btn().click(), "Click Sign In button")
        self.page.wait_for_load_state("domcontentloaded")
        self.snooze(800)
        self.go_home()

    def go_home(self):
        with suppress(Exception):
            self.page.get_by_role("link", name="Home", exact=True).click()
            self.snooze()

    def is_logged_in(self) -> bool:
        try:
            self.page.get_by_role("link", name="Home", exact=True).wait_for(
                state="visible", timeout=15000
            )
            return True
        except Exception:
            return False


# --------------------------------------------------------------------------
# IDCS login — single screen (Username / Password / Next).
# Only the field labels and button text differ from standard; everything else
# is inherited. Selectors confirmed via Playwright codegen against the live page.
# --------------------------------------------------------------------------
class LoginPageIDCS(LoginPage):
    USERNAME_NAME = re.compile(r"^Username$", re.I)
    PASSWORD_NAME = re.compile(r"^Password$", re.I)
    SIGN_IN_NAME  = re.compile(r"^Next$", re.I)

    def _enter_password(self, box, pwd: str):
        # IDCS password field can reject fill(); type() is more reliable
        self._do(lambda: box.type(pwd), "Type password")


# --------------------------------------------------------------------------
# Factory + auto-detect
# --------------------------------------------------------------------------
LOGIN_TYPES = {
    "standard": LoginPage,
    "idcs": LoginPageIDCS,
}


def _detect_login_type(page, base_url: str, logger=None) -> str:
    """Navigate to the deep link (triggers any IdP redirect), then fingerprint the URL."""
    page.goto(base_url)
    page.wait_for_load_state("domcontentloaded")
    url = page.url.lower()

    if "/ui/v1/signin" in url or "idcs" in url or "identity.oraclecloud.com" in url:
        detected = "idcs"
    else:
        detected = "standard"

    if logger:
        logger(f"[login] auto-detect -> {detected} (url={page.url})")
    return detected


def get_login_page(page, config: dict, logger=None):
    """Return the right login page object. login_type 'auto' runs detection."""
    login_type = config.get("login_type", "standard").lower()

    if login_type == "auto":
        login_type = _detect_login_type(page, config["base_url"], logger)

    if login_type not in LOGIN_TYPES:
        raise ValueError(
            f"Unknown login_type: '{login_type}'. Available: {list(LOGIN_TYPES)}."
        )

    return LOGIN_TYPES[login_type](page, config)