import os
import urllib.request
import re
import sys

# Configuration
DATA_DIR = "/opt/data/raw"
BASE_URL = "https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/latest/"
# We will try to find the sqlite tar.gz because it's a single file and commonly used, 
# though for Spark, CSV would be better, ChEMBL CSVs are usually split.
# Let's try to find a file pattern.
FILE_PATTERN = r'chembl_[0-9]+_sqlite\.tar\.gz'

def get_latest_file_url():
    print(f"Checking {BASE_URL} for latest version...")
    try:
        with urllib.request.urlopen(BASE_URL) as response:
            html = response.read().decode('utf-8')
            matches = re.findall(FILE_PATTERN, html)
            if matches:
                # Return the generic first match, likely the file we want
                filename = matches[0]
                return BASE_URL + filename, filename
    except Exception as e:
        print(f"Error fetching directory listing: {e}")
        return None, None
    return None, None

def download_file(url, dest_path):
    print(f"Downloading {url} to {dest_path}")
    if os.path.exists(dest_path):
        print("File already exists. Skipping download.")
        return

    try:
        with urllib.request.urlopen(url) as response:
            total_size = int(response.info().get('Content-Length', 0))
            block_size = 8192
            downloaded = 0
            
            with open(dest_path, 'wb') as f:
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    downloaded += len(buffer)
                    f.write(buffer)
                    # Simple progress indicator
                    if total_size > 0:
                        percent = downloaded * 100 / total_size
                        if downloaded % (block_size * 1000) == 0:
                            print(f"Downloaded {downloaded}/{total_size} bytes ({percent:.1f}%)")
            
            print("Download complete.")
    except Exception as e:
        print(f"Error downloading file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    url, filename = get_latest_file_url()
    
    # Fallback if we can't parse (e.g. if the directory listing format changes)
    if not url:
        print("Could not auto-detect file. Using fallback URL.")
        filename = "chembl_33_sqlite.tar.gz"
        url = BASE_URL + filename
    
    dest = os.path.join(DATA_DIR, filename)
    download_file(url, dest)
