from airflow import DAG
from airflow.sensors.filesystem import FileSensor
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
from datetime import timedelta
from chembl_webresource_client.new_client import new_client

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'chembl_processing_pipeline',
    default_args=default_args,
    description='A simple pipeline to process ChEMBL data with Spark',
    schedule_interval=timedelta(days=1),
    start_date=days_ago(1),
    catchup=False,
) as dag:

    # 0. Download Data
    download_data = BashOperator(
        task_id='download_chembl_data',
        bash_command='python /opt/scripts/download_chembl.py',
        execution_timeout=timedelta(minutes=60)
    )

    # 1. Check if the input file exists
    # Note: FileSensor checks locally. Since we mounted ./data to /opt/data, it checks in the container.
    wait_for_file = FileSensor(
        task_id='wait_for_chembl_data',
        filepath='/opt/data/raw/chembl_sample.csv',
        fs_conn_id='fs_default', # Check default filesystem
        poke_interval=10,
        timeout=600
    )

    # 2. Submit the Spark Job
# Pamiętaj o imporcie: from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator

submit_spark_job = SparkSubmitOperator(
    task_id='submit_spark_job',
    application='/opt/airflow/dags/chembl_pipeline.py',  # Ścieżka do Twojego pliku DAG/skryptu w kontenerze Airflow
    conn_id='spark_default', # Musisz utworzyć to połączenie w Airflow UI!
    master='spark://spark-master:7077', # Nazwa hosta usługi Spark Master
    conf={
        "spark.driver.extraClassPath": "/opt/airflow/dags/postgresql-42.7.3.jar" # Opcjonalnie: do połączenia PG
    },
    # Dodaj argumenty do Twojej funkcji process_chembl_data() jeśli jest w osobnym pliku
    application_args=[
        "/opt/data/raw/chembl_sample.csv", 
        "/opt/data/processed/chembl_clean"
    ]
)

    # 3. Verify output
    verify_processing = BashOperator(
        task_id='verify_output',
        bash_command='ls -l /opt/data/processed/chembl_clean || echo "Output not found"'
    )

    download_data >> wait_for_file >> submit_spark_job >> verify_processing
