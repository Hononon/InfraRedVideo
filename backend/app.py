import os
from functools import wraps
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, session, send_file

from backend.config import Config
from backend.users import create_user, verify_user
from backend.cases import new_case_id, get_case_paths, ensure_case_dirs, write_json, read_json
from backend.processor import start_raw_processing
from backend.preview import start_generate_preview_from_raw
from backend.camera_capture import start_capture_from_cameras
from imgs_2_video import create_video_from_pngs


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = Config.SECRET_KEY

    os.makedirs(Config.CASES_ROOT, exist_ok=True)
    os.makedirs(os.path.dirname(Config.USERS_DB_PATH), exist_ok=True)

    allowed_origins = [o.strip() for o in (Config.CORS_ORIGINS or "").split(",") if o.strip()]

    @app.after_request
    def _add_cors_headers(resp):
        origin = request.headers.get("Origin")
        if origin and (origin in allowed_origins or "*" in allowed_origins):
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Credentials"] = "true"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
            resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
        return resp

    @app.route("/api/<path:_any>", methods=["OPTIONS"])
    def _cors_preflight(_any: str):
        return jsonify({"ok": True})

    def require_login(fn):
        @wraps(fn)
        def _wrap(*args, **kwargs):
            if not session.get("user"):
                return jsonify({"ok": False, "msg": "未登录"}), 401
            return fn(*args, **kwargs)

        return _wrap

    @app.post("/api/auth/register")
    def api_register():
        data = request.get_json(force=True, silent=False) or {}
        try:
            u = create_user(Config.USERS_DB_PATH, data.get("username", ""), data.get("password", ""))
            session["user"] = u.username
            return jsonify({"ok": True, "user": {"username": u.username}})
        except Exception as e:
            return jsonify({"ok": False, "msg": str(e)}), 400

    @app.post("/api/auth/login")
    def api_login():
        data = request.get_json(force=True, silent=False) or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        if not verify_user(Config.USERS_DB_PATH, username, password):
            return jsonify({"ok": False, "msg": "用户名或密码错误"}), 400
        session["user"] = username
        return jsonify({"ok": True, "user": {"username": username}})

    @app.post("/api/auth/logout")
    def api_logout():
        session.pop("user", None)
        return jsonify({"ok": True})

    @app.get("/api/auth/me")
    def api_me():
        u = session.get("user")
        return jsonify({"ok": True, "user": {"username": u} if u else None})

    @app.post("/api/cases")
    @require_login
    def api_create_case():
        """
        Create a new case by uploading:
        - type=raw with file (.raw)
        - type=mp4 with file (.mp4)        [预览已接通，计算仍按 raw 流程]
        - type=folder with file (.zip)     [预览已接通，计算仍按 raw 流程]
        - type=camera                      [采集一段短视频并生成预览，计算仍按 raw 流程]
        """
        case_type = (request.form.get("type") or "").strip().lower()
        f = request.files.get("file")
        if case_type not in {"raw", "mp4", "folder", "camera"}:
            return jsonify({"ok": False, "msg": "type 必须是 raw/mp4/folder/camera"}), 400
        if case_type != "camera" and not f:
            return jsonify({"ok": False, "msg": "缺少上传文件 file"}), 400

        case_id = new_case_id()
        created_at = datetime.now().isoformat(timespec="seconds")
        if case_type == "raw":
            p = get_case_paths(Config.CASES_ROOT, case_id, input_ext=".raw")
        elif case_type == "mp4":
            p = get_case_paths(Config.CASES_ROOT, case_id, input_ext=".mp4")
        else:
            p = get_case_paths(Config.CASES_ROOT, case_id, input_ext=".bin")

        ensure_case_dirs(p)

        write_json(
            os.path.join(p.case_dir, "meta.json"),
            {"case_id": case_id, "type": case_type, "owner": session.get("user"), "created_at": created_at},
        )

        if case_type == "camera":
            # 摄像头采集：后端启动独立线程，从双目摄像头抓取一小段数据，
            # 生成 frames/*.png + preview.mp4，并将 16 位热像数据写入 input*.bin，
            # 以便后续和 raw 流程对齐使用。
            start_capture_from_cameras(p)
        else:
            # Save uploaded file
            f.save(p.input_path)

            # Generate preview for frontend ROI selection.
            if case_type == "raw":
                start_generate_preview_from_raw(
                    case_id=case_id,
                    raw_path=p.input_path,
                    frames_dir=p.frames_dir,
                    preview_base=os.path.join(p.case_dir, "preview"),
                )
            elif case_type == "mp4":
                # 对 mp4 上传，直接将原始 mp4 作为 preview.mp4
                try:
                    import shutil

                    shutil.copyfile(p.input_path, p.preview_mp4)
                except Exception:
                    pass
            elif case_type == "folder":
                # 对 zip 文件夹上传，解压出帧图像并合成为 preview.mp4
                try:
                    import zipfile

                    with zipfile.ZipFile(p.input_path, "r") as zf:
                        zf.extractall(p.frames_dir)
                    create_video_from_pngs(p.frames_dir, p.preview_mp4)
                except Exception as e:
                    print(f"[folder] 解压或生成预览失败: {e}")

        write_json(
            p.result_json,
            {
                "case_id": case_id,
                "processing": False,
                "status": "created",
                "result": None,
                "progress": "已上传，等待框选区域与参数提交",
                "process_time": None,
            },
        )

        return jsonify(
            {
                "ok": True,
                "case_id": case_id,
                "case_type": case_type,
                "created_at": created_at,
                "preview_url": f"/api/cases/{case_id}/preview.mp4",
            }
        )

    @app.get("/api/cases/<case_id>")
    @require_login
    def api_case_info(case_id: str):
        case_dir = os.path.join(Config.CASES_ROOT, case_id)
        meta = read_json(os.path.join(case_dir, "meta.json")) or {}
        preview_path = os.path.join(case_dir, "preview.mp4")
        preview_exists = os.path.exists(preview_path) and os.path.getsize(preview_path) > 1024
        return jsonify(
            {
                "ok": True,
                "case_id": case_id,
                "meta": meta,
                "preview_exists": preview_exists,
                "preview_url": f"/api/cases/{case_id}/preview.mp4" if preview_exists else None,
            }
        )

    @app.post("/api/cases/<case_id>/params")
    @require_login
    def api_submit_params(case_id: str):
        data = request.get_json(force=True, silent=False) or {}
        # basic validation
        crop = data.get("crop") or {}
        if not all(k in crop for k in ("x", "y", "w", "h")):
            return jsonify({"ok": False, "msg": "缺少 crop 参数"}), 400
        if data.get("distance") is None or data.get("fov") is None:
            return jsonify({"ok": False, "msg": "缺少 distance/fov 参数"}), 400

        # Determine case type by meta
        meta = read_json(os.path.join(Config.CASES_ROOT, case_id, "meta.json")) or {}
        case_type = meta.get("type")
        if case_type != "raw":
            return jsonify({"ok": False, "msg": "目前仅 raw 流程已接通（mp4/folder/camera 后续接入）"}), 501

        p = get_case_paths(Config.CASES_ROOT, case_id, input_ext=".raw")
        if not os.path.exists(p.input_path):
            return jsonify({"ok": False, "msg": "case input 文件不存在"}), 404

        # Save params.json (so processing thread can read it via your existing bridge logic if needed)
        write_json(p.params_json, data)

        # Start background processing (RAW pipeline)
        start_raw_processing(p)

        return jsonify({"ok": True})

    @app.get("/api/cases/<case_id>/result")
    @require_login
    def api_case_result(case_id: str):
        result = read_json(os.path.join(Config.CASES_ROOT, case_id, "result.json"))
        if not result:
            return jsonify({"ok": True, "processing": True, "status": "pending", "result": None, "progress": "等待中"})
        # If final video exists, provide URL for frontend
        final_path = os.path.join(Config.CASES_ROOT, case_id, "raw_final_visualization_video.mp4")
        final_exists = os.path.exists(final_path) and os.path.getsize(final_path) > 1024
        return jsonify(
            {
                "ok": True,
                **result,
                "final_video_exists": final_exists,
                "final_video_url": f"/api/cases/{case_id}/raw_final_visualization_video.mp4" if final_exists else None,
            }
        )

    @app.get("/api/cases/<case_id>/<path:relpath>")
    @require_login
    def api_case_file(case_id: str, relpath: str):
        # restrict to case directory
        case_dir = os.path.abspath(os.path.join(Config.CASES_ROOT, case_id))
        path = os.path.abspath(os.path.join(case_dir, relpath))
        if not path.startswith(case_dir + os.sep):
            return jsonify({"ok": False, "msg": "非法路径"}), 400
        if not os.path.exists(path):
            return jsonify({"ok": False, "msg": "文件不存在"}), 404
        return send_file(path, conditional=True)

    @app.get("/api/user/history")
    @require_login
    def api_user_history():
        """
        返回当前用户的历史检测记录和过去一周的使用统计：
        - recent_usage: 最近 7 天每天创建的 case 数量
        - cases: 该用户所有 case 的列表（按创建时间倒序）
        """
        user = session.get("user")
        items = []

        if os.path.exists(Config.CASES_ROOT):
            for case_id in os.listdir(Config.CASES_ROOT):
                case_dir = os.path.join(Config.CASES_ROOT, case_id)
                if not os.path.isdir(case_dir):
                    continue
                meta = read_json(os.path.join(case_dir, "meta.json")) or {}
                if meta.get("owner") != user:
                    continue
                created_at = meta.get("created_at")
                res = read_json(os.path.join(case_dir, "result.json")) or {}
                value = res.get("result")
                try:
                    value_f = float(value) if value is not None else None
                except Exception:
                    value_f = None
                items.append(
                    {
                        "case_id": case_id,
                        "created_at": created_at,
                        "result": value_f,
                    }
                )

        # 按创建时间倒序
        def _parse_dt(s):
            if not s:
                return datetime.min
            try:
                return datetime.fromisoformat(s)
            except Exception:
                return datetime.min

        items.sort(key=lambda x: _parse_dt(x.get("created_at")), reverse=True)

        # 最近 7 天使用统计
        today = datetime.now().date()
        recent_usage = []
        for i in range(6, -1, -1):  # 从 6 天前到今天
            day = today - timedelta(days=i)
            cnt = 0
            for it in items:
                dt_str = it.get("created_at")
                if not dt_str:
                    continue
                try:
                    dt = datetime.fromisoformat(dt_str)
                except Exception:
                    continue
                if dt.date() == day:
                    cnt += 1
            recent_usage.append({"date": day.isoformat(), "count": cnt})

        return jsonify({"ok": True, "username": user, "recent_usage": recent_usage, "cases": items})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5001, debug=True)

