from flask import Flask, Response, render_template_string
import cv2
import threading
import platform
import os
import numpy as np
import base64

# 建立 Flask 應用
app = Flask(__name__)
capture = None
is_running = False

# 轉換影像為 base64 格式
def to_base64(image):
    _, buffer = cv2.imencode('.png', image)
    base64_image = base64.b64encode(buffer).decode('utf-8')
    return base64_image

# 影像流生成器
def generate_frames():
    global capture, is_running
    while is_running and capture.isOpened():
        success, frame = capture.read()
        if not success:
            continue

        # 灰階轉換與人臉檢測
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml").detectMultiScale(gray, 1.3, 5)
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

        # 將影像編碼為 JPEG 格式
        _, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()

        # 使用 multipart/x-mixed-replace 來提供影像流
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

# 設定路由來提供影像流
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# 根路由，用於返回包含 JavaScript 的 HTML 頁面
@app.route('/')
def index():
    # HTML 頁面，包含請求攝像頭和藍牙權限的 JavaScript
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-Hant">
    <head>
        <meta charset="UTF-8">
        <title>請求硬件權限</title>
    </head>
    <body>
        <h1>請允許應用使用您的攝像頭和藍牙</h1>
        <script>
            // 請求攝像頭權限
            navigator.mediaDevices.getUserMedia({ video: true })
                .then(function(stream) {
                    console.log("攝像頭已經授權");
                })
                .catch(function(err) {
                    alert("請允許使用攝像頭權限：" + err.message);
                });

            // 請求藍牙權限
            navigator.bluetooth.requestDevice({ acceptAllDevices: true })
                .then(device => {
                    console.log("藍牙設備已選擇：" + device.name);
                })
                .catch(error => {
                    alert("請允許使用藍牙權限：" + error.message);
                });
        </script>
    </body>
    </html>
    """
    return render_template_string(html_content)

# 啟動 Flask 伺服器的執行緒
def run_flask(port):
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# 開始攝影機
def start_camera(port):
    global capture, is_running
    if capture is None or not capture.isOpened():
        # 根據作業系統設定攝影機
        num = 0 if platform.system() == 'Windows' else 2 if platform.system() == 'Linux' and 'ANDROID_ARGUMENT' in os.environ else 0
        capture = cv2.VideoCapture(num)

    if not capture.isOpened():
        print("無法啟動攝影機")
        return

    is_running = True
    threading.Thread(target=run_flask, args=(port,), daemon=True).start()

# 停止攝影機
def stop_camera():
    global is_running, capture
    if is_running:
        is_running = False
        if capture:
            capture.release()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    start_camera(port)
