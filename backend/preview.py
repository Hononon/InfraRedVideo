import os
import threading
from typing import Dict

import numpy as np
from PIL import Image

from imgs_2_video import create_video_for_web
from raw_to_frames import decode_raw_video


_LOCKS: Dict[str, threading.Lock] = {}


def _lock_for(case_id: str) -> threading.Lock:
    if case_id not in _LOCKS:
        _LOCKS[case_id] = threading.Lock()
    return _LOCKS[case_id]


def _to_uint8_stack(frames):
    gmin = min(float(np.min(f)) for f in frames)
    gmax = max(float(np.max(f)) for f in frames)
    denom = max(gmax - gmin, 1e-9)
    for f in frames:
        arr = ((f - gmin) / denom * 255.0).clip(0, 255).astype("uint8")
        yield arr


def _save_preview_frames_png(frames, frames_dir: str) -> None:
    os.makedirs(frames_dir, exist_ok=True)
    for i, arr in enumerate(_to_uint8_stack(frames)):
        Image.fromarray(arr).save(os.path.join(frames_dir, f"{i:04d}.png"))


def start_generate_preview_from_raw(case_id: str, raw_path: str, frames_dir: str, preview_base: str) -> None:
    """
    Generate:
    - <frames_dir>/*.png  (uint8 stretched)
    - <preview_base>.mp4  (25fps, browser-friendly)
    """

    def _run():
        lock = _lock_for(case_id)
        if not lock.acquire(blocking=False):
            return
        try:
            frames = decode_raw_video(raw_path, frame_width=320, frame_height=256, save_as_tiff=False)
            if len(frames) >= 100:
                frames = frames[100:]
            _save_preview_frames_png(frames, frames_dir)
            create_video_for_web(frames_dir=frames_dir, out_base=preview_base)
        finally:
            lock.release()

    t = threading.Thread(target=_run, daemon=True)
    t.start()

