import os
import math
from datetime import datetime
from planck import inverse_planck
# from ui_bridge import make_preview_and_wait
from ui_bridge import make_preview_and_wait, save_leakage_result  # 新增 save_leakage_result

from bg_2_foreground import full_foreground_pipeline
from bg_reconstruction import run_background_model
from crop_tiff import crop_frames
from flownet2_for_opticalflow import run_optical_flow_inference
from hitran import generate_d_i_cl
from imgs_2_video import create_video_for_web, create_video_from_pngs
from invert_and_pairs import prepare_optical_flow_input
from linear_for_bg import linearize_frames
from predict_leakage import predict_leakage
from raw_to_frames import decode_raw_video
from foreground_colormap import generate_heatmap_and_paste_to_raw


def _predict_leakage_with_params(rawFilePath, user_raw_image_dir, params, case_id=1, output_case_dir=None):
    """
    优化后流程：
    1. 原有泄漏量预测逻辑不变（裁剪、线性化、前景提取等）
    2. 新增：直接将热力图前景贴到原尺寸图像→生成25fps视频
    参数：
        rawFilePath: 输入RAW文件路径（原有）
        user_raw_image_dir: 用户指定的原尺寸图像文件夹（新增）
        case_id: 可以是数字或字符串（用于标记一次检测）
    """
    # 旧流程里 case_id 是 int，新 Web 流程中是 UUID 字符串，这里统一转成字符串即可
    inspection_id = str(case_id)

    # 1. 解析RAW文件（原有）
    frames = decode_raw_video(
        rawFilePath,
        frame_width=320,
        frame_height=256,
        save_as_tiff=False
    )
    # 去掉前100帧（原有）
    if len(frames) >= 100:
        frames = frames[100:]
    else:
        frames = []
        print("警告：视频总帧数不足100帧，已清空帧列表")
        return {
            "dateTime": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "value": "0",
            "video_path": "无",
            "processed_frames_dir": "无"
        }

    # 2. 获取前端参数（由外部传入）
    crop = params["crop"]
    # Tb = float(params["Tb"])
    # Tg = float(params["Tg"])
    distance_val = float(params["distance"]) 
    fov_val = float(params["fov"])

    # 3. 裁剪参数处理（宽高向上取整为偶数，原有）
    crop_width = float(crop["w"])
    crop_height = float(crop["h"])
    # 宽高转偶数（确保后续处理兼容）
    width_ceil = math.ceil(crop_width)
    width_even = width_ceil if width_ceil % 2 == 0 else width_ceil + 1
    height_ceil = math.ceil(crop_height)
    height_even = height_ceil if height_ceil % 2 == 0 else height_ceil + 1
    print(f"🔄 裁剪参数优化：原始({crop_width},{crop_height}) → 偶数({width_even},{height_even})")

    # 4. 裁剪帧（原有，用于后续前景提取）
    cropped_frames, gmin, gmax = crop_frames(
        frames,
        width_even,
        height_even,
        crop["x"],
        crop["y"],
        output_dir=f"{rawFilePath}_frames_tiff_cropped"
    )
    print("全局最小值:", gmin, "全局最大值:", gmax)

    # --------------------------
    # 背景温度 Tb / 环境温度 Tg 处理逻辑：
    # - 如果前端提供 Tb / Tg（单位 K），则优先使用用户输入的精确值
    # - 否则，回退到当前的粗略拟合算法
    # --------------------------
    Tb_param = params.get("Tb")
    Tg_param = params.get("Tg")

    if Tb_param is not None and Tb_param != "":
        Tb = float(Tb_param)
    else:
        Tb = inverse_planck(3.25 * 0.000001, (gmax - 8175.31) / 0.01875)

    if Tg_param is not None and Tg_param != "":
        Tg = float(Tg_param)
    else:
        Tg = inverse_planck(3.25 * 0.000001, (gmin - 8175.31) / 0.01875)

    print("背景温度 Tb(K):", Tb, "环境温度 Tg(K):", Tg)

    # 5. 线性化（原有，用于背景建模和光流）
    scale = linearize_frames(
        input_dir=f"{rawFilePath}_frames_tiff_cropped",
        output_dir=f"{rawFilePath}_frames_tiff_cropped_linearized",
        min_val=gmin,
        max_val=gmax
    )

    # 6. 背景建模（仅用于前景提取，不参与后续叠加，原有）
    linear_video_path = f"{rawFilePath}_linearized_video.mp4"
    create_video_from_pngs(f"{rawFilePath}_frames_tiff_cropped_linearized", linear_video_path)
    background_path = f"{rawFilePath}_background_ori.png"
    run_background_model(
        linear_video_path,
        background_path,
        binary_path="/media/ecust/新加卷/qyx/qyx/bgs_method/background_model"
    )

    # 7. 前景提取（核心输入，原有）
    foreground_dir = f"{rawFilePath}_foreground"
    full_foreground_pipeline(
        frames_folder=f"{rawFilePath}_frames_tiff_cropped",
        linear_background_png=background_path,
        output_foreground_folder=foreground_dir,
        restored_background_tiff_path=f"{rawFilePath}_background.tiff",
        min_val=gmin,
        scale_factor=scale
    )

    # --------------------------
    # 新增核心步骤：热力图贴到原图像+生成视频
    # --------------------------
    # 整理裁剪参数（传给热力图粘贴函数）
    crop_params = {
        "x": crop["x"],
        "y": crop["y"],
        "width": width_even,
        "height": height_even
    }
    # 替换后帧的保存文件夹
    processed_frame_dir = f"{rawFilePath}_processed_frames_with_heatmap"
    # 1. 生成热力图并贴到原图像
    paste_success = generate_heatmap_and_paste_to_raw(
        input_foreground_dir=foreground_dir,
        user_raw_image_dir=user_raw_image_dir,
        crop_params=crop_params,
        output_frame_dir=processed_frame_dir,
        sigma=1.5,  # 可调整：值越大热力图越平滑
        threshold=10  # 可调整：值越大仅显示高浓度区域
    )

    # 2. 生成25fps视频（用于浏览器展示）
    # 构建新的视频保存目录，包含case_id变量
    if output_case_dir is None:
        output_case_dir = os.path.dirname(os.path.abspath(rawFilePath))
    os.makedirs(output_case_dir, exist_ok=True)
    # 构建完整的视频路径（不带 .mp4 后缀，create_video_for_web 会加）
    final_video_path = os.path.join(output_case_dir, "raw_final_visualization_video")

    if paste_success:
        video_success = create_video_for_web(
            frames_dir=processed_frame_dir,
            out_base=final_video_path
        )
        video_result = final_video_path if video_success else "视频生成失败"
    else:
        video_result = "热力图粘贴失败，无法生成视频"
        processed_frame_dir = "无"

    # --------------------------
    # 原有后续步骤（光流、查找表、泄漏量预测，保持不变）
    # --------------------------
    prepare_optical_flow_input(
        linear_folder=f"{rawFilePath}_frames_tiff_cropped_linearized",
        output_pair_folder=f"{rawFilePath}_frames_tiff_cropped_linearized_invert_pairs",
        invert=True
    )
    run_optical_flow_inference(
        input_dir=f"{rawFilePath}_frames_tiff_cropped_linearized_invert_pairs",
        flo_output_dir=f"{rawFilePath}_infer_flo",
        config_file='/media/ecust/新加卷/qyx/qyx/mmflow/configs/flownet2/flownet2_8x1_slong_flyingchairs_384x448.py',
        checkpoint_file='/media/ecust/新加卷/qyx/qyx/mmflow/work_dirs/my_flownet2_8x1_slong_flyingchairs_384x448/latest.pth',
        device='cuda:0'
    )
    # 生成查找表
    ch4_coef_path = "/media/ecust/新加卷/qyx/qyx/hanjie_demo/hanjie_demo/InfraRedVideo/CH4_nu_coef.npy"
    lookup_table_path = f"{rawFilePath}_d_i_cl.npy"
    CLs, d_i_list = generate_d_i_cl(Tb, Tg, ch4_coef_path, lookup_table_path)
    # 泄漏量预测
    fov_val = math.radians(fov_val)
    pixel_size = 2 * distance_val * math.tan(fov_val / 2) / 320
    print("换算像素尺寸:", pixel_size)
    leakage_value = predict_leakage(
        foreground_folder=foreground_dir,
        flow_folder=f"{rawFilePath}_infer_flo",
        lookup_table_path=lookup_table_path, 
        pixel_size=pixel_size
    )

    # --------------------------
    # 结果输出（包含视频和处理后帧路径）
    # --------------------------
    process_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    leakage_value_str = f"{leakage_value:.4f}" if leakage_value is not None else "0"
    # 保存泄漏量结果
    save_leakage_result(
        case_id=inspection_id,
        leakage_value=leakage_value,
        process_time=process_time
    )

    return {
        "dateTime": process_time,
        "value": leakage_value_str
    }


