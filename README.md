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