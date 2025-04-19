from pylablib.devices import Andor
import numpy as np
import pandas as pd
from time import sleep
from astropy.io import fits
import os
# iXonSerialNumbers = [13703]

'''
class: AndorCamera
description: This is a basic andor camera class. This class will contain all of the methods needed for configuring the andor cameras

'''
class AndoriXonCamera():
    def __init__(self, camIndex, serialNumber):
        self.serialNumber = serialNumber

        self.cam_config = dict()
        self.camIndex = camIndex
        self.cameraObj = None
        self.cam_config = {
            'acquisitionMode': "kinetic",
            'triggeringMode': 'int',
            'readoutMode': 'image',
            'exposureTime': 0.04,
            'acquistionNumber': 1,
            'frameTransfer': True,
            'verticalShift': {'shiftSpeed': 0.6, 'clockVoltageAmplitude': None},
            'horizontalShift': {'readoutRate': '30 MHz', 'preAmpGain': 'Gain 1', 'outputAmp': 'Electron Multiplying'},
            'baselineClamp': True,
            'emGain': {'state': False, 'gainLevel': 0},
            'shutterSettings': {'mode': 'open'},
            'fanLevel': 'full',
            'ampMode': {'channel': self.cameraObj.get_all_amp_modes()[0].channel,
                        'oamp': self.cameraObj.get_all_amp_modes()[0].oamp,
                        'hsspeed': self.cameraObj.get_all_amp_modes()[0].hsspeed,
                        'preamp': self.cameraObj.get_all_amp_modes()[0].preamp
                        },
            'temperatureSetpoint': 20
        }
        self.cam_config['AcqConfiguration'] = {
            'acqMode': 'kinetic',
            'nframes': 10,
            'overflowBehavior': 'restart'
        }
        
        self.is_connected = False
        self.is_in_acquisition = False
        self.is_configured = False
        self.data = None
        # print(f"Setting up camera {self.serialNumber} with default configuration")
        # self.camera_configuration()


    def connection_status(self):
        if self.cameraObj.is_opened():
            print(f"Camera {self.cameraObj.get_device_info()} is connected")
            return True
        return False

    def acquisition_status(self):
        return self.cameraObj.get_status()

    def camera_configuration(self, cameraDict = None):
        '''
        :param cameraDict: A dictionary that contains two elements. 1. Camera OBJ, 2. Camera config dict
        :return: True or False on configuration
        '''
        
        if (cameraDict is not None):
            configDict = cameraDict['CameraConfiguration']
            
        else:
            configDict = self.cam_config
    
        try:
                self.cameraObj.set_acquisition_mode(mode = configDict['acquisitionMode'])
                self.cameraObj.set_trigger_mode(mode = configDict['triggeringMode'])
                self.cameraObj.set_read_mode(mode = configDict['readoutMode'])
                self.cameraObj.set_exposure(exposure=configDict['exposureTime'])
                self.cameraObj.set_EMCCD_gain(gain=configDict['emGain']['gainLevel'], advanced=configDict['emGain']['state'])
                self.cameraObj.setup_shutter(mode=configDict['shutterSettings']['mode'])
                self.cameraObj.set_fan_mode(mode=configDict['fanLevel'])
                self.cameraObj.setup_kinetic_mode(num_cycle=configDict['acquistionNumber'])
                self.cameraObj.enable_frame_transfer_mode(enable=configDict['frameTransfer'])
                self.cameraObj.setup_image_mode() #letting default values be passed
                self.cameraObj.set_amp_mode(channel = configDict['ampMode']['channel'],
                                    oamp = configDict['ampMode']['oamp'],
                                    hsspeed = configDict['ampMode']['hsspeed'],
                                    preamp = configDict['ampMode']['preamp']
                                    )
                self.cameraObj.set_vsspeed(configDict['verticalShift']['shiftSpeed'])
                self.cameraObj.set_temperature(configDict['temperatureSetpoint'])


                if not self.cameraObj.is_metadata_enabled():
                    self.cameraObj.enable_metadata()

                return True
        except Exception as e:
            print(f"Camera {self.serialNumber} configuration failed: {e}")
            return False
    
    def acquistion_configuration(self, cameraDict):
        # cameraObj, acqDict = cameraDict['Camera'], cameraDict['AcqConfiguration']
        acqDict = cameraDict['AcqConfiguration']
        self.cameraObj.setup_acquisition(acqDict['acqMode'], acqDict['nframes'])
        self.cameraObj.set_overflow_behavior(behavior=acqDict['overflowBehavior'])
    
    def getCamera_default_config(self):
        return self.cam_config

    def connect(self):
        try:
            self.cameraObj = Andor.AndorSDK2Camera(idx=self.camIndex, temperature=None, fan_mode='full', amp_mode=None)
            if self.cameraObj.is_opened():
                self.is_connected = True
                print(f"Camera {self.serialNumber} is connected")
                return True
            else:
                print(f"Camera {self.serialNumber} is not connected")
                return False
        except Exception as e:
            print(f"Error connecting to camera {self.serialNumber}: {e}")
            return False    
    
    def disconnect(self):
        try:
            if self.cameraObj.is_opened():
                self.cameraObj.close()
                self.is_connected = False
                print(f"Camera {self.serialNumber} is disconnected")
                return True
            else:
                print(f"Camera {self.serialNumber} is already disconnected")
                return False
        except Exception as e:
            print(f"Error disconnecting camera {self.serialNumber}: {e}")
            return False
            


