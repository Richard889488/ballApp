import cv2
import time

class CameraHandler:
    def __init__(self):
        self.capture = None
        self.is_running = False
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    def start_camera(self):
        if self.is_running:
            print("摄像头已经启动")
            return

        self.capture = cv2.VideoCapture(0)  # 默认使用索引 0，您可以通过 find_camera_index() 自动检测
        if not self.capture.isOpened():
            print("无法打开摄像头")
            return

        self.is_running = True
        print("摄像头已启动")

    def stop_camera(self):
        if not self.is_running:
            print("摄像头已经停止")
            return

        self.is_running = False
        if self.capture:
            self.capture.release()
            self.capture = None
            print("摄像头已停止")

    def generate_frames(self):
        while self.is_running:
            if not self.capture or not self.capture.isOpened():
                print("摄像头未启动或已释放")
                time.sleep(0.1)
                continue

            success, frame = self.capture.read()
            if not success:
                print("无法读取摄像头帧")
                self.stop_camera()
                break

            # 人脸检测
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

            _, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    def get_face_x_coordinate(self):
        if not self.is_running or not self.capture:
            print("摄像头未启动，无法获取 X 坐标")
            return None

        success, frame = self.capture.read()
        if not success:
            print("无法读取摄像头帧")
            return None

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
        if len(faces) > 0:
            x, _, _, _ = faces[0]  # 获取第一个人脸的 X 坐标
            return x
        return None
