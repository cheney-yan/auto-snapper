import cv2
from simplelog import get_logger
import threading
import logging
from time import sleep


def resize(original, camera, last_image=None):
    width = int(original.shape[1] * camera.scale_percent / 100)
    height = int(original.shape[0] * camera.scale_percent / 100)
    dim = (width, height)
    view = cv2.resize(original, dim, interpolation=cv2.INTER_AREA)
    return view

def greyify(original, camera, last_image):
    return cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)

def get_max_change(original, camera, last_image):
    return None # todo: here


class VideoCamera(object):
    def __init__(self, config):
        self.scale_percent = config.get('scale_percent', 25)
        self.video = cv2.VideoCapture(config.get('source', 0))
        # Queue item is a a dict:
        # (original, view, grey, max_diff_size)
        self.buffer = []
        self.log = get_logger('VideoCamera')
        self.log.setLevel(logging.DEBUG)
        self.start_daemon()
        self.queue_size = config.get('queue_size', 10)
        self.sleep_time = config.get('sleep_time', 1)
        self.plugins = {
            'view': resize,
            'grey': greyify,
            'max_diff_size': get_max_change,
        }

    def __del__(self):
        self.video.release()

    def start_daemon(self):
        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True
        thread.start()

    def run(self):
        while True:
            self.log.debug('Process one frame.')
            self.buffer.append(self.process_frame(self.buffer[-1] if self.buffer else None))
            if len(self.buffer) > self.queue_size:
                self.buffer.pop(0)
            self.log.debug('Current queue size: %s', len(self.buffer))

            self.log.debug("Waiting...")
            sleep(self.sleep_time)

    def process_frame(self, compared=None):
        success, original = self.video.read()
        item = {
            'original': original
        }
        for key, method in self.plugins.items():
            item[key] = method(original, self, compared) if method else None
        return item

    def get_latest_motion_frame(self):
        if self.buffer:
            ret, jpeg = cv2.imencode('.jpg', self.buffer[-1]['grey'])
            return jpeg.tobytes()

    def get_latest_full_frame(self):
        if self.buffer:
            ret, jpeg = cv2.imencode('.jpg', self.buffer[-1]['original'])
            return jpeg.tobytes()
