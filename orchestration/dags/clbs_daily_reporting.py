"""Airflow DAG replacing src/jcl/batch/*.jcl and src/jcl/RTNANA.jcl."""

from orchestration.catalog import DAILY_REPORTING
from orchestration.dag_factory import build_dag

dag = build_dag(DAILY_REPORTING)
