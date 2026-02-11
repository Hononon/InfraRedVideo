import subprocess
import os

def run_background_model(input_video_path, output_image_path, binary_path="./background_model"):
    """
    调用 C++ 背景建模程序，输入视频并输出背景图像。

    参数:
    input_video_path (str): 输入视频的路径
    output_image_path (str): 背景图像保存的路径
    binary_path (str): 编译后的 C++ 可执行文件路径（默认是当前目录下的 ./background_model）

    返回:
    str: 背景图像的实际保存路径
    """
    if not os.path.exists(binary_path):
        raise FileNotFoundError(f"找不到 C++ 可执行文件：{binary_path}")

    if not os.path.exists(input_video_path):
        raise FileNotFoundError(f"输入视频不存在：{input_video_path}")

    # 调用命令行执行 C++ 程序
    result = subprocess.run(
        [binary_path, input_video_path, output_image_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # 定义一个安全解码函数，尝试多种编码并处理错误
    def safe_decode(byte_data):
        try:
            return byte_data.decode('utf-8')
        except UnicodeDecodeError:
            try:
                return byte_data.decode('gbk')  # 尝试GBK编码（常见于中文环境）
            except UnicodeDecodeError:
                return byte_data.decode('latin-1')  # 最后尝试latin-1（不会报错）

    # 检查是否成功执行
    if result.returncode != 0:
        print("C++ 程序执行失败！错误信息：")
        print(safe_decode(result.stderr))  # 使用安全解码
        raise RuntimeError("背景建模程序出错")

    print("背景建模程序执行成功：")
    print(safe_decode(result.stdout))  # 使用安全解码

    # 确认输出文件存在
    if os.path.exists(output_image_path):
        return output_image_path
    else:
        raise FileNotFoundError(f"未找到生成的背景图像文件：{output_image_path}")
