import os
import threading
import time
from typing import Dict

import cv2
import numpy as np

from backend.cases import CasePaths
from backend.config import Config
from imgs_2_video import create_video_from_pngs


_LOCKS: Dict[str, threading.Lock] = {}


def _lock_for(case_id: str) -> threading.Lock:
    if case_id not in _LOCKS:
        _LOCKS[case_id] = threading.Lock()
    return _LOCKS[case_id]


def _normalize_thermal_16u_to_8u(arr16: np.ndarray, low: int = 3500, high: int = 5200) -> np.ndarray:
    """将 16 位热像素按固定窗口归一化到 0-255，便于预览显示。"""
    arr = arr16.astype(np.float32)
    arr = (arr - float(low)) * (255.0 / float(max(high - low, 1)))
    arr = np.clip(arr, 0, 255).astype("uint8")
    return arr


def start_capture_from_cameras(case_paths: CasePaths, duration_sec: int = 10) -> None:
    """
    参考给定的 C++ 示例，仅从红外摄像头采集一段短视频：

    - 只使用 16 位 Y16 热像摄像头（不再打开 RGB 摄像头）
    - 生成：
        * input*.bin：逐帧顺序保存 16 位原始数据（保持 16 位深度）
        * frames/*.png：从 16 位数据归一化得到的 8bit 预览图（仅用于前端显示）
        * preview.mp4：由预览 PNG 合成的浏览器友好 MP4，用于前端 ROI 选取

    注意：具体相机索引、分辨率、帧率通过 Config.* 环境变量可调。
    """

    def _run():
        lock = _lock_for(case_paths.case_id)
        if not lock.acquire(blocking=False):
            return
        try:
            os.makedirs(case_paths.frames_dir, exist_ok=True)

            cam2_idx = Config.CAMERA_2_INDEX
            w = Config.CAMERA_FRAME_WIDTH
            h = Config.CAMERA_FRAME_HEIGHT
            fps = Config.CAMERA_FPS
            # 仅打开红外摄像头（16 位 Y16）
            cap = cv2.VideoCapture(cam2_idx)

            if not cap.isOpened():
                print(f"[camera] 打开红外摄像头失败: {cam2_idx}")
                cap.release()
                return

            # 分辨率与帧率设置
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            cap.set(cv2.CAP_PROP_FPS, fps)

            # 设置为 16 位 Y16，不自动转换为 RGB
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc("Y", "1", "6", " "))
            cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)

            # 录制一段固定时长
            start_ts = time.time()
            frame_idx = 0

            # 将 16 位热像素顺序写入 input 文件，方便后端 raw 流程按需对接
            raw_f = open(case_paths.input_path, "wb")

            try:
                while time.time() - start_ts < duration_sec:
                    ok, frame = cap.read()
                    if not ok:
                        print("[camera] 读取红外帧失败，中止采集")
                        break

                    # 确保尺寸一致
                    if frame.shape[1] != w or frame.shape[0] != h:
                        frame = cv2.resize(frame, (w, h))

                    # 期望 frame 为单通道 16 位；若含有多通道，取第一通道
                    if frame.ndim == 3:
                        frame16 = frame[:, :, 0].astype("uint16")
                    else:
                        frame16 = frame.astype("uint16")

                    # 写入原始 16 位数据（保持 16 位深度）
                    raw_f.write(frame16.tobytes())

                    # 从 16 位数据生成 8bit 预览帧并保存为 PNG（仅用于显示）
                    gray8 = _normalize_thermal_16u_to_8u(frame16)
                    png_path = os.path.join(case_paths.frames_dir, f"{frame_idx:04d}.png")
                    cv2.imwrite(png_path, gray8)

                    frame_idx += 1
            finally:
                raw_f.close()
                cap.release()

            # 从 PNG 序列合成 preview.mp4，供前端使用
            try:
                create_video_from_pngs(case_paths.frames_dir, case_paths.preview_mp4)
            except Exception as e:
                print(f"[camera] 生成预览视频失败: {e}")
        finally:
            lock.release()

    t = threading.Thread(target=_run, daemon=True)
    t.start()

