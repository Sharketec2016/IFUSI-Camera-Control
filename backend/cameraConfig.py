from pylablib.devices import Andor
import numpy as np
import pandas as pd
from time import sleep
from astropy.io import fits
import os
from enum import Enum
import logging as log
'''
class: AndorCamera
description: This is a basic andor camera class. This class will contain all of the methods needed for configuring the andor cameras

'''
class CameraState(Enum):
    CONNECTED = 1
    DISCONNECTED = 2
    ACQUIRING = 3
    NOT_ACQUIRING = 4
    CONFIGURED = 5
    NOT_CONFIGURED = 6
    ERROR = 7
    



class AndoriXonCamera():
    def __init__(self):
        self.serialNumber = None

        self.cam_config = dict()
        self.camIndex = None
        self.cameraObj = None
        self.cam_config = None
        self.head_model = None
        self.controller_mode = None

        
        self.is_connected = CameraState.DISCONNECTED
        self.is_in_acquisition = CameraState.NOT_ACQUIRING
        self.is_configured = CameraState.NOT_CONFIGURED
        self.data = None
        self.error = None
        
        self.logger = self.setup_logging() #for now implement the logging feature automatically. we might want to change that later if it takes up too much time. 

    def connection_status(self):
        if self.cameraObj.is_opened():
            try:
                info =  self.cameraObj.get_device_info()
                self.is_connected = CameraState.CONNECTED
                return True
            except Exception as e:
                self.is_connected = CameraState.DISCONNECTED
                return False
        else:
            self.is_connected = CameraState.DISCONNECTED
        return False

    def acquisition_status(self):
        if self.cameraObj.get_status() == 'acquiring':
            self.is_in_acquisition = CameraState.ACQUIRING
        else:
            self.is_in_acquisition = CameraState.NOT_ACQUIRING
            
        return self.is_in_acquisition

    def camera_configuration(self, cameraDict = None):
        '''
        :param cameraDict: A dictionary that contains two elements. 1. Camera OBJ, 2. Camera config dict
        :return: True or False on configuration
        '''
        
        if (cameraDict is not None):
            configDict = cameraDict['CameraConfiguration']
            
        else:
            amp_mode_defaults = {
                'channel': 0, 'oamp': 1, 'hsspeed': 100, 'preamp': 200
            }
            if self.cameraObj and self.cameraObj.is_opened():
                amp_modes = self.cameraObj.get_all_amp_modes()
                if amp_modes:
                    amp_mode_defaults = {
                        'channel': amp_modes[0].channel,
                        'oamp': amp_modes[0].oamp,
                        'hsspeed': amp_modes[0].hsspeed,
                        'preamp': amp_modes[0].preamp
                    }

            configDict = {
            'acquisitionMode': "kinetic",
            'triggeringMode': 'int',
            'readoutMode': 'image',
            'exposureTime': 0.004,
            'acquisitionNumber': 1,
            'frameTransfer': True,
            'verticalShift': {'shiftSpeed': 0.6, 'clockVoltageAmplitude': None},
            'horizontalShift': {'readoutRate': '30 MHz', 'preAmpGain': 'Gain 1', 'outputAmp': 'Electron Multiplying'},
            'baselineClamp': True,
            'emGain': {'state': False, 'gainLevel': 0},
            'shutterSettings': {'mode': 'open'},
            'fanLevel': 'full',
            'ampMode': amp_mode_defaults,
            'temperatureSetpoint': 20
        }
        configDict['acqconfiguration'] = {
            'acqMode': 'kinetic',
            'nframes': 10,
            'overflowBehavior': 'restart'
        }
        self.cam_config = configDict
        self.logger.info(f"Configuring camera {self.serialNumber} with config: {configDict}")

        if self.cameraObj:
            if self.cameraObj.is_opened():
                try:
                        self.cameraObj.set_fan_mode(mode=configDict['fanLevel'])
                        self.cameraObj.set_acquisition_mode(mode = configDict['acquisitionMode'])
                        self.cameraObj.set_trigger_mode(mode = configDict['triggeringMode'])
                        self.cameraObj.set_read_mode(mode = configDict['readoutMode'])
                        self.cameraObj.set_exposure(exposure=configDict['exposureTime'])
                        self.cameraObj.set_EMCCD_gain(gain=configDict['emGain']['gainLevel'], advanced=configDict['emGain']['state'])
                        self.cameraObj.setup_shutter(mode=configDict['shutterSettings']['mode'])
                        self.cameraObj.setup_kinetic_mode(num_cycle=configDict['acquisitionNumber'])
                        self.cameraObj.enable_frame_transfer_mode(enable=configDict['frameTransfer'])
                        self.cameraObj.setup_image_mode() #letting default values be passed
                        self.cameraObj.set_amp_mode(channel = configDict['ampMode']['channel'],
                                            oamp = configDict['ampMode']['oamp'],
                                            hsspeed = configDict['ampMode']['hsspeed'],
                                            preamp = configDict['ampMode']['preamp']
                                            )
                        self.cameraObj.set_vsspeed(configDict['verticalShift']['shiftSpeed'])
                        self.cameraObj.set_temperature(configDict['temperatureSetpoint'])
                        self.acquistion_configuration(self.cam_config)
                        self.is_configured = CameraState.CONFIGURED
                        self.logger.info(f"Camera {self.serialNumber} configured successfully")
                        return True
                except Exception as e:
                    self.logger.error(f"Camera {self.serialNumber} configuration failed: {e}")
                    self.is_configured = CameraState.NOT_CONFIGURED
                    return False
        return True
    
    def acquistion_configuration(self, cameraDict):
        acqDict = cameraDict['acqconfiguration']
        self.cameraObj.setup_acquisition(acqDict['acqMode'], acqDict['nframes'])
        self.cameraObj.set_overflow_behavior(behavior=acqDict['overflowBehavior'])
    
    def get_cam_config(self):
        return self.cam_config

    def connect(self, camIndex):
        try:
            self.cameraObj = Andor.AndorSDK2Camera(idx=camIndex, temperature=None, fan_mode='full', amp_mode=None)
            if self.cameraObj.is_opened():
                self.is_connected = CameraState.CONNECTED
                self.logger.info(f"Camera {self.serialNumber} is connected")
                return True
            else:
                self.logger.error(f"Camera {self.serialNumber} is not connected")
                self.is_connected = CameraState.DISCONNECTED
                return False
        except Exception as e:
            print(f"Error connecting to camera {self.serialNumber}: {e}")
            return False    
    
    def disconnect(self):
        try:
            if self.cameraObj.is_opened():
                self.cameraObj.close()
                self.is_connected = CameraState.DISCONNECTED
                self.logger.info(f"Camera {self.serialNumber} is disconnected")
                return True
            else:
                self.logger.info(f"Camera {self.serialNumber} is already disconnected")
                return False
        except Exception as e:
            self.logger.error(f"Error disconnecting camera {self.serialNumber}: {e}")
            self.is_connected = CameraState.ERROR
            return False
    
    def setup_logging(self):
        logger = log.getLogger(f"Camera-{self.serialNumber}")
        logger.setLevel(log.DEBUG)
        
        if not logger.handlers:
            dir_path = os.path.dirname(os.path.realpath(__file__))
            if not os.path.exists(f"{dir_path}/logs"):
                os.makedirs(f"{dir_path}/logs")
            save_path = f"{dir_path}/logs"
            handler = log.FileHandler(f'{save_path}/camera_{self.serialNumber}.log')
            handler.setLevel(log.DEBUG)
            formatter = log.Formatter('[%(asctime)s] %(name)s:%(levelname)s:%(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
        
    # def capture_still(self):
    def live_stream_camera(self):
        """
            Continuously grab images from the camera and display them in real time.

            :param exposure: Exposure time in seconds (e.g. 0.040 for 40 ms)
            :param roi: Optional ROI spec (e.g. (xmin, xmax, ymin, ymax) or as required by your camera API)
        """
        # Instantiate your camera (replace with your camera class)
        cam = Andor.AndorSDK2Camera(idx=0)
        cam.open()
        try:
            # Optionally set ROI if your camera supports it
            if roi is not None:
                # You may need to adapt this call depending on your camera API
                cam.set_roi(*roi)

            # Set exposure
            cam.set_exposure(exposure)

            # Optionally setup acquisition buffer etc.
            cam.setup_acquisition(mode="sequence", nframes=100)  # buffer of 100 frames
            cam.start_acquisition()

            # Prepare matplotlib figure
            fig, ax = plt.subplots()
            # Acquire one initial frame to define the plot
            cam.wait_for_frame()
            frame0 = cam.read_oldest_image()
            im = ax.imshow(frame0, cmap='gray', vmin=np.min(frame0), vmax=np.max(frame0))
            ax.set_title(f"Live camera (exposure = {exposure * 1000:.1f} ms)")
            ax.axis('off')
            plt.colorbar(im, ax=ax)

            # Continuous loop
            while True:
                # Wait for the next frame
                cam.wait_for_frame()
                frame = cam.read_oldest_image()
                if frame is None:
                    # If no frame, skip
                    continue

                # Update the image display
                im.set_data(frame)
                # Optionally adjust contrast scaling if dynamic range changes
                im.set_clim(vmin=np.min(frame), vmax=np.max(frame))
                plt.pause(0.001)  # small pause to allow GUI event loop to update

                # If you want a breaking condition, you could check keyboard or time
                # Here’s an example to break on close of window:
                if not plt.fignum_exists(fig.number):
                    break
        except KeyboardInterrupt:
            print('Closing camera')
        finally:
            # Clean up
            try:
                cam.stop_acquisition()
            except Exception:
                pass
            cam.close()
            plt.close(fig)


