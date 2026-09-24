"""Airflow DAG replacing src/jcl/portfolio/PORT{ADD,UPDT,DEL,READ}.jcl."""

from orchestration.catalog import PORTFOLIO_MAINTENANCE
from orchestration.dag_factory import build_dag

dag = build_dag(PORTFOLIO_MAINTENANCE)
