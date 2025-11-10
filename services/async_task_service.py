import time
import traceback
import atexit

from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Dict, Any, Optional
from datetime import datetime
from zoneinfo import ZoneInfo

TAIPEI_TZ = ZoneInfo("Asia/Taipei")


class AsyncTaskService:
    _executor: Optional[ThreadPoolExecutor] = None
    _max_workers: int = 20
    
    _active_tasks: Dict[str, Future] = {}
    _task_results: Dict[str, Dict[str, Any]] = {}
    _task_metadata: Dict[str, Dict[str, Any]] = {}
    _max_results_history: int = 1000
    
    @staticmethod
    def initialize(max_workers: int = 20):
        if AsyncTaskService._executor is None:
            AsyncTaskService._max_workers = max_workers
            AsyncTaskService._executor = ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix='async-task-'
            )
            atexit.register(AsyncTaskService.shutdown)
    
    @staticmethod
    def shutdown(wait: bool = True):
        if AsyncTaskService._executor is not None:
            AsyncTaskService._executor.shutdown(wait=wait)
            AsyncTaskService._executor = None
    
    @staticmethod
    def submit_task(
        task_func: Callable,
        task_name: str,
        *args,
        **kwargs
    ) -> str:
        if AsyncTaskService._executor is None:
            AsyncTaskService.initialize()
        
        now = datetime.now(TAIPEI_TZ)
        task_id = f"{task_name}_{now.strftime('%Y%m%d_%H%M%S_%f')}"
        created_at = now.isoformat()
        
        AsyncTaskService._task_metadata[task_id] = {
            "task_id": task_id,
            "name": task_name,
            "status": "pending",
            "created_at": created_at,
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None
        }
        
        def task_wrapper():
            start_time = time.time()
            started_at = datetime.now(TAIPEI_TZ).isoformat()
            
            if task_id in AsyncTaskService._task_metadata:
                AsyncTaskService._task_metadata[task_id]["status"] = "running"
                AsyncTaskService._task_metadata[task_id]["started_at"] = started_at
            
            result = {
                "task_id": task_id,
                "task_name": task_name,
                "status": "running",
                "start_time": started_at,
                "end_time": None,
                "duration_ms": None,
                "success": False,
                "result": None,
                "error": None
            }
            
            try:
                task_result = task_func(*args, **kwargs)
                
                result["status"] = "completed"
                result["success"] = True
                result["result"] = task_result
                
            except Exception as e:
                result["status"] = "failed"
                result["success"] = False
                result["error"] = str(e)
                result["traceback"] = traceback.format_exc()
                
            finally:
                end_time = time.time()
                completed_at = datetime.now(TAIPEI_TZ).isoformat()
                result["end_time"] = completed_at
                result["duration_ms"] = int((end_time - start_time) * 1000)
                
                if task_id in AsyncTaskService._task_metadata:
                    AsyncTaskService._task_metadata[task_id]["status"] = result["status"]
                    AsyncTaskService._task_metadata[task_id]["completed_at"] = completed_at
                    AsyncTaskService._task_metadata[task_id]["result"] = result.get("result")
                    AsyncTaskService._task_metadata[task_id]["error"] = result.get("error")
                
                AsyncTaskService._store_result(task_id, result)
                
                if task_id in AsyncTaskService._active_tasks:
                    del AsyncTaskService._active_tasks[task_id]
            
            return result
        
        future = AsyncTaskService._executor.submit(task_wrapper)
        AsyncTaskService._active_tasks[task_id] = future
        
        return task_id
    
    @staticmethod
    def _store_result(task_id: str, result: Dict[str, Any]):
        AsyncTaskService._task_results[task_id] = result
        
        if len(AsyncTaskService._task_results) > AsyncTaskService._max_results_history:
            to_remove = len(AsyncTaskService._task_results) - AsyncTaskService._max_results_history
            oldest_keys = sorted(AsyncTaskService._task_results.keys())[:to_remove]
            for key in oldest_keys:
                del AsyncTaskService._task_results[key]
    
    @staticmethod
    def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
        if task_id in AsyncTaskService._task_metadata:
            metadata = AsyncTaskService._task_metadata[task_id]
            
            if task_id in AsyncTaskService._active_tasks:
                future = AsyncTaskService._active_tasks[task_id]
                if not future.done():
                    return metadata
            
            if task_id in AsyncTaskService._task_results:
                return AsyncTaskService._task_results[task_id]
            
            return metadata
        
        return AsyncTaskService._task_results.get(task_id)
    
    @staticmethod
    def get_stats() -> Dict[str, Any]:
        total_tasks = len(AsyncTaskService._task_results)
        pending_tasks = sum(1 for m in AsyncTaskService._task_metadata.values() if m.get("status") == "pending")
        running_tasks = sum(1 for m in AsyncTaskService._task_metadata.values() if m.get("status") == "running")
        
        completed = sum(1 for r in AsyncTaskService._task_results.values() if r.get("status") == "completed")
        failed = sum(1 for r in AsyncTaskService._task_results.values() if r.get("status") == "failed")
        
        durations = [r.get("duration_ms", 0) for r in AsyncTaskService._task_results.values() if r.get("duration_ms")]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        active_workers = 0
        if AsyncTaskService._executor:
            active_workers = len(AsyncTaskService._active_tasks)
        
        return {
            "total_tasks": total_tasks,
            "pending_tasks": pending_tasks,
            "running_tasks": running_tasks,
            "active_tasks": active_workers,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "success_rate": f"{(completed / total_tasks * 100):.1f}%" if total_tasks > 0 else "N/A",
            "average_duration_ms": int(avg_duration),
            "max_workers": AsyncTaskService._max_workers,
            "active_workers": active_workers,
            "executor_status": "active" if AsyncTaskService._executor else "shutdown"
        }

def with_retry(max_retries: int = 3, initial_delay: float = 1.0, backoff_factor: float = 2.0):
    def decorator(func):
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        raise last_exception
            raise last_exception
        return wrapper
    return decorator
