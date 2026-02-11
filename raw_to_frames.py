import os
import time
import numpy as np
from PIL import Image

def decode_raw_video(file_path, frame_width=320, frame_height=256,
                     output_folder=None, save_as_tiff=True):
    """
    将RAW格式视频解码为帧序列，并可选择保存为TIFF图像。

    参数：
        file_path (str): RAW文件路径
        frame_width (int): 每帧宽度（像素）
        frame_height (int): 每帧高度（像素）
        output_folder (str): 保存路径（如果为None则不保存）
        save_as_tiff (bool): 是否保存为16位TIFF文件

    返回：
        frames (list[np.ndarray]): 每帧的14位灰度图像（numpy数组）
    """
    def read_raw_file(path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"文件 {path} 不存在")
        with open(path, 'rb') as f:
            return f.read()

    def count_frames(all_bytes):
        frame_size = frame_width * frame_height * 2
        return len(all_bytes) // frame_size

    def extract_frame_data(all_bytes, idx):
        frame_size = frame_width * frame_height * 2
        start = idx * frame_size
        return all_bytes[start:start + frame_size]

    def bytes_to_ints(frame_data):
        ints_data = []
        for i in range(0, len(frame_data), 2):
            low_byte = frame_data[i]
            high_byte = frame_data[i + 1]
            value = (high_byte << 8) | low_byte
            ints_data.append(value & 0x3FFF)  # 14位有效数据
        return np.array(ints_data, dtype=np.uint16)

    def save_tiff(data, idx):
        image_data = data.reshape((frame_height, frame_width))
        image = Image.fromarray(image_data)
        filename = f"frame_{idx+1:04d}.tiff"
        path = os.path.join(output_folder, filename)
        image.save(path, format='TIFF')
        return path

    # --- 主逻辑 ---
    all_bytes = read_raw_file(file_path)
    total_frames = count_frames(all_bytes)
    frames = []

    if output_folder and not os.path.exists(output_folder):
        os.makedirs(output_folder)

    print(f"开始解码：{total_frames} 帧")
    start_time = time.time()

    for idx in range(total_frames):
        frame_bytes = extract_frame_data(all_bytes, idx)
        ints_data = bytes_to_ints(frame_bytes)
        frames.append(ints_data.reshape((frame_height, frame_width)))

        if save_as_tiff and output_folder:
            save_tiff(ints_data, idx)

        if (idx + 1) % 10 == 0 or idx == total_frames - 1:
            progress = (idx + 1) / total_frames * 100
            elapsed = time.time() - start_time
            eta = (elapsed / (idx + 1)) * (total_frames - idx - 1)
            print(f"进度: {progress:.1f}% ({idx+1}/{total_frames}), 剩余时间: {eta:.1f}s")

    print(f"解码完成，总耗时 {time.time() - start_time:.2f} 秒")
    return frames

# 调用方式：------------------------------------------------------------------------
# # 仅提取帧，不保存
# frames = decode_raw_video("video.raw", 320, 256, save_as_tiff=False)
#
# # 解码并保存为TIFF
# frames = decode_raw_video(
#     "video.raw",
#     frame_width=320,
#     frame_height=256,
#     output_folder="output_frames",
#     save_as_tiff=True
# )