from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lower, trim
import os

def process_chembl_data(input_path, output_path):
    # Initialize Spark Session
    spark = SparkSession.builder \
        .appName("ChEMBL Data Processor") \
        .getOrCreate()

    print(f"Reading data from {input_path}")
    
    # Read the data (handling header)
    df = spark.read.option("header", "true").csv(input_path)

    print("Data loaded. performing cleaning...")
    
    # Basic Cleaning:
    # 1. Drop rows where 'smiles' is null (molecular structure is essential)
    # 2. Trim whitespace from string columns
    # 3. Rename columns to standardized format if needed
    
    # Assuming standard ChEMBL columns like 'molecule_chembl_id', 'smiles', 'molecular_weight'
    # If columns contain whitespace, we clean them
    
    cleaned_df = df.dropna(subset=["smiles"]) \
                   .withColumn("smiles", trim(col("smiles"))) \
                   .withColumn("molecule_chembl_id", trim(col("molecule_chembl_id")))

    # Example: Filter for valid molecular weight if column exists
    if "molecular_weight" in df.columns:
        cleaned_df = cleaned_df.filter(col("molecular_weight").isNotNull())

    print(f"Writing processed data to {output_path}")
    
    # Batch Processing Strategy:
    # 1. Repartition: Control the number of output files (e.g., 10 files)
    # 2. PartitionBy: Organize data physically by a column (e.g., if we had 'year' or 'type')
    # 3. maxRecordsPerFile: Ensure no single file is too huge
    
    # Example: Writing 10 part files, ensuring max 100k records per file
    cleaned_df.repartition(10) \
              .write \
              .option("maxRecordsPerFile", 100000) \
              .mode("overwrite") \
              .parquet(output_path)
    
    print("Processing complete.")
    spark.stop()

if __name__ == "__main__":
    # Define paths (mapped in DockerCompose)
    # Check if download occurred, otherwise fallback to sample
    if os.path.exists("/opt/data/raw/chembl_33_sqlite.tar.gz"): 
        # Note: Spark cannot read tar.gz sqlite directly easily without extraction.
        # Ideally we process the CSV. For this demo, we assume the input might be different 
        # or we stick to the sample if the big file isn't ready.
        # This script assumes CSV input.
        INPUT_FILE = "/opt/data/raw/chembl_sample.csv" 
    else:
         INPUT_FILE = "/opt/data/raw/chembl_sample.csv"

    OUTPUT_DIR = "/opt/data/processed/chembl_clean"
    
    process_chembl_data(INPUT_FILE, OUTPUT_DIR)
