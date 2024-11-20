from flask import Flask, Response, jsonify
from camera_handler import CameraHandler
#
app = Flask(__name__)
camera = CameraHandler()

@app.route('/')
def index():
    # 主页面 HTML
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Camera App</title>
        <script>
            async function requestPermissions() {
                try {
                    // 请求摄像头权限
                    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
                    console.log('摄像头权限已授予');
                    stream.getTracks().forEach(track => track.stop());
                } catch (err) {
                    console.error('摄像头权限请求失败:', err);
                    alert('请检查摄像头权限设置并刷新页面');
                }
            }
            window.onload = requestPermissions;
        </script>
    </head>
    <body>
        <h1>摄像头应用</h1>
        <div>
            <button onclick="fetch('/start_camera')">启动摄像头</button>
            <button onclick="fetch('/stop_camera')">停止摄像头</button>
        </div>
        <h2>视频流</h2>
        <img src="/video_feed" width="640" height="480">
        <h2>获取人脸 X 坐标</h2>
        <button onclick="getFaceX()">获取 X 坐标</button>
        <p id="face-x">X 坐标: 未知</p>
        <script>
            async function getFaceX() {
                const response = await fetch('/get_face_x');
                const data = await response.json();
                document.getElementById('face-x').innerText = 'X 坐标: ' + (data.x ?? '未检测到');
            }
        </script>
    </body>
    </html>
    """

@app.route('/video_feed')
def video_feed():
    return Response(camera.generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start_camera')
def start_camera():
    camera.start_camera()
    return "摄像头已启动"

@app.route('/stop_camera')
def stop_camera():
    camera.stop_camera()
    return "摄像头已停止"

@app.route('/get_face_x')
def get_face_x():
    x_coordinate = camera.get_face_x_coordinate()
    return jsonify({'x': x_coordinate})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
