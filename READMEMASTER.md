SUNNYVALE ESS JOBS
Master README & Setup Guide
**Update August 2026 1.0.4 not complete yet for email notification**
Updated July 2026
**Update 1.0.3 IDCS Login Support (UI Scripts)**

**What is New:**
Oracle migrated the sign-in page to IDCS (/ui/v1/signin), which broke the old inline browser login in the UI scripts. Login is now handled by a shared login.py module that auto-detects whether an environment uses the classic Oracle login or the new IDCS login and picks the right one automatically. No per-environment configuration is required.

*1.1 What changed:*

New file login.py — one login module for all UI scripts. Contains a standard login class, an IDCS login class, and an auto-detect factory (get_login_page).
main_ui_auto.py and new_alertcomp.py no longer log in inline. They call get_login_page(...) which navigates, detects the login type from the redirect URL, fills credentials, and verifies success.
Auto-detect logs its decision to the env-specific log, e.g. [login] auto-detect -> idcs. If a login ever fails, check that line first.
Credentials are unchanged — still FUSION_USER / FUSION_PASS read via get_env() from .env.encrypted, so nothing new to add to .env.
Fully backward compatible — environments still on the classic login continue to work with no change.

*1.2 Optional override:*
Auto-detect runs by default. To force a specific login type for an environment and skip detection, add a prefixed var to .env (then re-encrypt):
TEST_LOGIN_TYPE=idcs
DEV1_LOGIN_TYPE=standard
Valid values: standard, idcs, or auto (default).
1.3 Files changed:
login.py            NEW — shared login module (standard + IDCS + auto-detect).
main_ui_auto.py     Login now delegates to login.py via get_login_page().
new_alertcomp.py    ensure_logged_in() now delegates to login.py.


UPDATED May 2026
**Update 1.0.2** Multi-Environment Support

1. What is New:
The project now supports running against multiple Oracle Fusion environments simultaneously. Previously you had to change the URL in .env each time and run scripts one at a time. Now you can open 4 separate command prompt windows and run each against a different environment in parallel.

1.1 what changed:
•	All scripts now accept an --env argument (e.g. --env TEST, --env DEV1).
•	The .env file now has prefixed sections for each environment (TEST_, DEV1_, DEV2_, DEV3_).
•	Each environment gets its own log file so parallel runs don't mix output.
•	crypto_env.py has two new helper functions: get_env() and _get_env_prefix().
•	logger.py now accepts an env_prefix parameter to write to the correct log file.
•	Running without --env still works exactly as before — fully backward compatible

1.2 How to run parallel:
Open 4 separate Command Prompt or PowerShell windows and run one per environment:

# Window 1 — TEST
python main.py --env TEST --folder P2T

# Window 2 — DEV1
python main.py --env DEV1 --folder P2T

# Window 3 — DEV2
python main.py --env DEV2 --folder P2T

# Window 4 — DEV3
python main.py --env DEV3 --folder P2T

Each window runs as a completely separate Python process with its own credentials, URL, and log file. They do not interfere with each other.

1.3 The --env argument how to's:
- Here are some example son how to run in terminal. Of course without --env arg the code will still work. Can use "python" or "py" at beginning. And can replace test with any environment such as DEV1
Script                                  Command
main.py	                                python main.py --env TEST --folder P2T 
security_refresh.py	                    python security_refresh.py --env TEST
main_ui_auto.py                     	python main_ui_auto.py --env TEST
new_alertcomp.py	                    python new_alertcomp.py --env TEST
resetpasswords.py	                    python resetpasswords.py --env TEST
HDLimport.py	                        python HDLimport.py --env TEST
ldap.py	                                python ldap.py --env TEST
data_access_loader.py	                python data_access_loader.py --env TEST

1.4  How get_env() Works
All credential reads now use get_env() instead of os.getenv(). It reads the prefixed var first and falls back to the unprefixed var:

