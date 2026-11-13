"""Run the worker:  arq worker.settings.WorkerSettings"""
import os

from arq import cron
from arq.connections import RedisSettings
from dotenv import load_dotenv

load_dotenv(".env")
from worker import tasks  # noqa: E402
from apps.api.runtime import RUNTIME  # noqa: E402


async def startup(ctx):
    await RUNTIME.start()


class WorkerSettings:
    functions = [tasks.run_bid, tasks.scout, tasks.resume_run, tasks.run_conversation, tasks.replay_run]
    cron_jobs = [cron(tasks.scout_saved_searches, minute={0, 15, 30, 45}), cron(tasks.retry_waiting, second={0, 30})]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6380/0"))
    max_tries = 3
    job_timeout = 600
    keep_result = 3600
