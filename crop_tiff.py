import os
import cv2
import numpy as np

def crop_frames(input_source, crop_width, crop_height,
                offset_left, offset_top,
                output_dir=None, file_ext=".tiff"):
    """
    裁剪一组帧图像，并计算全局最小值和最大值。

    参数：
        input_source (str | list[np.ndarray]):
            - 如果是字符串，则认为是输入文件夹路径
            - 如果是numpy数组列表，则直接处理这些帧
        crop_width (int): 裁剪宽度
        crop_height (int): 裁剪高度
        offset_left (int): 裁剪起始x位置
        offset_top (int): 裁剪起始y位置
        output_dir (str): 保存裁剪结果的目录（None表示不保存）
        file_ext (str): 保存文件扩展名（仅在保存时有效）

    返回：
        cropped_frames (list[np.ndarray]): 裁剪后的帧
        global_min (int): 全局最小值
        global_max (int): 全局最大值
    """
    cropped_frames = []
    global_min = float('inf')
    global_max = float('-inf')

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    if isinstance(input_source, str):
        # 从文件夹读取
        filenames = sorted(os.listdir(input_source))
        for filename in filenames:
            if filename.lower().endswith(('.tiff', '.tif')):
                img_path = os.path.join(input_source, filename)
                img = cv2.imread(img_path, cv2.IMREAD_ANYDEPTH | cv2.IMREAD_ANYCOLOR)
                if img is None:
                    print(f"无法读取图像: {filename}")
                    continue

                crop = img[offset_top:offset_top + crop_height,
                           offset_left:offset_left + crop_width]

                if crop.shape != (crop_height, crop_width):
                    print(f"图像尺寸不足，无法裁剪：{filename}")
                    continue

                # 更新全局统计
                current_min, current_max = np.min(crop), np.max(crop)
                global_min = min(global_min, current_min)
                global_max = max(global_max, current_max)

                cropped_frames.append(crop)

                if output_dir:
                    out_path = os.path.join(output_dir, filename)
                    cv2.imwrite(out_path, crop)

    elif isinstance(input_source, list):
        # 从内存帧数组读取
        for idx, img in enumerate(input_source):
            crop = img[offset_top:offset_top + crop_height,
                       offset_left:offset_left + crop_width]

            if crop.shape != (crop_height, crop_width):
                print(f"第 {idx} 帧尺寸不足，无法裁剪")
                continue

            current_min, current_max = np.min(crop), np.max(crop)
            global_min = min(global_min, current_min)
            global_max = max(global_max, current_max)

            cropped_frames.append(crop)

            if output_dir:
                filename = f"frame_{idx+1:04d}{file_ext}"
                out_path = os.path.join(output_dir, filename)
                cv2.imwrite(out_path, crop)

    else:
        raise ValueError("input_source 必须是文件夹路径或帧数组列表")

    return cropped_frames, global_min, global_max

# 调用方式：-------------------------------------------------------------------------------
# 直接处理第一步返回的帧数组
# frames = decode_raw_video("video.raw", 320, 256, save_as_tiff=False)
# cropped_frames, gmin, gmax = crop_frames(frames, 80, 60, 122, 76)
# print("全局最小值:", gmin, "全局最大值:", gmax)
# 处理已有的 TIFF 文件夹（磁盘裁剪并保存）
# cropped_frames, gmin, gmax = crop_frames(
#     input_source="Q_10_frames_tiff",
#     crop_width=80,
#     crop_height=60,
#     offset_left=122,
#     offset_top=76,
#     output_dir="Q_10_frames_tiff_cropped"
# )