get_env("FUSION_BASEURL", "TEST")
  → looks for TEST_FUSION_BASEURL first
  → falls back to FUSION_BASEURL if not found

This means the same code works for all environments just by passing a different prefix.

1.5 Files changed:
crypto_env.py	                    Added get_env(key, prefix) and _get_env_prefix() helper functions.
logger.py	                        get_logger() now accepts env_prefix to write to env-specific log file.
main.py	                            Added --env arg, uses get_env() for all credential reads, env-specific logger.
security_refresh.py	                Added --env arg, env-specific log file name.
main_ui_auto.py	                    Added --env arg, uses get_env() for BASEURL/USER/PASS, env-specific logger.
new_alertcomp.py	                Added --env arg, uses get_env() for all SOAP and UI credentials, env-specific logger.
resetpasswords.py	                Added --env arg, uses get_env() for all credential reads.
HDLimport.py	                    Added --env arg, uses get_env() for BASEURL and IT credentials.
ldap.py	                            Added --env arg, uses get_env() for BASEURL and IT credentials.
data_access_loader.py	            Added --env arg, uses get_env() for BASEURL and IT credentials.
.env	                            Restructured with TEST_, DEV1_, DEV2_, DEV3_ prefixed sections.



Updated March 2026
1.  What's New Since Last Setup
The following updates have been made since the original guide. You do not need to re-install VSCode, Python, or set up the virtual environment again — those are done. You only need to action the items below.

1.1  Encryption — Credentials No Longer Stored in Plain Text
The project previously used a plain .env file to store all credentials. This has been replaced with an encrypted system. Here is how it works:
•	Your .env file is encrypted into .env.encrypted using a master key.
•	The plain .env is then deleted.
•	At runtime every script decrypts the file into memory — no plain file is ever written to disk.
•	A single Windows environment variable called ENV_MASTER_KEY holds the encryption key.

New files added for this:
•	crypto_env.py — core encryption/decryption engine. Imported by all scripts. Never run directly.
•	encrypt.py — run this once to encrypt your .env and delete the plain file.
•	decrypt.py — run this when you need to edit credentials, then re-encrypt when done.

1.2  Security Refresh Automation (Post-P2T)
A new orchestrator script runs the full post-P2T security refresh sequence automatically in order:

Step	What It Does
1	resetpasswords.py — HCMClient
2	HDLimport.py — Worker.zip
3	ldap.py — LDAPJobClient
4	HDLimport.py — User.zip
5	ldap.py — LDAPJobClient
6	data_access_loader.py
7	HDLimport.py — RoleMapping.zip

Each step has its own error handler. If any step fails the script logs the error and stops immediately — it will not silently continue to the next step.

NOTE: Run security_refresh.py ONLY after a P2T (Production-to-Test) environment refresh. Running it at other times is safe but unnecessary.

1.3  New Individual Scripts
File	                    Purpose
security_refresh.py       Orchestrator that runs all 7 post-P2T steps in sequence. The main file to run after a refresh.
resetpasswords.py         Resets the HCM, FIN, and IT scheduler account passwords using the Oracle SCIM API.
HDLimport.py	          Uploads a .zip file to Oracle HCM Data Loader, triggers the load, and polls until done.
ldap.py	                  Submits the ProcessLdapRequests ESS job and waits for completion.
data_access_loader.py	  Reads Data Access.xlsx and POSTs each record to the Oracle dataSecurities endpoint.
crypto_env.py	          Encryption helper used internally by all scripts. Never run directly.
encrypt.py	              One-time tool to encrypt .env into .env.encrypted and delete the plain file.
decrypt.py	              Tool to decrypt credentials back to plain text for editing. Always re-encrypt when done.

NOTE: security_refresh.py auomatically runs all the security files to correct confiuration. But Each security file resetpasswords.py,HDLimport.py,ldap.py,data_access_loader.py can all be run individually as well.

