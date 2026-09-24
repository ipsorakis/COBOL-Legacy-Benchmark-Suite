"""Airflow DAG replacing src/jcl/utility/UTLMON.jcl."""

from orchestration.catalog import SYSTEM_MONITOR
from orchestration.dag_factory import build_dag

dag = build_dag(SYSTEM_MONITOR)
