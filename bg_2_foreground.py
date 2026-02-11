import os
import cv2
import numpy as np
import tifffile
from tqdm import tqdm
import re  # 用于自然排序


def reverse_linearize_background(png_path, output_tiff_path, min_val, scale_factor):
    """将线性化的背景图 PNG 恢复为原始16位灰度图（TIFF）。"""
    # 读取8位PNG背景（线性化后的）
    img_mapped = cv2.imread(png_path, cv2.IMREAD_GRAYSCALE)
    if img_mapped is None:
        raise FileNotFoundError(f"未能读取背景图像: {png_path}")
    if img_mapped.dtype != np.uint8:
        raise TypeError(f"背景PNG应为8位灰度图，实际为{img_mapped.dtype}")
    

    # 逆线性化计算（恢复为16位）
    img_restored = img_mapped.astype(np.float32) * scale_factor + min_val
    img_restored = np.clip(img_restored, 0, 65535).astype(np.uint16)  # 16位范围限制

    # 保存为16位TIFF
    tifffile.imwrite(output_tiff_path, img_restored)
    print(f"背景图已逆线性化保存为: {output_tiff_path}")


def extract_foreground_from_linearized_sequence(
        frames_folder, background_tiff_path, output_folder
):
    """使用逆线性化后的16位TIFF背景图与帧图像序列相减，提取前景。"""
    os.makedirs(output_folder, exist_ok=True)

    # 读取16位TIFF背景图（逆线性化后的）
    try:
        background = tifffile.imread(background_tiff_path)
    except Exception as e:
        raise FileNotFoundError(f"未能读取背景TIFF图像: {background_tiff_path}，错误: {e}")

    # 校验背景图格式
    if background.ndim != 2:
        raise ValueError(f"背景图必须是单通道灰度图，实际通道数: {background.ndim}")
    if background.dtype != np.uint16:
        raise TypeError(f"背景TIFF应为16位，实际为{background.dtype}")
    bg_height, bg_width = background.shape

    # 自然排序帧文件（按文件名中的数字排序）
    frame_files = [f for f in os.listdir(frames_folder) if f.lower().endswith(('.tiff', '.tif'))]
    # 提取文件名中的数字进行排序（如"frame_10.tif"提取10）
    frame_files.sort(key=lambda x: int(re.findall(r'\d+', x)[-1]))

    for filename in tqdm(frame_files, desc="提取前景"):
        frame_path = os.path.join(frames_folder, filename)
        # 用tifffile读取16位TIFF帧
        try:
            frame = tifffile.imread(frame_path)
        except Exception as e:
            print(f"跳过错误帧 {filename}: 读取失败 - {e}")
            continue

        # 校验帧图像格式
        if frame.ndim != 2:
            print(f"跳过 {filename}: 非单通道灰度图")
            continue
        if frame.dtype != np.uint16:
            print(f"跳过 {filename}: 非16位TIFF（实际{frame.dtype}）")
            continue
        if frame.shape != (bg_height, bg_width):
            print(f"跳过 {filename}: 尺寸与背景不匹配（帧: {frame.shape}, 背景: {background.shape}）")
            continue

        # 背景相减（确保结果非负，转为16位）
        # foreground = np.maximum(frame - background, 0).astype(np.uint16)  # 替代cv2.subtract，更直观控制
        foreground = np.maximum(frame.astype(np.int32) - background.astype(np.int32), 0).astype(np.uint16)

        # 保存为16位TIFF
        output_path = os.path.join(output_folder, filename)
        tifffile.imwrite(output_path, foreground)

    print(f"前景提取完成，结果保存在: {output_folder}")


def full_foreground_pipeline(
        frames_folder,
        linear_background_png,
        output_foreground_folder,
        restored_background_tiff_path,
        min_val,
        scale_factor,
):
    """总流程：先逆线性化背景图为16位TIFF，再用该背景提取前景。"""
    # 第一步：逆线性化背景图（PNG→16位TIFF）
    reverse_linearize_background(
        png_path=linear_background_png,
        output_tiff_path=restored_background_tiff_path,
        min_val=min_val,
        scale_factor=scale_factor
    )

    # 第二步：用逆线性化后的16位TIFF背景提取前景（修正原逻辑错误）
    extract_foreground_from_linearized_sequence(
        frames_folder=frames_folder,
        background_tiff_path=restored_background_tiff_path,  # 关键修改：使用恢复后的16位背景
        output_folder=output_foreground_folder
    )


# 调用示例
# if __name__ == "__main__":
#     full_foreground_pipeline(
#         frames_folder="/Users/Exper_Chapter2/hanjie_camera/250606RAW/outdoor/Q_10/Q_10_frames_tiff_80_60_linear",
#         linear_background_png="/Users/Exper_Chapter2/hanjie_camera/250606RAW/outdoor/Q_10/background/background.png",
#         output_foreground_folder="/Users/Exper_Chapter2/hanjie_camera/250606RAW/outdoor/Q_10/foreground",
#         restored_background_tiff_path="/Users/Exper_Chapter2/hanjie_camera/250606RAW/outdoor/Q_10/background/background_restored.tiff",
#         min_val=12609,
#         scale_factor=3
#     )
