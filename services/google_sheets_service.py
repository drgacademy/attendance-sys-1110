from config import Config
from typing import Dict, Any, Optional, List
from datetime import datetime
import os
import threading

from google.oauth2 import service_account
from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class GoogleSheetsService:
    _service = None
    _service_lock = threading.Lock()

    @staticmethod
    def _format_timestamp(timestamp: Optional[str]) -> str:
        if not timestamp:
            return ''
        try:
            normalized = timestamp.replace('Z', '+00:00')
            dt = datetime.fromisoformat(normalized)
            return dt.strftime('%Y-%m-%dT%H:%M:%S')
        except Exception:
            if '+' in timestamp:
                return timestamp.split('+')[0]
            return timestamp
    
    @staticmethod
    def get_service():
        with GoogleSheetsService._service_lock:
            if GoogleSheetsService._service is None:
                try:
                    scopes = ['https://www.googleapis.com/auth/spreadsheets']
                    
                    # 如果有設定憑證路徑且檔案存在，使用服務帳戶檔案
                    if Config.GOOGLE_CREDENTIALS_PATH and os.path.exists(Config.GOOGLE_CREDENTIALS_PATH):
                        creds = service_account.Credentials.from_service_account_file(
                            Config.GOOGLE_CREDENTIALS_PATH,
                            scopes=scopes
                        )
                    else:
                        # 否則使用 Application Default Credentials (ADC)
                        # 這會自動使用 Cloud Run 的服務帳戶
                        creds, project = default(scopes=scopes)
                    
                    GoogleSheetsService._service = build('sheets', 'v4', credentials=creds)
                except Exception as e:
                    raise RuntimeError(f"Failed to initialize Google Sheets service: {e}")
            return GoogleSheetsService._service
    
    @staticmethod
    def append_attendance_record(
        ident: str,
        punch_time: str,
        image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        
        try:
            service = GoogleSheetsService.get_service()
            spreadsheet_id = Config.GOOGLE_SHEETS_ID
            
            if not spreadsheet_id:
                raise ValueError("GOOGLE_SHEETS_ID is not configured")
            
            row_data = [
                GoogleSheetsService._format_timestamp(punch_time),
                ident,
                image_url or ''
            ]
            
            print(f"[ATTENDANCE] Uploading to Google Sheets: ident={ident}, time={punch_time}, url={image_url}")
            print(f"[ATTENDANCE] Row data: {row_data}")
            
            range_name = f"{Config.GOOGLE_SHEETS_ATTENDANCE_TAB}!A:C"
            body = {
                'values': [row_data]
            }
            
            result = service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            print(f"✓ Attendance record uploaded to Google Sheets: {ident} at {punch_time}")
            
            return {
                'success': True,
                'updates': result.get('updates', {}),
                'spreadsheet_id': spreadsheet_id,
                'updated_range': result.get('updates', {}).get('updatedRange')
            }
            
        except HttpError as e:
            error_msg = f"Google Sheets API error: {e}"
            print(f"✗ {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"Failed to append attendance record: {e}"
            print(f"✗ {error_msg}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': error_msg
            }
    
    @staticmethod
    def append_personnel_record(
        ident: str,
        time_zone: str
    ) -> Dict[str, Any]:
        try:
            import re
            
            print(f"[PERSONNEL] Parsing ident: '{ident}', time_zone: '{time_zone}'")
            
            # Check if it's a TEACHER or STAFF identifier
            teacher_match = re.match(r'^TEACHER\s+(.+)$', ident)
            staff_match = re.match(r'^STAFF\s+(.+)$', ident)
            
            if teacher_match:
                # Format: TEACHER {name}
                prefix = 'TEACHER'
                name = teacher_match.group(1).strip()
                row_data = [
                    prefix,
                    name,
                    '',
                    '',
                    time_zone or 'Asia/Taipei'
                ]
            elif staff_match:
                # Format: STAFF {name}
                prefix = 'STAFF'
                name = staff_match.group(1).strip()
                row_data = [
                    prefix,
                    name,
                    '',
                    '',
                    time_zone or 'Asia/Taipei'
                ]
            else:
                # Student format: {School}{Year} {FirstName} {LastName}
                # Example: NTU2025 Vincent Cheng
                match = re.match(r'^([A-Z]+)(\d{4})\s+(.+)$', ident)
                
                if match:
                    school = match.group(1)
                    year = match.group(2)
                    full_name = match.group(3).strip()
                    school_year = f"{school}{year}"
                else:
                    # Fallback if pattern doesn't match
                    school_year = ident
                    full_name = ident
                
                row_data = [
                    school_year,
                    full_name,
                    '',
                    '',
                    time_zone or 'Asia/Taipei'
                ]
            
            service = GoogleSheetsService.get_service()
            spreadsheet_id = Config.GOOGLE_SHEETS_ID
            
            if not spreadsheet_id:
                raise ValueError("GOOGLE_SHEETS_ID is not configured")
            
            print(f"[PERSONNEL] Uploading to Google Sheets: {row_data}")
            
            range_name = f"{Config.GOOGLE_SHEETS_PERSONNEL_TAB}!A:E"
            body = {
                'values': [row_data]
            }
            
            result = service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            print(f"✓ Personnel record uploaded to Google Sheets: {ident}")
            
            return {
                'success': True,
                'updates': result.get('updates', {}),
                'spreadsheet_id': spreadsheet_id,
                'updated_range': result.get('updates', {}).get('updatedRange'),
                'parsed_data': {
                    'row_data': row_data,
                    'time_zone': time_zone
                }
            }
            
        except HttpError as e:
            error_msg = f"Google Sheets API error: {e}"
            print(f"✗ {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"Failed to append personnel record: {e}"
            print(f"✗ {error_msg}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': error_msg
            }
    
    @staticmethod
    def batch_append_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            service = GoogleSheetsService.get_service()
            spreadsheet_id = Config.GOOGLE_SHEETS_ID
            
            rows = []
            for record in records:
                row = [
                    GoogleSheetsService._format_timestamp(record.get('punch_time', '')),
                    record.get('ident', ''),
                    record.get('image_url', '')
                ]
                rows.append(row)
            
            range_name = f"{Config.GOOGLE_SHEETS_ATTENDANCE_TAB}!A:C"
            body = {
                'values': rows
            }
            
            result = service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            return {
                'success': True,
                'updates': result.get('updates', {}),
                'records_added': len(rows)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Batch append failed: {e}"
            }
