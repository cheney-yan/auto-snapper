from flask import Flask, render_template, Response, make_response
from camera import VideoCamera
from time import sleep
from config import config
app = Flask(__name__, template_folder='.')

camera = VideoCamera(config)


@app.route('/')
def index():
  return render_template('index.html')


def gen(camera):
  while True:
    frame = camera.get_last_saved_frame()
    sleep(camera.sleep_time)
    yield (b'--frame\r\n'
           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')


def debug_gen(camera):
  while True:
    frame = camera.get_latest_debug_frame()
    sleep(camera.sleep_time)
    yield (b'--frame\r\n'
           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')


@app.route('/video_feed')
def video_feed():
  return Response(gen(camera),
                  mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/debug_feed')
def debug_feed():
  return Response(debug_gen(camera),
                  mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/static')
def static_file():
  response = make_response(camera.get_latest_full_frame())
  response.headers.set('Content-Type', 'image/jpeg')
  response.headers.set(
    'Content-Disposition', 'attachment', filename='static.jpg')
  return response


if __name__ == '__main__':
  app.run(host='0.0.0.0', debug=config.get('debug'), port=config.get('port', 8080))
