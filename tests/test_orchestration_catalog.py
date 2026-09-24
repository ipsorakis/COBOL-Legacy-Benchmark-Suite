from pathlib import Path

import pytest

from orchestration.catalog import (
    PIPELINES,
    RETIRED_JCL,
    Dataset,
    Dependency,
    JobStep,
    Pipeline,
    get_pipeline,
    get_step,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _step(step_id: str = "step", **overrides: object) -> JobStep:
    defaults: dict[str, object] = {
        "step_id": step_id,
        "program": "RPTPOS00",
        "description": "example",
        "source_jcl": "src/jcl/batch/RPTPOS.jcl",
        "entrypoint": "app.batch.reports.position_report:run",
        "datasets": (Dataset("RPTFILE", "artifact:reports/example", "write"),),
    }
    return JobStep(**(defaults | overrides))  # type: ignore[arg-type]


def test_every_jcl_member_is_either_orchestrated_or_retired() -> None:
    members = {
        str(path.relative_to(REPO_ROOT)) for path in (REPO_ROOT / "src" / "jcl").rglob("*.jcl")
    }
    orchestrated = {step.source_jcl for pipeline in PIPELINES for step in pipeline.steps}
    assert members == orchestrated | set(RETIRED_JCL)


def test_source_jcl_paths_exist() -> None:
    for pipeline in PIPELINES:
        for step in pipeline.steps:
            assert (REPO_ROOT / step.source_jcl).is_file()


def test_pipeline_and_program_identifiers_are_unique() -> None:
    pipeline_ids = [pipeline.pipeline_id for pipeline in PIPELINES]
    programs = [step.program for pipeline in PIPELINES for step in pipeline.steps]
    assert len(pipeline_ids) == len(set(pipeline_ids))
    assert len(programs) == len(set(programs))


def test_lookup_helpers() -> None:
    assert get_pipeline("clbs_daily_reporting").frequency == "daily"
    assert get_step("clbs_daily_reporting", "position_report").program == "RPTPOS00"
    with pytest.raises(KeyError):
        get_pipeline("nope")
    with pytest.raises(KeyError):
        get_step("clbs_daily_reporting", "nope")


def test_retries_follow_restart_flag() -> None:
    assert _step(restartable=True, max_restarts=3).retries == 3
    assert _step(restartable=False, max_restarts=3).retries == 0


def test_dataset_target_needs_a_known_prefix() -> None:
    with pytest.raises(ValueError, match="must start with"):
        Dataset("PORTFILE", "PORTFOLIO.MASTER.FILE")


def test_entrypoint_must_name_a_callable() -> None:
    with pytest.raises(ValueError, match="module:callable"):
        _step(entrypoint="app.batch.reports.position_report")


def test_dependencies_must_reference_earlier_steps() -> None:
    with pytest.raises(ValueError, match="not an earlier step"):
        Pipeline(
            pipeline_id="p",
            description="d",
            schedule="@daily",
            frequency="daily",
            steps=(_step("first", depends_on=(Dependency("second"),)), _step("second")),
        )


def test_duplicate_step_ids_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate step ids"):
        Pipeline(
            pipeline_id="p",
            description="d",
            schedule="@daily",
            frequency="daily",
            steps=(_step("first"), _step("first")),
        )


def test_on_demand_pipelines_must_not_be_scheduled() -> None:
    with pytest.raises(ValueError, match="on_demand"):
        Pipeline(
            pipeline_id="p",
            description="d",
            schedule="@daily",
            frequency="on_demand",
            steps=(_step(),),
        )
    with pytest.raises(ValueError, match="on_demand"):
        Pipeline(
            pipeline_id="p",
            description="d",
            schedule=None,
            frequency="daily",
            steps=(_step(),),
        )