def test_predict_leakage(rawFilePath, user_raw_image_dir):
    """
    兼容旧入口：仍然通过 ui_server 页面框选/填参并阻塞等待 params.json。
    新的上传式 Web API 不会走这个函数，而是直接传入 params 并指定输出目录。
    """
    inspection_id = 1
    frames = decode_raw_video(
        rawFilePath,
        frame_width=320,
        frame_height=256,
        save_as_tiff=False
    )
    if len(frames) >= 100:
        frames = frames[100:]
    else:
        frames = []
        print("警告：视频总帧数不足100帧，已清空帧列表")
        return {
            "dateTime": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "value": "0",
            "video_path": "无",
            "processed_frames_dir": "无"
        }

    params = make_preview_and_wait(
        frames=frames,
        case_id=inspection_id,
        server_host="58.246.12.34",
        server_port=5001
    )
    return _predict_leakage_with_params(
        rawFilePath=rawFilePath,
        user_raw_image_dir=user_raw_image_dir,
        params=params,
        case_id=inspection_id,
        output_case_dir=f"{rawFilePath}_case_output"
    )


# --------------------------
# 主函数调用（需用户指定原始图像文件夹）
# --------------------------
if __name__ == "__main__":
    # 1. 原有RAW文件路径
    raw_path = "/mnt/video/2025-06-06-11-47-03.raw"  
    # 2. 用户指定的原始图像文件夹（需确保与前景帧数量相等）
    user_raw_image_dir = "/mnt/video/preview/1/frames"  # 替换为你的原始图像文件夹路径

    # 执行完整流程
    result = test_predict_leakage(raw_path, user_raw_image_dir)
    # 打印结果
    print("\n" + "="*50)
    print("处理完成！结果汇总：")
    print(f"处理时间：{result['dateTime']}")
    print(f"泄漏量：{result['value']}")
    print("="*50)