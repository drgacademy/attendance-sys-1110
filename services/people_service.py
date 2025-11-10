import psycopg2
import numpy as np

from typing import List, Dict, Any, Optional
from flask import abort, request
from models.database import get_db
from utils.helpers import row_to_dict, now_iso_seconds
from services.async_task_service import AsyncTaskService, with_retry
from config import Config

class PeopleService:
    @staticmethod
    def parse_people_payload(files, form_json) -> Dict[str, Any]:
        data = {}
        
        if form_json:
            data['ident'] = form_json.get('ident')
        else:
            data['ident'] = request.form.get('ident')
        
        if not data.get('ident'):
            abort(400, "ident (student ID) is required")
        
        if form_json and 'time_zone' in form_json:
            data['time_zone'] = form_json.get('time_zone')
        elif request.form and 'time_zone' in request.form:
            data['time_zone'] = request.form.get('time_zone')
        
        file = files.get("face_embedding_file") if files else None
        if file and file.filename:
            try:
                arr = np.load(file, allow_pickle=False)
                if arr.dtype != "float32":
                    arr = arr.astype("float32")
                data["face_embedding"] = arr.tobytes()
            except Exception as e:
                abort(400, f"Failed to read face embedding file: {e}")
        
        photo_file = files.get("face_photo") if files else None
        photo_base64 = request.form.get("face_photo_base64") if request.form else None
        
        if photo_file and photo_file.filename:
            try:
                from utils.image_processing import read_image_from_request
                from services.face_service import FaceService
                
                img = read_image_from_request(photo_file, None)
                emb, face_count = FaceService.extract_embedding(img)
                
                if face_count != 1:
                    abort(400, f"Detected {face_count} faces in photo, please ensure only one person in photo")
                
                data["face_embedding"] = emb.tobytes()
            except Exception as e:
                abort(400, f"Failed to process face photo: {e}")
        elif photo_base64:
            try:
                from utils.image_processing import read_image_from_request
                from services.face_service import FaceService
                
                img = read_image_from_request(None, photo_base64)
                emb, face_count = FaceService.extract_embedding(img)
                
                if face_count != 1:
                    abort(400, f"Detected {face_count} faces in photo, please ensure only one person in photo")
                
                data["face_embedding"] = emb.tobytes()
            except Exception as e:
                abort(400, f"Failed to process face photo: {e}")
        
        return data
    
    @staticmethod
    def list_all() -> List[Dict[str, Any]]:
        db = get_db()
        rows = db.execute(
            "SELECT ident, time_zone, created_at, updated_at "
            "FROM people ORDER BY updated_at DESC"
        ).fetchall()
        return [row_to_dict(r) for r in rows]
    
    @staticmethod
    def create(data: Dict[str, Any]) -> None:
        if not data.get("ident"):
            abort(400, "ident is required")
        
        ident = data["ident"].strip()
        if not ident:
            abort(400, "ident cannot be empty")
        
        cols = ["ident"]
        vals = [ident]
        qms = ["%s"]

        timestamp = now_iso_seconds()
        
        for k in ["face_embedding", "time_zone"]:
            if k in data:
                cols.append(k)
                vals.append(data[k])
                qms.append("%s")

        cols.extend(["created_at", "updated_at"])
        vals.extend([timestamp, timestamp])
        qms.extend(["%s", "%s"])
        
        sql = f"INSERT INTO people ({','.join(cols)}) VALUES ({','.join(qms)})"
        db = get_db()
        try:
            db.execute(sql, vals)
            db.commit()
            
            if "face_embedding" in data:
                try:
                    from services.faiss_index_service import FaissIndexService
                    emb = np.frombuffer(data["face_embedding"], dtype="float32")
                    FaissIndexService.add_embedding(ident, emb)
                except Exception as e:
                    pass
            
            try:
                time_zone = data.get("time_zone", "Asia/Taipei")
                
                print(f"[PEOPLE CREATE] Submitting sheets upload task for: {ident}, time_zone: {time_zone}")
                
                def sheets_upload_task():
                    print(f"[PEOPLE TASK] Starting sheets upload for {ident}")
                    
                    @with_retry(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
                    def sheets_upload():
                        from services.google_sheets_service import GoogleSheetsService
                        return GoogleSheetsService.append_personnel_record(
                            ident=ident,
                            time_zone=time_zone
                        )
                    
                    try:
                        result = sheets_upload()
                        print(f"[PEOPLE TASK] Google Sheets upload result: {result}")
                        return result
                    except Exception as e:
                        print(f"[PEOPLE TASK] Google Sheets upload failed after retries: {e}")
                        import traceback
                        traceback.print_exc()
                        raise
                
                task_id = AsyncTaskService.submit_task(
                    sheets_upload_task,
                    task_name=f"sheets_personnel_{ident}",
                )
                
                print(f"[PEOPLE CREATE] Submitted sheets upload task: {task_id}")
                
            except Exception as e:
                print(f"[PEOPLE CREATE] Failed to submit sheets upload task: {e}")
                import traceback
                traceback.print_exc()
            
        except psycopg2.IntegrityError as e:
            abort(409, f"Creation failed: Person with ident '{ident}' already exists")
    
    @staticmethod
    def update(ident: str, data: Dict[str, Any]) -> None:
        if not data:
            return
        
        sets = []
        vals = []
        has_face_embedding = False
        
        for k in ["face_embedding", "time_zone"]:
            if k in data:
                sets.append(f"{k} = %s")
                vals.append(data[k])
                if k == "face_embedding":
                    has_face_embedding = True

        if sets:
            sets.append("updated_at = %s")
            vals.append(now_iso_seconds())
        
        if not sets:
            return
        
        sql = f"UPDATE people SET {', '.join(sets)} WHERE ident = %s"
        vals.append(ident)
        db = get_db()
        cur = db.execute(sql, vals)
        db.commit()
        if cur.rowcount == 0:
            abort(404, "Person not found")
        
        if has_face_embedding:
            try:
                from services.faiss_index_service import FaissIndexService
                FaissIndexService.update_embedding(ident, np.frombuffer(data["face_embedding"], dtype="float32"))
            except Exception as e:
                pass
    
    @staticmethod
    def delete(ident: str) -> None:
        db = get_db()
        cur = db.execute("DELETE FROM people WHERE ident = %s", (ident,))
        db.commit()
        if cur.rowcount == 0:
            abort(404, "Person not found")
        
        try:
            from services.faiss_index_service import FaissIndexService
            FaissIndexService.remove_embedding(ident)
        except Exception as e:
            pass
    
    @staticmethod
    def get_by_ident(ident: str) -> Optional[Dict]:
        db = get_db()
        return db.execute(
            "SELECT * FROM people WHERE ident = %s", 
            (ident,)
        ).fetchone()
    
    @staticmethod
    def get_all_with_embeddings() -> List[Dict]:
        db = get_db()
        return db.execute(
            "SELECT ident, face_embedding "
            "FROM people WHERE face_embedding IS NOT NULL"
        ).fetchall()


