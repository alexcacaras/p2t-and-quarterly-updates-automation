import os                          # for creating log directory
import sys                         # for sys.exit on step failure
from datetime import datetime      # for timestamps if needed
from resetpasswords import HCMClient          # password reset module for scheduler accounts
from HDLimport import HDLClient               # HDL file import module for Oracle HCM
from ldap import LDAPJobClient                # ESS LDAP sync job module
from data_access_loader import DataAccessClient  # data access assignment module
from notify import send_notification #email sender 
from crypto_env import load_env_from_encrypted, _get_env_prefix
load_env_from_encrypted()
ENV_PREFIX = _get_env_prefix()
# ----------------- For logging -------------------
import logging  # built in logging
from logging.handlers import RotatingFileHandler  # for preventing too large logs
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

def make_ui_logger():
    log_name = f"Security_Refresh_{ENV_PREFIX}" if ENV_PREFIX else "Security_Refresh"
    log_file = f"Security_Refresh_{ENV_PREFIX}.log" if ENV_PREFIX else "Security_Refresh.log"
    log = logging.getLogger(log_name)
    if log.handlers:
        return log  # already configured
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | Security_Refresh | %(message)s",
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


def main():
    errors = []
    crashed = False
    try:


        log.info("=" * 50)
        log.info("SECURITY REFRESH STARTED")
        log.info("=" * 50)

        try:
            log.info("STEP 1: Resetting passwords...")
            HCMClient().run()
            log.info("STEP 1: Complete ")
        except Exception as e:
            log.error(f"STEP 1 FAILED — Password Reset: {e}")
            errors.append(f"STEP 1 FAILED — Password Reset: {e}")
            crashed = True
            sys.exit(1)

        try:
            log.info("STEP 2: HDL import Worker.zip...")
            HDLClient().run("Worker.zip")
            log.info("STEP 2: Complete ")
        except Exception as e:
            log.error(f"STEP 2 FAILED — HDL Worker: {e}")
            errors.append(f"STEP 2 FAILED — HDL Worker: {e}")
            crashed = True
            sys.exit(1)

        try:
            log.info("STEP 3: Running LDAP job...")
            LDAPJobClient().run()
            log.info("STEP 3: Complete ")
        except Exception as e:
            log.error(f"STEP 3 FAILED — LDAP Job: {e}")
            errors.append(f"STEP 3 FAILED — LDAP Job: {e}")
            crashed = True
            sys.exit(1)

        try:
            log.info("STEP 4: HDL import User.zip...")
            HDLClient().run("User.zip")
            log.info("STEP 4: Complete ")
        except Exception as e:
            log.error(f"STEP 4 FAILED — HDL User: {e}")
            errors.append(f"STEP 4 FAILED — HDL User: {e}")
            crashed = True
            sys.exit(1)

        try:
            log.info("STEP 5: Running LDAP job...")
            LDAPJobClient().run()
            log.info("STEP 5: Complete ")
        except Exception as e:
            log.error(f"STEP 5 FAILED — LDAP Job: {e}")
            errors.append(f"STEP 5 FAILED — LDAP Job: {e}")
            crashed = True
            sys.exit(1)

        try:
            log.info("STEP 6: Updating data access...")
            DataAccessClient().run()
            log.info("STEP 6: Complete ")
        except Exception as e:
            log.error(f"STEP 6 FAILED — Data Access: {e}")
            errors.append(f"STEP 6 FAILED — Data Access: {e}")
            crashed = True
            sys.exit(1)

        try:
            log.info("STEP 7: HDL import RoleMapping.zip...")
            HDLClient().run("RoleMapping.zip")
            log.info("STEP 7: Complete ")
        except Exception as e:
            log.error(f"STEP 7 FAILED — HDL RoleMapping: {e}")
            errors.append(f"STEP 7 FAILED — HDL RoleMapping: {e}")
            crashed = True
            sys.exit(1)

        log.info("=" * 50)
        log.info("SECURITY REFRESH COMPLETE ")
        log.info("=" * 50)
        
    finally:
        if errors:
            status = "TERMINATED" if crashed else "COMPLETED WITH ERRORS"
            subject = f"[{ENV_PREFIX or 'default'}] Security Refresh - {status}"
            body = "\n".join(errors)
            send_notification(subject, body)

        

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="")
    ap.parse_args()
    main()