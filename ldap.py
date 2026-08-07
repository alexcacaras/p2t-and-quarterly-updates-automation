import os # read environment variables
from typing import Dict, Any # type hints for return values
from crypto_env import load_env_from_encrypted, get_env, _get_env_prefix # dotenv for loading env variables from .env file into python but from the encypted version
from fusion_api import ESSClient # shared Oracle Fusion REST API client created from my code
load_env_from_encrypted()   # load .env before reading env vars from encrypted version

ENV_PREFIX = _get_env_prefix()


class LDAPJobClient:
    """
    Submits and polls the 'Send Pending LDAP Requests' ESS job.
    Uses ESSClient from fusion_api.py for HTTP handling.
    """
    JOB_NAME = "ProcessLdapRequests"
    JOB_PATH = "/oracle/apps/ess/hcm/users"
    JOB_APP  = "EarHcmEss"
    JOB_ARGS = {"argument1": "ALL", "argument2": "ALL", "argument3": "A"}

    def __init__(self):
        self.client = ESSClient(
            base_url=get_env("FUSION_BASEURL", ENV_PREFIX),
            username=get_env("FUSION_it_LOGIN", ENV_PREFIX),
            password=get_env("FUSION_it_PASSWORD", ENV_PREFIX)
        )

    def run(self) -> Dict[str, Any]:
        print("\n==================================================")
        print("ESS JOB: Send Pending LDAP Requests")
        print("==================================================")

        # Step 1 — Submit directly (bypass ESSClient submit to avoid ID mangling)
        print("STEP 1: Submitting LDAP job...")
        url = f"{self.client.base}/ess/rest/scheduler/v1/requests"
        payload = {
            "jobDefinitionId": "JobDefinition://oracle/apps/ess/hcm/users/ProcessLdapRequests",
            "application": "EarHcmEss",
            "parameters": [
                {"name": "argument1", "value": "ALL", "paramType": "STRING"},
                {"name": "argument2", "value": "ALL", "paramType": "STRING"},
                {"name": "argument3", "value": "A",   "paramType": "STRING"}
            ]
        }
        resp = self.client.sess.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        request_id = resp.json()["id"]
        print(f"  → RequestId: {request_id}")

        # Step 2 — Poll
        print("STEP 2: Waiting for job to complete...")
        result = self.client.poll_until_complete(request_id, poll_seconds=30)
        status = result.get("Status", "UNKNOWN")
        print(f"   Job complete | Status: {status}")

        if status not in ("SUCCEEDED", "SUCCESS"):
            raise Exception(f"LDAP job failed with status: {status}. RequestId: {request_id}")

        return {"request_id": request_id, "status": status}
# --------------------------
# Standalone test
# --------------------------
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="")
    ap.parse_args()
    ldap = LDAPJobClient()
    result = ldap.run()
    print(f"\nResult: {result}")