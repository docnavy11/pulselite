from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class QueueStats(BaseModel):
    pending: int
    running: int
    throughput_per_hour: float


class TopError(BaseModel):
    task_name: str
    error: str
    count: int


class ReliabilityStats(BaseModel):
    total: int
    succeeded: int
    failed: int
    failure_rate_pct: float
    total_retries: int
    top_errors: list[TopError]


class TaskPerformance(BaseModel):
    task_name: str
    count: int
    success_rate_pct: float
    avg_duration_ms: Optional[float] = None
    p95_duration_ms: Optional[float] = None
    last_failure_at: Optional[datetime] = None


class PerformanceStats(BaseModel):
    by_task: list[TaskPerformance]


class TimeseriesBucket(BaseModel):
    bucket: datetime
    completed: int
    failed: int


class WorkerHealthResponse(BaseModel):
    queue: QueueStats
    reliability: ReliabilityStats
    performance: PerformanceStats
    timeseries: list[TimeseriesBucket]
