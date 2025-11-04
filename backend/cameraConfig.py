from pylablib.devices import Andor
from pylablib.devices.Andor import AndorSDK2Camera
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
    



class AndoriXonCamera:
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

    def configure_camera_settings(self, configDict = None):
        '''
        :param cameraDict: A dictionary that contains two elements. 1. Camera OBJ, 2. Camera config dict
        :return: True or False on configuration
        '''

        if(configDict is None):
            return False
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
                    self.cameraObj.set_EMCCD_gain(gain=configDict['emGain']['gainLevel'])
                    if(configDict['shutterSettings']['ExternalShutter'].lower() == 'fullauto'):
                        self.cameraObj.setup_shutter(mode='auto')
                    elif(configDict['shutterSettings']['ExternalShutter'].lower() == 'open'):
                        self.cameraObj.setup_shutter(mode='open')
                    elif(configDict['shutterSettings']['ExternalShutter'].lower() == 'close'):
                        self.cameraObj.setup_shutter(mode='close')


                    if(configDict['acquisitionMode'].lower() == 'kinetic'):
                        self.cameraObj.setup_kinetic_mode(num_cycle=configDict['KineticSeriesLength'],
                                                          cycle_time=configDict['KineticCycleTime'],
                                                          num_acc=configDict['acquisitionNumber']
                                                          )

                    if(configDict['frameTransfer'].lower() == 'on'):
                        self.cameraObj.enable_frame_transfer_mode(enable=True)
                    else:
                        self.cameraObj.enable_frame_transfer_mode(enable=False)

                    # self.cameraObj.setup_image_mode() #letting default values be passed
                    # self.cameraObj.set_amp_mode(channel = configDict['ampMode']['channel'],
                    #                     oamp = configDict['ampMode']['oamp'],
                    #                     hsspeed = configDict['ampMode']['hsspeed'],
                    #                     preamp = configDict['ampMode']['preamp']
                    #                     )
                    self._configure_amp_mode(configDict)
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
        return False


    
    def acquistion_configuration(self, cameraDict):
        acqDict = cameraDict['acqconfiguration']
        self.cameraObj.setup_acquisition(acqDict['acqMode'], acqDict['nframes'])
        self.cameraObj.set_overflow_behavior(behavior=acqDict['overflowBehavior'])

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

