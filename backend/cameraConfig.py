import json
from pprint import pprint
from pylablib.devices import Andor
from pylablib.devices.Andor import AndorSDK2Camera
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
    


class Camera(AndorSDK2Camera):
    def __init__(self, idx, temperature=None, fan_mode='full', amp_mode=None):
        super().__init__(idx=idx, temperature=temperature, fan_mode=fan_mode, amp_mode=amp_mode)
        self.serialNumber = None
        self.cam_config = None
        self.head_model = None
        self.controller_mode = None
        self.temperature_setpoint = temperature
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

        if configDict is not None:
            self.cam_config = configDict

        elif configDir is not None and os.path.isdir(configDir):
            expected_name = f"{self.serialNumber}_configs.json"
            for f in os.listdir(configDir):
                if f == expected_name:
                    file_path = os.path.join(configDir, f)
                    try:
                        with open(file_path, "r") as json_file:
                            configDict = json.load(json_file)
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Error reading {file_path}: {e}\nCould not import camera settings.")
                        self.is_configured = CameraState.NOT_CONFIGURED
                    except Exception as e:
                        self.logger.error(f"Error reading {file_path}: {e} | GENERAL CONFIGURATION ERROR ")
                        self.is_configured = CameraState.NOT_CONFIGURED
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

                '''
                It appears that there are specific "modes" for the amplifier and preamp. 
                Only those modes can be set and will work. As such we need to specify to the user which mode 
                they can choose from. 
                '''


                self.set_fan_mode(mode=configDict['fanLevel'])
                if (configDict['acquisitionMode'].lower() == 'kinetic'):
                    self.setup_kinetic_mode(num_cycle=configDict['KineticSeriesLength'],
                                            cycle_time=configDict['KineticCycleTime'],
                                            num_acc=configDict['acquisitionNumber']
                                            )
                else:
                    self.set_acquisition_mode(mode=configDict['acquisitionMode'])

                self.set_trigger_mode(mode=configDict['triggeringMode'])
                self.set_read_mode(mode=configDict['readoutMode'])
                self.set_exposure(exposure=configDict['exposureTime'])
                self.set_EMCCD_gain(gain=configDict['emGain']['gainLevel'], advanced=False)
                if (configDict['shutterSettings']['ExternalShutter'].lower() == 'fullauto'):
                    self.setup_shutter(mode='auto')
                elif (configDict['shutterSettings']['ExternalShutter'].lower() == 'open'):
                    self.setup_shutter(mode='open')
                elif (configDict['shutterSettings']['ExternalShutter'].lower() == 'close'):
                    self.setup_shutter(mode='close')



                if (configDict['frameTransfer'].lower() == 'on'):
                    self.enable_frame_transfer_mode(enable=True)
                else:
                    self.enable_frame_transfer_mode(enable=False)



                self._configure_amp_mode(configDict=configDict)
                self._configure_vsspeed(configDict=configDict)

                self.set_temperature(int(configDict['temperatureSetpoint']))
                self.temperature_setpoint = int(configDict['temperatureSetpoint'])


                if self.is_acquisition_setup():
                    self.is_configured = CameraState.CONFIGURED
                    self.logger.info(f"Camera {self.serialNumber} configured successfully")
                    return True
                else:
                    self.is_configured = CameraState.NOT_CONFIGURED
                    self.logger.error(f"Camera {self.serialNumber} not configured")
                    return False
            except Exception as e:
                self.logger.error(f"Camera {self.serialNumber} configuration failed: {e}")
                self.is_configured = CameraState.NOT_CONFIGURED
                return False
        self.is_configured = CameraState.NOT_CONFIGURED
        return False

    def _configure_amp_mode(self, configDict):
        configured_amp = False
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

        #now that we have all of the settings. We need to find the mode that matches this
        for mode in self.get_all_amp_modes():
            if mode.channel == channel and mode.oamp == oamp and mode.hsspeed == hsspeed and mode.preamp == preamp:
                self.set_amp_mode(
                    channel=mode.channel,
                    oamp = mode.oamp,
                    hsspeed = mode.hsspeed,
                    preamp = mode.preamp
                )
                configured_amp = True
        if not configured_amp:          #backup incase we were unsuccessful in configuring the amp for the camera
            self.init_amp_mode(mode = self.get_all_amp_modes()[8])
            self.logger.error(f"Camera {self.serialNumber} amplifier was not manually configured correctly. Setting amp to default conventional setting")

    def _configure_vsspeed(self, configDict):
        all_speeds = self.get_all_vsspeeds()
        if(configDict['verticalShift']['shiftSpeed'] == '0.6'):
            self.set_vsspeed(0)
        elif(configDict['verticalShift']['shiftSpeed'] == '1.13'):
            self.set_vsspeed(1)
        elif(configDict['verticalShift']['shiftSpeed'] == '2.2'):
            self.set_vsspeed(2)
        elif(configDict['verticalShift']['shiftSpeed'] == '4.33'):
            self.set_vsspeed(3)
        else:
            self.set_vsspeed(0)

    def get_camera_connetion_status(self):
        self.connection_status = CameraState.CONNECTED if self.is_opened() else CameraState.DISCONNECTED
        return self.connection_status
    def get_acquisition_status(self):
        self.is_in_acquisition = CameraState.ACQUIRING if self.get_status() == "acquiring" else CameraState.NOT_ACQUIRING
        return self.is_in_acquisition

    def full_camera_info(self):
        pprint(self.get_full_info(include = 'all'))
        pprint(self.get_full_status(include = 'all'))
        pprint(self.get_settings(include = 'all'))

