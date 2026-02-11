import os
import numpy as np
import tifffile as tiff

def calculate_tiff_mean(folder_path):
    """
    遍历文件夹中的所有TIFF文件，计算并打印每张图片的均值
    
    参数:
        folder_path: 包含TIFF文件的文件夹路径
    """
    # 检查文件夹是否存在
    if not os.path.exists(folder_path):
        print(f"错误: 文件夹 '{folder_path}' 不存在")
        return
    
    # 获取文件夹中所有TIFF文件
    tiff_files = []
    for filename in os.listdir(folder_path):
        # 检查文件扩展名
        if filename.lower().endswith(('.tif', '.tiff')):
            tiff_files.append(os.path.join(folder_path, filename))
    
    if not tiff_files:
        print(f"在文件夹 '{folder_path}' 中未找到TIFF文件")
        return
    
    # 按文件名排序
    tiff_files.sort()
    
    print(f"找到 {len(tiff_files)} 个TIFF文件，开始计算均值...\n")
    
    # 遍历并处理每个TIFF文件
    for file_path in tiff_files:
        try:
            # 读取TIFF文件
            img = tiff.imread(file_path)
            
            # 提取文件名（不含路径）
            filename = os.path.basename(file_path)
            
            # 处理多通道图像（计算所有通道的均值）
            if len(img.shape) == 3:
                # 对每个通道计算均值，再求所有通道的平均
                channel_means = [np.mean(channel) for channel in img]
                overall_mean = np.mean(channel_means)
                print(f"文件: {filename}")
                print(f"  通道数: {img.shape[0]}")
                print(f"  各通道均值: {[f'{m:.6f}' for m in channel_means]}")
                print(f"  整体均值: {overall_mean:.6f}\n")
            else:
                # 单通道图像直接计算均值
                mean_value = np.mean(img)
                print(f"文件: {filename}")
                print(f"  尺寸: {img.shape}")
                print(f"  均值: {mean_value:.6f}\n")
                
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {str(e)}\n")

if __name__ == "__main__":
    # 示例：替换为你的文件夹路径
    target_folder = "/mnt/video/2025-06-06-11-47-03.raw_foreground"  # 可以修改为实际的文件夹路径
    
    # 如果需要手动输入文件夹路径，可以使用下面这行代码
    # target_folder = input("请输入包含TIFF文件的文件夹路径: ")
    
    calculate_tiff_mean(target_folder)
    