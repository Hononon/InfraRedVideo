import os
import cv2
from natsort import natsorted
import subprocess


def create_video_from_pngs(image_folder, output_file):
    """
    将指定文件夹中的PNG图片按顺序合成MP4视频

    参数:
    image_folder (str): 包含PNG图片的文件夹路径
    output_file (str): 输出视频文件路径
    """

    # 获取所有PNG文件并按自然顺序排序
    images = [img for img in os.listdir(image_folder) 
          if any(img.lower().endswith(ext) for ext in [".png", ".jpg"])]
    if not images:
        print(f"错误: 在 {image_folder} 中未找到PNG图片")
        return

    images = natsorted(images)

    # 读取第一张图片确定尺寸
    first_img_path = os.path.join(image_folder, images[0])
    frame = cv2.imread(first_img_path)
    if frame is None:
        print(f"错误: 无法读取图片 {first_img_path}")
        return

    height, width = frame.shape[:2]
    print(f"视频尺寸: {width}x{height}，帧率: 25fps")

    # 定义编码器和创建VideoWriter对象
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video = cv2.VideoWriter(output_file, fourcc, 25, (width, height))

    # 写入每帧
    for image in images:
        img_path = os.path.join(image_folder, image)
        frame = cv2.imread(img_path)
        if frame is None:
            print(f"警告: 无法读取图片 {image}，已跳过")
            continue
        video.write(frame)

    video.release()
    print(f"视频已成功保存为: {output_file}")

    # 示例路径
    # IMAGE_FOLDER = "/your/path/to/frames"
    # OUTPUT_FILE = "/your/path/to/output_video.mp4"
    #
    # create_video_from_pngs(IMAGE_FOLDER, OUTPUT_FILE)

def create_video_from_pngs_264(frames_dir, output_path, fps=25):
    """从 PNG 序列生成 mp4，自动选择可用编码器"""
    encoder = detect_available_encoder()
    print(f"[INFO] 使用编码器: {encoder}")

    cmd = [
        "ffmpeg",
        "-y",
        "-framerate", str(fps),
        "-i", os.path.join(frames_dir, "%04d.png"),
        "-c:v", encoder,
        "-pix_fmt", "yuv420p",   # 浏览器友好
    ]

    # 如果是 mpeg4，可以调节画质参数
    if encoder == "mpeg4":
        cmd.extend(["-q:v", "5"])

    cmd.append(output_path)

    subprocess.run(cmd, check=True)

def detect_available_encoder():
    """检测 ffmpeg 可用的编码器，按优先级返回名字"""
    candidates = ["libx264", "mpeg4", "libopenh264"]
    for enc in candidates:
        try:
            # ffmpeg -hide_banner -encoders 会列出支持的编码器
            result = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True, text=True, check=True
            )
            if enc in result.stdout:
                return enc
        except Exception:
            pass
    raise RuntimeError("没有可用的视频编码器，请检查 ffmpeg 安装！")


def create_video_for_web(frames_dir, out_base):
    # 1. 关键：替换为你手动执行时的 FFmpeg 路径（从 which ffmpeg 得到的结果）
    FFMPEG_PATH = "/usr/bin/ffmpeg"  # 替换成你的输出！比如 which ffmpeg 得到的 /usr/bin/ffmpeg
    
    input_pattern = os.path.join(frames_dir, "%04d.png")
    out_mp4 = f"{out_base}.mp4"

    # 2. 用和手动完全一致的命令（保留 -preset、-crf，因为全局 FFmpeg 支持）
    cmd = [
        FFMPEG_PATH,  # 用指定路径的 FFmpeg，而非默认的 Anaconda 版本
        "-y",
        "-framerate", "25",
        "-i", input_pattern,
        "-c:v", "libx264",
        "-preset", "medium",  # 现在支持了，因为用的是全局 FFmpeg
        "-crf", "23",         # 现在支持了，和手动命令完全一致
        "-pix_fmt", "yuv420p",
        out_mp4
    ]

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"[OK] 代码生成视频成功：{out_mp4}")

        # 3. 验证生成的视频是否和手动的一致（关键检查）
        verify_cmd = [
            FFMPEG_PATH,  # 同样用全局 FFmpeg 验证
            "-i", out_mp4,
            "-hide_banner"
        ]
        verify_result = subprocess.run(verify_cmd, capture_output=True, text=True)
        print(f"[视频信息] {verify_result.stderr}")  # 打印视频编码信息，确认是 h264

        return out_mp4

    except subprocess.CalledProcessError as e:
        print(f"[错误] 命令：{' '.join(cmd)}")
        print(f"[FFmpeg 输出] {e.stderr}")
        raise