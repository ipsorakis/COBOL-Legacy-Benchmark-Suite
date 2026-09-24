# Batch orchestration (replacement for `src/jcl/`)

The Python tier schedules batch work with [Apache Airflow](https://airflow.apache.org/) instead of
JCL submitted to JES. Every JCL member in `src/jcl/` is either represented in the job catalog or
explicitly retired; `tests/test_orchestration_catalog.py` fails if a member is added without being
accounted for.

```
orchestration/
├── catalog.py      # pipelines, job steps, DD bindings, return-code and restart rules
├── runtime.py      # resolves a step's Python entrypoint and runs it with a JobContext
├── dag_factory.py  # turns a Pipeline into an Airflow DAG
└── dags/           # AIRFLOW__CORE__DAGS_FOLDER — one module per pipeline
```

## JCL → DAG mapping

| JCL member | Program | DAG (`pipeline_id`) | Task | Schedule |
| --- | --- | --- | --- | --- |
| `src/jcl/batch/RPTPOS.jcl` | `RPTPOS00` | `clbs_daily_reporting` | `position_report` | daily 02:00 |
| `src/jcl/batch/RPTAUD.jcl` | `RPTAUD00` | `clbs_daily_reporting` | `audit_report` | daily 02:00 |
| `src/jcl/batch/RPTSTA.jcl` | `RPTSTA00` | `clbs_daily_reporting` | `system_stats_report` | daily 02:00 |
| `src/jcl/RTNANA.jcl` | `RTNANA00` | `clbs_daily_reporting` | `return_code_analysis` | daily 02:00 |
| `src/jcl/portfolio/PORTADD.jcl` | `PORTADD` | `clbs_portfolio_maintenance` | `add_portfolios` | weekdays 22:00 |
| `src/jcl/portfolio/PORTUPDT.jcl` | `PORTUPDT` | `clbs_portfolio_maintenance` | `update_portfolios` | weekdays 22:00 |
| `src/jcl/portfolio/PORTDEL.jcl` | `PORTDEL` | `clbs_portfolio_maintenance` | `delete_portfolios` | weekdays 22:00 |
| `src/jcl/portfolio/PORTREAD.jcl` | `PORTREAD` | `clbs_portfolio_maintenance` | `extract_portfolios` | weekdays 22:00 |
| `src/jcl/utility/UTLVAL.jcl` | `UTLVAL00` | `clbs_utility_operations` | `data_validation` | Saturdays 04:00 |
| `src/jcl/utility/UTLMNT.jcl` | `UTLMNT00` | `clbs_utility_operations` | `file_maintenance` | Saturdays 04:00 |
| `src/jcl/utility/UTLMON.jcl` | `UTLMON00` | `clbs_system_monitor` | `system_monitor` | every 15 min |
| `src/jcl/test/TSTGEN.jcl` | `TSTGEN00` | `clbs_test_data_refresh` | `generate_test_data` | manual |
| `src/jcl/portfolio/PORTTEST.jcl` | `PORTTEST` | `clbs_test_data_refresh` | `generate_portfolio_test_file` | manual |
| `src/jcl/test/TSTVAL.jcl` | `TSTVAL00` | `clbs_test_data_refresh` | `validate_test_results` | manual |

`src/jcl/portfolio/PORTDEF.jcl` is retired rather than ported: its `IDCAMS DEFINE CLUSTER` for
`PORTFOLIO.MASTER.FILE` is now the Alembic migration that creates `portfolio_master` (Task 7.1).
`catalog.RETIRED_JCL` records that decision.

JCL carried no schedules — they lived in the scheduler definitions, of which only the
`PRCSEQ`/`BCHCTL` control-record layouts survive in this repository. The frequencies above come
from the `PSR-FREQ`, `PSR-ACTIVE-DAYS` and program documentation, and are the one part of the
catalog expected to be re-tuned against the production scheduler calendar.

## How mainframe constructs are re-expressed

| JCL / COBOL construct | Airflow equivalent |
| --- | --- |
| `JOB` card + `EXEC PGM=` step | DAG + `PythonOperator` task per step |
| `DD` statement (VSAM/DB2/SYSOUT dataset) | `Dataset` binding (`table:`, `artifact:`, `config:`, `metric:`) passed to the job in `JobContext.datasets` |
| `COND=` / `PSR-MAX-RC` | `JobStep.max_return_code`; a higher code raises `BatchJobFailedError` |
| `PSR-DEP-HARD` | task dependency with `all_success` |
| `PSR-DEP-SOFT` | task dependency with `all_done`, so e.g. return-code analysis still runs after a failed report |
| `PSR-RESTART` / `CK-MAX-RESTARTS` | task `retries` (0 for `PSR-NO-RESTART` steps), 5-minute `retry_delay` |
| `CK-RESTART-MODE` | `JobContext.restart`, set on any attempt after the first |
| `CK-COMMIT-FREQ` | `IPMS_BATCH_COMMIT_INTERVAL` (`Settings.batch_commit_interval`) |
| Single-threaded job class | `max_active_runs=1`, `catchup=False` |
| `NOTIFY=&SYSUID` | scheduler-level notification/alerting configuration, not code |

## Running it

```bash
make install                                    # installs the orchestration dependency group
export AIRFLOW__CORE__DAGS_FOLDER=$PWD/orchestration/dags
export PYTHONPATH=$PWD                          # DAG modules import the orchestration package
uv run airflow dags list
uv run airflow standalone                       # local scheduler + UI on http://localhost:8080
```

`uv run pytest tests/test_orchestration_dags.py` parses the DAG folder and asserts each DAG matches
its catalog pipeline, which is the check to run before shipping a catalog change.

## Job implementations

The catalog points at the batch entrypoints (`app.batch.<area>.<job>:run`, taking a `JobContext` and
returning a return code). Those implementations arrive with the batch-tier port (EPIC 2); until a
step's entrypoint exists, running the task raises `BatchJobNotPortedError` naming the COBOL program
and its JCL origin, so the orchestration graph can be reviewed and scheduled without pretending the
work is done.
