import uuid
import numpy as np
import os
from config import Config
from typing import Optional, Tuple
from datetime import datetime, timedelta
from google.cloud import storage
from google.oauth2 import service_account
from google.auth import default
from utils.image_processing import optimize_image, compress_image_to_bytes

class StorageService:
    _client = None
    _bucket = None
    
    @staticmethod
    def get_client():
        if StorageService._client is None:
            try:
                # 如果有設定憑證路徑且檔案存在，使用服務帳戶檔案
                if Config.GCS_CREDENTIALS_PATH and os.path.exists(Config.GCS_CREDENTIALS_PATH):
                    credentials = service_account.Credentials.from_service_account_file(
                        Config.GCS_CREDENTIALS_PATH,
                        scopes=['https://www.googleapis.com/auth/devstorage.read_write']
                    )
                    StorageService._client = storage.Client(
                        credentials=credentials,
                        project=credentials.project_id
                    )
                else:
                    # 否則使用 Application Default Credentials (ADC)
                    # 這會自動使用 Cloud Run 的服務帳戶
                    credentials, project = default(scopes=['https://www.googleapis.com/auth/devstorage.read_write'])
                    StorageService._client = storage.Client(
                        credentials=credentials,
                        project=project
                    )
            except Exception as e:
                raise RuntimeError(f"Failed to initialize Google Cloud Storage client: {e}")
        return StorageService._client
    
    @staticmethod
    def get_bucket():
        if StorageService._bucket is None:
            client = StorageService.get_client()
            StorageService._bucket = client.bucket(Config.GCS_BUCKET_NAME)
        return StorageService._bucket
    
    @staticmethod
    def upload_attendance_image(
        image: np.ndarray,
        student_id: str,
        timestamp: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        try:
            optimized_image, stats = optimize_image(image, max_width=1024, max_height=1024, quality=85)
            
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            date_str = dt.strftime('%Y%m%d')
            time_str = dt.strftime('%H%M%S')
            
            unique_id = str(uuid.uuid4())[:8]
            filename = f"attendance/{date_str}/{student_id}_{time_str}_{unique_id}.jpg"
            
            image_bytes, size = compress_image_to_bytes(optimized_image, quality=85)
            bucket = StorageService.get_bucket()

            blob = bucket.blob(filename)
            blob.content_type = 'image/jpeg'
            blob.upload_from_string(image_bytes, content_type='image/jpeg')
            
            public_url = blob.public_url
            
            return True, public_url, None
            
        except Exception as e:
            return False, None, f"Failed to upload image: {str(e)}"
    
    @staticmethod
    def upload_attendance_image_with_expiry(
        image: np.ndarray,
        student_id: str,
        timestamp: str,
        expiry_hours: int = 24
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        
        try:
            optimized_image, stats = optimize_image(image, max_width=1024, max_height=1024, quality=85)
            
            print(f"Image optimization: {stats['original_dimensions']} → {stats['optimized_dimensions']}, "
                  f"size: {stats['original_size_bytes']} → {stats['compressed_size_bytes']} bytes "
                  f"({stats['compression_ratio']} reduction)")
            
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            date_str = dt.strftime('%Y%m%d')
            time_str = dt.strftime('%H%M%S')
            
            unique_id = str(uuid.uuid4())[:8]
            filename = f"attendance/{date_str}/{student_id}_{time_str}_{unique_id}.jpg"
            
            image_bytes, size = compress_image_to_bytes(optimized_image, quality=85)
            
            bucket = StorageService.get_bucket()
            blob = bucket.blob(filename)
            blob.content_type = 'image/jpeg'
            blob.upload_from_string(image_bytes, content_type='image/jpeg')

            expiration = timedelta(hours=expiry_hours)
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=expiration,
                method="GET"
            )
            
            return True, signed_url, None
            
        except Exception as e:
            return False, None, f"Failed to upload image with expiry: {str(e)}"
    
    @staticmethod
    def delete_old_images(days_old: int = 30) -> Tuple[int, int]:
        try:
            bucket = StorageService.get_bucket()
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            deleted_count = 0
            error_count = 0
            
            blobs = bucket.list_blobs(prefix='attendance/')
            
            for blob in blobs:
                try:
                    if blob.time_created and blob.time_created.replace(tzinfo=None) < cutoff_date:
                        blob.delete()
                        deleted_count += 1
                except Exception as e:
                    print(f"Error deleting blob {blob.name}: {e}")
                    error_count += 1
            
            return deleted_count, error_count
            
        except Exception as e:
            print(f"Error in delete_old_images: {e}")
            return 0, 1
    
    @staticmethod
    def test_connection() -> Tuple[bool, str]:
        try:
            bucket = StorageService.get_bucket()
            bucket.reload()
            message = f"Successfully connected to bucket: {bucket.name}"
            return True, message
            
        except Exception as e:
            message = f"Failed to connect to GCS: {str(e)}"
            return False, message
