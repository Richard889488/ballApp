import flet as ft
import cv2
import numpy as np
import base64
import threading
import time
import socket
import json

# Flet 应用的主函数
def main(page: ft.Page):
    page.title = "Ball Face Detection App"

    # 用于存储摄像头帧的全局变量
    global latest_frame_base64
    latest_frame_base64 = None

    # 定义一个 WebSocket，用于在前端和后端之间传输数据
    class WSHandler(ft.Control):
        def __init__(self):
            super().__init__()
            self.create_ref()

        def build(self):
            return ft.RawControl(
                html="""
                <script>
                    let ws = new WebSocket("ws://localhost:8000/ws");
                    ws.onopen = function() {
                        console.log("WebSocket 连接已建立");
                    };
                    ws.onmessage = function(event) {
                        let data = JSON.parse(event.data);
                        if (data.type === "command") {
                            if (data.command === "request_permissions") {
                                requestPermissions();
                            }
                        }
                    };
                    async function requestPermissions() {
                        try {
                            // 请求摄像头权限
                            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
                            const video = document.createElement('video');
                            video.srcObject = stream;
                            video.play();

                            // 将视频帧发送给后端
                            const canvas = document.createElement('canvas');
                            const context = canvas.getContext('2d');
                            setInterval(() => {
                                canvas.width = video.videoWidth;
                                canvas.height = video.videoHeight;
                                context.drawImage(video, 0, 0, canvas.width, canvas.height);
                                let frameData = canvas.toDataURL('image/jpeg', 0.5);
                                ws.send(JSON.stringify({ type: 'frame', data: frameData }));
                            }, 100);

                            // 请求蓝牙权限并连接设备
                            const device = await navigator.bluetooth.requestDevice({ acceptAllDevices: true });
                            const server = await device.gatt.connect();
                            console.log('已连接到蓝牙设备：', device.name);
                            ws.send(JSON.stringify({ type: 'bluetooth', data: 'connected' }));
                        } catch (err) {
                            console.error(err);
                        }
                    }
                </script>
                """,
                css='',
                scripts=[],
            )

    ws_handler = WSHandler()

    # 显示摄像头图像的控件
    image_view = ft.Image(width=640, height=480)

    # 处理从前端接收到的数据
    def handle_websocket():
        import asyncio
        import websockets

        async def handler(websocket, path):
            async for message in websocket:
                data = json.loads(message)
                if data['type'] == 'frame':
                    # 处理接收到的图像帧
                    frame_data = data['data'].split(',')[1]
                    frame_bytes = base64.b64decode(frame_data)
                    nparr = np.frombuffer(frame_bytes, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                    # 在这里可以使用 OpenCV 对帧进行处理，例如人脸检测
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml") \
                        .detectMultiScale(gray, 1.3, 5)
                    for (x, y, w, h) in faces:
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

                    # 将处理后的帧转换为 base64 编码
                    _, buffer = cv2.imencode('.jpg', frame)
                    frame_base64 = base64.b64encode(buffer).decode('utf-8')

                    # 更新图像控件
                    def update_image():
                        image_view.src_base64 = frame_base64
                        page.update()

                    page.invoke_method(update_image)

                elif data['type'] == 'bluetooth':
                    # 处理蓝牙连接状态
                    print('蓝牙设备已连接')

        start_server = websockets.serve(handler, 'localhost', 8000)
        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()

    # 启动 WebSocket 服务器的线程
    threading.Thread(target=handle_websocket, daemon=True).start()

    # 定义一个按钮，用于请求权限
    def request_permissions(e):
        # 通过 WebSocket 向前端发送请求
        page.eval_js("ws.send(JSON.stringify({ type: 'command', command: 'request_permissions' }))")

    request_button = ft.ElevatedButton("请求权限", on_click=request_permissions)

    # 添加控件到页面
    page.add(
        request_button,
        image_view,
        ws_handler,
    )

if __name__ == "__main__":
    # 启动 Flet 应用，指定运行模式为 Web 浏览器
    ft.app(target=main, view=ft.WEB_BROWSER)
