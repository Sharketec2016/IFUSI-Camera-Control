'''
Author: Matthew Buchkowski
Department: Physics - Astronomy

Description: Parent file for configuring and handling the iXAndor cameras.

'''

from pylablib.devices import Andor
import numpy as np
import pandas as pd
from time import sleep
# from cameraConfig import *
# from csv_to_fits import *

#These are the serial numbers of the cameras that are connected to the computer.
iXonSerialNumbers = [13703]

Cameras = []  # parent list of all the camera dictionary

def camera_settings(cameraObj):
    cameraSerialNumber = cameraObj.get_device_info()[-1]

    print(f"Camera {cameraSerialNumber}")
    print(f"Capabilities: {cameraObj.get_capabilities()}\n\n")
    print(f"Camera: {cameraSerialNumber} Acquisition parameters : {cameraObj.get_acquisition_parameters()}")
    print(
        f"Camera: {cameraSerialNumber} Temperature Setpoint : {cameraObj.get_temperature_setpoint()} | Temperature Range: {cameraObj.get_temperature_range()} | Temperatuer Status: {cameraObj.get_temperature_status()}")
    print(f"Camera: {cameraSerialNumber} Current Amplifier Mode: {cameraObj.get_amp_mode(full=True)}")
    print(f"Camera: {cameraSerialNumber} Horizontal Speed Index : {cameraObj.get_hsspeed()} and Frequency {cameraObj.get_hsspeed_frequency()}")

    print(f"Camera: {cameraSerialNumber} EMCCD Gain : {cameraObj.get_EMCCD_gain()}")
    allAmpModes = cameraObj.get_all_amp_modes()
    print(f"Camera: {cameraSerialNumber} Possible Amplifier Modes")
    for mode in allAmpModes:
        print(f"    {mode}")

    print(f"Camera: {cameraSerialNumber} Shutter Parameters : {cameraObj.get_shutter_parameters()}")

def acquistion_configuration(cameraDict):
    cameraObj, acqDict = cameraDict['Camera'], cameraDict['AcqConfiguration']

    cameraObj.setup_acquisition(acqDict['acqMode'], acqDict['nframes'])
    cameraObj.set_overflow_behavior(behavior=acqDict['overflowBehavior'])




'''
This function is the main function for running the experiment. We will follow the steps below:
1. Check if the cameras are connected and working properly.
2. Configure the acquisition parameters.
3. Configure the cameras for acquisition.
4. Start the acquisition.
5. Wait for the acquisition to finish.
6. Stop the acquisition.
7. Process the data for header generation. 
8. Save the data to a file.
9. Close the cameras.

9 easy steps, lol. 

'''
# def main2():
#     # camera_confirmation(iXonSerialNumbers) #running the check on cameras, and making sure they are connected
#     cam1 = AndorCamera(camIndex=0, serialNumber=11111)

#     cam1Dict = cam1.cam_config

#     try:
#         config_cam_cond = cam1.camera_configuration(cameraDict=cam1Dict)
#         config_cam_acq = cam1.acquistion_configuration(cameraDict=cam1Dict)
#     except:
#         config_cam_cond = False
#     #sent_software_trigger() is the function used to capture an image from the cameras.

#     Cameras.append(cam1Dict)

#     cam1Dict['Camera'].start_acquisition()
#     sleep(0.04) #sleeping for 40 ms, typical acquisition time for one frame. TODO need to double check that the wait time is properlly set to 40ms. 
#     cam1Dict['Camera'].stop_acquisition()

#     tmp_data = cam1Dict['Camera'].grab(10)
#     try:
#         for i in range(10):
#             tmp_df = pd.DataFrame(tmp_data[i])
#             hdul = convertData()

#             # tmp_df.to_excel("../Data/datatest.xlsx", f'{i}')


#     except:
#         pass


#     buildHeader()



#     for cameraDict in Cameras:
#         cameraDict['Camera'].close()


#     return 0



# if __name__ == '__main__':
#     main2()



