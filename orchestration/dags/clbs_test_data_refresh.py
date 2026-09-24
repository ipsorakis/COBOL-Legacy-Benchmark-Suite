"""Airflow DAG replacing src/jcl/test/*.jcl and src/jcl/portfolio/PORTTEST.jcl."""

from orchestration.catalog import TEST_DATA_REFRESH
from orchestration.dag_factory import build_dag

dag = build_dag(TEST_DATA_REFRESH)
