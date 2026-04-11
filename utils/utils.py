import polars as pl
from chembl_webresource_client.new_client import new_client
import os

def fetch_chembl_activity_to_polars(target_id="CHEMBL203", activity_type="IC50"):
    activity = new_client.activity
    query = activity.filter(target_chembl_id=target_id).filter(standard_type=activity_type)
    
    print(f"Pobieranie danych dla celu: {target_id}...")
    data = list(query)

    if data:
        df = pl.DataFrame(data, infer_schema_length=None)
        
        # Konwersja standard_value na float (jeśli istnieje)
        if "standard_value" in df.columns:
             df = df.with_columns(
                pl.col("standard_value").cast(pl.Float64, strict=False)
            )
        
        return df
    else:
        print("Nie znaleziono danych.")
        return pl.DataFrame()

def get_data_from_parquet(file_path = "Chembl203_IC50.parquet"):
    if os.path.exists(file_path):
        print(f"Wczytywanie danych z pliku lokalnego: {file_path}")
        return pl.read_parquet(file_path)
    else:
        print(f"Plik nie istnieje: {file_path}")
        return None

        
def save_data_to_parquet(df, file_path = "Chembl203_IC50.parquet"):
    if df is not None:
        print(f"Zapisywanie danych do pliku: {file_path}")
        df.write_parquet(file_path)
    else:
        print("Nie ma danych do zapisania.")

# Uruchomienie
