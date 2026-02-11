import os


def _abs_from_repo(rel: str) -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, ".."))
    return os.path.abspath(os.path.join(repo, rel))


class Config:
    # Where all uploaded/derived artifacts live.
    # Layout: data/cases/<case_id>/{input.*,frames/,preview.mp4,params.json,result.json,...}
    DATA_ROOT = os.environ.get("IRV_DATA_ROOT", _abs_from_repo("data"))
    CASES_ROOT = os.path.join(DATA_ROOT, "cases")
    USERS_DB_PATH = os.path.join(DATA_ROOT, "users", "users.json")

    # Flask session secret (set in environment for real deployments)
    SECRET_KEY = os.environ.get("IRV_SECRET_KEY", "dev-secret-change-me")

    # CORS (comma-separated origins), e.g. "http://localhost:5173"
    # 默认开发环境下放宽为 "*"，方便从 localhost / 127.0.0.1 / 局域网 IP 访问。
    CORS_ORIGINS = os.environ.get("IRV_CORS_ORIGINS", "*")

    # 摄像头采集相关配置（可用环境变量覆盖）
    # 默认值 59 / 61 与示例 C++ 代码保持一致，如有需要可通过
    # IRV_CAMERA_1_INDEX / IRV_CAMERA_2_INDEX 等环境变量修改。
    CAMERA_1_INDEX = int(os.environ.get("IRV_CAMERA_1_INDEX", "59"))
    CAMERA_2_INDEX = int(os.environ.get("IRV_CAMERA_2_INDEX", "61"))
    CAMERA_FRAME_WIDTH = int(os.environ.get("IRV_CAMERA_WIDTH", "640"))
    CAMERA_FRAME_HEIGHT = int(os.environ.get("IRV_CAMERA_HEIGHT", "512"))
    CAMERA_FPS = int(os.environ.get("IRV_CAMERA_FPS", "30"))

