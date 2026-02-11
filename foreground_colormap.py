import os
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from scipy.ndimage import binary_dilation, gaussian_filter

from imgs_2_video import create_video_from_pngs

def generate_heatmap_and_paste_to_raw(
    input_foreground_dir,  # 第6步输出的前景文件夹（TIFF）
    user_raw_image_dir,    # 用户指定的原尺寸图像文件夹
    crop_params,           # 裁剪参数（x:左偏移, y:上偏移, width:裁剪宽, height:裁剪高）
    output_frame_dir,      # 最终替换后的帧保存文件夹
    sigma=1.5,             # 高斯模糊强度（控制热力图平滑度）
    threshold=10           # 热力图显示阈值（浓度>该值才显色）
):
    """
    直接将热力图形式的前景，贴到原尺寸图像的对应裁剪位置
    流程：前景→热力图→按裁剪参数贴到原图像→保存替换后帧
    """
    # 输入合法性检查
    for path in [input_foreground_dir, user_raw_image_dir]:
        if not os.path.exists(path):
            print(f"错误：文件夹 {path} 不存在！")
            return False
    os.makedirs(output_frame_dir, exist_ok=True)
    print(f"替换后帧将保存到：{output_frame_dir}")

    # 按文件名排序（确保帧顺序严格对应）
    foreground_files = sorted([f for f in os.listdir(input_foreground_dir) 
                              if f.lower().endswith(('.tiff', '.tif'))])
    raw_files = sorted([f for f in os.listdir(user_raw_image_dir) 
                       if f.lower().endswith(('.png', '.jpg', '.tiff', '.bmp'))])

    # 检查帧数量匹配
    if len(foreground_files) != len(raw_files):
        print(f"错误：前景帧数量（{len(foreground_files)}）与原图像数量（{len(raw_files)}）不匹配！")
        return False
    if not foreground_files:
        print("错误：前景文件夹中无有效TIFF文件！")
        return False

    # 解析裁剪参数（转为整数，确保坐标准确）
    crop_x = int(crop_params["x"])
    crop_y = int(crop_params["y"])
    crop_w = int(crop_params["width"])
    crop_h = int(crop_params["height"])
    print(f"\n热力图粘贴参数：位置({crop_x},{crop_y})，尺寸({crop_w}x{crop_h})")

    # 逐帧处理：前景→热力图→贴到原图像
    for idx, (fg_fn, raw_fn) in enumerate(zip(foreground_files, raw_files), 1):
        fg_path = os.path.join(input_foreground_dir, fg_fn)
        raw_path = os.path.join(user_raw_image_dir, raw_fn)
        print(f"处理第 {idx}/{len(foreground_files)} 帧：{raw_fn}")

        try:
            # 1. 读取前景TIFF并转为单通道数组
            with Image.open(fg_path) as fg_img:
                fg_array = np.array(fg_img)
                if len(fg_array.shape) == 3:
                    fg_array = fg_array[:, :, 0]  # 多通道转单通道（取第一通道）
                # 确保前景尺寸与裁剪尺寸一致（若不一致，按裁剪尺寸缩放）
                if fg_array.shape != (crop_h, crop_w):
                    fg_img_resized = fg_img.resize((crop_w, crop_h), Image.LANCZOS)
                    fg_array = np.array(fg_img_resized)

            # 2. 生成平滑热力图（消除像素感+渐变效果）
            # 步骤1：创建浓度阈值掩码（只显示>threshold的区域）
            mask = fg_array > threshold
            # 步骤2：膨胀操作（连接离散点，形成连续区域）
            dilated_mask = binary_dilation(mask, structure=np.ones((5, 5)))
            # 步骤3：高斯模糊（让颜色过渡自然）
            blurred_array = gaussian_filter(fg_array, sigma=sigma)
            # 步骤4：过滤无效区域（仅保留膨胀后且浓度达标的像素）
            masked_heatmap = np.where(dilated_mask & (blurred_array > threshold), blurred_array, np.nan)

            # 3. 渲染热力图为PIL图像（带透明背景）
            # 创建与裁剪尺寸匹配的画布
            fig, ax = plt.subplots(figsize=(crop_w/100, crop_h/100), dpi=100)
            ax.axis('off')  # 隐藏坐标轴
            # 渲染热力图（双线性插值确保平滑）
            valid_vals = masked_heatmap[~np.isnan(masked_heatmap)]
            if len(valid_vals) > 0:
                im = ax.imshow(
                    masked_heatmap,
                    cmap='YlOrRd',  # 黄→橙→红渐变（符合之前需求）
                    vmin=valid_vals.min(),
                    vmax=valid_vals.max(),
                    interpolation='bilinear'  # 关键：消除像素感
                )
            # 保存热力图为临时PNG（透明背景）
            temp_heatmap = os.path.join(output_frame_dir, f"temp_heatmap_{idx}.png")
            plt.subplots_adjust(left=0, right=1, top=1, bottom=0)  # 移除边距
            plt.savefig(
                temp_heatmap,
                dpi=100,
                bbox_inches='tight',
                pad_inches=0,
                transparent=True  # 背景透明，只保留热力图区域
            )
            plt.close()  # 关闭画布，释放内存

            # 4. 将热力图贴到原尺寸图像的对应裁剪位置
            # 读取原图像（转为RGBA支持透明叠加）
            raw_img = Image.open(raw_path).convert("RGBA")
            # 读取热力图（带透明通道）
            heatmap_img = Image.open(temp_heatmap).convert("RGBA")
            # 粘贴热力图到原图像的裁剪位置（透明区域不覆盖原图像）
            raw_img.paste(heatmap_img, (crop_x, crop_y), heatmap_img)

            # 5. 保存替换后的帧（转为RGB格式，兼容视频生成）
            output_fn = f"{idx:04d}.png"  # 按顺序命名，确保视频帧正确
            output_path = os.path.join(output_frame_dir, output_fn)
            raw_img.convert("RGB").save(output_path)

            # 6. 删除临时热力图文件
            os.remove(temp_heatmap)

        except Exception as e:
            print(f"处理帧 {raw_fn} 出错：{str(e)}")
            return False

    print(f"\n所有帧处理完成！替换后帧路径：{output_frame_dir}")
    return True

