import cv2
from simplelog import get_logger
import threading
import logging
from time import sleep


def resize(original, camera):
    width = int(original.shape[1] * camera.scale_percent / 100)
    height = int(original.shape[0] * camera.scale_percent / 100)
    dim = (width, height)
    view = cv2.resize(original, dim, interpolation=cv2.INTER_AREA)
    return view


def greyify(original, camera):
    return cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)


def get_max_change(image, camera, compared):
    # Compare the two frames, find the difference
    frame_delta = cv2.absdiff(image, compared)
    thresh = cv2.threshold(
        frame_delta, camera.image_diff_threshold, 255, cv2.THRESH_BINARY)[1]
    # Fill in holes via dilate(), and find contours of the thesholds
    thresh = cv2.dilate(thresh, None, iterations=2)
    cnts, _ = cv2.findContours(
        thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # loop over the contours
    movement_inf = (0, 0, 0, 0, 0)  # size, x, y w, h

    for c in cnts:
        # Save the coordinates of all found contours
        (x, y, w, h) = cv2.boundingRect(c)
        size = w * h
        if size > movement_inf[0]:
            movement_inf = (size, x, y, w, h)

    # If the contour is too small, ignore it, otherwise, there's transient
    # movement
    if movement_inf[0] > camera.image_diff_mize_threshold:
        return movement_inf
    return (0, 0, 0, 0, 0)


def get_max_change_from_start(image, camera):
    if len(camera.buffer)>1:
        return get_max_change(camera.buffer[-1]['grey'], camera, camera.buffer[0]['grey'])
    return None


def get_max_change_from_end(image, camera):
    if len(camera.buffer)>1:
        return get_max_change(camera.buffer[-1]['grey'], camera, camera.buffer[-2]['grey'])
    return None


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
        self.image_diff_threshold = config.get('image_diff_threshold', 25)
        self.image_diff_mize_threshold = config.get(
            'image_diff_mize_threshold', 99999)
        self.plugins = {
            'view': resize,
            'grey': greyify,
            'change_from_start': get_max_change_from_start,
            'change_from_last': get_max_change_from_end,
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
            self.buffer.append(self.process_frame())
            if len(self.buffer) > self.queue_size:
                self.buffer.pop(0)
            self.log.debug('Current queue size: %s', len(self.buffer))
            if len(self.buffer)>2:
                # self.log.debug('Process result of last frame %s', self.buffer[-1])
                self.log.debug('Change since %d frame ago: %d pixels', self.queue_size, self.buffer[-1]['change_from_start'][0])
                self.log.debug('Change since last frame: %d ', self.buffer[-1]['change_from_last'][0])
            self.log.debug("Waiting...")
            sleep(self.sleep_time)

    def process_frame(self):
        success, original = self.video.read()
        item = {
            'original': original
        }
        for key, method in self.plugins.items():
            item[key] = method(original, self) if method else None
        return item

    def get_latest_motion_frame(self):
        if self.buffer:
            ret, jpeg = cv2.imencode('.jpg', self.buffer[-1]['grey'])
            return jpeg.tobytes()

    def get_latest_full_frame(self):
        if self.buffer:
            ret, jpeg = cv2.imencode('.jpg', self.buffer[-1]['original'])
            return jpeg.tobytes()
