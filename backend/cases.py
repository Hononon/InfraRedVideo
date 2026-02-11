import json
import os
import uuid
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass(frozen=True)
class CasePaths:
    case_id: str
    case_dir: str
    input_path: str
    frames_dir: str
    preview_mp4: str
    params_json: str
    result_json: str
    final_mp4: str


def new_case_id() -> str:
    return uuid.uuid4().hex


def get_case_paths(cases_root: str, case_id: str, input_ext: str) -> CasePaths:
    case_dir = os.path.join(cases_root, case_id)
    return CasePaths(
        case_id=case_id,
        case_dir=case_dir,
        input_path=os.path.join(case_dir, f"input{input_ext}"),
        frames_dir=os.path.join(case_dir, "frames"),
        preview_mp4=os.path.join(case_dir, "preview.mp4"),
        params_json=os.path.join(case_dir, "params.json"),
        result_json=os.path.join(case_dir, "result.json"),
        final_mp4=os.path.join(case_dir, "raw_final_visualization_video.mp4"),
    )


def ensure_case_dirs(p: CasePaths) -> None:
    os.makedirs(p.case_dir, exist_ok=True)
    os.makedirs(p.frames_dir, exist_ok=True)


def write_json(path: str, data: Dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def read_json(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