1.4  All Scripts Now Use Encryption
Every script that reads credentials has been updated to replace:
from dotenv import load_dotenv
load_dotenv()
with:
from crypto_env import load_env_from_encrypted
load_env_from_encrypted()

This change is in: main.py, main_ui_auto.py, new_alertcomp.py, resetpasswords.py, HDLimport.py, ldap.py, data_access_loader.py, security_refresh.py.

2.  Python Packages — What to Install
Your virtual environment is already set up. Run the following command in the terminal to make sure all required packages are installed:

pip install --upgrade pip && pip install requests openpyxl pandas urllib3 python-dateutil playwright cryptography

Then install Playwright browsers (only needs to be done once):
playwright install chromium

Package	Used For
requests	All HTTP calls to Oracle Fusion REST APIs.
openpyxl	Reading/writing Excel files (data.XLSX, Data Access.xlsx, audit logs).
pandas	Used in new_alertcomp.py to process the SOAP report data.
urllib3	HTTP retry logic in fusion_api.py.
python-dateutil	Date parsing utilities.
playwright	Browser automation use in main_ui_auto.py and new_alertcomp.py.
cryptography	NEW — powers the Fernet encryption in crypto_env.py. Required for all scripts.

NOTE: python-dotenv is no longer required since all scripts now use crypto_env.py instead.

3.  Setting Up the ENV_MASTER_KEY
The master key is a single string that encrypts and decrypts your credentials. It must be set as a permanent Windows environment variable on any machine that runs these scripts.

