import base64          # encode .zip file to base64 string for API payload
import os              # read environment variables
import time            # sleep between polling attempts
from pathlib import Path          # handle file paths cross-platform
from typing import Dict, Any      # type hints for return values
import sys
import requests                   # HTTP requests to Oracle Fusion REST API
from requests.auth import HTTPBasicAuth   # basic auth for API session
from crypto_env import load_env_from_encrypted, get_env, _get_env_prefix # dotenv for loading env variables from .env file into python but from the encypted version

load_env_from_encrypted()   # load .env before reading env vars from encrypted version

ENV_PREFIX = _get_env_prefix()


class HDLClient:
    """
    Handles HDL (HCM Data Loader) file imports for Oracle Fusion.

    Flow:
        1) Base64 encode the .zip file from HDLimport folder
        2) POST to uploadFile → get ContentId
        3) POST to createFileDataSet → get RequestId
        4) Poll status until Success or Failure

    Required role on auth account:
        - Upload data for Human Capital Management file based import

    Usage:
        hdl = HDLClient()
        result = hdl.run("Worker.zip")
        result = hdl.run("User.zip")
        result = hdl.run("RoleMapping.zip")
    """

    HDL_FILES_FOLDER = "HDLimport"

    # --------------------------
    # Config
    # --------------------------
    def __init__(self):
        self.base_url = get_env("FUSION_BASEURL", ENV_PREFIX).rstrip("/")
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(
            get_env("FUSION_it_LOGIN", ENV_PREFIX),
            get_env("FUSION_it_PASSWORD", ENV_PREFIX)
        )
        self.session.headers.update({
            "Content-Type": "application/vnd.oracle.adf.action+json"
        })

    # --------------------------
    # Step 0 — Encode zip
    # --------------------------
    def _encode_zip(self, zip_path: Path) -> str:
        """
        Reads the .zip file and returns base64 encoded string.
        """
        with open(zip_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    # --------------------------
    # Step 1 — Upload
    # --------------------------
    def _upload_file(self, content: str, file_name: str) -> str:
        """
        POST to uploadFile endpoint.
        Returns ContentId.
        """
        url = f"{self.base_url}/hcmRestApi/resources/11.13.18.05/dataLoadDataSets/action/uploadFile"
        payload = {
            "content": content,
            "fileName": file_name
        }

        resp = self.session.post(url, json=payload, timeout=120)
        resp.raise_for_status()

        content_id = resp.json()["result"]["ContentId"]
        print(f"  → Uploaded {file_name} | ContentId: {content_id}")
        return content_id

    # --------------------------
    # Step 2 — Trigger HDL Load
    # --------------------------
    def _create_dataset(self, content_id: str) -> str:
        """
        POST to createFileDataSet endpoint.
        Returns RequestId.
        """
        url = f"{self.base_url}/hcmRestApi/resources/11.13.18.05/dataLoadDataSets/action/createFileDataSet"
        payload = {
            "contentId": content_id
        }

        resp = self.session.post(url, json=payload, timeout=120)
        resp.raise_for_status()

        request_id = resp.json()["result"]["RequestId"]
        print(f"  → HDL load triggered | RequestId: {request_id}")
        return request_id

    # --------------------------
    # Step 3 — Poll Status
    # --------------------------
    def _wait_for_completion(self, request_id: str, poll_interval: int = 10, timeout_minutes: int = 30):
        """
        Polls dataLoadDataSets/{requestId} until DataSetStatusCode is ORA_SUCCESS or fails.
        Raises exception if load fails or times out.
        """
        url = f"{self.base_url}/hcmRestApi/resources/11.13.18.05/dataLoadDataSets/{request_id}"
        headers = {"Accept": "application/json"}

        max_attempts = (timeout_minutes * 60) // poll_interval
        attempt = 0

        print(f"  → Polling status every {poll_interval}s (timeout: {timeout_minutes} min)...")
        time.sleep(15)
        while attempt < max_attempts:
            time.sleep(poll_interval)
            attempt += 1

            resp = self.session.get(url, headers=headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            status = data["DataSetStatusCode"]
            load_pct = data.get("LoadPercentageComplete", 0)
            import_pct = data.get("ImportPercentageComplete", 0)

            print(f"  → [{attempt}] Status: {status} | Import: {import_pct}% | Load: {load_pct}%")

            if status == "ORA_SUCCESS":
                failed_objects = data.get("ObjectLoadErrorCount", 0)
                total_objects = data.get("ObjectTotalCount", 0)
                print(f"   Load complete | Objects: {total_objects} total, {failed_objects} failed")
                if failed_objects > 0:
                    raise Exception(f"HDL load completed but {failed_objects} objects failed. Check Oracle HCM for details.")
                return data

            elif status == "ORA_WARNING":
                if import_pct == 100 and load_pct == 100:  # reuse same variables, no re-read
                    failed_objects = data.get("ObjectLoadErrorCount", 0)
                    total_objects = data.get("ObjectTotalCount", 0)
                    print(f"   Load complete with warnings | Objects: {total_objects} total, {failed_objects} failed")
                    return data
                # not 100% yet — keep polling

            elif status in ("ORA_ERROR", "ERROR", "FAILED"):
                raise Exception(f"HDL load failed with status: {status}. RequestId: {request_id}")

    # --------------------------
    # Run
    # --------------------------
    def run(self, zip_file: str, wait_for_completion: bool = True) -> Dict[str, Any]:
        """
        Full HDL load flow for a single .zip file.

        Args:
            zip_file: filename e.g. "Worker.zip", "User.zip", "RoleMapping.zip"
            wait_for_completion: if True, polls until done before returning

        Returns:
            dict with file, content_id, request_id, status
        """
        zip_path = Path(self.HDL_FILES_FOLDER) / zip_file

        if not zip_path.exists():
            raise FileNotFoundError(f"HDL file not found: {zip_path}")

        print(f"\n{'='*50}")
        print(f"HDL LOAD: {zip_file}")
        print(f"{'='*50}")

        # Step 0 — Encode zip
        print("STEP 1: Encoding zip...")
        content = self._encode_zip(zip_path)

        # Step 1 — Upload
        print("STEP 2: Uploading to Oracle WebCenter...")
        content_id = self._upload_file(content, zip_file)

        # Step 2 — Trigger load
        print("STEP 3: Triggering HDL load...")
        request_id = self._create_dataset(content_id)

        result = {
            "file": zip_file,
            "content_id": content_id,
            "request_id": request_id,
            "status": "submitted"
        }

        # Step 3 — Wait
        if wait_for_completion:
            print("STEP 4: Waiting for load to complete...")
            self._wait_for_completion(str(request_id))
            result["status"] = "success"

        return result


# --------------------------
# Standalone test
# --------------------------
if __name__ == "__main__":
    import argparse
    ap= argparse.ArgumentParser()
    ap.add_argument("--env", default="")
    ap.parse_args()
    hdl = HDLClient()
    result = hdl.run("Worker.zip") #change this to run others or to run all add , "" etc
    print(f"\nResult: {result}")