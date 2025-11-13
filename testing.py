import traceback

from pylablib.devices import Andor
import numpy as np
import matplotlib.pyplot as plt
from backend.cameraConfig import Camera, CameraState







def main():

    '''
    We are going to establish connections to all cameras.
    Then we are going to configure each camera will a different setting
    then we will read out their images at once
    and then we will save the images to a jpeg or png from matplotlib
    :return:
    '''



    #Assuming we have 4 cameras connected.
    connected_cameras = Andor.get_cameras_number_SDK2()
    cameras = dict()
    cam = None
    for i in range(connected_cameras):
        cam = Camera(idx = i, temperature=-20, fan_mode='full')
        if cam is not None and cam.is_opened():
            info = cam.get_device_info()
            cam.serialNumber = str(info[2])
            cam.head_model = info[1]
            cam.controller_mode = info[0]
            cameras.update({cam.serialNumber : cam})

    #Now we are going to configure each camera









if __name__ == '__main__':
    main()