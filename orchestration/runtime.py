"""Execution shim between the scheduler and the ported batch jobs.

A scheduler task knows only which catalog step to run; this module resolves the step's entrypoint,
builds the job context that replaces the JCL DD statements and PARM field, and enforces the
`PSR-MAX-RC` return-code tolerance that `COND=` codes used to express.
"""

import importlib
import logging
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date

from app.core.context import log_context
from app.core.settings import get_settings
from orchestration.catalog import JobStep, get_step

logger = logging.getLogger(__name__)


class BatchJobNotPortedError(RuntimeError):
    """The COBOL program behind a catalog step has no Python implementation yet."""


class BatchJobFailedError(RuntimeError):
    """A batch job returned a code above the step's tolerated maximum."""


@dataclass(frozen=True)
class JobContext:
    """What a batch job needs to run: replaces DD statements, PARM and checkpoint mode."""

    program: str
    process_date: date
    datasets: Mapping[str, str]
    commit_interval: int
    restart: bool


BatchJob = Callable[[JobContext], int]


def resolve_job(step: JobStep) -> BatchJob:
    module_name, _, attribute = step.entrypoint.partition(":")
    try:
        module = importlib.import_module(module_name)
        job = getattr(module, attribute)
    except (ModuleNotFoundError, AttributeError) as exc:
        raise BatchJobNotPortedError(
            f"{step.program} ({step.source_jcl}) is not ported yet: "
            f"expected callable {step.entrypoint}"
        ) from exc
    if not callable(job):
        raise BatchJobNotPortedError(f"{step.entrypoint} is not callable")
    return job  # type: ignore[no-any-return]


def run_step(step: JobStep, *, process_date: date, attempt: int = 1) -> int:
    """Run one catalog step and return its return code."""
    context = JobContext(
        program=step.program,
        process_date=process_date,
        datasets=step.dataset_bindings(),
        commit_interval=get_settings().batch_commit_interval,
        restart=attempt > 1,
    )
    with log_context(correlation_id=str(uuid.uuid4()), program_id=step.program):
        logger.info(
            "batch step starting",
            extra={
                "process_date": process_date.isoformat(),
                "attempt": attempt,
                "restart_mode": "R" if context.restart else "N",
            },
        )
        return_code = resolve_job(step)(context)
        if return_code > step.max_return_code:
            raise BatchJobFailedError(
                f"{step.program} returned {return_code}, above the tolerated {step.max_return_code}"
            )
        logger.info("batch step complete", extra={"return_code": return_code})
        return return_code


def run_catalog_step(*, pipeline_id: str, step_id: str, process_date: str, attempt: str) -> int:
    """Scheduler entrypoint; arguments arrive as rendered templates, hence the strings."""
    return run_step(
        get_step(pipeline_id, step_id),
        process_date=date.fromisoformat(process_date),
        attempt=int(attempt),
    )
