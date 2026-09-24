import sys
import types
from datetime import date

import pytest

from orchestration.catalog import Dataset, JobStep
from orchestration.runtime import (
    BatchJobFailedError,
    BatchJobNotPortedError,
    JobContext,
    resolve_job,
    run_catalog_step,
    run_step,
)

PROCESS_DATE = date(2026, 3, 20)


def _step(entrypoint: str, **overrides: object) -> JobStep:
    defaults: dict[str, object] = {
        "step_id": "position_report",
        "program": "RPTPOS00",
        "description": "Daily position report",
        "source_jcl": "src/jcl/batch/RPTPOS.jcl",
        "entrypoint": entrypoint,
        "datasets": (
            Dataset("POSMSTRE", "table:investment_positions"),
            Dataset("RPTFILE", "artifact:reports/daily-position-report", "write"),
        ),
    }
    return JobStep(**(defaults | overrides))  # type: ignore[arg-type]


@pytest.fixture
def fake_job(request: pytest.FixtureRequest) -> list[JobContext]:
    """Register a stub batch job module and return the contexts it was called with."""
    calls: list[JobContext] = []
    return_code = getattr(request, "param", 0)

    def run(context: JobContext) -> int:
        calls.append(context)
        return return_code

    module = types.ModuleType("stub_batch_job")
    module.run = run  # type: ignore[attr-defined]
    sys.modules["stub_batch_job"] = module
    request.addfinalizer(lambda: sys.modules.pop("stub_batch_job", None))
    return calls


def test_unported_program_is_reported_with_its_jcl_origin() -> None:
    step = _step("app.batch.reports.position_report:run")
    with pytest.raises(BatchJobNotPortedError, match=r"RPTPOS00 \(src/jcl/batch/RPTPOS.jcl\)"):
        resolve_job(step)


def test_missing_callable_in_existing_module_is_also_reported(fake_job: list[JobContext]) -> None:
    with pytest.raises(BatchJobNotPortedError):
        resolve_job(_step("stub_batch_job:missing"))


def test_run_step_builds_the_job_context_from_dd_bindings(fake_job: list[JobContext]) -> None:
    return_code = run_step(_step("stub_batch_job:run"), process_date=PROCESS_DATE)

    assert return_code == 0
    (context,) = fake_job
    assert context.program == "RPTPOS00"
    assert context.process_date == PROCESS_DATE
    assert context.datasets == {
        "POSMSTRE": "table:investment_positions",
        "RPTFILE": "artifact:reports/daily-position-report",
    }
    assert context.restart is False


def test_retries_run_the_job_in_restart_mode(fake_job: list[JobContext]) -> None:
    run_step(_step("stub_batch_job:run"), process_date=PROCESS_DATE, attempt=2)

    assert fake_job[0].restart is True


@pytest.mark.parametrize("fake_job", [4], indirect=True)
def test_return_code_above_the_maximum_fails_the_step(fake_job: list[JobContext]) -> None:
    with pytest.raises(BatchJobFailedError, match="returned 4, above the tolerated 0"):
        run_step(_step("stub_batch_job:run"), process_date=PROCESS_DATE)


@pytest.mark.parametrize("fake_job", [4], indirect=True)
def test_tolerated_return_code_passes(fake_job: list[JobContext]) -> None:
    assert run_step(_step("stub_batch_job:run", max_return_code=4), process_date=PROCESS_DATE) == 4


def test_run_catalog_step_accepts_rendered_template_arguments() -> None:
    with pytest.raises(BatchJobNotPortedError):
        run_catalog_step(
            pipeline_id="clbs_daily_reporting",
            step_id="position_report",
            process_date="2026-03-20",
            attempt="1",
        )
