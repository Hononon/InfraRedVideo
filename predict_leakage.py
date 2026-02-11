import os
import re
import numpy as np
import cv2
import struct
from PIL import Image
import tifffile as tiff
import matplotlib.pyplot as plt
from scipy.stats import entropy

plt.rcParams["font.family"] = ["Arial", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False


# ---------- 小工具：提取文件名中的“最后一段数字” ----------
def _extract_last_int_from_name(name: str):
    """
    从文件名（不含路径）中提取最后一段连续数字，返回 int。
    若不存在数字，返回 +inf（用于排序时把它排到最后）。
    """
    nums = re.findall(r'\d+', name)
    return int(nums[-1]) if nums else float('inf')


def load_lookup_table(file_path='./d_i_cl.npy'):
    try:
        d_i_list = np.load(file_path)
        CLs = np.arange(0, 300000, 100) * 100
        return d_i_list, CLs
    except Exception as e:
        print(f"❌ Lookup table loading failed: {e}")
        return None, None


def convert_tif_to_cl_tif(tif_path, d_i_list, CLs, save_folder):
    try:
        img_name = os.path.splitext(os.path.basename(tif_path))[0]
        img_array = tiff.imread(tif_path)
        if len(img_array.shape) > 2:
            img_array = img_array[..., 0]  # 处理多通道TIFF，取第一个通道
        img_array = img_array.astype(np.float32)
        camera_param = 30724
        delta_i_array = img_array / camera_param
         # ---------------------- 新增代码 ----------------------
        # 计算并打印当前帧 delta_I 的均值（保留4位小数，便于阅读）
        # delta_i_mean = np.mean(delta_i_array)
        # print(f"📊 帧 {img_name} - delta_I 均值: {delta_i_mean:.4f}")

        cl_array = np.interp(delta_i_array, d_i_list, CLs)
        save_path = os.path.join(save_folder, f"{img_name}_CL.tif")
        if not os.path.exists(save_folder):
            os.makedirs(save_folder, exist_ok=True)
        tiff.imwrite(save_path, cl_array.astype(np.float32))
        # print(f"✅ Saved: {save_path}")
        return save_path
    except Exception as e:
        print(f"❌ Image processing failed ({tif_path}): {e}")
        return None


def batch_process_images(tif_folder, d_i_list, CLs, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder, exist_ok=True)
    tif_files = [f for f in os.listdir(tif_folder) if f.lower().endswith(('.tif', '.tiff'))]

    # 使用“最后一段数字”稳健排序（frame_0164.tif -> 164）
    tif_files.sort(key=lambda f: (_extract_last_int_from_name(f), f))

    saved_paths = []
    for f in tif_files:
        full_path = os.path.join(tif_folder, f)
        saved_path = convert_tif_to_cl_tif(full_path, d_i_list, CLs, output_folder)
        if saved_path:
            saved_paths.append(saved_path)
    return saved_paths


def read_flo_file(filename):
    with open(filename, 'rb') as f:
        magic = struct.unpack('f', f.read(4))[0]
        if magic != 202021.25:
            raise Exception("Invalid .flo file")
        w = struct.unpack('i', f.read(4))[0]
        h = struct.unpack('i', f.read(4))[0]
        data = np.fromfile(f, np.float32, count=2 * w * h)
        flow = np.reshape(data, (h, w, 2))
    return flow


def visualize_flow(flow):
    h, w = flow.shape[:2]
    hsv = np.zeros((h, w, 3), dtype=np.uint8)
    hsv[..., 1] = 255
    mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    hsv[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
    hsv[..., 0] = ang * 180 / np.pi / 2
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    return bgr


def calculate_fragmentation(flow_or_img, is_raw_flow=True):
    if is_raw_flow:
        flow = flow_or_img
        img = visualize_flow(flow)
    else:
        img = flow_or_img
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(edges, connectivity=8)
    if num_labels <= 1:
        return 0
    component_areas = stats[1:, -1]
    max_area = np.max(component_areas)
    total_area = np.sum(component_areas)
    max_ratio = max_area / total_area if total_area > 0 else 0
    fragmentation = (num_labels - 1) * (1 - max_ratio)
    return fragmentation


def load_image_safe(image_path):
    try:
        img = tiff.imread(image_path)
        img_array = np.array(img)
        if img_array.size == 0:
            raise ValueError("Empty image data")
        return img_array
    except Exception as e:
        print(f"Error loading image {image_path}: {e}")
        return None


def compute_cl_valid_ratio(cl_path, min_cl_value=0):
    cl_img = load_image_safe(cl_path)
    if cl_img is None:
        return 0
    if cl_img.dtype != np.float32:
        cl_img = cl_img.astype(np.float32)
    valid_mask = cl_img > min_cl_value
    return np.sum(valid_mask) / valid_mask.size


def compute_flow_valid_ratio(flow_path, min_flow_magnitude=0.5):
    try:
        flow = read_flo_file(flow_path)
    except Exception as e:
        print(f"Failed to read flow: {e}")
        return 0
    mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
    valid = mag > min_flow_magnitude
    return np.sum(valid) / valid.size


def compute_iou(cl_path, flow_path, min_cl_value=0, min_flow_magnitude=0.5):
    cl = load_image_safe(cl_path)
    if cl is None:
        return 0
    try:
        flow = read_flo_file(flow_path)
    except Exception as e:
        print(f"Failed to read flow file: {e}")
        return 0
    if cl.dtype != np.float32:
        cl = cl.astype(np.float32)
    cl_valid = cl > min_cl_value
    flow_mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
    flow_valid = flow_mag > min_flow_magnitude
    inter = np.logical_and(cl_valid, flow_valid)
    union = np.logical_or(cl_valid, flow_valid)
    return np.sum(inter) / np.sum(union) if np.sum(union) > 0 else 0


def find_matching_flow_file(plume_filename, flow_dir):
    """
    通用匹配：优先用“数字帧号”精确匹配 .flo；若失败再用多模式包含匹配。
    """
    base = os.path.splitext(plume_filename)[0]          # e.g. frame_0001_CL
    base_num = _extract_last_int_from_name(base)        # -> 1 或 inf
    frame_num_str = None if base_num == float('inf') else str(base_num)

    # 1) 优先：在 .flo 文件名中提取“最后一段数字”，若与 CL 的帧号完全相等则命中
    exact_candidates = []
    for f in os.listdir(flow_dir):
        if not f.endswith('.flo'):
            continue
        f_num = _extract_last_int_from_name(f)
        if frame_num_str is not None and f_num != float('inf') and f_num == int(frame_num_str):
            exact_candidates.append(os.path.join(flow_dir, f))
    if exact_candidates:
        exact_candidates.sort()
        return exact_candidates[0]  # 保证可重复性

    # 2) 回退：多模式包含匹配（与你提供的方法一致）
    patterns = []
    if frame_num_str:
        # 注意：这里放未去前导零的数字也通常能匹配（如果你的 .flo 里保留了前导零）
        # 如果需要严格等宽匹配，可另外构造零填充的版本。
        patterns.append(frame_num_str)
    parts = base.split('_')
    patterns.extend([
        base,                               # frame_0001_CL
        parts[0] if parts else base,        # frame
        '_'.join(parts[:2]) if len(parts) >= 2 else base  # frame_0001
    ])

    for f in os.listdir(flow_dir):
        if f.endswith('.flo') and any(p in f for p in patterns if p):
            return os.path.join(flow_dir, f)

    print(f"未找到匹配的光流文件！CL文件名：{plume_filename}，尝试过的模式：{patterns}")
    return None


def compute_leakage_from_image_and_flow(plume_path, flow_path,
                                        pixel_size=0.002, frame_interval=0.04,
                                        ppm_to_kgm2=0.7142857e-6,
                                        boxes=None, min_overlap=50,
                                        min_flow_valid_ratio=0.5,
                                        min_flow_magnitude=0.5):
    plume = load_image_safe(plume_path)
    if plume is None:
        return None
    if plume.dtype != np.float32:
        plume = plume.astype(np.float32)
    rho = plume * ppm_to_kgm2
    h, w = rho.shape
    try:
        flow = read_flo_file(flow_path)
    except Exception:
        return None
    vx = flow[:, :, 0] * pixel_size / frame_interval
    vy = flow[:, :, 1] * pixel_size / frame_interval
    flux_x = rho * vx * pixel_size
    flux_y = rho * vy * pixel_size
    region_fluxes = []
    if not boxes:
        return None
    for center, half in boxes:
        cy, cx = center
        y0 = max(cy - half, 0)
        y1 = min(cy + half, h - 1)
        x0 = max(cx - half, 0)
        x1 = min(cx + half, w - 1)
        f_right = np.sum(flux_x[y0:y1, x1])
        f_left = np.sum(-flux_x[y0:y1, x0])
        f_top = np.sum(-flux_y[y0, x0:x1])
        f_bottom = np.sum(flux_y[y1, x0:x1])
        total = f_right + f_left + f_top + f_bottom
        region_fluxes.append(total)
    return np.abs(np.mean(region_fluxes)) * 3600  # kg/h


def predict_leakage(foreground_folder, flow_folder, lookup_table_path,
                    frames_per_group=3, window_size=30,
                    fragmentation_threshold=15, min_flow_magnitude=1.0,
                    min_cl_value=10, save_curve=False, pixel_size=0.002):
    """
    主函数：返回平均泄漏量 (kg/h)
    - foreground_folder: 原始前景TIFF目录
    - flow_folder: 光流 .flo 目录
    - lookup_table_path: 查找表 .npy 路径
    """
    # 与你原 main() 一致：CL 放在 foreground 的同级目录
    output_tif_folder = os.path.join(os.path.dirname(foreground_folder), "CL")

    d_i_list, CLs = load_lookup_table(lookup_table_path)
    if d_i_list is None:
        return None

    plume_files = batch_process_images(foreground_folder, d_i_list, CLs, output_tif_folder)
    if not plume_files:
        print("⚠️ 没有可用的 CL 图像。")
        return None

    # 稳健排序：按文件名最后一段数字排序（frame_0164_CL.tif -> 164）
    plume_files.sort(key=lambda p: (_extract_last_int_from_name(os.path.basename(p)),
                                    os.path.basename(p)))

    all_valid_q, cl_valid_ratios, flow_valid_ratios, iou_values = [], [], [], []
    plotted_q, plotted_time = [], []

    for frame_idx, plume_path in enumerate(plume_files):
        plume_filename = os.path.basename(plume_path)
        flow_path = find_matching_flow_file(plume_filename, flow_folder)
        if not flow_path or not os.path.exists(flow_path):
            continue

        try:
            flow = read_flo_file(flow_path)
            frag_val = calculate_fragmentation(flow, is_raw_flow=True)
            if frag_val > fragmentation_threshold:
                continue
        except Exception:
            continue

        q = compute_leakage_from_image_and_flow(
            plume_path, flow_path,
            pixel_size=pixel_size,   # 👈 这里传进去
            boxes=[((50, 45), 31), ((50, 45), 32), ((50, 45), 33)],
            min_flow_magnitude=min_flow_magnitude
        )

        cl_valid = compute_cl_valid_ratio(plume_path, min_cl_value)
        flow_valid = compute_flow_valid_ratio(flow_path, min_flow_magnitude)
        iou = compute_iou(plume_path, flow_path, min_cl_value, min_flow_magnitude)

        cl_valid_ratios.append(cl_valid)
        flow_valid_ratios.append(flow_valid)
        iou_values.append(iou)
        all_valid_q.append(q if q is not None else None)

        if frame_idx < window_size:
            continue

        if (frame_idx + 1 - window_size) % frames_per_group == 0:
            start_idx = max(0, frame_idx - window_size + 1)
            window_q = all_valid_q[start_idx:frame_idx + 1]
            window_cl = cl_valid_ratios[start_idx:frame_idx + 1]
            window_flow = flow_valid_ratios[start_idx:frame_idx + 1]
            window_iou = iou_values[start_idx:frame_idx + 1]

            avg_cl = np.mean(window_cl)
            avg_flow = np.mean(window_flow)
            avg_iou = np.mean(window_iou)
            filtered_q = [
                q_ for i_, q_ in enumerate(window_q)
                if q_ is not None and
                   window_cl[i_] >= avg_cl and
                   window_flow[i_] >= avg_flow and
                   window_iou[i_] >= avg_iou
            ]

            if filtered_q:
                avg_q = np.mean(filtered_q)
                plotted_q.append(avg_q)
                time_sec = (frame_idx + 1) * 0.04
                plotted_time.append(time_sec)

    if plotted_q and save_curve:
        plt.figure(figsize=(12, 6))
        plt.plot(plotted_time, plotted_q, 'o-', linewidth=2, markersize=6)
        plt.xlabel('Time (seconds)')
        plt.ylabel('Sliding Window Average Leakage Q (kg/h)')
        plt.title(f'Leakage vs Time Curve (Window Size = {window_size} frames)')
        plt.ylim(0, 5)
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.tight_layout()
        save_path = os.path.join(os.path.dirname(output_tif_folder), 'flow_vs_time.png')
        plt.savefig(save_path)

    return np.mean(plotted_q) if plotted_q else None