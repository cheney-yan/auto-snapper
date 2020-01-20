from flask import Flask, render_template, Response, make_response
from camera import VideoCamera
from time import sleep
app = Flask(__name__, template_folder='.')
config = {
  # 'source': '/opt/awscam/out/ch2_out.mjpeg'
  'source': 0,
  'port': 9080,
  'debug' : True, 
  'scale_percent': 30,
  'sleep_time':0.5
}
camera=VideoCamera(config)
@app.route('/')
def index():
    return render_template('index.html')

def gen(camera):
    while True:
        frame = camera.get_latest_motion_frame()
        sleep(camera.sleep_time)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen(camera),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/static') 
def static_file():
    response = make_response(camera.get_latest_full_frame())
    response.headers.set('Content-Type', 'image/jpeg')
    response.headers.set(
        'Content-Disposition', 'attachment', filename='static.jpg')
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=config.get('debug'), port=config.get('port', 9080))
