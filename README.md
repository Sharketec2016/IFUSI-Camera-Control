-------------------------------------------
Author: Matthew Buchkowski \
Department: SCSU Physics (Astronomy)
-------------------------------------------
# IFUSI Speckling Imaging
The Integrated Field Unit Speckle Imager (IFUSI) is a next-generation speckle imaging instrument that combines a fiber-fed Integral Field Unit (IFU) with an array of four Andor iXon Ultra 888 EMCCD cameras.
The fiber bundle acts as the IFU, dividing the telescope’s image into thousands of individual spatial elements (spaxels). Each fiber carries light from a small patch of the image into the spectrograph and cameras, allowing IFUSI to capture hyperspectral speckle data—images with full wavelength information across the field.

Traditional two-channel speckle interferometers are limited to capturing narrow wavelength bands.
By contrast, the IFU-based design in IFUSI significantly increases the spectral bandwidth and data richness, enabling the simultaneous capture of spatial and spectral information for every frame.

This Python project provides a graphical user interface (GUI) for controlling up to N connected Andor cameras. Through the GUI, users can:
1. Automatically detect and connect available cameras
2. Configure individual camera settings
3. Preview live video feeds from each camera
4. Run full experimental data acquisitions and save results to disk

> [!NOTE]
> This program is designed specifically for the Andor iXon Ultra 888 EMCCD cameras.
Before running the GUI, you must install the appropriate Andor SDK and DLL libraries on the host system.
These libraries are Windows-only — the DLLs are not compatible with Linux.
You can obtain the latest SDK and driver package from:
👉 https://andor.oxinst.com/downloads 


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
    Note: All other packages used within the project should be included by default, or should already be installed along side the above packages automatically. If any missing dependency errors occur, install the missing packages/dependances accordingly. 
4. Within the package populated env, run the command `python main.py` to launch the application. 

### Working with Python Env
1. Install python 3.12 
2. Within the project root directory run the command `python -m venv _name of env_`. 
3. Once the env has been created, you should see a folder in the project root dir with the name of your env.
4. Descend into your venv/bin to find the _activate_ file. Depending of your OS you will activate your env differently, but run either `source activate` or `./activate` or `activate` within the terminal
5. Once the venv has been activated, ascend back into the root directory. Make sure you are not in the same dir as the _requirements.txt_ file. 
6. run the command `pip install -r requirements.txt`. This will recursively install all the necessary packages for running the project. 

> [!NOTE]
> If you include the `-d` flag when executing the script, lower level debug log files will be created for increased resolution on camera handling. 
> 
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

