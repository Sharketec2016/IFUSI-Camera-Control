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
        4. After capture of each image, they need to be saved locally within a folder. Since a total of 4 (or 5) cameras will be used, 4/5 folders is needed. Each camera will save its images into a unique folder, where later someone can go through and post process.
