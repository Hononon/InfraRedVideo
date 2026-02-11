from flask import Flask, request, jsonify, render_template_string
import os, json
import time

def _default_static_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, "."))
    return os.path.join(repo, "data", "cases")


STATIC_ROOT = os.environ.get("IRV_PREVIEW_ROOT", _default_static_root())
app = Flask(__name__, static_folder=STATIC_ROOT, static_url_path="/static")

# 存储计算结果的临时变量（实际应用中可能需要用数据库）
# results = {}

INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>预览与参数填写</title>
<style>
  body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;padding:16px;background:#0b0f14;color:#e6edf3}
  .wrap{max-width:1080px;margin:0 auto}
  .row{display:flex;gap:16px;flex-wrap:wrap}
  .card{background:#11161d;padding:16px;border-radius:16px;box-shadow:0 2px 12px rgba(0,0,0,.35);flex:1;display:flex;flex-direction:column;align-items:center;}
  .player{position:relative;display:inline-block;margin:auto 0;}
  video{display:block;max-width:100%;height:auto;border-radius:12px}
  canvas{position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:auto}
  label{display:block;margin:8px 0 4px;font-size:14px;color:#9fb3c8}
  input{width:100%;max-width:380px;padding:10px;border-radius:10px;border:1px solid #243241;background:#0b0f14;color:#e6edf3}
  button{padding:10px 16px;border:0;border-radius:12px;background:#2b6cb0;color:#fff;font-weight:600;cursor:pointer}
  .btns{display:flex;gap:12px;margin-top:12px}
  .muted{color:#75879a;font-size:13px}
  .pill{display:inline-block;padding:4px 10px;background:#13202e;border-radius:999px;color:#9ecbff;font-size:12px}
  .result-card {
    margin-top: 20px;
    text-align: center;
    height: 180px;
    justify-content: center;
  }
  .result-value {
    font-size: 32px;
    font-weight: bold;
    margin: 15px 0;
    color: #4ade80;
  }
  .loading {
    color: #9fb3c8;
    font-style: italic;
  }
</style>
</head>
<body>
  <div class="wrap">
    <h2>预览与参数填写 <span class="pill">先播放视频，在上面拖拽矩形</span></h2>
    <p class="muted">提示：URL 需要带 <code>?case_id=...</code>；视频来自 <code>/static/&lt;case_id&gt;/preview.mp4</code>。</p>

    <div class="row">
      <div class="card" style="min-width:320px">
        <div class="player">
          <video id="vid" controls autoplay loop>
            您的浏览器不支持视频播放。
          </video>
          <canvas id="overlay"></canvas>
        </div>
        <div class="btns">
          <button id="clear">清除矩形</button>
        </div>
        <p class="muted" id="rectInfo">未选择裁剪区域</p>
      </div>

      <div class="card" style="max-width:420px">
        <h3>参数</h3>
        <!-- 移除 Tb（背景温度）和 Tg（环境温度）输入框 -->
        <label>距离（distance，m）</label><input id="distance" type="number" step="0.01" placeholder="如 10" />
        <label>视场角（FOV，度）</label><input id="fov" type="number" step="0.01" placeholder="如 45" />
        <div class="btns">
          <button id="submit">提交参数并继续</button>
        </div>
        <p class="muted" id="msg"></p>
      </div>
    </div>

    <!-- 新增泄漏量估计结果展示区域 -->
    <div class="row">
      <div class="card result-card" style="width: 100%;">
        <h3>泄漏量估计结果</h3>
        <div id="resultContainer">
          <div class="loading">等待参数提交后计算...</div>
        </div>
        <p class="muted">单位：kg/h（千克/小时）</p>
      </div>
    </div>
  </div>

<script>
(function(){
  const qs = new URLSearchParams(location.search);
  const caseId = qs.get("case_id");
  const vid = document.getElementById("vid");
  const canvas = document.getElementById("overlay");
  const ctx = canvas.getContext("2d");
  const rectInfo = document.getElementById("rectInfo");
  const msg = document.getElementById("msg");
  const btnClear = document.getElementById("clear");
  const btnSubmit = document.getElementById("submit");
  // 移除 Tb 和 Tg 元素引用
  const distance = document.getElementById("distance");
  const fov = document.getElementById("fov");
  const resultContainer = document.getElementById("resultContainer");
  
  // 轮询计时器
  let pollTimer = null;

  // 视频切换相关变量
  let newVideoExists = false;       // 标记新视频是否已生成
  let videoSwitchPollTimer = null;  // 视频状态轮询计时器
  const OLD_VIDEO_URL = `/static/${caseId}/preview.mp4`;  // 旧视频URL
  let NEW_VIDEO_URL = "";           // 新视频URL（从后端接口获取）

  if(!caseId){
    msg.textContent = "URL 缺少 ?case_id=... 参数。";
    btnSubmit.disabled = true;
    return;
  }

  vid.src = `/static/${caseId}/preview.mp4`;

  let start=null, rect=null, drawing=false;

  function resizeCanvas(){
    const w = vid.videoWidth, h = vid.videoHeight;
    if(!w || !h) return;
    canvas.width = w; 
    canvas.height = h;
    draw();
  }

  function toCanvasXY(e){
    const r = canvas.getBoundingClientRect();
    const scaleX = canvas.width / r.width;
    const scaleY = canvas.height / r.height;
    return {
      x: (e.clientX - r.left) * scaleX,
      y: (e.clientY - r.top) * scaleY
    };
  }

  function draw(){
    ctx.clearRect(0,0,canvas.width,canvas.height);
    if(rect){
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#9ecbff";
      ctx.setLineDash([6,3]);
      ctx.strokeRect(rect.x, rect.y, rect.w, rect.h);
    }
    rectInfo.textContent = rect ? 
      `裁剪: x=${Math.round(rect.x)}, y=${Math.round(rect.y)}, w=${Math.round(rect.w)}, h=${Math.round(rect.h)}` 
      : "未选择裁剪区域";
  }

  canvas.addEventListener("mousedown", e => {
    canvas.style.pointerEvents = "auto"; // 开始绘制，接管鼠标
    drawing = true;
    start = toCanvasXY(e);
    rect = {x:start.x, y:start.y, w:0, h:0};
    draw();
  });

  canvas.addEventListener("mousemove", e => {
    if(!drawing) return;
    const p = toCanvasXY(e);
    rect.w = p.x - start.x;
    rect.h = p.y - start.y;
    const nx = rect.w<0 ? rect.x+rect.w : rect.x;
    const ny = rect.h<0 ? rect.y+rect.h : rect.y;
    const nw = Math.abs(rect.w);
    const nh = Math.abs(rect.h);
    rect = {x:nx, y:ny, w:nw, h:nh};
    draw();
  });

  window.addEventListener("mouseup", () => {
    drawing = false;
    canvas.style.pointerEvents = "none"; // 绘制结束，事件透传给视频
  });

  btnClear.addEventListener("click", ()=>{
    rect = null; draw();
  });

  vid.addEventListener("loadedmetadata", resizeCanvas);
  window.addEventListener("resize", resizeCanvas);

  // 轮询函数：检查后端是否计算完成
  function pollResult() {
    fetch(`/api/result/${caseId}`)
      .then(response => response.json())
      .then(data => {
        if (data.ok && data.result !== null) {
          // 显示结果
          resultContainer.innerHTML = `<div class="result-value">${data.result.toFixed(2)}</div>`;
          clearInterval(pollTimer);
        } else if (data.processing) {
          // 仍在处理中
          resultContainer.innerHTML = `<div class="loading">计算中...(${data.progress || '请等待'})</div>`;
        }
      })
      .catch(error => {
        console.error("获取结果失败:", error);
      });
  }

  // 轮询检测新视频是否生成
  function pollNewVideoStatus() {
      fetch(`/api/check_new_video/${caseId}`)
          .then(response => response.json())
          .then(data => {
              if (data.ok && data.new_video_exists && !newVideoExists) {
                  // 新视频已生成且未切换过：执行切换逻辑
                  newVideoExists = true;
                  NEW_VIDEO_URL = data.new_video_url;
                  switchToNewVideo();
                  // 停止轮询（已切换，无需继续检测）
                  clearInterval(videoSwitchPollTimer);
              }
          })
          .catch(error => {
              console.error("检测新视频状态失败:", error);
          });
  }

  // 切换到新视频（raw_final_visualization_video.mp4）
  function switchToNewVideo() {
      // 1. 记录旧视频的播放状态（是否在播放）
      const wasPlaying = !vid.paused;
      // 2. 停止旧视频播放，切换源
      vid.pause();
      vid.src = NEW_VIDEO_URL;
      // 3. 新视频加载完成后，恢复播放状态并保持虚线框
      vid.addEventListener("loadeddata", () => {
          if (wasPlaying) {
              vid.play();
          }
          // 重绘虚线框（确保切换视频后框选不消失）
          draw();
          // 提示用户视频已更新（可选）
          msg.textContent = "已切换到最终可视化视频（raw_final_visualization_video.mp4）";
      }, { once: true }); // once: true 确保事件只执行一次
      // 4. 监听新视频加载失败（可选）
      vid.addEventListener("error", () => {
          msg.textContent = "新视频 raw_final_visualization_video.mp4 加载失败，请检查文件。";
      }, { once: true });
  }

  btnSubmit.addEventListener("click", async ()=>{
    msg.textContent = "";
    if(!rect){ msg.textContent = "请先在视频上框选裁剪范围。"; return; }
    // 移除 Tb 和 Tg 的必填校验
    if(!distance.value || !fov.value){
      msg.textContent = "请填写 距离/FOV。"; return;
    }
    const payload = {
      crop: {
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        w: Math.round(rect.w),
        h: Math.round(rect.h)
      },
      // 移除 Tb 和 Tg 字段
      distance: parseFloat(distance.value),
      fov: parseFloat(fov.value)
    };
    try{
      const res = await fetch(`/api/submit/${caseId}`, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify(payload)
      });
      const j = await res.json();
      if(!res.ok || j.ok===false){
        msg.textContent = "提交失败：" + (j.msg || res.statusText);
      }else{
        msg.textContent = "提交成功！正在计算泄漏量...";
        // 开始轮询结果，每2秒一次
        resultContainer.innerHTML = '<div class="loading">开始计算...</div>';
        pollTimer = setInterval(pollResult, 2000);
        // 立即执行一次
        pollResult();
      }
    }catch(err){
      msg.textContent = "网络错误：" + (err && err.message);
    }
  });

  // 启动新视频状态轮询（每2秒检测一次，可根据需求调整间隔）
  videoSwitchPollTimer = setInterval(pollNewVideoStatus, 2000);
  // 立即执行一次检测（避免等待2秒才开始首次检测）
  pollNewVideoStatus();
})();
</script>
</body>
</html>
"""

@app.get("/")
def index():
    return render_template_string(INDEX_HTML)

@app.post("/api/submit/<case_id>")
def submit(case_id: str):
    try:
        # 1. 接收前端提交的参数（仅保留 crop、distance、fov）
        data = request.get_json(force=True)
        case_dir = os.path.join(STATIC_ROOT, case_id)
        os.makedirs(case_dir, exist_ok=True)
        
        # 2. 保存参数到 params.json（不再包含 Tb 和 Tg 字段）
        params_path = os.path.join(case_dir, "params.json")
        with open(params_path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # 3. 初始化 result.json（标记为“计算中”，主程序会更新这个文件）
        result_path = os.path.join(case_dir, "result.json")
        with open(result_path, "w") as f:
            json.dump({
                "case_id": case_id,
                "result": None,          # 泄漏量（初始为 None）
                "processing": True,      # 计算状态：True=正在算，False=算完了
                "progress": "参数已提交，主程序正在计算泄漏量..."  # 进度提示
            }, f, ensure_ascii=False, indent=2)
        
        # 4. 返回成功响应给前端
        return jsonify({
            "ok": True,
            "msg": "参数提交成功！主程序正在计算泄漏量，请稍候..."
        })
    except Exception as e:
        return jsonify({"ok": False, "msg": f"参数提交失败：{str(e)}"}), 400

@app.get("/api/result/<case_id>")
def get_result(case_id: str):
    """从 result.json 读取泄漏量结果（主程序计算后会更新这个文件）"""
    case_dir = os.path.join(STATIC_ROOT, case_id)
    result_path = os.path.join(case_dir, "result.json")
    
    # 情况1：result.json 还没生成（主程序还没开始计算）
    if not os.path.exists(result_path):
        return jsonify({
            "ok": True,
            "result": None,
            "processing": True,
            "progress": "主程序尚未开始计算，请等待..."
        })
    
    # 情况2：读取 result.json 中的真实结果
    with open(result_path, "r") as f:
        result_data = json.load(f)
    
    # 返回结果给前端（前端轮询时会拿到这些数据）
    return jsonify({
        "ok": True,
        "result": result_data["result"],       # 泄漏量（主程序计算后会填充）
        "processing": result_data["processing"], # 计算状态
        "progress": result_data["progress"]    # 进度提示
    })

@app.get("/api/check_new_video/<case_id>")
def check_new_video(case_id: str):
    """检查 raw_final_visualization_video.mp4 是否已生成"""
    case_dir = os.path.join(STATIC_ROOT, case_id)
    # 新视频的路径（与 preview.mp4 同目录）
    new_video_path = os.path.join(case_dir, "raw_final_visualization_video.mp4")
    
    # 检查文件是否存在且大小大于0（避免检测到未生成完成的空文件）
    video_exists = False
    if os.path.exists(new_video_path):
        # 获取文件大小（单位：字节），大于 1KB 视为生成完成
        if os.path.getsize(new_video_path) > 1024:
            video_exists = True
    
    return jsonify({
        "ok": True,
        "new_video_exists": video_exists,  # 布尔值：True=已生成，False=未生成
        "new_video_url": f"/static/{case_id}/raw_final_visualization_video.mp4"  # 新视频URL（提前返回，方便切换）
    })

if __name__ == "__main__":
    os.makedirs(STATIC_ROOT, exist_ok=True)
    app.run(host="0.0.0.0", port=5001, debug=False)
