from pathlib import Path

import pytest
from airflow.models.dagbag import DagBag
from airflow.sdk import DAG, TriggerRule
from airflow.sdk.definitions.timetables.simple import NullTimetable

from orchestration.catalog import PIPELINES, Pipeline
from orchestration.dag_factory import build_dag

DAGS_FOLDER = Path(__file__).resolve().parents[1] / "orchestration" / "dags"


@pytest.fixture(scope="module")
def dag_bag() -> DagBag:
    return DagBag(dag_folder=str(DAGS_FOLDER), include_examples=False)


def test_dags_folder_imports_cleanly(dag_bag: DagBag) -> None:
    assert dag_bag.import_errors == {}
    assert set(dag_bag.dag_ids) == {pipeline.pipeline_id for pipeline in PIPELINES}


@pytest.mark.parametrize("pipeline", PIPELINES, ids=lambda pipeline: pipeline.pipeline_id)
def test_dag_mirrors_its_pipeline(pipeline: Pipeline) -> None:
    dag: DAG = build_dag(pipeline)

    assert {task.task_id for task in dag.tasks} == {step.step_id for step in pipeline.steps}
    assert dag.max_active_runs == 1
    assert dag.catchup is False
    for step in pipeline.steps:
        task = dag.get_task(step.step_id)
        assert task.retries == step.retries
        assert task.upstream_task_ids == {dependency.step_id for dependency in step.depends_on}
        expected_rule = (
            TriggerRule.ALL_DONE
            if any(dependency.kind == "soft" for dependency in step.depends_on)
            else TriggerRule.ALL_SUCCESS
        )
        assert task.trigger_rule == expected_rule


def test_soft_dependencies_let_the_return_code_analysis_run_after_failures() -> None:
    dag = build_dag(next(p for p in PIPELINES if p.pipeline_id == "clbs_daily_reporting"))

    assert dag.get_task("return_code_analysis").trigger_rule == TriggerRule.ALL_DONE


def test_on_demand_pipeline_has_no_schedule() -> None:
    dag = build_dag(next(p for p in PIPELINES if p.pipeline_id == "clbs_test_data_refresh"))

    assert isinstance(dag.timetable, NullTimetable)
