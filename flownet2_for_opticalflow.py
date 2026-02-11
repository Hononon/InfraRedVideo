import os
import glob
import numpy as np
from mmflow.apis import init_model, inference_model


def save_flow_as_flo(flow, filepath):
    """保存光流为 .flo 文件"""
    TAG_STRING = np.array([202021.25], dtype=np.float32)
    height, width = flow.shape[:2]
    with open(filepath, 'wb') as f:
        TAG_STRING.tofile(f)
        np.array([width, height], dtype=np.int32).tofile(f)
        flow.astype(np.float32).tofile(f)


def run_optical_flow_inference(
    input_dir,
    flo_output_dir,
    config_file,
    checkpoint_file,
    device='cuda:0'
):
    """
    使用光流模型对图像对进行推理并保存 .flo 文件

    参数：
        input_dir (str): 包含成对输入图像的文件夹
        flo_output_dir (str): 输出 .flo 文件的目录
        config_file (str): 光流模型的 config 路径
        checkpoint_file (str): 模型权重路径
        device (str): 设备，如 'cuda:0' 或 'cpu'
    """
    # 初始化模型
    print(f"初始化光流模型：{config_file}")
    model = init_model(config_file, checkpoint_file, device=device)

    # 创建输出目录
    os.makedirs(flo_output_dir, exist_ok=True)

    # 获取图像列表
    images = sorted(glob.glob(os.path.join(input_dir, '*.png')))
    print(f"找到图像数: {len(images)}")

    if len(images) < 2:
        print("图像数量不足以成对推理")
        return

    # 按对处理图像
    for i in range(0, len(images) - 1, 2):
        img1, img2 = images[i], images[i + 1]
        print(f"正在处理图像对: {os.path.basename(img1)} 和 {os.path.basename(img2)}")

        # 推理
        result = inference_model(model, img1, img2)

        if result is None or result.size == 0:
            print(f"无效光流结果: {img1} 和 {img2}")
            continue

        # 构造输出文件名
        base_name = os.path.splitext(os.path.basename(img1))[0]
        flo_path = os.path.join(flo_output_dir, f'{base_name}.flo')

        # 保存 .flo 文件
        save_flow_as_flo(result, flo_path)
        # print(f"已保存光流: {flo_path}")

# 调用示例：
# run_optical_flow_inference(
#     input_dir='data/real_data/frames_192_144_pairs_invert',
#     flo_output_dir='infer_on_real_data/gf320_0526/out',
#     config_file='configs/flownet2/flownet2_8x1_slong_flyingchairs_384x448.py',
#     checkpoint_file='pretrain_model/flownet2_8x1_slong_flyingchairs_384x448_20220625_212801-88d61800.pth',
#     device='cuda:0'
# )