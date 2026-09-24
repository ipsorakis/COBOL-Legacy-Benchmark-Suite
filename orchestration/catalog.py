"""Declarative catalog of the batch jobs previously orchestrated by `src/jcl/`.

Each JCL member becomes a `JobStep`; the `EXEC PGM=` program keeps its COBOL name for
traceability, the DD statements become `Dataset` bindings, and `PRCSEQ`/`CKPRST` control fields
(`PSR-FREQ`, `PSR-DEP-TYPE`, `PSR-MAX-RC`, `PSR-RESTART`, `CK-MAX-RESTARTS`) become pipeline
schedules, dependency kinds, return-code tolerance and retry counts.
"""

from dataclasses import dataclass
from typing import Literal

DatasetMode = Literal["read", "write", "append"]
DependencyKind = Literal["hard", "soft"]
Frequency = Literal["intraday", "daily", "weekly", "monthly", "on_demand"]

DATASET_TARGET_PREFIXES = ("table:", "artifact:", "config:", "metric:")


@dataclass(frozen=True)
class Dataset:
    """A DD statement re-expressed as a logical resource of the modernized tier."""

    dd_name: str
    target: str
    mode: DatasetMode = "read"

    def __post_init__(self) -> None:
        if not self.target.startswith(DATASET_TARGET_PREFIXES):
            raise ValueError(
                f"{self.dd_name}: target {self.target!r} must start with one of "
                f"{DATASET_TARGET_PREFIXES}"
            )


@dataclass(frozen=True)
class Dependency:
    """An intra-pipeline dependency; `soft` mirrors `PSR-DEP-SOFT` (run regardless of outcome)."""

    step_id: str
    kind: DependencyKind = "hard"


@dataclass(frozen=True)
class JobStep:
    """One JCL job step: the program to run, its data bindings and its restart behaviour."""

    step_id: str
    program: str
    description: str
    source_jcl: str
    entrypoint: str
    datasets: tuple[Dataset, ...]
    depends_on: tuple[Dependency, ...] = ()
    max_return_code: int = 0
    restartable: bool = True
    max_restarts: int = 3

    def __post_init__(self) -> None:
        if ":" not in self.entrypoint:
            raise ValueError(f"{self.step_id}: entrypoint must be 'module:callable'")
        if self.max_restarts < 0:
            raise ValueError(f"{self.step_id}: max_restarts must not be negative")

    @property
    def retries(self) -> int:
        """`CK-MAX-RESTARTS` for restartable programs, none for `PSR-NO-RESTART` ones."""
        return self.max_restarts if self.restartable else 0

    def dataset_bindings(self) -> dict[str, str]:
        return {dataset.dd_name: dataset.target for dataset in self.datasets}


@dataclass(frozen=True)
class Pipeline:
    """A scheduled group of job steps, replacing one or more JCL members."""

    pipeline_id: str
    description: str
    schedule: str | None
    frequency: Frequency
    steps: tuple[JobStep, ...]
    tags: tuple[str, ...] = ()
    catchup: bool = False

    def __post_init__(self) -> None:
        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError(f"{self.pipeline_id}: duplicate step ids in {step_ids}")
        seen: set[str] = set()
        for step in self.steps:
            for dependency in step.depends_on:
                if dependency.step_id not in seen:
                    raise ValueError(
                        f"{self.pipeline_id}.{step.step_id}: depends on "
                        f"{dependency.step_id!r}, which is not an earlier step"
                    )
            seen.add(step.step_id)
        if (self.schedule is None) != (self.frequency == "on_demand"):
            raise ValueError(
                f"{self.pipeline_id}: on_demand pipelines must have no schedule, "
                f"scheduled pipelines must declare one"
            )

    def step(self, step_id: str) -> JobStep:
        for step in self.steps:
            if step.step_id == step_id:
                return step
        raise KeyError(f"{self.pipeline_id} has no step {step_id!r}")


