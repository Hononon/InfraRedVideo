import os
import shutil
import numpy as np
from PIL import Image
import re


def prepare_optical_flow_input(linear_folder, output_pair_folder, invert=True):
    """
    将线性化图像反转后，生成成对图像用于光流推理

    参数：
        linear_folder (str): 原始线性化图像文件夹
        output_pair_folder (str): 输出的图像对文件夹
        invert (bool): 是否进行像素值反转（默认True）
    """

    # 确保输出文件夹存在
    os.makedirs(output_pair_folder, exist_ok=True)

    # 获取所有png图像（按名称排序）
    frames = sorted([f for f in os.listdir(linear_folder) if f.lower().endswith('.png')])
    if not frames:
        print("源文件夹中未找到PNG图像")
        return

    # 提取起始编号（从文件名提取4位数字）
    match = re.search(r'\d{4}', frames[0])
    if match:
        start_num = int(match.group())
        print(f"起始编号提取成功: {start_num}")
    else:
        start_num = 1
        print(f"起始编号提取失败，使用默认值: {start_num}")

    for i in range(len(frames) - 1):
        img1_name, img2_name = frames[i], frames[i + 1]
        img1_path = os.path.join(linear_folder, img1_name)
        img2_path = os.path.join(linear_folder, img2_name)

        # 读取图像
        img1 = Image.open(img1_path)
        img2 = Image.open(img2_path)

        # 转换为numpy数组
        img1_np = np.array(img1)
        img2_np = np.array(img2)

        # 像素反转
        if invert:
            img1_np = 255 - img1_np
            img2_np = 255 - img2_np

        # 转回PIL图像
        img1_inv = Image.fromarray(img1_np)
        img2_inv = Image.fromarray(img2_np)

        # 保存为成对命名格式
        pair_idx = start_num + i
        out_img1_path = os.path.join(output_pair_folder, f"{pair_idx:04d}_img1.png")
        out_img2_path = os.path.join(output_pair_folder, f"{pair_idx:04d}_img2.png")

        img1_inv.save(out_img1_path)
        img2_inv.save(out_img2_path)

        # print(f"已保存图像对 {pair_idx:04d}: {img1_name}, {img2_name}")

    print(f"\n图像对准备完成，共计 {len(frames) - 1} 对")

# 调用示例：
# prepare_optical_flow_input(
#     linear_folder='/你的/线性化图像路径',
#     output_pair_folder='/你的/反转配对图像输出路径',
#     invert=True  # 反转像素值
# )