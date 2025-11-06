-------------------------------------------
Author: Matthew Buchkowski
Date: October 25, 2024

-------------------------------------------
This readme file contains all notes, information about pylablib and equipment/cameras, and project structure for the python programming to acquire images.


Program Project Structure:
1. Confirm that all necessary cameras are connected by comparing the unique serial numbers.
            a. This method will be done first by quering how many cameras the program thinks are connected. After that, it will then run through a for loop and grab all of the serial numbers from each of the cameras and compare them against a global list. As long as the serial number is within this list, then the queried one should be within. Since time is not of a concern at this step, a simple O(n) search time is fine.

2. If all cameras are connected, and registering, we then need to go one by one and configure them
            a. NOTE: Dr Horch has mentioned that 4 cameras would be used in the normal experiment, but that a 5th camera could be added. This camera might have a different configuration than the other four.
3. After configuration, and confirmation of settings, is set we need to perform the actual capture. These are also some extra settings that need to be defined
4. After capture of each image, they need to be saved locally within a folder. Since a total of 4 (or 5) cameras will be used, 4\5 folders is needed. Each camera will save its images into a unique folder, where later someone can go through and post process.

## Creating a workable env
To properly use the camera application, a suitable environment needs to be created first. It is recommended that Ananconda (conda) be used. Follow the steps below will result in a workable enviornment (env). 

### Working with Anaconda
1. Install anaconda3 from Anaconda (https://www.anaconda.com/download/success). Following the installation instruction per your host operating system. 
2. Using the command `conda activate _put your env name here_`, activate the env if it isn't already active. Refer to the anaconda installation or instructions page for further guidance on activating your env.
3. Using the command `conda install _packageName_` install the following packages
    1. numpy - This will be used for array handling of data
    2. astropy - Package for data formatting, header creation, and data saving.
    3. pandas - Package for dataframe creation, data handling, and data saving.
    4. Use the command `conda install -c conda-forge pylablib`  - Contains all camera drivers for the iXon Andor cameras.
    Note: All other packages used within the project should be included by default, or should aldready be installed along side the above packages automatically. If any missing dependency errors occur, install the missing packages/dependances accordingly. 
4. Within the package populated env, run the command `python main.py` to launch the application. 

### Working with Python Env
1. Install python 3.12 
2. Within the project root directory run the command `python -m venv _name of env_`. 
3. Once the env has been created, you should see a folder in the project root dir with the name of your env.
4. Decend into your venv/bin to find the _activate_ file. Depending of your OS you will activate your env differently, but run either `source activate` or `./activate` or `activate` within the terminal
5. Once the venv has been activated, ascend back into the root directory. Make sure you are not in the same dir as the _requirements.txt_ file. 
6. run the command `pip install -r requirements.txt`. This will recusivly install all of the necessary packages for running the project. 


Note: If you include the `-d` flag when executing the script, lower level debug log files will be created for increased resolution on camera handling. 

### Trouble Shooting Camera Connection
Sometimes when you attempt to connect to the camera you may encounter an error like this `Failed to connect cameras: function 'Initialize' raised error 20992(DRV_NOT_AVAILABLE)`. When this error happens it is usually due to a couple of reason. 
1. The camera(s) is/are not powered on. If so please power on and connect to the computer. To verify you have a successful connection check device manager for a new device called `libusb-win32 devices` and find your camera in there. 
2. The camera is not plugged in. Plug in the camera and follow the same verification process as step 1
3. Another process is holding up the camera resources. Close all other programs (like Solis) that might be restricting you from connecting. Then try again. 
4. Corrupted USB driver stack. This is a bit of a phantom bug, but essentially the usb driver stack for either the camera or windows itself is able to detect a device connected but you are unable to communicate with it over the USB line. To resolve this you need to folow these steps.
   1. Open device manager and find the possibly Andor iXon Ultra device. 
   2. Right click the camera and select `Disable device`. - This will disable the usb driver for that device. 
   3. wait ~5 seconds
   4. Right click the camera again and `Enable device`. - This will restart the usb driver. 
   5. Open a known working, stable, program (like solis) to confirm you are now able to connect and stream data from the camera. 

### Software Requirements
The required DLL can have different names depending on the Solis version and SDK bitness. For 64-bit version it will be called atmcd64d.dll or atmcd64d_legacy.dll. For 32-bit version, correspondingly, atmcd32d.dll or atmcd32d_legacy.dll. By default, library searches for DLLs in Andor Solis and Andor SDK folder in Program Files folder (or Program files (x86), if 32-bit version of Python is running), as well as in the folder containing the script. If the DLLs are located elsewhere, the path can be specified using the library parameter devices/dlls/andor_sdk2:
```
import pylablib as pll
pll.par["devices/dlls/andor_sdk2"] = "path/to/dlls"
from pylablib.devices import Andor
cam = Andor.AndorSDK2Camera()
```
**Note**: At the top of the main file are these lines. If necessary, change them to point to the appropriate dlls.