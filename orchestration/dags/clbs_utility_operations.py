"""Airflow DAG replacing src/jcl/utility/UTLVAL.jcl and src/jcl/utility/UTLMNT.jcl."""

from orchestration.catalog import UTILITY_OPERATIONS
from orchestration.dag_factory import build_dag

dag = build_dag(UTILITY_OPERATIONS)
