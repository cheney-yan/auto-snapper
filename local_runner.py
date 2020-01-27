from camera import VideoCamera
import cv2
from time import sleep
from config import config
config['desktop_run'] = True

camera = VideoCamera(config)
# LOOP!
while True:
  sleep(0.5)
  # Set transient motion detected as false
  transient_movement_flag = False

  # Read frame
  camera.main()

  ch = cv2.waitKey(1)