class Camera(AndorSDK2Camera):
    def __init__(self, idx, temperature=None, fan_mode='full', amp_mode=None):
        super().__init__(idx=idx, temperature=temperature, fan_mode=fan_mode, amp_mode=amp_mode)
        self.serialNumber = None
        self.cam_config = None
        self.head_model = None
        self.controller_mode = None

        self.connection_status = CameraState.CONNECTED if self.is_opened() else CameraState.DISCONNECTED
        self.is_in_acquisition = CameraState.NOT_ACQUIRING
        self.is_configured = CameraState.NOT_CONFIGURED
        self.logger = self.setup_logging()  # for now implement the logging feature automatically. we might want to change that later if it takes up too much time.


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
    def disconnect(self):
        try:
            if self.is_opened():
                self.close()
                self.connection_status = CameraState.DISCONNECTED
                self.logger.info(f"Camera {self.serialNumber} is disconnected")
                return True
            else:
                self.logger.info(f"Camera {self.serialNumber} is already disconnected")
                return False
        except Exception as e:
            self.logger.error(f"Error disconnecting camera {self.serialNumber}: {e}")
    def camera_configuration(self, configDict=None, configDir = None):
        '''
        :param cameraDict: A dictionary that contains two elements. 1. Camera OBJ, 2. Camera config dict
        :return: True or False on configuration
        '''

        if (configDict is not None):
            self.cam_config = configDict

        elif(configDir is not None):
                pass
        else:
            configDict = {
                'acquisitionMode': "kinetic",
                'triggeringMode': 'int',
                'readoutMode': 'image',
                'exposureTime': 0.004,
                'acquisitionNumber': 1,
                'frameTransfer': "OFF",
                'verticalShift': {'shiftSpeed': "0.6",
                                  'clockVoltageAmplitude': "Normal"
                                  },
                'horizontalShift': {'readoutRate': '30 MHz',
                                    'preAmpGain': 'Gain1',
                                    'outputAmp': 'EM'
                                    },
                'baselineClamp': "OFF",
                'emGain': {'state': "ON", 'gainLevel': 1},
                'shutterSettings': {
                    "InternalShutter" : "Open",
                    "ExternalShutter" : "Open"
                  },
                'fanLevel': 'full',
                'temperatureSetpoint': -25
            }
        self.cam_config = configDict
        self.logger.info(f"Configuring camera {self.serialNumber} with config: {configDict}")


        if self.is_opened():
            try:
                self.set_fan_mode(mode=configDict['fanLevel'])
                self.set_acquisition_mode(mode=configDict['acquisitionMode'])
                self.set_trigger_mode(mode=configDict['triggeringMode'])
                self.set_read_mode(mode=configDict['readoutMode'])
                self.set_exposure(exposure=configDict['exposureTime'])
                self.set_EMCCD_gain(gain=configDict['emGain']['gainLevel'])
                if (configDict['shutterSettings']['ExternalShutter'].lower() == 'fullauto'):
                    self.setup_shutter(mode='auto')
                elif (configDict['shutterSettings']['ExternalShutter'].lower() == 'open'):
                    self.setup_shutter(mode='open')
                elif (configDict['shutterSettings']['ExternalShutter'].lower() == 'close'):
                    self.setup_shutter(mode='close')

                if (configDict['acquisitionMode'].lower() == 'kinetic'):
                    self.setup_kinetic_mode(num_cycle=configDict['KineticSeriesLength'],
                                                      cycle_time=configDict['KineticCycleTime'],
                                                      num_acc=configDict['acquisitionNumber']
                                                      )

                if (configDict['frameTransfer'].lower() == 'on'):
                    self.enable_frame_transfer_mode(enable=True)
                else:
                    self.enable_frame_transfer_mode(enable=False)



                self._configure_amp_mode(configDict=configDict)
                self._configure_vsspeed(configDict=configDict)
                self.set_temperature(int(configDict['temperatureSetpoint']))
                self.is_configured = CameraState.CONFIGURED
                self.logger.info(f"Camera {self.serialNumber} configured successfully")
                return True
            except Exception as e:
                self.logger.error(f"Camera {self.serialNumber} configuration failed: {e}")
                self.is_configured = CameraState.NOT_CONFIGURED
                return False
        return True


    def _configure_amp_mode(self, configDict):
        channel = 0
        oamp = 0 if configDict['horizontalShift']['outputAmp'] is "EM" else 1
        preamp = 0 if configDict['horizontalShift']['preAmpGain'] is "Gain1" else 1
        if(configDict['horizontalShift']['readoutRate'] == "30MHz"):
            hsspeed = 0
        elif (configDict['horizontalShift']['readoutRate'] == "20MHz"):
            hsspeed = 1
        elif(configDict['horizontalShift']['readoutRate'] == "10MHz"):
            hsspeed = 2
        elif(configDict['horizontalShift']['readoutRate'] == "1MHz"):
            hsspeed = 3
        else:
            hsspeed = 0


        self.set_amp_mode(
            channel=channel,
            oamp = oamp,
            hsspeed = hsspeed,
            preamp = preamp
        )

    def _configure_vsspeed(self, configDict):
        all_speeds = self.get_all_vsspeeds()
        if(configDict['verticalShift']['shiftSpeed'] == '0.6'):
            self.set_vsspeed(all_speeds[0])
        elif(configDict['verticalShift']['shiftSpeed'] == '1.13'):
            self.set_vsspeed(all_speeds[1])
        elif(configDict['verticalShift']['shiftSpeed'] == '2.2'):
            self.set_vsspeed(all_speeds[2])
        elif(configDict['verticalShift']['shiftSpeed'] == '4.33'):
            self.set_vsspeed(all_speeds[3])
        else:
            self.set_vsspeed(all_speeds[0])

    def get_camera_connetion_status(self):
        self.connection_status = CameraState.CONNECTED if self.is_opened() else CameraState.DISCONNECTED
        return self.connection_status
    def get_acquisition_status(self):
        self.is_in_acquisition = CameraState.ACQUIRING if self.get_status() == "acquiring" else CameraState.NOT_ACQUIRING
        return self.is_in_acquisition

