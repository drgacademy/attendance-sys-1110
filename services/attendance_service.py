import numpy as np

from typing import Dict, Any, Optional
from flask import abort, current_app
from models.database import get_db
from utils.helpers import now_iso_seconds
from services.google_sheets_service import GoogleSheetsService
from services.storage_service import StorageService
from services.async_task_service import AsyncTaskService, with_retry
from config import Config

class AttendanceService:
    @staticmethod
    def punch(ident: str, face_image: Optional[np.ndarray] = None) -> Dict[str, Any]:
        db = get_db()
        person = db.execute(
            "SELECT ident FROM people WHERE ident = %s", 
            (ident,)
        ).fetchone()
        if not person:
            abort(404, "Person with this ident not found")
        
        punch_time = now_iso_seconds()
        
        result = db.execute(
            "INSERT INTO attendance (ident, punch_time, image_url, created_at) VALUES (%s, %s, %s, %s) RETURNING id",
            (ident, punch_time, None, punch_time)
        )
        attendance_id = result.fetchone()['id']
        db.commit()
        
        combined_task_id = None
        if face_image is not None:
            app = current_app._get_current_object()
            
            try:
                def combined_upload_task():
                    print(f"[ATTENDANCE TASK] Starting combined upload for {ident}")
                    
                    # Upload to GCS with retry
                    @with_retry(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
                    def gcs_upload():
                        if Config.GCS_USE_PUBLIC_URLS:
                            success, url, error = StorageService.upload_attendance_image(
                                face_image, ident, punch_time
                            )
                        else:
                            success, url, error = StorageService.upload_attendance_image_with_expiry(
                                face_image, ident, punch_time, Config.GCS_SIGNED_URL_EXPIRY_HOURS
                            )
                        
                        if not success:
                            raise Exception(f"GCS upload failed: {error}")
                        return url
                    
                    try:
                        url = gcs_upload()
                        print(f"[ATTENDANCE TASK] GCS upload successful: {url}")
                    except Exception as e:
                        print(f"[ATTENDANCE TASK] GCS upload failed after retries: {e}")
                        raise
                    
                    # Update database with image URL
                    try:
                        with app.app_context():
                            db_local = get_db()
                            db_local.execute(
                                "UPDATE attendance SET image_url = %s WHERE id = %s",
                                (url, attendance_id)
                            )
                            db_local.commit()
                        print(f"[ATTENDANCE TASK] Database updated with image URL")
                    except Exception as e:
                        print(f"[ATTENDANCE TASK] Database update failed: {e}")
                        raise
                    
                    # Upload to Google Sheets with retry
                    @with_retry(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
                    def sheets_upload():
                        return GoogleSheetsService.append_attendance_record(
                            ident=ident,
                            punch_time=punch_time,
                            image_url=url
                        )
                    
                    try:
                        sheets_result = sheets_upload()
                        print(f"[ATTENDANCE TASK] Google Sheets upload result: {sheets_result}")
                        return {
                            "image_url": url,
                            "sheets_result": sheets_result
                        }
                    except Exception as e:
                        print(f"[ATTENDANCE TASK] Google Sheets upload failed after retries: {e}")
                        # Don't raise - GCS upload was successful, which is the primary goal
                        return {
                            "image_url": url,
                            "sheets_result": {"success": False, "error": str(e)}
                        }
                
                combined_task_id = AsyncTaskService.submit_task(
                    combined_upload_task,
                    task_name=f"attendance_upload_{ident}",
                )
                print(f"[ATTENDANCE] Submitted combined upload task: {combined_task_id}")
                
            except Exception as e:
                print(f"[ATTENDANCE] Failed to submit combined upload task: {e}")
                import traceback
                traceback.print_exc()
        else:
            try:
                def sheets_only_task():
                    print(f"[ATTENDANCE TASK] Starting sheets-only upload for {ident}")
                    
                    @with_retry(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
                    def sheets_upload():
                        return GoogleSheetsService.append_attendance_record(
                            ident=ident,
                            punch_time=punch_time,
                            image_url=None
                        )
                    
                    try:
                        result = sheets_upload()
                        print(f"[ATTENDANCE TASK] Google Sheets upload result: {result}")
                        return result
                    except Exception as e:
                        print(f"[ATTENDANCE TASK] Google Sheets upload failed after retries: {e}")
                        import traceback
                        traceback.print_exc()
                        raise
                
                combined_task_id = AsyncTaskService.submit_task(
                    sheets_only_task,
                    task_name=f"attendance_sheets_{ident}",
                )
                print(f"[ATTENDANCE] Submitted sheets-only task: {combined_task_id}")
                
            except Exception as e:
                print(f"[ATTENDANCE] Failed to submit sheets-only task: {e}")
                import traceback
                traceback.print_exc()
        
        result = {
            "ident": ident,
            "punch_time": punch_time,
            "attendance_id": attendance_id,
            "message": "Attendance recorded successfully",
            "background_task": combined_task_id
        }
        
        return result

