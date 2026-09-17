"""
Airflow DAG for silver/gold layer transformations.

Runs dbt models to transform bronze → silver → gold.
Triggered after bronze ingestion quality gate passes.
"""
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    "owner": "data-eng",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "depends_on_past": False,
}

with DAG(
    dag_id="marketfeed_dbt_transformation",
    default_args=default_args,
    description="Transform data through silver and gold layers with dbt",
    schedule_interval="0 23 * * 1-5",  # 11pm UTC, after bronze ingestion
    start_date=datetime(2026, 8, 1),
    catchup=False,  # No backfill needed for transformations
    tags=["dbt", "silver", "gold", "transformation"],
) as dag:

    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command="cd /opt/airflow/dbt && dbt seed --profiles-dir .",
    )

    dbt_snapshot = BashOperator(
        task_id="dbt_snapshot",
        bash_command="cd /opt/airflow/dbt && dbt snapshot --profiles-dir .",
    )

    dbt_run_silver = BashOperator(
        task_id="dbt_run_silver",
        bash_command="cd /opt/airflow/dbt && dbt run --select silver --profiles-dir .",
    )

    dbt_test_silver = BashOperator(
        task_id="dbt_test_silver",
        bash_command="cd /opt/airflow/dbt && dbt test --select silver --profiles-dir .",
    )

    dbt_run_gold = BashOperator(
        task_id="dbt_run_gold",
        bash_command="cd /opt/airflow/dbt && dbt run --select gold --profiles-dir .",
    )

    dbt_test_gold = BashOperator(
        task_id="dbt_test_gold",
        bash_command="cd /opt/airflow/dbt && dbt test --select gold --profiles-dir .",
    )

    # DAG flow: seed → snapshot → silver (run + test) → gold (run + test)
    dbt_seed >> dbt_snapshot >> dbt_run_silver >> dbt_test_silver >> dbt_run_gold >> dbt_test_gold
