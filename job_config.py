#job_config.py
from  dataclasses import dataclass
from typing import Optional
import datetime
@dataclass
class JobConfig:
    job_name : str # Name of the Oracle Ess job
    parameters: dict # dictionary of parameters for job
    schedule_type: str # "on_demand" or "recurring"
    schedule_time: Optional[datetime.datetime] = None #if recurrng or delayed
    frequency: Optional[str] = None # daily, weekly, monthly for recurring


#if main for testing
if __name__ == "__main__":
    import datetime

    # Example 1: On-demand job
    job1 = JobConfig(
        job_name="Import Payables Invoices",
        parameters={"ledger": "Vision Ops", "period": "AUG-25"},
        schedule_type="on_demand"
    )
    print("Job 1:", job1)

    # Example 2: Recurring job
    job2 = JobConfig(
        job_name="General Ledger Post",
        parameters={"ledger": "Vision Ops"},
        schedule_type="recurring",
        schedule_time=datetime.datetime(2025, 8, 20, 10, 0),
        frequency="daily"
    )
    print("Job 2:", job2)
