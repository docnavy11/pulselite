"""Background task infrastructure — replaces Celery.

Two-tier system:
- enqueue(): fire-and-forget asyncio tasks for quick, non-critical work
- run_job_worker(): Postgres-backed queue for crash-resilient long-running jobs
"""

import asyncio
import logging
import uuid

from sqlalchemy import text

from app.database import async_session_factory

logger = logging.getLogger(__name__)

# --- Fire-and-forget tier ---

_tasks: set[asyncio.Task] = set()


def enqueue(coro, name: str | None = None):
    """Fire-and-forget an async coroutine as a background task."""
    task = asyncio.create_task(coro, name=name)
    _tasks.add(task)
    task.add_done_callback(_on_done)


def _on_done(task: asyncio.Task):
    _tasks.discard(task)
    if not task.cancelled() and task.exception():
        logger.exception("Background task %s failed", task.get_name(), exc_info=task.exception())


# --- Postgres job queue tier ---

JOB_HANDLERS: dict[str, callable] = {}
_worker_task: asyncio.Task | None = None


def register_job(job_type: str):
    """Decorator to register an async function as a job handler."""

    def decorator(func):
        JOB_HANDLERS[job_type] = func
        return func

    return decorator


async def submit_job(
    job_type: str,
    payload: dict | None = None,
    max_retries: int = 3,
) -> uuid.UUID:
    """Insert a job into the background_jobs table. Returns the job ID."""
    job_id = uuid.uuid4()
    async with async_session_factory() as db:
        await db.execute(
            text("""
            INSERT INTO background_jobs (id, job_type, payload, max_retries)
            VALUES (:id, :job_type, CAST(:payload AS jsonb), :max_retries)
        """),
            {
                "id": job_id,
                "job_type": job_type,
                "payload": __import__("json").dumps(payload or {}),
                "max_retries": max_retries,
            },
        )
        await db.commit()
    return job_id


async def _process_one_job() -> bool:
    """Try to claim and process one pending job. Returns True if a job was processed."""
    async with async_session_factory() as db:
        result = await db.execute(
            text("""
            UPDATE background_jobs SET status='running', started_at=now()
            WHERE id = (
                SELECT id FROM background_jobs
                WHERE status='pending'
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id, job_type, payload, attempts, max_retries
        """)
        )
        row = result.fetchone()
        if not row:
            return False

        job_id, job_type, payload, attempts, max_retries = row
        await db.commit()

    handler = JOB_HANDLERS.get(job_type)
    if handler is None:
        logger.error("No handler registered for job type: %s", job_type)
        await _mark_job(job_id, "failed", error=f"Unknown job type: {job_type}")
        return True

    try:
        await handler(payload)
        await _mark_job(job_id, "completed")
    except Exception as e:
        logger.exception("Job %s (%s) failed", job_id, job_type)
        if attempts + 1 < max_retries:
            await _mark_job(job_id, "pending", attempts=attempts + 1)
        else:
            await _mark_job(job_id, "failed", error=str(e)[:500])

    return True


async def _mark_job(
    job_id: uuid.UUID,
    status: str,
    error: str | None = None,
    attempts: int | None = None,
):
    async with async_session_factory() as db:
        if status in ("completed", "failed"):
            await db.execute(
                text("""
                UPDATE background_jobs
                SET status=:status, completed_at=now(), error=:error
                WHERE id=:id
            """),
                {"id": job_id, "status": status, "error": error},
            )
        elif attempts is not None:
            await db.execute(
                text("""
                UPDATE background_jobs
                SET status=:status, attempts=:attempts, error=:error
                WHERE id=:id
            """),
                {"id": job_id, "status": status, "attempts": attempts, "error": error},
            )
        await db.commit()


async def run_job_worker():
    """Poll Postgres for pending jobs. Runs as a long-lived asyncio task."""
    logger.info("Background job worker started")
    while True:
        try:
            processed = await _process_one_job()
            if not processed:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Background job worker shutting down")
            break
        except Exception:
            logger.exception("Job worker loop error")
            await asyncio.sleep(5)


def start_worker():
    """Start the job worker as a background task. Call from app startup."""
    global _worker_task
    _worker_task = asyncio.create_task(run_job_worker())


def stop_worker():
    """Cancel the job worker. Call from app shutdown."""
    global _worker_task
    if _worker_task:
        _worker_task.cancel()
        _worker_task = None
