import os, time, json
import numpy as np
from PIL import Image
from imgs_2_video import create_video_from_pngs, create_video_from_pngs_264
from imgs_2_video import create_video_for_web

def _default_preview_root() -> str:
    # Default to <repo>/data/cases to match the new upload-based layout.
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, "."))
    return os.path.join(repo, "data", "cases")


# Backward compatible override:
# - old code used "/mnt/video/preview/<case_id>/..."
# - new code stores everything in "data/cases/<case_id>/..."
PREVIEW_ROOT = os.environ.get("IRV_PREVIEW_ROOT", _default_preview_root())

def _to_uint8_stack(frames):
    # 全局 min-max 拉伸，保持预览视频亮度一致
    gmin = min(float(np.min(f)) for f in frames)
    gmax = max(float(np.max(f)) for f in frames)
    denom = max(gmax - gmin, 1e-9)
    for f in frames:
        arr = ((f - gmin) / denom * 255.0).clip(0, 255).astype("uint8")
        yield arr

def make_preview_and_wait(frames, case_id, server_host="localhost", server_port=5001, poll_sec=1):
    """
    1) 生成 PNG + preview.mp4 到 /mnt/video/preview/<case_id>/
    2) 打印前端访问 URL
    3) 阻塞轮询 params.json，返回参数字典
    """
    case_id_str = str(case_id)
    case_dir = os.path.join(PREVIEW_ROOT, case_id_str)
    frames_dir = os.path.join(case_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    # 1) 存 PNG
    for i, arr in enumerate(_to_uint8_stack(frames)):
        Image.fromarray(arr).save(os.path.join(frames_dir, f"{i:04d}.png"))

    # 2) 合成预览视频
    preview_mp4 = create_video_for_web(frames_dir, os.path.join(case_dir, "preview"))

    # 新增：初始化 result.json（供后端读取状态）
    result_path = os.path.join(case_dir, "result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump({
            "case_id": case_id_str,
            "result": None,
            "processing": False,
            "progress": "等待前端提交裁剪区域和参数..."
        }, f, ensure_ascii=False, indent=2)

    # 3) 提示用户打开前端
    url = f"http://{server_host}:{server_port}/?case_id={case_id_str}"
    print(f"预览已就绪，请在浏览器打开： {url}")
    print("在页面上框选裁剪区域并填写 Tb/Tg/距离/FOV，然后点击提交。")

    # 4) 阻塞等待参数
    params_path = os.path.join(case_dir, "params.json")
    while not os.path.exists(params_path):
        time.sleep(poll_sec)
    with open(params_path, "r") as f:
        params = json.load(f)
    
    # 新增：更新 result.json 为“计算中”
    with open(result_path, "r+", encoding="utf-8") as f:
        result_data = json.load(f)
        result_data["processing"] = True
        result_data["progress"] = "参数已提交，正在执行泄漏量计算..."
        f.seek(0)
        json.dump(result_data, f, ensure_ascii=False, indent=2)
        f.truncate()

    return params

# 新增：保存泄漏量结果到 result.json
def save_leakage_result(case_id, leakage_value, process_time, error_message=None):
    case_id_str = str(case_id)
    case_dir = os.path.join(PREVIEW_ROOT, case_id_str)
    result_path = os.path.join(case_dir, "result.json")

    result_data = {
        "case_id": case_id_str,
        "process_time": process_time,
        "result": leakage_value,
        "status": "completed" if error_message is None else "failed",
        "processing": False,
        "progress": error_message or "泄漏量计算完成"
    }

    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 泄漏量结果已保存到：{result_path}")
    print(f"📊 计算结果：{leakage_value} kg/h")