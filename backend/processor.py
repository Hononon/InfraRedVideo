import threading
from datetime import datetime
from typing import Dict

from backend.cases import CasePaths, write_json

# Reuse your existing pipeline for RAW as much as possible
from infra_red_video_for_local_test import _predict_leakage_with_params
from backend.cases import read_json


_LOCKS: Dict[str, threading.Lock] = {}


def _lock_for(case_id: str) -> threading.Lock:
    if case_id not in _LOCKS:
        _LOCKS[case_id] = threading.Lock()
    return _LOCKS[case_id]


def start_raw_processing(case_paths: CasePaths) -> None:
    """
    Fire-and-forget processing thread:
    - reads user params.json (written by API)
    - runs RAW pipeline
    - writes result.json + final video under case_dir
    """

    def _run():
        lock = _lock_for(case_paths.case_id)
        if not lock.acquire(blocking=False):
            return
        try:
            # Mark as processing
            write_json(
                case_paths.result_json,
                {
                    "case_id": case_paths.case_id,
                    "processing": True,
                    "status": "running",
                    "result": None,
                    "progress": "正在执行泄漏量计算...",
                    "process_time": None,
                },
            )

            params = read_json(case_paths.params_json) or {}
            res = _predict_leakage_with_params(
                rawFilePath=case_paths.input_path,
                user_raw_image_dir=case_paths.frames_dir,
                params=params,
                case_id=case_paths.case_id,
                output_case_dir=case_paths.case_dir,
            )

            write_json(
                case_paths.result_json,
                {
                    "case_id": case_paths.case_id,
                    "processing": False,
                    "status": "completed",
                    "result": float(res.get("value") or 0.0),
                    "progress": "泄漏量计算完成",
                    "process_time": res.get("dateTime") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                },
            )
        except Exception as e:
            write_json(
                case_paths.result_json,
                {
                    "case_id": case_paths.case_id,
                    "processing": False,
                    "status": "failed",
                    "result": None,
                    "progress": f"计算失败: {e}",
                    "process_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                },
            )
        finally:
            lock.release()

    t = threading.Thread(target=_run, daemon=True)
    t.start()

