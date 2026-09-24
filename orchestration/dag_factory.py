"""Builds one Airflow DAG per catalog pipeline.

The factory keeps the JCL semantics in one place: hard dependencies become `all_success` edges,
soft dependencies (`PSR-DEP-SOFT`) become `all_done` edges, and `PSR-RESTART`/`CK-MAX-RESTARTS`
become task retries.
"""

from datetime import UTC, datetime, timedelta

from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import DAG, TriggerRule
from airflow.sdk.bases.operator import BaseOperator
from airflow.sdk.definitions.dag import ScheduleArg

from orchestration.catalog import JobStep, Pipeline
from orchestration.runtime import run_catalog_step

DAG_START_DATE = datetime(2026, 1, 1, tzinfo=UTC)
DEFAULT_RETRY_DELAY = timedelta(minutes=5)
OWNER = "clbs-batch"


def _trigger_rule(step: JobStep) -> str:
    if any(dependency.kind == "soft" for dependency in step.depends_on):
        return TriggerRule.ALL_DONE
    return TriggerRule.ALL_SUCCESS


def _build_task(pipeline: Pipeline, step: JobStep) -> BaseOperator:
    return PythonOperator(
        task_id=step.step_id,
        python_callable=run_catalog_step,
        op_kwargs={
            "pipeline_id": pipeline.pipeline_id,
            "step_id": step.step_id,
            "process_date": "{{ ds }}",
            "attempt": "{{ task_instance.try_number }}",
        },
        retries=step.retries,
        retry_delay=DEFAULT_RETRY_DELAY,
        trigger_rule=_trigger_rule(step),
        doc_md=(
            f"`{step.program}` — {step.description}\n\n"
            f"Ported from `{step.source_jcl}`; tolerates return codes up to "
            f"{step.max_return_code}.\n\n"
            + "\n".join(
                f"- `{dataset.dd_name}` ({dataset.mode}) → `{dataset.target}`"
                for dataset in step.datasets
            )
        ),
    )


def build_dag(pipeline: Pipeline) -> DAG:
    schedule: ScheduleArg = pipeline.schedule
    with DAG(
        dag_id=pipeline.pipeline_id,
        description=pipeline.description,
        schedule=schedule,
        start_date=DAG_START_DATE,
        catchup=pipeline.catchup,
        max_active_runs=1,
        tags=list(pipeline.tags),
        default_args={"owner": OWNER, "retry_delay": DEFAULT_RETRY_DELAY},
        doc_md=_dag_docs(pipeline),
    ) as dag:
        tasks = {step.step_id: _build_task(pipeline, step) for step in pipeline.steps}
        for step in pipeline.steps:
            for dependency in step.depends_on:
                tasks[dependency.step_id] >> tasks[step.step_id]
    return dag


def _dag_docs(pipeline: Pipeline) -> str:
    sources = "\n".join(
        f"- `{step.source_jcl}` → `{step.program}` (`{step.step_id}`)" for step in pipeline.steps
    )
    return (
        f"{pipeline.description}\n\n"
        f"Frequency: {pipeline.frequency}. Replaces the following JCL members:\n\n{sources}\n"
    )
