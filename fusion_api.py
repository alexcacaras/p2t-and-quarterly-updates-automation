# fusion_api.py
from __future__ import annotations  # must be the very first import, for simplifying type hinting throughout file

import json  #for conversion between python object and json format for logging rest api requests
import time #for time-related functions such as timeout
from typing import Optional, Dict, List, TypedDict  #for type hint and code readability

import requests #for HTTP library to simplify rest api calls
from requests.adapters import HTTPAdapter #for HTTP sessions
from urllib3.util.retry import Retry  #for auto retries

# terminal states as seen in ESS request objects
TERMINAL_STATES = {"SUCCEEDED", "SUCCESS", "ERROR", "FAILED", "WARNING", "CANCELLED"}


class ESSApiError(Exception):
    ...


class ESSDuplicatePendingError(ESSApiError):
    ...


# --- helper to normalize/split any jobDefinitionId into package+name -----------------
def _split_job_id(job_definition_id: str) -> Dict[str, str]:
    """
    Accepts any of:
      - JobDefinition://<path>/<name>
      - /<path>/<name>
      - <path>/<name>
      - <name>

    Returns a dict with keys:
      - jobPackageName (optional, includes leading '/')
      - jobDefinitionName
    """
    s = (job_definition_id or "").strip()
    if not s:
        return {}
    if s.startswith("JobDefinition://"):
        s = s[len("JobDefinition://") :]
    s = s.lstrip("/")  # make parsing tolerant

    parts = s.rsplit("/", 1)
    if len(parts) == 2:
        return {"jobPackageName": "/" + parts[0], "jobDefinitionName": parts[1]}
    else:
        return {"jobDefinitionName": s}


