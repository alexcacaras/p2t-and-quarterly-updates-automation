from typing import Any, Dict, List            # type hints for return values
import requests                               # HTTP requests to Oracle Fusion REST API
import os
import sys                                     # read environment variables
from requests.auth import HTTPBasicAuth       # basic auth for API session
from crypto_env import load_env_from_encrypted, get_env, _get_env_prefix # loads credentials from encrypted .env file into memory
load_env_from_encrypted()                     # decrypt and inject .env vars into os.environ at module load


ENV_PREFIX = _get_env_prefix()

class HCMClient:
    """
    Flow:
    1) Get GUID for each username via GET /hcmCoreSetupApi/scim/Users?filter=userName eq "XXX"
    2) Use each GUID to reset password via PATCH /hcmRestApi/scim/Users/{GUID}

    Auth: FUSION_USER_RESETTER account (Stella or sdayanathan) — must have IT Security Manager role
    Passwords: each scheduler account resets to its own password stored in .env
    """

    def __init__(self):
        self.base_url = get_env("FUSION_BASEURL", ENV_PREFIX).rstrip("/")
        self.session = requests.Session()
        # Resetter account — the full-access user running this script
        self.session.auth = HTTPBasicAuth(
            get_env("FUSION_USER_RESETTER", ENV_PREFIX),
            get_env("FUSION_PASS_RESETTER", ENV_PREFIX)
        )
        # Each account maps to its own password in .env
        self.scheduler_accounts = [
            {
                "username": get_env("FUSION_hcm_LOGIN", ENV_PREFIX),
                "password": get_env("FUSION_hcm_PASSWORD", ENV_PREFIX),
            },
            {
                "username": get_env("FUSION_fin_LOGIN", ENV_PREFIX),
                "password": get_env("FUSION_fin_PASSWORD", ENV_PREFIX),
            },
            {
                "username": get_env("FUSION_it_LOGIN", ENV_PREFIX),
                "password": get_env("FUSION_it_PASSWORD", ENV_PREFIX),
            },
        ]
    # ------------------------------------------------------------------
    # Step 1 — Get GUID for a single username
    # ------------------------------------------------------------------
    def get_guid_by_username(self, username: str) -> str:
        """
        GET /hcmCoreSetupApi/scim/Users?filter=userName eq "username"
        Returns the GUID string for that user.
        """
        url = f"{self.base_url}/hcmCoreSetupApi/scim/Users"
        params = {"filter": f'userName eq "{username}"'}

        resp = self.session.get(url, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        resources = data.get("Resources", [])
        if not resources:
            raise ValueError(f"No user found for username: {username}")

        guid = resources[0]["id"]
        print(f"  Found GUID for {username}: {guid}")
        return guid

    # ------------------------------------------------------------------
    # Step 2 — Patch password for a single user by GUID
    # ------------------------------------------------------------------
    def patch_password(self, username: str, guid: str, new_password: str) -> Dict[str, Any]:
        """
        PATCH /hcmRestApi/scim/Users/{guid}
        Sets the password to the account's own password from .env
        """
        url = f"{self.base_url}/hcmRestApi/scim/Users/{guid}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "schemas": ["urn:scim:schemas:core:2.0:User"],
            "password": new_password
        }

        resp = self.session.patch(url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        print(f"  Password reset successful for {username} (GUID: {guid})")
        return resp.json()

    # ------------------------------------------------------------------
    # Main workflow — loops all 3 accounts
    # ------------------------------------------------------------------
    def run(self, dry_run: bool = False) -> List[Dict[str, Any]]:
        """
        For each scheduler account:
          1. Get GUID
          2. Reset password to its own .env password
        Returns a list of results.
        """
        results = []

        for account in self.scheduler_accounts:
            username = account["username"]
            new_password = account["password"]
            print(f"\nProcessing: {username}")

            if not new_password:
                print(f"  ERROR: No password found in .env for {username} — skipping")
                results.append({"username": username, "error": "missing password in .env"})
                continue

            try:
                # Step 1 — get GUID
                print("  Step 1: Getting GUID...")
                guid = self.get_guid_by_username(username)

                # Step 2 — reset password
                if dry_run:
                    print(f"  DRY RUN — would PATCH password for {username} (GUID: {guid})")
                    results.append({"username": username, "guid": guid, "dry_run": True})
                else:
                    print("  Step 2: Resetting password...")
                    result = self.patch_password(username, guid, new_password)
                    results.append({"username": username, "guid": guid, "result": result})

            except Exception as e:
                print(f"  ERROR for {username}: {e}")
                results.append({"username": username, "error": str(e)})

        return results


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="")
    ap.parse_args()
    client = HCMClient()
    # Set dry_run=True to test without actually changing passwords
    results = client.run(dry_run=False)
    print("\n--- Summary ---")
    for r in results:
        print(r)