3.1  Generate a New Key (if you don't have one)
Open a terminal and run:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
This prints a key like: WQJEZp_jVlLVAvKUe-3rEv9N6-Z1bDWv0nYYCf_2ARY=
Copy it — you will need it in the next step and to give to any other user who runs these scripts.

3.2  Set the Key Permanently in Windows
Run this in PowerShell (replace YOUR_KEY_HERE with your actual key):
[System.Environment]::SetEnvironmentVariable('ENV_MASTER_KEY', 'YOUR_KEY_HERE', 'User')
Then open a new PowerShell window and verify:
[System.Environment]::GetEnvironmentVariable('ENV_MASTER_KEY', 'User')
It should print your key back. The 'User' scope means it persists for your Windows user account permanently — you do not need to set it again after reboots.

3.3  Check the Key in the Current Session
At any point you can confirm the key is active in the current PowerShell session:
echo $env:ENV_MASTER_KEY

3.4  Giving the Key to Another User (e.g. Stella)
Copy your key string and have them run the same PowerShell command above on their machine. They must use the exact same key — a different key cannot decrypt your .env.encrypted file.
NOTE: Keep the key somewhere safe (e.g., a password manager). If you lose it you cannot recover the encrypted file and must re-create the .env from scratch and re-encrypt.

4.  The .env File — Credentials Reference
Before encrypting you need a .env file in the project root with the following variables:

Variable	Description
FUSION_BASEURL	Oracle Fusion base URL, e.g. https://ejvv-test.fa.us6.oraclecloud.com
FUSION_USER_RESETTER	Email/username of the account that resets passwords (e.g. Stella or sdayanathan). Must have IT Security Manager role.
FUSION_PASS_RESETTER	Password for the resetter account above.
FUSION_hcm_LOGIN	HCM scheduler account username (SUN_JOB_HCM_Scheduler).
FUSION_hcm_PASSWORD	HCM scheduler account password.
FUSION_fin_LOGIN	FIN scheduler account username (SUN_JOB_FIN_Scheduler).
FUSION_fin_PASSWORD	FIN scheduler account password.
FUSION_it_LOGIN	IT scheduler account username (SUN_Job_IT_Scheduler).
FUSION_it_PASSWORD	IT scheduler account password.
FUSION_USERS	Comma-separated list of aliases for main.py multi-user support, e.g. hcm,fin,it
FUSION_USER	Username for main_ui_auto.py browser login.
FUSION_PASS	Password for main_ui_auto.py browser login.
SOAP_USERNAME	Username for new_alertcomp.py SOAP report calls.
SOAP_PASSWORD	Password for new_alertcomp.py SOAP report calls.
REPORT_PATH	Oracle BI Publisher report path used in new_alertcomp.py.
DATA_DROP_DIR	Folder path where Excel files are dropped for main.py, e.g. C:\Shared\ESSJobsDrop
DATA_PREFER_REGEX	Optional regex to prefer certain filenames in the drop folder.
DATA_STABLE_SEC	Seconds to wait to confirm a dropped file is stable (default: 2).

NOTE: Case matters. FUSION_it_LOGIN (lowercase 'it') is correct. FUSION_IT_LOGIN will not work in ldap.py and data_access_loader.py.

The password.txt file is NOT used. The password folder exists but password.txt should be deleted. All passwords are read from .env (or .env.encrypted at runtime).

5.  How to Encrypt and Decrypt Credentials
5.1  Encrypting (first time or after editing)
Make sure your .env file is complete and your ENV_MASTER_KEY is set. Then run:
python encrypt.py
The script will ask:
•	Encrypt .env → .env.encrypted? → type yes
•	Delete plain .env now? → type yes
After this only .env.encrypted exists on disk. Scripts will decrypt it at runtime.

NOTE: If encrypt.py also asks about password.txt and you do not have one, just say no or it will skip automatically.

5.2  Decrypting (to edit credentials)
When you need to update a password or add a variable:
python decrypt.py
The script will confirm you want to proceed, then decrypt .env.encrypted back to a plain .env file. Edit the .env file, then re-encrypt:
python encrypt.py
And delete the plain .env when prompted.

5.3  File Summary
File	Status After Encryption
.env	DELETED after encrypting. Only exists temporarily when decrypting for edits.
.env.encrypted	Always present. This is what scripts read at runtime.
password/password.txt	DELETE THIS. Not used. Leave the folder but remove the file.
password/password.txt.encrypted	Not used. Does not need to exist.

6.  Project File Structure
File / Folder	                        Description
security_refresh.py	                    RUN THIS for post-P2T refresh. Orchestrates all 7 steps.
main.py	                                RUN THIS for ESS job scheduling. Reads Excel and submits jobs to Oracle.
main_ui_auto.py	                        RUN THIS to disable Oracle email notifications via browser automation.
new_alertcomp.py	                    RUN THIS to fix alert composer email expressions.
backfill_from_log.py	                Optional. Rebuilds audit Excel from ess.log text file.
screenshot_cleanup.py / cleanup.py	    Optional. Deletes old screenshots to save disk space.
resetpasswords.py	                    Called by security_refresh.py. Can also be run standalone.
HDLimport.py	                        Called by security_refresh.py. Can also be run standalone for one zip.
ldap.py	                                Called by security_refresh.py. Can also be run standalone.
data_access_loader.py	                Called by security_refresh.py. Can also be run standalone.
fusion_api.py	                        Shared Oracle Fusion API client. Not run directly.
crypto_env.py	                        Encryption engine. Not run directly.
encrypt.py	                            Run to encrypt .env. One-time setup and after any credential edit.
decrypt.py	                            Run to decrypt .env for editing.
logger.py	                            Shared logging setup. Not run directly.
job_audit_xlsx.py	                    Shared Excel audit writer. Not run directly.
job_config.py / get_job_details.py	    Utility helpers. Not run directly.
HDLimport/	Folder                      containing Worker.zip, User.zip, RoleMapping.zip for HDL loads.
DATA_ACCESS/Data Access.xlsx	        Excel file read by data_access_loader.py. The space in the name is intentional — do not rename.
scenarios/	                            Subfolders containing Excel files for scenario/folder mode runs.
.env.encrypted	                        Encrypted credentials file. Always keep this.
logs/	                                Auto-created. Contains ess.log, ui_auto.log, Security_Refresh.log, job_runs.xlsx.
screenshots/	                        Auto-created. Screenshots from main_ui_auto.py runs.
screenshots_alert_composer/            	Auto-created. Screenshots from new_alertcomp.py runs.

7.  How to Run Each Script
7.1  Post-P2T Security Refresh (NEW)
This is the main new script. Run it after every P2T refresh:
python security_refresh.py
It runs all 7 steps in sequence and logs everything to logs/Security_Refresh.log. If any step fails it stops and logs the error — check the log to see which step failed.

Estimated runtime: depends on HDL load sizes and LDAP sync duration in the test environment.

7.2  ESS Job Scheduling (main.py)
Same as before. Set DRY_RUN = True at the top of main.py to test, False for real runs.

•	Legacy (drop folder): python main.py
•	Folder mode: python main.py --folder P2T
•	Folder strict order: python main.py --folder P2T --strict-order
•	Scenario mode: python main.py --scenario P2T
•	Scenario mode: python main.py --scenario QuarterlyPatch

7.3  UI Email Notification Disabler (main_ui_auto.py)
Same as before. Set DRY_RUN = False in the file to save changes.
python main_ui_auto.py

7.4  Alert Composer Fixer (new_alertcomp.py)
python new_alertcomp.py

7.5  Run Scripts Independently
Each security refresh component can also be run on its own if you only need to run one step:
python resetpasswords.py
python HDLimport.py
python ldap.py
python data_access_loader.py

NOTE: HDLimport.py has a hardcoded default of Worker.zip when run standalone (last line of the file). Edit to change which zip it loads. E.g result = hdl.run("Worker.zip") or result = hdl.run("User.zip") so change the "User.zip" to "Worker.zip" or "RoleMapping.zip"

7.6  Screenshot Cleanup
python screenshot_cleanup.py 7 200
The 7 is days to keep, 200 is max files. Use 0 0 to delete everything.

7.7  Audit Log Backfill
python backfill_from_log.py
Reads logs/ess.log and writes a structured Excel audit to logs/job_runs.xlsx (sheet: Runs_v2).

8.  What Each New Script Does
8.1  security_refresh.py
The post-P2T orchestrator. Imports and calls all four client classes in the correct order. Each step is wrapped in try/except — failure stops the run immediately with a clear error message. Logs to logs/Security_Refresh.log with timestamps.

Auth accounts used:
•	Resetter account (FUSION_USER_RESETTER / FUSION_PASS_RESETTER) — for password resets.
•	IT scheduler account (FUSION_it_LOGIN / FUSION_it_PASSWORD) — for HDL loads, LDAP, and data access.

8.2  resetpasswords.py — HCMClient
Resets the password for all three scheduler accounts after a P2T refresh (Oracle resets all passwords back to defaults).
Flow:
•	Step 1: GET /hcmCoreSetupApi/scim/Users to find the GUID for each username.
•	Step 2: PATCH /hcmRestApi/scim/Users/{GUID} to set the new password.
The new password for each account is read from .env (FUSION_hcm_PASSWORD, FUSION_fin_PASSWORD, FUSION_it_PASSWORD). In other words each account resets to its own stored password — the passwords in .env are the passwords Oracle should have after the refresh.

NOTE: The resetter account must have the IT Security Manager role in Oracle.

8.3  HDLimport.py — HDLClient
Handles HDL (HCM Data Loader) file imports. Accepts any of the three zip files.
Flow:
•	Step 1: Base64-encode the .zip from the HDLimport/ folder.
•	Step 2: POST to uploadFile endpoint — get ContentId.
•	Step 3: POST to createFileDataSet endpoint — get RequestId.
•	Step 4: Poll dataLoadDataSets/{RequestId} every 10 seconds until ORA_SUCCESS or ORA_WARNING (both treated as success if 100% complete).

Important details:
•	A 15-second initial delay is added before the first poll — Oracle needs time to register the job.
•	ORA_WARNING with 100% import and load is treated as success (some records may have non-fatal warnings).
•	ORA_SUCCESS with failed objects > 0 raises an exception — check Oracle HCM for details.

8.4  ldap.py — LDAPJobClient
Submits the Send Pending LDAP Requests ESS job and polls until complete.
Job definition: JobDefinition://oracle/apps/ess/hcm/users/ProcessLdapRequests
Arguments: argument1=ALL, argument2=ALL, argument3=A
Polls every 30 seconds. Raises an exception if the final status is not SUCCEEDED or SUCCESS.

8.5  data_access_loader.py — DataAccessClient
Reads the Data Access Excel file and posts each row as a data security record to Oracle.
Excel columns used:
Column	Field
Col A	SecurityContext
Col B	SecurityContextValue
Col E	UserName
Col F	Role display name (translated to internal code automatically)
Col G	Active — Yes or No
Col H	Manual role code override (optional — if blank, the role map is used) If you add this col H where the code is then will be faster

Role translation logic:
•	If Col H has a value, it is used as the role code directly (faster — skips the API lookup).
•	If Col H is blank, the script fetches all existing dataSecurities from Oracle and builds a map of display name to internal code. This takes about 2 minutes.
•	If neither works, the display name from Col F is sent as-is.

NOTE: If you populate Col H for all rows you can skip the 2-minute role map build entirely.

Duplicate handling: if a record already exists Oracle returns 400 with 'already exists' — the script skips it and logs 'Skipped'.

8.6  crypto_env.py
The encryption engine. You never call it directly — it is imported by all other scripts. Key functions:
•	load_env_from_encrypted() — decrypts .env.encrypted into memory and injects all variables into os.environ. Called at the top of every script.
•	encrypt_file(plain, encrypted) — used by encrypt.py.
•	decrypt_file(encrypted, plain) — used by decrypt.py.
•	decrypt_to_memory(encrypted) — used internally; never writes to disk.

9.  Existing Scripts — Quick Reference
These were covered in the previous guide. Only the encryption update is new for each.

Script	                                        What It Does (Summary)
main.py:                          Reads Excel files, submits Oracle ESS jobs, polls for completion, and logs results. Supports legacy drop, folder mode and                 scenario mode. Credentials now come from .env.encrypted.

fusion_api.py:	                    Shared REST API client for Oracle Fusion ESS. Used by main.py and ldap.py. Handles submission, retries, polling, and duplicate detection. No encryption change needed (no direct credential reads).

main_ui_auto.py:                	Browser automation to disable Oracle email notifications. Logs in, disables admin/contractor/default category notifications. Takes screenshots. Credentials now from .env.encrypted.

new_alertcomp.py:               	Fetches an Oracle BI Publisher SOAP report, identifies alert templates with wrong email expressions, and fixes them via UI automation. Credentials now from .env.encrypted.

logger.py:                      	Shared logging factory. Creates logs/ess.log and console output with UTC timestamps. No changes.

job_audit_xlsx.py:              	Appends each job run to logs/job_runs.xlsx for audit trail. No changes.

backfill_from_log.py:	            Parses logs/ess.log and rebuilds a structured audit Excel (Runs_v2 sheet). No changes.

screenshot_cleanup.py:          	Deletes old screenshots by age and count. Can be scheduled via Windows Task Scheduler. No changes.

10.  Required Oracle Roles Per Account
Account	Required Oracle Role(s)
FUSION_USER_RESETTER (e.g. Stella)	IT Security Manager — to reset passwords via SCIM API.
Manage Data Access — to post data security records (if also used for data access).
SUN_Job_IT_Scheduler (FUSION_it)	Upload data for Human Capital Management file based import — for HDL loads.
ESS Adhoc Request Submission — for submitting LDAP ESS job.
Manage Data Access — for posting data security records.
SUN_JOB_HCM_Scheduler (FUSION_hcm)	ESS Adhoc Request Submission — for submitting HCM ESS jobs from main.py.
SUN_JOB_FIN_Scheduler (FUSION_fin)	ESS Adhoc Request Submission — for submitting FIN ESS jobs from main.py.

11.  Log Files Reference
Log File	                            What It Contains
logs/Security_Refresh.log	            Step-by-step log of each security_refresh.py run. Shows which steps passed or failed.
logs/ess.log	                        All ESS job submissions and poll results from main.py runs.
logs/ui_auto.log	                    Browser automation actions and results from main_ui_auto.py.
logs/alert_composer.log	                Alert fixer actions and results from new_alertcomp.py.
logs/job_runs.xlsx	                    Live audit Excel written during main.py runs (sheet: Runs).
logs/job_runs.xlsx (Runs_v2)	        Rebuilt audit from backfill_from_log.py (richer, more fields).

All rotating log files keep 5 backups at 5 MB each. Timestamps are UTC (ISO-8601 format).

12.  Quick Start Checklist — New Machine Setup
Use this checklist when setting up on a new machine or giving access to a new user (e.g. Stella):

1.	Install Python packages:
pip install requests openpyxl pandas urllib3 python-dateutil playwright cryptography
playwright install chromium

2.	Set the ENV_MASTER_KEY permanently:
[System.Environment]::SetEnvironmentVariable('ENV_MASTER_KEY', 'YOUR_KEY_HERE', 'User')
Open a new PowerShell window and verify: echo $env:ENV_MASTER_KEY

3.	Copy the project folder to the machine.
Make sure .env.encrypted is present. The plain .env should NOT be present.

4.	Delete password/password.txt if it exists.
The folder can stay but the file inside should not exist.

5.	Test the decryption:
python -c "from crypto_env import load_env_from_encrypted; load_env_from_encrypted(); import os; print(os.getenv('FUSION_BASEURL'))"
Should print the Oracle base URL if decryption works correctly.

6.	Run a test:
Open main.py, set DRY_RUN = True, and press the play button. Should print job payloads without submitting to Oracle.

13.  Common Errors & Fixes
Error	                                        Cause & Fix
ERROR:                          ENV_MASTER_KEY environment variable is not set	The encryption key is not set in the current session or permanently. Run the PowerShell SetEnvironmentVariable command and open a new terminal.

ERROR:                          Decryption failed. Wrong master key or corrupted file.	The ENV_MASTER_KEY does not match the key used to encrypt the file. Make sure the same key is used on all machines.

ESS-01050	                    Oracle is blocking a duplicate job submission. The script handles this automatically — it detects the duplicate and logs "not submitting a duplicate" and skips. No action needed.

ESS-02002 / 403 Forbidden	     The Oracle user account does not have the ESS Adhoc Request Submission privilege. Add this role to the account in Oracle Security Console.
400: The value of the attribute Role is not valid.	In data_access_loader.py — the role code does not exist in Oracle for that user, which usually means the RoleMapping HDL has not been loaded yet for this user. Check step order.

HDL: ORA_ERROR or FAILED status     	The HDL zip file has invalid data. Check Oracle HCM Data Loader for the detailed error report (Data Exchange > Import and Load Data > View Load Request Details).

LDAP job not SUCCEEDED	            The Send Pending LDAP Requests job failed. Check the Oracle ESS job log for the RequestId returned by ldap.py.

FileNotFoundError: HDL file not found       	The .zip file is missing from the HDLimport/ folder. Confirm Worker.zip, User.zip, and RoleMapping.zip are all present.

openpyxl: File not found: DATA_ACCESS/Data Access.xlsx      	The Data Access Excel file is missing or the folder name is wrong. The space in "Data Access.xlsx" is intentional — do not rename it.


— End of README —