class ESSClient:
    """
    Thin client for Fusion ESS REST.

    - POST /ess/rest/scheduler/v1/requests to submit jobs.
    - GET  /ess/rest/scheduler/v1/requests/{id} to check status.
    """

    def __init__(self, base_url: str, username: str, password: str, timeout: int = 60):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self._requests = f"{self.base}/ess/rest/scheduler/v1/requests"
        self._jobdefs = f"{self.base}/ess/rest/scheduler/v1/jobDefinitions"
        # kept in case you later want ERP Integrations fallback
        self._erp_status = f"{self.base}/fscmRestApi/resources/11.13.18.05/erpintegrations"

        s = requests.Session()
        s.auth = (username, password)

        # Use JSON and include X-Requested-By for POSTs
        s.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Requested-By": "ess-client",
            }
        )

        retry = Retry(
            total=5,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        s.mount("https://", HTTPAdapter(max_retries=retry))
        s.mount("http://", HTTPAdapter(max_retries=retry))
        s.verify = False  # skip SSL cert verification for corporate proxy environments
        self.sess = s

    # -------------------- SUBMIT (with schema/404 auto-fallback) --------------------
    def submit(
        self,
        job_definition_id: str,
        application: str,
        params: Dict[str, str],
        schedule: Dict,
        description: str = "",
        dry_run: bool = False,
        logger=None,
        *,
        job_package_name: Optional[str] = None,
        job_definition_name: Optional[str] = None,
        class_name: Optional[str] = None,  # fully-qualified Java class if required
    ) -> int:
        """
        Submit a job.

        - `params` may contain named prompts (e.g., "Index Name for recreate"),
          generic "argumentN", and/or "submit.argumentN".
        - We build the expected array of {"name","value","paramType"} and include it
          under BOTH `requestParameters` and `parameters`.
        - We keep parameter names EXACT (do NOT strip 'submit.'), because some pods
          only read 'submit.argument1'.
        """

        # --- request parameters array (keep names exact) ---
        req_params: List[Dict[str, str]] = []
        for k, v in (params or {}).items():
            if v is None or str(v) == "":
                continue
            name = k  # KEEP EXACT KEY, INCLUDING 'submit.argument1'
            req_params.append({"name": name, "paramType": "STRING", "value": str(v)})

        # Optional debug: confirm which names are being sent
        if logger:
            try:
                logger.info("Param names being sent: " + ", ".join([p["name"] for p in req_params]))
            except Exception:
                pass

        # --- normalize identifiers (derive pkg/name from id if not provided)
        pkg = (job_package_name or "").strip()
        jname = (job_definition_name or "").strip()
        if not (pkg and jname):
            split = _split_job_id(job_definition_id)
            pkg = pkg or split.get("jobPackageName", "")
            jname = jname or split.get("jobDefinitionName", "")

        # Canonicalize common typo for this path (harmless elsewhere)
        jd_for_id = (job_definition_id or "").strip()
        if jd_for_id and "/fnd/appcore/" in jd_for_id:
            jd_for_id = jd_for_id.replace("/fnd/appcore/", "/fnd/applcore/")
        # If we have pkg+name but no explicit ID, synthesize one
        if pkg and jname and not jd_for_id:
            jd_for_id = f"/{pkg.lstrip('/')}/{jname}"

        def _base_payload() -> Dict:
            p = {
                "description": description or "",
                "application": application,
                # send on BOTH keys for cross-pod compatibility
                "requestParameters": req_params,
                "parameters": req_params,
            }
            if schedule:
                p["schedule"] = schedule
            return p

        # two payload shapes
        payload_id = _base_payload()
        if jd_for_id:
            payload_id["jobDefinitionId"] = jd_for_id
        if class_name:
            payload_id["className"] = class_name

        payload_pkg = _base_payload()
        if pkg:
            payload_pkg["jobPackageName"] = pkg
        if jname:
            payload_pkg["jobDefinitionName"] = jname
        if class_name:
            payload_pkg["className"] = class_name

        # Decide attempt order: if className present → try ID-mode first
        attempts: List[tuple[str, Dict]] = []
        if class_name:
            attempts.append(("jobDefinitionId", payload_id))
            attempts.append(("package+name", payload_pkg))
        else:
            attempts.append(("package+name", payload_pkg))
            attempts.append(("jobDefinitionId", payload_id))

        if dry_run:
            if logger:
                first_label, first_payload = attempts[0]
                logger.info(
                    f"[DRY RUN] Would POST to {self._requests} with payload ({first_label}):\n"
                    f"{json.dumps(first_payload, indent=2)}\n"
                    f"(fallback would be {attempts[1][0]} if needed)"
                )
            return 0

        last_err = None
        for label, payload in attempts:
            if logger:
                mode = "runNow" if not payload.get("schedule") else "scheduled"
                logger.info(f"Submitting ({label}) {mode} → app={application}")
                logger.info("Payload:\n" + json.dumps(payload, indent=2))

            r = self.sess.post(self._requests, json=payload, timeout=self.timeout)
            if r.status_code < 300:
                data = r.json() or {}
                req_id = (
                    data.get("id")
                    or data.get("requestId")
                    or (data.get("requestExecutionContext") or {}).get("requestId")
                )
                if not req_id:
                    raise ESSApiError(f"No requestId in response: {data}")
                return int(req_id)

            txt = (r.text or "")
            last_err = f"{r.status_code} {txt}"

            # Fallback on schema mismatch *or* not-found errors
            schema_or_not_found = (
                r.status_code == 404
                or any(
                    m in txt.lower()
                    for m in (
                        "unrecognized field",
                        "unrecognized property",
                        "invalid metadata object type",
                        "while parsing the metadata object id string",
                        "ess-11003",
                        "not found",
                        "does not exist",
                        "no job definition",
                    )
                )
            )
            if schema_or_not_found:
                continue  # try the alternate payload shape

            if "ESS-01050" in txt:
                raise ESSDuplicatePendingError(txt)
            raise ESSApiError(f"Submit failed: {last_err}")

        raise ESSApiError(f"Submit failed after both forms. Last error: {last_err}")

    # -------------------- Lookup helpers (by Display Name) --------------------------
    def search_job_definitions(self, display_name: str, exact: bool = True) -> List[Dict]:
        """
        Query the ESS job catalog for job definitions by display name.
        Tries SCIM-style filters (exact: 'eq', fuzzy: 'co').
        NOTE: Some pods block catalog access; in that case this returns [].
        """
        q = f'displayName eq "{display_name}"' if exact else f'displayName co "{display_name}"'
        r = self.sess.get(self._jobdefs, params={"q": q}, timeout=self.timeout)
        if r.status_code >= 300:
            return []
        return (r.json() or {}).get("items") or []

    def resolve_job_by_name(self, display_name: str) -> Optional[Dict[str, str]]:
        """
        Best-effort resolver:
          1) exact match
          2) contains match
        Returns as much as the pod exposes (may include package+name).
        """
        if not display_name:
            return None

        items = self.search_job_definitions(display_name, exact=True)
        if not items:
            items = self.search_job_definitions(display_name, exact=False)
        if not items:
            return None

        it = items[0]
        out = {
            "application": it.get("application") or "",
            "jobDefinitionId": "",
            "jobPackageName": it.get("jobPackageName") or it.get("path") or "",
            "jobDefinitionName": it.get("jobDefinitionName") or it.get("name") or "",
        }
        if out["jobPackageName"] and out["jobDefinitionName"]:
            out["jobDefinitionId"] = f"/{out['jobPackageName'].lstrip('/')}/{out['jobDefinitionName']}"
        return out

    # -------------------- Request status helpers ------------------------------------
    def get_request(self, request_id: int) -> Dict:
        r = self.sess.get(f"{self._requests}/{request_id}", timeout=self.timeout)
        return r.json() if r.status_code == 200 else {}

    def get_status(self, request_id: int) -> Dict:
        j = self.get_request(request_id)
        st = (j.get("state") or j.get("Status") or j.get("status") or "").upper()
        if st:
            j["Status"] = st
        return j

    def list_requests_by_definition(self, job_definition_id: str) -> List[Dict]:
        r = self.sess.get(
            self._requests,
            params={"q": f'jobDefinitionId eq "{job_definition_id}"'},
            timeout=self.timeout,
        )
        if r.status_code >= 300:
            return []
        return (r.json() or {}).get("items") or []

    def find_active_request_for_definition(self, job_definition_id: str) -> Optional[int]:
        for it in self.list_requests_by_definition(job_definition_id):
            state = (it.get("state") or it.get("Status") or "").upper()
            rid = it.get("requestId") or it.get("absParentRequestId") or it.get("id")
            if rid and state and state not in TERMINAL_STATES:
                try:
                    return int(rid)
                except Exception:
                    continue
        return None
    def find_active_scheduled_request( #new*******
        self,
        job_definition_id: str,
        start_date: str = "",
        argument1: str = "",
    ) -> Optional[int]:
        """
        Smarter duplicate check for SCHEDULED jobs.
        Only considers it a duplicate if ALL THREE match:
          - same jobDefinitionId
          - same startDate (if provided)
          - same argument1 (if provided)
        If any one differs → NOT a duplicate → returns None.
        ***********************THIS IS NEW**************************
        """
        def _norm(d: str) -> str:
            return d.strip().split(".")[0].replace("Z", "").replace("+00:00", "")

        for it in self.list_requests_by_definition(job_definition_id):
            state = (it.get("state") or it.get("Status") or "").upper()
            rid = it.get("requestId") or it.get("absParentRequestId") or it.get("id")
            if not rid or not state or state in TERMINAL_STATES:
                continue

            # Check startDate if we have one to compare
            if start_date:
                existing_start = ""
                try:
                    existing_start = (
                        it.get("schedule", {})
                        .get("recurrences", [{}])[0]
                        .get("startDate", "")
                    ) or ""
                except Exception:
                    pass
                if _norm(start_date) != _norm(existing_start):
                    continue  # different startDate → NOT a duplicate

            # Check argument1 if we have one to compare
            if argument1:
                existing_arg1 = ""
                try:
                    req_params = it.get("requestParameters") or it.get("parameters") or []
                    for p in req_params:
                        if (p.get("name") or "").lower() in ("argument1", "submit.argument1"):
                            existing_arg1 = str(p.get("value") or "").strip()
                            break
                except Exception:
                    pass
                if argument1.lower() != existing_arg1.lower():
                    continue  # different argument1 → NOT a duplicate

            # All checks passed → it's a duplicate
            try:
                return int(rid)
            except Exception:
                continue

        return None
    
    def cancel(self, request_id: int) -> Dict:
        r = self.sess.post(f"{self._requests}/{request_id}/cancel", timeout=self.timeout)
        return {"status": r.status_code, "body": r.text}

    def force_cancel(self, request_id: int) -> Dict:
        r = self.sess.post(f"{self._requests}/{request_id}/forceCancel", timeout=self.timeout)
        return {"status": r.status_code, "body": r.text}

    def poll_until_complete(
        self,
        request_id: int,
        poll_seconds: int = 10,
        timeout_seconds: int = 3600,
        wait_warn_minutes: int = 20,
        logger=None,
    ) -> Dict:
        start = time.time()
        wait_started = None
        while True:
            status = self.get_status(request_id)
            state = (status.get("Status") or "").upper()

            if logger:
                logger.info(f"Polling request_id={request_id} → {state or 'UNKNOWN'}")
                extra = []
                for k in (
                    "progress",
                    "submittedTime",
                    "startTime",
                    "endTime",
                    "stateDetails",
                    "message",
                    "description",
                ):
                    if status.get(k):
                        extra.append(f"{k}={status.get(k)}")
                if extra:
                    logger.info("  details: " + ", ".join(extra))

            if state in TERMINAL_STATES:
                return status

            if state == "WAIT":
                if wait_started is None:
                    wait_started = time.time()
                elif time.time() - wait_started > wait_warn_minutes * 60 and logger:
                    logger.warning(
                        f"request_id={request_id} stuck in WAIT > {wait_warn_minutes} min (still polling)."
                    )
            else:
                wait_started = None

            if time.time() - start > timeout_seconds:
                if logger:
                    logger.error(f"Timeout waiting for request_id={request_id}")
                return status or {}

            time.sleep(poll_seconds)


class JobRequest(TypedDict, total=False):
    pass
