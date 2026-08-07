
THIS IS ORIGINAL README:




Quick summary: 
excel->jobconfig->main->oracle 
utc time can be changed to proper time zone
dry run true for test dry run false for real run
reads `data.XLSX` and submits Oracle Fusion ESS jobs. supports on-demand runs and recurring (via `icalString` or a full `schedule_json`), accepts up to `argument1..argument30`, de-duplicates pending runs, and logs final status for one-time jobs or the parent request ID for scheduled jobs. Works across modules because status is read from the generic Scheduler endpoint
rows are prepared in data.xlsx, main.py reads them schedule rows get recurrence object from either icalstring or schedulejson and then calls oracle with essclient.submit. once schedule is created fusion runs automatically, no human in loop. Duplicates are prevented.
Excel rows scanned and then ESSclient converts them into the request parameters array oracle expects. So it supports different parameters because the parameter sets per job are arbitrary. Diff jobs can use diff counts/types et
On-demand(ad-hoc) if no icalstring and no schedule json then it returns runnow for recurring if row has ical or json schedule then builds recurrence
After on demand jobs are submitted main.py calls clientpoll in fusion api and the poller calls repeadetly /ess/rest/scheduler/v1/requests/{id} logs current state such as wait, success, etc.
When state reaches terminal value the final status is logged for the request id
when schedule jobs are submitted fusion returns the parent request id and main.py logs it.
It submits via jobDefinitonId and application as fusion expects and arguments are passed generically
the status the scheduler endpoint is used and that works across all models. A allback ERP finder is in the API client
So any ess job in hcm, erp,scm etc can be used by adding a row in excel


ESS-01050 error is oracle blocking job duplicates being created, some jobs allow some don't right now the code will skip duplicates to avoid this error


Create scheduled jobs (start time / end time / recurrence)?
Yes — if the Excel row includes either schedule_json or icalString.

schedule_json → full control (you pass the whole schedule object through).

icalString (+ optional startDate / endDate) → the recurrence wrapper built for you.

If neither is present, the code defaults to runNow (on-demand). It won’t invent a schedule by itself.

Create jobs with only jobDefinitionId + application (no parameters, no dates)?
Yes. If you leave arguments blank and omit schedule fields, we submit the job on-demand with no parameters.

“Every 15 minutes” schedule from Excel?
Yes — put a recurrence into the Excel row. Two common ways:

Minimal iCal:
icalString = FREQ=MINUTELY;INTERVAL=15

Or by-minute pattern:
icalString = FREQ=HOURLY;INTERVAL=1;BYMINUTE=0,15,30,45
Optionally include startDate like 2025-08-21T20:00:00Z and endDate if needed


See below after update changes for env
Explaining.env: 
FUSION_BASEURL=  fusionurl
FUSION_USERNAME=  fusionusername
FUSION_PASSWORD=   fusionpassword
DATA_DROP_DIR=C:\Shared\ESSJobsDrop   tells script where client will drop excel
DATA_PREFER_REGEX=  preferd file name(s) lets you prefer files if name matches, if not uses latest file
DATA_STABLE_SEC=2  ensures file stops changing sizes before we use it/copy


How the auto excel picker woks:
Look in DROP_DIR for files ending in .xlsx or .xlsm (skip Excel temp files that start with ~$).

If DATA_PREFER_REGEX is set, try to prefer files matching it; otherwise use all Excels.

Sort candidates by last modified time (newest first) and pick the top one.

Ensure the picked file is “stable” (size unchanged for DATA_STABLE_SEC seconds).

Copy that file to a canonical path data.XLSX in your project so the rest of the code always reads the same file name.

Parse data.XLSX and submit jobs.

HOW the auto-fill jobdefid and application works:

fusion_api.ESSClient.resolve_job_by_name() first calls the Fusion job catalog endpoint to find job definitions by Display Name.

It tries an exact match, then a contains match.

If it finds one unambiguous job, it returns { jobDefinitionId, application }.

In main.py we only backfill these fields when they’re blank in Excel; if your sheet already has them, we don’t override.

Before update^^^^^^^^^^^^

///***IMPORTANT***/// Some new upates:

ENV changed to allow as many different usernames as you'd like. Choose Alias and add the username and password to env. The code reads the username in the excel files.

Added skips for duplicates and timeout time settings

Audit logger creates excel during run and backfill_from_log creates excel from the logger and ess.logs

Now code runs multiple Excel files via running with args so from the args it parses folders and creates list of excel to run

so basically through folder path scenarios you can add subfolders and in these folders multiple Excel files can be added

In scenaros mode we have hardcoded file names as another run option, it searches every method drop dir then project root then folders and runs only those fixed file names found in scenario_files. Have choice between P2T and QuarterlyPatch scenarios

The folders can be run in alphabetical order, otherwise newest first

How to run:
Original way- "python main.py" in terminal or press play button

Folder method- "python main.py --folder P2T" in terminal the format is "folder (name of the folder e.g P2T)"

Scenario mode- "python main.py --scenario P2T" in terminal or "python main.py --scenario QuarterlyPatch" in terminal

Strict Order- "python main.py --folder (name) --strict-order"

So when you put argument the code parses it and selects the corresponding path/folder, if no argument found then legacy run(the original drop folder way)

In the run section we parse through the arguments collected and run otherwise no arguments run legacy

Excel files staged as data.xlsx, no xls allowed no excel 97-2003.

Any new subfolder in scenarios can be read if created



how it works as of right now: 

press play and it auto does all steps for email disabling.

Logs in by itself to the saved user and password.

It separates the different accounts used for different sessions so code doesntget confused if using different accouts or different urls

Takes screenshot after each finishing step example before typing both password and username into sign in and after sign in

Optional add but takes more space the code could be recorded instea of screenshotted.

Has scroll feature to take clear screenshots of steps

Can run with it showing live feed or not showing live feed of browser

The code goes to the notification area and disables it.

Dry run toggle is enabled

have the loop for if notifications have 0 or multiple unread 

adjusted to different instances (have to test more)

right now passwords in code, in future pull from elsewhere

added clean up code for screenshots to save space that works by say keep last 7 days saved and keep 200 screenshots

added a clean up file for windows task scheduler to scheduler clean ups for screenshots can adjust the 7 days and 200 if you want

added logger for the auto ui file so we can have record of succcessful or failed runs and cleanups

How to run:
for auto disable:
press play in file or 
type in terminal "python main_ui_auto.py"

for cleaner:
press play button or
type in terminal "python screenshot_cleanup.py 7 200" change 7 and 200 to fit the needs example want to delete all then 0 0