DAILY_REPORTING = Pipeline(
    pipeline_id="clbs_daily_reporting",
    description="End-of-day reporting cycle (src/jcl/batch/, src/jcl/RTNANA.jcl)",
    schedule="0 2 * * *",
    frequency="daily",
    tags=("clbs", "reporting"),
    steps=(
        JobStep(
            step_id="position_report",
            program="RPTPOS00",
            description="Daily position report",
            source_jcl="src/jcl/batch/RPTPOS.jcl",
            entrypoint="app.batch.reports.position_report:run",
            datasets=(
                Dataset("POSMSTRE", "table:investment_positions"),
                Dataset("TRANHIST", "table:transaction_history"),
                Dataset("RPTFILE", "artifact:reports/daily-position-report", "write"),
            ),
        ),
        JobStep(
            step_id="audit_report",
            program="RPTAUD00",
            description="System audit report",
            source_jcl="src/jcl/batch/RPTAUD.jcl",
            entrypoint="app.batch.reports.audit_report:run",
            datasets=(
                Dataset("AUDITLOG", "table:audit_log"),
                Dataset("ERRLOG", "table:errlog"),
                Dataset("RPTFILE", "artifact:reports/audit-report", "write"),
            ),
        ),
        JobStep(
            step_id="system_stats_report",
            program="RPTSTA00",
            description="System statistics report",
            source_jcl="src/jcl/batch/RPTSTA.jcl",
            entrypoint="app.batch.reports.system_stats_report:run",
            datasets=(
                Dataset("DB2STATS", "metric:database-statistics"),
                Dataset("BCHSTATS", "metric:batch-statistics"),
                Dataset("RPTFILE", "artifact:reports/system-stats-report", "write"),
            ),
        ),
        JobStep(
            step_id="return_code_analysis",
            program="RTNANA00",
            description="Return code analysis over the reporting cycle",
            source_jcl="src/jcl/RTNANA.jcl",
            entrypoint="app.batch.utility.return_code_analysis:run",
            datasets=(
                Dataset("RTNCODES", "table:rtncodes"),
                Dataset("RPTFILE", "artifact:reports/return-code-analysis", "write"),
            ),
            depends_on=(
                Dependency("position_report", "soft"),
                Dependency("audit_report", "soft"),
                Dependency("system_stats_report", "soft"),
            ),
            max_return_code=4,
        ),
    ),
)

PORTFOLIO_MAINTENANCE = Pipeline(
    pipeline_id="clbs_portfolio_maintenance",
    description="Portfolio master maintenance cycle (src/jcl/portfolio/)",
    schedule="0 22 * * 1-5",
    frequency="daily",
    tags=("clbs", "portfolio"),
    steps=(
        JobStep(
            step_id="add_portfolios",
            program="PORTADD",
            description="Apply inbound portfolio additions",
            source_jcl="src/jcl/portfolio/PORTADD.jcl",
            entrypoint="app.batch.portfolio.add_portfolios:run",
            datasets=(
                Dataset("PORTFILE", "table:portfolio_master", "write"),
                Dataset("INPTFILE", "artifact:inbound/portfolio-additions"),
            ),
        ),
        JobStep(
            step_id="update_portfolios",
            program="PORTUPDT",
            description="Apply inbound portfolio updates",
            source_jcl="src/jcl/portfolio/PORTUPDT.jcl",
            entrypoint="app.batch.portfolio.update_portfolios:run",
            datasets=(
                Dataset("PORTFILE", "table:portfolio_master", "write"),
                Dataset("UPDTFILE", "artifact:inbound/portfolio-updates"),
            ),
            depends_on=(Dependency("add_portfolios"),),
        ),
        JobStep(
            step_id="delete_portfolios",
            program="PORTDEL",
            description="Apply inbound portfolio closures",
            source_jcl="src/jcl/portfolio/PORTDEL.jcl",
            entrypoint="app.batch.portfolio.delete_portfolios:run",
            datasets=(
                Dataset("PORTFILE", "table:portfolio_master", "write"),
                Dataset("DELEFILE", "artifact:inbound/portfolio-deletions"),
                Dataset("AUDFILE", "table:audit_log", "append"),
            ),
            depends_on=(Dependency("update_portfolios"),),
        ),
        JobStep(
            step_id="extract_portfolios",
            program="PORTREAD",
            description="Post-maintenance portfolio extract",
            source_jcl="src/jcl/portfolio/PORTREAD.jcl",
            entrypoint="app.batch.portfolio.extract_portfolios:run",
            datasets=(
                Dataset("PORTFILE", "table:portfolio_master"),
                Dataset("RPTFILE", "artifact:reports/portfolio-extract", "write"),
            ),
            depends_on=(Dependency("delete_portfolios"),),
            restartable=False,
        ),
    ),
)

