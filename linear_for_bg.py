import os
import numpy as np
import tifffile
import cv2
from tqdm import tqdm
import math


def linearize_frames(input_dir, output_dir, min_val, max_val):
    """
    将裁剪后的16位TIFF图像线性映射到0-255，并保存为PNG。
    自动选择合适的整数倍数进行缩放，以最大化对比度。

    参数：
        input_dir (str): 输入裁剪后TIFF图像的文件夹
        output_dir (str): 输出PNG文件夹
        min_val (int): 全局最小值
        max_val (int): 全局最大值

    返回：
        scale_factor (int): 线性映射时除以的整数倍数（用于逆线性化）
    """
    os.makedirs(output_dir, exist_ok=True)

    # 自动计算整数倍数
    value_range = max_val - min_val
    scale_factor = math.ceil(value_range / 255)  # 向上取整，保证不溢出

    # 新增：打印线性化参数
    print(f"📉 线性化参数：")
    print(f"  - 全局最小值Gmin: {min_val}")
    print(f"  - 全局最大值Gmax: {max_val}")
    print(f"  - 数值范围: {value_range}")
    print(f"  - 缩放因子scale_factor: {scale_factor}")

    print(f"自动选择的倍数: {scale_factor} (范围 {value_range} / 255 ≈ {value_range / 255:.2f})")

    # 遍历文件
    for filename in tqdm(os.listdir(input_dir)):
        if filename.lower().endswith(('.tif', '.tiff')):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, os.path.splitext(filename)[0] + '.png')

            img = tifffile.imread(input_path)

            # 映射到0-255
            img_mapped = (img - min_val) / scale_factor
            img_mapped = np.clip(img_mapped, 0, 255).astype(np.uint8)

            cv2.imwrite(output_path, img_mapped)

    print("✅ 全部完成！PNG图像已保存到：", output_dir)
    return scale_factor

# 调用示例：-------------------------------------------------------------------------------
# scale = linearize_frames(
#     input_dir="Q_10_frames_tiff_80_60",
#     output_dir="Q_10_frames_tiff_80_60_linear",
#     min_val=12609,
#     max_val=13297
# )
#
# print("映射时使用的倍数:", scale)
