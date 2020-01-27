import cv2
from simplelog import get_logger
import threading
import logging
from time import sleep
from collections import OrderedDict
import numpy as np
import copy
import datetime
import glob
import os


def get_image_timestamp():
  dt = datetime.datetime.now()
  return dt.strftime("%Y%m%d-%H%M%S.") + str(dt.microsecond)


def resize(camera):
  original = camera.buffer[-1]['original']
  width = int(original.shape[1] * camera.scale_percent / 100)
  height = int(original.shape[0] * camera.scale_percent / 100)
  dim = (width, height)
  view = cv2.resize(original, dim, interpolation=cv2.INTER_AREA)
  return view


def greynify(camera):
  img = camera.buffer[-1]['view']
  gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
  blur = cv2.GaussianBlur(gray, (21, 21), 0)
  return blur


def get_max_change(image, camera, compared):
  # Compare the two frames, find the difference
  image = copy.deepcopy(image)
  frame_delta = cv2.absdiff(image, compared)
  thresh = cv2.threshold(
    frame_delta, camera.image_diff_threshold, 255, cv2.THRESH_BINARY)[1]
  camera.buffer[-1]['thresh'] = thresh
  thresh = cv2.dilate(thresh, None, iterations=2)
  camera.buffer[-1]['thresh2'] = thresh
  cnts, _ = cv2.findContours(
    thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
  camera.buffer[-1]['cnts'] = cnts

  # loop over the contours
  movement_inf = (0, 0, 0, 0, 0)  # size, x, y w, h
  for c in cnts:
    # Save the coordinates of all found contours
    (x, y, w, h) = cv2.boundingRect(c)
    if camera.desktop_run:
      cv2.rectangle(image, (x, y),
                    (x + w, y + h),
                    (0, 255, 0), 2)
    size = w * h
    if size > movement_inf[0]:
      movement_inf = (size, x, y, w, h)
  if camera.desktop_run:
    cv2.imshow("frame", np.hstack((frame_delta, image)))

  return movement_inf


def get_max_change_from_start(camera):
  if len(camera.buffer) > 1:
    return get_max_change(camera.buffer[-1]['grey'], camera, camera.buffer[0]['grey'])
  return None


def get_max_change_from_end(camera):
  buffer = camera.buffer
  if len(buffer) > 1:
    result = get_max_change(buffer[-1]['grey'], camera, buffer[-2]['grey'])
    return result
  return None


def save_photo(image, name, storage_path):
  file_name = '/%s/%s.jpg' % (storage_path, name)
  with open(file=file_name, mode='wb') as f:
    ret, jpeg = cv2.imencode('.jpg', image)
    f.write(jpeg.tobytes())


def after_process(camera):
  if len(camera.buffer) < 3:
    return
  if camera.buffer[-1]['change_from_start'][0] > camera.image_diff_size_threshold:
    camera.log.info("Detected Change from %d grames ago", len(camera.buffer))
  else:
    return
  minimal_change = min(
    [b for b in camera.buffer if b.get('change_from_last')]
    , key=lambda x: x.get('change_from_last'))
  camera.log.info('Minimal change during between: %s', minimal_change['change_from_last'][0])
  if camera.storage_path:
    save_photo(minimal_change['original'], minimal_change['timestamp'], camera.storage_path)
  del camera.buffer[:]


class VideoCamera(object):
  def __init__(self, config):
    self.scale_percent = config.get('scale_percent', 25)
    self.debug = config.get('debug', False)
    self.video = cv2.VideoCapture(config.get('source', 0))
    self.buffer = []
    self.log = get_logger('VideoCamera')
    if self.debug:
      self.log.setLevel(logging.DEBUG)
    self.queue_size = config.get('queue_size', 10)
    self.sleep_time = config.get('sleep_time', 1)
    self.image_diff_threshold = config.get('image_diff_threshold', 25)
    self.image_diff_size_threshold = config.get(
      'image_diff_size_threshold', 60)
    self.plugins = OrderedDict({
      'view': resize,
      'grey': greynify,
      'change_from_start': get_max_change_from_start,
      'change_from_last': get_max_change_from_end,
      'after_process': after_process
    })
    self.desktop_run = config.get('desktop_run', False)
    self.storage_path = config.get('storage_path')
    if not self.desktop_run:
      self.start_daemon()

  def __del__(self):
    self.video.release()

  def start_daemon(self):
    thread = threading.Thread(target=self.run, args=())
    thread.daemon = True
    thread.start()

  def main(self):
    self.log.debug('Process one frame.')
    original = self.get_frame()
    item = {
      'original': original,
      'timestamp': get_image_timestamp()
    }
    self.buffer.append(item)
    self.process_frame(item)
    if len(self.buffer) > self.queue_size:
      self.buffer.pop(0)
    self.log.debug('Current queue size: %s', len(self.buffer))
    if len(self.buffer) > 2:
      # self.log.debug('Process result of last frame %s', self.buffer[-1])
      self.log.debug('Change since %d frame ago: %s', self.queue_size, self.buffer[-1].get('change_from_start'))
      self.log.debug('Change since last frame: %s ', self.buffer[-1]['change_from_last'])
    self.log.debug("Waiting...")
    sleep(self.sleep_time)

  def run(self):
    while True:
      self.main()

  def get_frame(self):
    success, original = self.video.read()
    if success:
      return original

  def process_frame(self, item):

    for key, method in self.plugins.items():
      item[key] = method(self) if method else None
    return item

  def get_latest_motion_frame(self):
    if self.buffer:
      ret, jpeg = cv2.imencode('.jpg', self.buffer[-1]['view'])
      return jpeg.tobytes()

  def get_latest_debug_frame(self):
    if self.debug and len(self.buffer) > 2:
      ret, jpeg = cv2.imencode('.jpg', self.buffer[-2]['debug'])  # the -1 might not be processed yet
      return jpeg.tobytes()
    else:
      return self.get_latest_full_frame()

  def get_latest_full_frame(self):
    if self.buffer:
      ret, jpeg = cv2.imencode('.jpg', self.buffer[-1]['original'])
      return jpeg.tobytes()

  def get_last_saved_frame(self):
    if self.storage_path:
      list_of_files = glob.glob('%s/*.jpg' % self.storage_path)  # * means all if need specific format then *.csv
      file_name = max(list_of_files, key=os.path.getctime)
      with open(file=file_name, mode='rb') as f:
        return f.read()