UTILITY_OPERATIONS = Pipeline(
    pipeline_id="clbs_utility_operations",
    description="Weekend validation and archival utilities (src/jcl/utility/)",
    schedule="0 4 * * 6",
    frequency="weekly",
    tags=("clbs", "utility"),
    steps=(
        JobStep(
            step_id="data_validation",
            program="UTLVAL00",
            description="Cross-file data validation",
            source_jcl="src/jcl/utility/UTLVAL.jcl",
            entrypoint="app.batch.utility.data_validation:run",
            datasets=(
                Dataset("VALCTL", "config:validation-rules"),
                Dataset("POSMSTRE", "table:investment_positions"),
                Dataset("TRANHIST", "table:transaction_history"),
                Dataset("ERRRPT", "artifact:reports/validation-report", "write"),
            ),
            max_return_code=4,
        ),
        JobStep(
            step_id="file_maintenance",
            program="UTLMNT00",
            description="Archive and reorganize aged records",
            source_jcl="src/jcl/utility/UTLMNT.jcl",
            entrypoint="app.batch.utility.file_maintenance:run",
            datasets=(
                Dataset("CTLFILE", "config:maintenance-control"),
                Dataset("ARCHFILE", "artifact:archive/maintenance-archive", "write"),
                Dataset("RPTFILE", "artifact:reports/maintenance-report", "write"),
            ),
            depends_on=(Dependency("data_validation"),),
        ),
    ),
)

SYSTEM_MONITOR = Pipeline(
    pipeline_id="clbs_system_monitor",
    description="Threshold monitoring and alerting (src/jcl/utility/UTLMON.jcl)",
    schedule="*/15 * * * *",
    frequency="intraday",
    tags=("clbs", "utility", "monitoring"),
    steps=(
        JobStep(
            step_id="system_monitor",
            program="UTLMON00",
            description="Sample system metrics and raise threshold alerts",
            source_jcl="src/jcl/utility/UTLMON.jcl",
            entrypoint="app.batch.utility.system_monitor:run",
            datasets=(
                Dataset("MONCFG", "config:monitor-thresholds"),
                Dataset("MONLOG", "artifact:monitoring/monitor-log", "append"),
                Dataset("ALERTS", "artifact:monitoring/alerts", "append"),
                Dataset("DB2STATS", "metric:database-statistics"),
            ),
            max_return_code=4,
            max_restarts=1,
        ),
    ),
)

TEST_DATA_REFRESH = Pipeline(
    pipeline_id="clbs_test_data_refresh",
    description="On-demand test data generation and validation (src/jcl/test/)",
    schedule=None,
    frequency="on_demand",
    tags=("clbs", "test-support"),
    steps=(
        JobStep(
            step_id="generate_test_data",
            program="TSTGEN00",
            description="Generate portfolio and transaction test data",
            source_jcl="src/jcl/test/TSTGEN.jcl",
            entrypoint="app.batch.test_support.generate_test_data:run",
            datasets=(
                Dataset("TSTCFG", "config:test-data-profile"),
                Dataset("PORTOUT", "table:portfolio_master", "write"),
                Dataset("TRANOUT", "table:transaction_history", "write"),
                Dataset("RANDSEED", "config:test-data-seed"),
            ),
        ),
        JobStep(
            step_id="generate_portfolio_test_file",
            program="PORTTEST",
            description="Generate the portfolio-only test extract",
            source_jcl="src/jcl/portfolio/PORTTEST.jcl",
            entrypoint="app.batch.test_support.generate_portfolio_test_file:run",
            datasets=(Dataset("TESTFILE", "artifact:test-data/portfolio-extract", "write"),),
        ),
        JobStep(
            step_id="validate_test_results",
            program="TSTVAL00",
            description="Compare actual against expected test results",
            source_jcl="src/jcl/test/TSTVAL.jcl",
            entrypoint="app.batch.test_support.validate_test_results:run",
            datasets=(
                Dataset("TESTCASE", "config:test-cases"),
                Dataset("EXPECTED", "artifact:test-data/expected-results"),
                Dataset("ACTUAL", "artifact:test-data/actual-results"),
                Dataset("TESTRPT", "artifact:reports/test-validation-report", "write"),
            ),
            depends_on=(
                Dependency("generate_test_data"),
                Dependency("generate_portfolio_test_file"),
            ),
            restartable=False,
        ),
    ),
)

PIPELINES: tuple[Pipeline, ...] = (
    DAILY_REPORTING,
    PORTFOLIO_MAINTENANCE,
    UTILITY_OPERATIONS,
    SYSTEM_MONITOR,
    TEST_DATA_REFRESH,
)

RETIRED_JCL: dict[str, str] = {
    "src/jcl/portfolio/PORTDEF.jcl": (
        "IDCAMS DEFINE CLUSTER for PORTFOLIO.MASTER.FILE; replaced by the Alembic migrations in "
        "alembic/versions/ (see Task 7.1)"
    )
}


def get_pipeline(pipeline_id: str) -> Pipeline:
    for pipeline in PIPELINES:
        if pipeline.pipeline_id == pipeline_id:
            return pipeline
    raise KeyError(f"unknown pipeline {pipeline_id!r}")


def get_step(pipeline_id: str, step_id: str) -> JobStep:
    return get_pipeline(pipeline_id).step(step_id)
