import requests
import pandas as pd
import time
from pathlib import Path
import logging
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Secop1DataExtractor:
    """Extractor for SECOP I Contratación data from Socrata API"""
    
    def __init__(self, base_url="https://www.datos.gov.co/resource/f789-7hwg.json"):
        # Note: The user provided https://www.datos.gov.co/api/v3/views/f789-7hwg/query.json
        # but typically for extraction we use the resource endpoint.
        # The resource ID is f789-7hwg.
        self.base_url = base_url
        self.batch_size = 50000  # Socrata's max limit per request
        
    def get_total_count(self):
        """Get the total number of records in the dataset"""
        try:
            url = f"{self.base_url}?$select=count(*)"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            count = int(response.json()[0]['count'])
            logger.info(f"Total records in dataset: {count:,}")
            return count
        except Exception as e:
            logger.warning(f"Could not get total count: {e}")
            return None
    
    def fetch_batch(self, offset, limit):
        """Fetch a single batch of data from the API"""
        params = {
            '$limit': limit,
            '$offset': offset,
            '$order': ':id'  # Order by internal ID for consistent pagination
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    self.base_url, 
                    params=params, 
                    timeout=60
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {wait_time} seconds..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to fetch batch after {max_retries} attempts: {e}")
                    raise
    
    def extract_all_data(self, output_file="datasets/01_raw/secop1_contratacion.csv", 
                        save_chunks=True):
        """
        Extract all data from the API with pagination
        
        Args:
            output_file: Path to save the final CSV file
            save_chunks: If True, saves intermediate chunks (useful for recovery)
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Get total count
        total_count = self.get_total_count()
        
        offset = 0
        all_data = []
        chunk_number = 0
        
        logger.info(f"Starting data extraction with batch size: {self.batch_size:,}")
        
        # Create progress bar
        if total_count:
            pbar = tqdm(total=total_count, desc="Extracting records", unit="records")
        else:
            pbar = None
        
        while True:
            try:
                logger.info(f"Fetching batch at offset {offset:,}")
                batch = self.fetch_batch(offset, self.batch_size)
                
                if not batch:
                    logger.info("No more data to fetch. Extraction complete.")
                    break
                
                batch_size = len(batch)
                all_data.extend(batch)
                
                if pbar:
                    pbar.update(batch_size)
                
                logger.info(f"Retrieved {batch_size:,} records. Total so far: {len(all_data):,}")
                
                # Save intermediate chunks if requested
                if save_chunks and len(all_data) >= 100000:
                    chunk_file = output_path.parent / f"secop1_chunk_{chunk_number:04d}.csv"
                    df_chunk = pd.DataFrame(all_data)
                    df_chunk.to_csv(chunk_file, index=False, encoding='utf-8-sig')
                    logger.info(f"Saved chunk {chunk_number} with {len(all_data):,} records to {chunk_file}")
                    all_data = []
                    chunk_number += 1
                
                # If we got fewer records than requested, we've reached the end
                if batch_size < self.batch_size:
                    logger.info("Reached end of dataset (batch smaller than limit).")
                    break
                
                offset += batch_size
                
                # Small delay to be respectful to the API
                time.sleep(0.5)
                
            except KeyboardInterrupt:
                logger.warning("Extraction interrupted by user.")
                break
            except Exception as e:
                logger.error(f"Error during extraction: {e}")
                break
        
        if pbar:
            pbar.close()
        
        # Save final data
        if all_data:
            if chunk_number > 0:
                # Save final chunk
                chunk_file = output_path.parent / f"secop1_chunk_{chunk_number:04d}.csv"
                df_final = pd.DataFrame(all_data)
                df_final.to_csv(chunk_file, index=False, encoding='utf-8-sig')
                logger.info(f"Saved final chunk {chunk_number} with {len(all_data):,} records")
                
                # Merge all chunks
                logger.info("Merging all chunks into final file...")
                self.merge_chunks(output_path.parent, output_file)
            else:
                # Save directly if no chunks were created
                df_final = pd.DataFrame(all_data)
                df_final.to_csv(output_file, index=False, encoding='utf-8-sig')
                logger.info(f"Saved {len(all_data):,} records to {output_file}")
        elif chunk_number > 0:
            # Merge chunks even if all_data is empty (all data in chunks)
            logger.info("Merging all chunks into final file...")
            self.merge_chunks(output_path.parent, output_file)
        
        logger.info("Data extraction completed!")
    
    def merge_chunks(self, chunks_dir, output_file):
        """Merge all chunk files into a single CSV"""
        chunk_files = sorted(chunks_dir.glob("secop1_chunk_*.csv"))
        
        if not chunk_files:
            logger.warning("No chunk files found to merge")
            return
        
        logger.info(f"Found {len(chunk_files)} chunks to merge")
        
        # Read and concatenate all chunks
        dfs = []
        for chunk_file in tqdm(chunk_files, desc="Reading chunks"):
            df = pd.read_csv(chunk_file)
            dfs.append(df)
        
        df_final = pd.concat(dfs, ignore_index=True)
        df_final.to_csv(output_file, index=False, encoding='utf-8-sig')
        logger.info(f"Merged {len(df_final):,} records into {output_file}")
        
        # Remove chunk files after merging
        for chunk_file in chunk_files:
            chunk_file.unlink()
        logger.info("Removed temporary chunk files")


def main():
    """Main execution function"""
    extractor = Secop1DataExtractor()
    
    # Extract all data
    extractor.extract_all_data(
        output_file="datasets/01_raw/secop1_contratacion.csv",
        save_chunks=True  # Save intermediate chunks for safety
    )
    
    # Print summary
    output_file = Path("datasets/01_raw/secop1_contratacion.csv")
    if output_file.exists():
        df = pd.read_csv(output_file, nrows=5)
        logger.info(f"\nDataset shape: {len(df):,} rows (showing first 5)")
        logger.info(f"Columns: {list(df.columns)}")
        logger.info(f"\nFirst few rows:\n{df.head()}")


if __name__ == "__main__":
    main()

