import cv2
from simplelog import get_logger
import threading, logging
from time import sleep


class VideoCamera(object):
    def __init__(self, config):
        self.scale_percent = config.get('scale_percent', 25)
        self.video = cv2.VideoCapture(config.get('source', 0))
        # Queue item is a a tuple:
        # (original, view, grey, max_diff_size)
        self.buffer = []
        self.log = get_logger('VideoCamera')
        self.log.setLevel(logging.DEBUG)
        self.start_daemon()
        self.queue_size = config.get('queue_size', 10)
        self.sleep_time = config.get('sleep_time', 1)


    def __del__(self):
        self.video.release()

    def start_daemon(self):
        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True                            
        thread.start()  

    def run(self):
        while True:
            self.log.debug('Process one frame.')
            self.buffer.append(self.process_frame())
            if len(self.buffer)> self.queue_size:
                self.buffer.pop(0)
            self.log.debug('Current queue size: %s', len(self.buffer))

            self.log.debug("Waiting...")
            sleep(self.sleep_time)
    

    def process_frame(self):
        success, original = self.video.read()

        width = int(original.shape[1] * self.scale_percent / 100)
        height = int(original.shape[0] * self.scale_percent / 100)
        dim = (width, height)
        view = cv2.resize(original, dim, interpolation = cv2.INTER_AREA)
        grey = None
        max_diff_size = None
        return original, view, grey, max_diff_size
    
    def get_latest_motion_frame(self):
        if self.buffer:
            ret, jpeg = cv2.imencode('.jpg', self.buffer[-1][0])
            return jpeg.tobytes()
    def get_latest_frame(self):
        if self.buffer:
            return self.buffer[-1][0].tobytes()