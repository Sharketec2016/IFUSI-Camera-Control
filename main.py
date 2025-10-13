'''
Author: Matthew Buchkowski
Department: Physics - Astronomy
Description: Main executable frontend for handing the iXAndor cameras.


'''


import tkinter as tk
from tkinter import filedialog
from tkinter.font import Font
from tkinter import ttk, messagebox
from PIL import ImageTk, Image, ImageOps
from tkinter.messagebox import showinfo
import threading
import time
from queue import Queue
from typing import Dict, List
# from backend.cameraLogging import *
from backend.cameraConfig import *
from backend.cameraDataHandle import *
import logging as log
import sys
from pprint import pprint
import json
import pylablib.devices.Andor as Andor

serial_numbers = ["13703", "12606", "12574"]
save_data_path = ""
path_to_config_options_json = "./backend/configuration_options.json"
cam_config_options_json = None


class CameraWorker:
    def __init__(self, camera, command_queue: Queue):
        self.camera = camera
        self.command_queue = command_queue
        self.running = False
        self.thread = None
        self.acquisition_count = 0
        self.total_acquisitions = 1000
        self.acquisition_interval = 0.04  # 40ms in seconds
        self.image_buffer = np.zeros((1024, 720, self.total_acquisitions), dtype=np.uint16)
        
    def start_worker(self):
        """Start the worker thread"""
        self.running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()
        
    def stop_worker(self):
        """Stop the worker thread"""
        self.running = False
        self.camera.data = self.image_buffer
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
            
    def _worker_loop(self):
        """Main worker loop that processes commands for the camera"""
        while self.running:
            try:
                command = self.command_queue.get(timeout=0.1)  # 100ms timeout
                if command is None:
                    break
                    
                action = command.get('action')
                if action == 'start_acquisition':
                    self._handle_acquisition()
                elif action == 'configure':
                    settings = command.get('settings', {})
                    self._handle_configure(settings)
                    
                self.command_queue.task_done()
            except Queue.Empty:
                continue
                
    def _handle_acquisition(self):
        """Handle starting acquisition with precise timing"""
        try:
            self.acquisition_count = 0
            print(f"Starting acquisition for camera {self.camera.serialNumber}")
            
            while self.running and self.acquisition_count < self.total_acquisitions:
                start_time = time.time()
                
                # Start acquisition
                self.camera.start_acquisition()
                # Wait for the frame to be ready
                time.sleep(self.acquisition_interval)
                # Stop acquisition
                self.camera.stop_acquisition()
                
            
                frame = self.camera.read_newest_image()
                if frame is not None:
                    self.image_buffer[self.acquisition_count, :,:] = frame
                    
                # Update progress
                self.acquisition_count += 1
                if self.acquisition_count % 100 == 0:
                    break

                    
        except Exception as e:
            print(f"Error during acquisition for camera {self.camera.serialNumber}: {e}")
            self.running = False
        finally:
            # Save the acquired data
            if self.acquisition_count > 0:
                try:
                    
                    # save_fits_data(self.image_buffer[self.acquisition_count, :,:])
                    
                    print(f"Saved {self.acquisition_count} frames for camera {self.camera.serialNumber}")
                except Exception as e:
                    print(f"Error saving data for camera {self.camera.serialNumber}: {e}")
                     
    def _handle_configure(self, settings):
        """Handle camera configuration"""
        try:
            self.camera.camera_configuration(settings)
        except Exception as e:
            print(f"Error configuring camera {self.camera.serialNumber}: {e}")

# Main application class
class CameraMonitorApp:
    def __init__(self, root, debugLogging = False, cam_config_options_json = None):
        self.root = root
        self.root.title("Camera Monitoring System")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)
        self.logger = self._setup_logging(debugLogging)
        self.custom_font = Font(family="Helvetica", size=14, weight="bold")
        self.cam_config_options_json = cam_config_options_json
        
        # Initialize camera drivers: TODO Change this to the actual camera driver library.
        # self.cameras = [self.camera1, self.camera2, self.camera3]#, self.camera4]
        # self.cameras_dict = {}
        self.cameras = []
        self.__identify_cameras__()
        self.cameras_dict = {}
        self.camera_serials = ["13703", "12606", "12574"]


        # Creating UI elements
        self.monitoring = True
        self.monitor_thread = None

        self.camera_queues: Dict[str, Queue] = {}
        self.camera_workers: Dict[str, CameraWorker] = {}
        self.running_experiment = False
        self.running_acquisition = False

        self.has_run_experiment = False

        self.queryingConnection = False

        self.config_labels_dict = dict()
        self.config_entrys_dict = dict()
        self.config_vars = dict()   # store tk.Variable for each config entry
        self.config_serial_number = None

        self.exampleConfig = {
            'acquisitionMode': "kinetic",
            'triggeringMode': 'int',
            'readoutMode': 'image',
            'exposureTime': 0.04,
            'acquisitionNumber': 1,
            'frameTransfer': True,
            'verticalShift': {'shiftSpeed': 0.6, 'clockVoltageAmplitude': None},
            'horizontalShift': {'readoutRate': '30 MHz', 'preAmpGain': 'Gain 1', 'outputAmp': 'Electron Multiplying'},
            'baselineClamp': True,
            'emGain': {'state': False, 'gainLevel': 0},
            'shutterSettings': {'mode': 'open'},
            'fanLevel': 'full',
            'ampMode': {'channel': 0,
                        'oamp': 1,
                        'hsspeed': 100,
                        'preamp': 200
                        },
            'temperatureSetpoint': 20
        }
        self.exampleConfig['acqconfiguration'] = {
            'acqMode': 'kinetic',
            'nframes': 10,
            'overflowBehavior': 'restart'
        }


        self.create_ui()
        # self.check_camera_conection()


    def __identify_cameras__(self):
        try:
            num_cameras = Andor.get_cameras_number_SDK2()
            if(num_cameras == 0):
                self.cameras = None
                return None
            print(f"Number of cameras detected: {num_cameras}")
            self.logger.info(f"Number of cameras detected: {num_cameras}")
            if num_cameras < 1:
                self.logger.error(f"ERROR: No cameras were detected when program was started.")
            return num_cameras
        except Exception as e:
            print(f"Error identifying cameras: {e}")
        return 0
        
    def setup_camera_workers(self):
        """Initialize worker threads for each camera"""
        self.logger.info("Setting up camera workers")
        for camera in list(self.cameras_dict.values()):
            queue = Queue()
            worker = CameraWorker(camera, queue)
            self.camera_queues[camera.serialNumber] = queue
            self.camera_workers[camera.serialNumber] = worker

    def create_ui(self):
        """Create the main UI elements"""
        self.logger.info("Creating UI")

        # Create the main frame (root container)
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Use grid for clean vertical layout control
        self.main_frame.rowconfigure(0, weight=1)  # Notebook expands
        self.main_frame.rowconfigure(1, weight=0)  # Buttons stay fixed
        self.main_frame.columnconfigure(0, weight=1)

        # Create notebook for different views
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew", pady=5)

        # Create the camera status tab
        self.status_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.status_frame, text="Camera Status")

        # Create the FITS Header tab
        self.notes_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.notes_frame, text="FITS Header")

        # Create the Camera Preview tab
        self.preview_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.preview_frame, text="Camera Preview")

        # Setup the tabs
        self.setup_status_display()
        self.setup_notes_display()
        self.setup_preview_options()

        # --- Bottom Button Bar ---
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.button_frame.columnconfigure(0, weight=1)

        # Exit Button
        self.exit_btn = ttk.Button(self.button_frame, text="Exit", command=self.exit_app)
        self.exit_btn.pack(side=tk.RIGHT, padx=5)

        # Save Button
        self.save_btn = ttk.Button(self.button_frame, text="Save", command=self.save_data)
        self.save_btn.pack(side=tk.RIGHT, padx=5)



    def save_data(self):
        self.logger.info("Saving data")
        if self.has_run_experiment:
            attempt, result_str = False, ""
            try:
                save_data_path = filedialog.askdirectory(
                    title="Select Directory to Save Data",
                    initialdir="."  # Starts in current directory
                )
                
                curr_header = self.notes_text.get("1.0", tk.END)
                curr_data = [cam.data for cam in list(self.cameras_dict.values())]
                
                for data in curr_data:
                    save_fits_data(curr_header, data, save_data_path)
                attempt = True
                result_str = "Data saved successfully!"
            except Exception as e:
                attempt = False
                result_str = f"Failed to save data: {str(e)}"
            finally:
                if attempt:
                    messagebox.showinfo("Success", result_str)
                    self.logger.info(f"{result_str}")
                else:
                    messagebox.showerror("Error", result_str)
                    self.logger.error(f"{result_str}")
        else:
            messagebox.showerror("Error", "No experiment data to save. Please run an experiment first.")
            self.logger.error(f"No experiment data to save. Please run an experiment first.")

    def setup_status_display(self):
        """
        Sets up the camera status display interface within the application.
        This method creates a user interface for monitoring the status of multiple cameras.
        It includes a title label, a frame for displaying the status of each camera, and
        additional buttons for camera operations such as connecting and disconnecting all cameras.
        The interface includes:
        - A title label for the status monitor.
        - A dynamic list of camera status displays, where each camera is represented by:
            - A label indicating the camera number.
            - A label displaying the camera's serial number.
            - A status label showing the current status of the camera.
        - Buttons for connecting and disconnecting all cameras.
        Attributes:
            self.camera_status_labels (dict): A dictionary mapping each camera's serial number to its
                                       corresponding labels for serial and status.
        Note:
            This method assumes that `self.status_frame` is a valid tkinter frame and that
            `self.camera_serials` is a list of camera serial numbers.
        """
        """Setup the camera status display"""
        # Title label
        self.logger.info("Setting up camera status display")
        status_title = ttk.Label(self.status_frame, text="Camera Status Monitor", font=("Arial", 14, "bold"))
        status_title.pack(pady=10)
        
        # Frame for camera status
        status_display_frame = ttk.Frame(self.status_frame)
        status_display_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Create labels for each camera
        self.camera_status_labels = {}
        for i, serial in enumerate(self.camera_serials):
            frame = ttk.Frame(status_display_frame)
            frame.pack(fill=tk.X, pady=5)
            
            label = ttk.Label(frame, text=f"Camera {i+1}:")
            label.pack(side=tk.LEFT, padx=5)
            
            serial_label = tk.Label(frame, text=serial, font=("Courier", 12, "bold"))
            serial_label.pack(side=tk.LEFT, padx=5)
            serial_label.config(fg="red")
            
                    
            status_label = ttk.Label(frame, text="Disconnected", font=("Arial", 12))

            status_label.pack(side=tk.LEFT, padx=20)
            
            self.camera_status_labels[serial] = {
                "serial_label": serial_label,
                "status_label": status_label
            }
        
        # Additional buttons for camera operations
        ops_frame = ttk.Frame(self.status_frame)
        ops_frame.pack(fill=tk.X, pady=10, padx=20)
        
        connect_all_btn = ttk.Button(ops_frame, text="Connect All", command=self.connect_all_cameras)
        connect_all_btn.pack(side=tk.LEFT, padx=5)
        
        disconnect_all_btn = ttk.Button(ops_frame, text="Disconnect All", command=self.disconnect_all_cameras)
        disconnect_all_btn.pack(side=tk.LEFT, padx=5)

    def check_if_idx_connected_already(self, cam_index):
        for sn, cam in self.cameras_dict.items():
            if cam.camIndex ==  cam_index:
                return True
        return False

    def update_UI_elements(self):
        """
        This function updated the necessary UI elements with the appropriate values for connected cameras.
        This should only really be called after a connect all, or disconnect all.
        :return:
        """
        try:
            camera_list = list(self.cameras_dict.keys())
            if hasattr(self, "preview_select"):
                self.preview_select['values'] = camera_list

                if camera_list:
                    self.preview_select.current(0)
                else:
                    self.preview_camera.set("")
        except Exception as e:
            self.logger.error(f"Error updating UI: {e}")

    def schedule_ui_refresh(self):
        self.update_UI_elements()
        self.root.after(2000, self.schedule_ui_refresh)  # every 2 seconds

    def connect_all_cameras(self):
        """Connect to all cameras and update their status, serial number, camIndex, and info."""
        self.logger.info("Connecting to all cameras...")
        try:
            num_cameras = self.__identify_cameras__() #This identifies the number of cameras connected.
            if num_cameras:
                for i in range(num_cameras):
                    cam = AndoriXonCamera()
                    if not self.check_if_idx_connected_already(i):
                        if cam.connect(camIndex=i):
                            try:
                                info = cam.cameraObj.get_device_info()
                                cam.serialNumber = str(info[2])
                                cam.head_model = info[1]
                                cam.controller_mode = info[0]
                                cam.camIndex = i
                                cam.camera_configuration(None)
                                self.cameras.append(cam)
                                self.cameras_dict.update( {cam.serialNumber: cam} )


                                self.camera_status_labels[cam.serialNumber]["status_label"].config(text="Connected", foreground="green")
                                self.camera_status_labels[cam.serialNumber]["serial_label"].config(fg="green")
                                self.logger.info(f"Camera {cam.serialNumber} connected successfully.")

                                self.logger.info(f"Successfully identified camera {cam.camIndex}")
                                self.logger.info(f"     Serial number: {cam.serialNumber}")
                                self.logger.info(f"     Model: {cam.head_model}")
                                self.logger.info(f"     Controller Mode: {cam.controller_mode}")
                            except Exception as e:
                                self.logger.error(f"Error connecting to camera at index {i}: {e}")
                                cam.disconnect()
                        else:
                            self.logger.error(f"Failed to connect to camera {cam.serialNumber}.")
                self.update_UI_elements()
        except Exception as e:
            self.logger.error(f"Failed within connecting to all cameras {e}")
            if self.logger.level == log.DEBUG:
                print(f"Failed to connect cameras: {e}")

    def disconnect_all_cameras(self):
        """Disconnect all cameras and update their status."""
        self.logger.info("Disconnecting all cameras...")
        serials = list(self.cameras_dict.keys())
        for serial in serials:
            cam = self.cameras_dict.pop(serial)
            try:
                if cam.disconnect():
                    self.camera_status_labels[serial]["status_label"].config(text="Disconnected", foreground="black")
                    self.camera_status_labels[serial]["serial_label"].config(fg="red")
                    self.logger.info(f"Camera {serial} disconnected.")
                    # self.cameras_dict.pop(serial)
                else:
                    self.camera_status_labels[serial]["status_label"].config(text="Error", foreground="black")
                    self.camera_status_labels[serial]["serial_label"].config(fg="red")
            except Exception as e:
                self.camera_status_labels[serial]["status_label"].config(text="Error", fg="red")
                self.logger.error(f"Error disconnecting from camera {serial}: {e}")
        self.update_UI_elements()

    # #TODO Need to investigate a different method for trying to confirm whether a camera is still connected. The current method doesnt seem to be working
    # def refresh_all(self):
    #     """Refresh the status of all cameras."""
    #     self.logger.info("Refreshing all camera statuses...")
    #     serials = list(self.cameras_dict.keys()) #we grab the serials from the dict because that dict contains all the cameras that are connected.
    #     for serial in serials:
    #         try:
    #             cam = self.cameras_dict[serial]
    #             if cam.connection_status():
    #                 self.camera_status_labels[serial]["status_label"].config(text="Connected", fg="green")
    #                 self.camera_status_labels[serial]["serial_label"].config(fg="green")
    #             else:
    #                 self.camera_status_labels[serial]["status_label"].config(text="Disconnected", fg="red")
    #                 self.camera_status_labels[serial]["serial_label"].config(fg="red")
    #         except Exception as e:
    #             self.logger.error(f"Failed to refresh camera status for {serial}. Might be disconnected: {e}")
    #             print(f"Failed to refresh camera status for {serial}. Might be disconnected.")


    def save_fits_header(self):
        """Save the content of the notes text area to a file."""
        # Ask the user for a file path to save to
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            title="Save Notes As"
        )

        # If the user cancels the dialog, filepath will be empty
        if not filepath:
            return

        try:
            # Open the file in write mode ('w') and save the content
            with open(filepath, "w") as output_file:
                text_content = self.notes_text.get("1.0", tk.END)
                output_file.write(text_content)
            # Log the action and notify the user
            self.logger.info(f"Notes saved to {filepath}")
            messagebox.showinfo("Success", f"Notes successfully saved to:\n{filepath}")
        except Exception as e:
            # Log the error and show an error message
            self.logger.error(f"Error saving notes: {e}")
            messagebox.showerror("Error", f"Failed to save notes:\n{e}")

    def load_fits_header(self):
        """Load content into the notes text area from a file."""
        # Ask the user to select a file to open
        filepath = filedialog.askopenfilename(
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            title="Open Notes File"
        )

        # If the user cancels the dialog, filepath will be empty
        if not filepath:
            return

        try:
            # Open the file in read mode ('r') and load the content
            with open(filepath, "r") as input_file:
                text_content = input_file.read()

                # Clear the existing content in the text box
                self.notes_text.delete("1.0", tk.END)

                # Insert the new content from the file
                self.notes_text.insert(tk.END, text_content)
            # Log the action and notify the user
            self.logger.info(f"Notes loaded from {filepath}")
            messagebox.showinfo("Success", f"Notes successfully loaded from:\n{filepath}")
        except Exception as e:
            # Log the error and show an error message
            self.logger.error(f"Error loading notes: {e}")
            messagebox.showerror("Error", f"Failed to load notes:\n{e}")
    
    def save_values(self):
        serialNumber = self.selected_camera.get()
        # self.config_serial_number = serialNumber
        configDict = self.cameras_dict[serialNumber].cam_config
        for key, value in configDict.items():
            if type(value) == dict:
                for k2, v2 in value.items():
                    # prefer variable-backed values if available
                    try:
                        var = self.config_vars.get(key, {}).get(k2, None)
                        if var is not None:
                            new_val = var.get()
                        else:
                            new_val = self.config_entrys_dict[key][k2].get()
                    except Exception:
                        new_val = self.config_entrys_dict[key][k2].get()

                    self.config_labels_dict[key][k2].config(text=new_val)
                    self.cameras_dict[serialNumber].cam_config[key][k2] = new_val
            else:
                try:
                    var = self.config_vars.get(key, None)
                    if var is not None and not isinstance(var, dict):
                        new_val = var.get()
                    else:
                        new_val = self.config_entrys_dict[key].get()
                except Exception:
                    new_val = self.config_entrys_dict[key].get()

                self.config_labels_dict[key].config(text=new_val)
                self.cameras_dict[serialNumber].cam_config[key] = new_val
        
    def setup_config_options(self):
        """Setup the camera configuration options"""
        # Title label
        config_title = ttk.Label(self.config_frame, text="Camera Configuration", font=("Arial", 14, "bold"))
        config_title.pack(pady=10)
        
        # Camera selection frame
        selection_frame = ttk.Frame(self.config_frame)
        selection_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(selection_frame, text="Select Camera:").pack(side=tk.LEFT, padx=5)
        
        # Camera selection combobox
        self.selected_camera = tk.StringVar()
        camera_select = ttk.Combobox(selection_frame, textvariable=self.selected_camera)
        camera_select['values'] = self.camera_serials
        camera_select.current(0)
        camera_select.pack(side=tk.LEFT, padx=5)
        camera_select.bind('<<ComboboxSelected>>', self._update_config_display)
        
        #Update Settings button
        self.update_button = ttk.Button(selection_frame, text="Update Settings", command=lambda: self.update_config_options(serialNumber=self.selected_camera.get()))
        self.update_button.pack(side=tk.LEFT, padx=5)
        
        self.config_canvas = tk.Canvas(self.config_frame)
        self.config_canvas.pack(side="left", fill="both", expand=True)
        
        self.config_scrollbar = ttk.Scrollbar(self.config_frame, orient="vertical", command=self.config_canvas.yview)
        self.config_scrollbar.pack(side="right", fill="y")
        self.config_canvas.configure(yscrollcommand=self.config_scrollbar.set)
        self.config_canvas.bind('<Configure>', lambda e: self.config_canvas.configure(scrollregion=self.config_canvas.bbox("all")))
        self.scrollable_frame = ttk.Frame(self.config_canvas)
        
        self.config_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        self.config_left_frame = ttk.Frame(self.scrollable_frame, padding=10) #this will contain the entry boxes for users to put values
        self.config_right_frame = ttk.Frame(self.scrollable_frame, padding=10) #this will show the current values for the camera configs.
        self.config_left_frame.pack(side="left", fill="both", expand=True)
        self.config_right_frame.pack(side="right", fill="both", expand=True)

        self.current_settings = ttk.Label(self.config_left_frame, text="Current Settings", font=self.custom_font)
        self.current_settings.grid(row=0, column=7, padx=(135, 1), pady=5)

        i = 1
        for key, value in self.exampleConfig.items():
            if type(value) is dict:
                tmp_label = ttk.Label(self.config_left_frame, text=f"{key}", font=self.custom_font)
                tmp_label.grid(row=i, column=0, sticky="w", padx=2, pady=2)
                i+=1
                for k2, v2 in value.items():

                    tmp2_label = ttk.Label(self.config_left_frame, text=f"{k2}", font=self.custom_font)
                    tmp2_label.grid(row=i, column=2, sticky="w", padx=0, pady=2)

                    curr_label = ttk.Label(self.config_left_frame, text=f"{v2}", font=self.custom_font)
                    curr_label.grid(row=i, column=7, sticky="w", padx=(135, 1), pady=2)

                    var = tk.StringVar(value=str(v2))
                    dropdown_values = self.cam_config_options_json[key][k2]
                        
                    widget = ttk.Combobox(self.config_left_frame, textvariable=var, values=dropdown_values, width=18)
                    widget.grid(row=i, column=3, padx=35, pady=2, sticky="w")

                    try:
                        # store label, widget and var
                        self.config_labels_dict[key].update({k2: curr_label})
                        self.config_entrys_dict[key].update({k2: widget})
                        self.config_vars.setdefault(key, {})[k2] = var
                    except Exception:
                        self.config_labels_dict.update({key: {k2: curr_label}})
                        self.config_entrys_dict.update({key: {k2: widget}})
                        self.config_vars.update({key: {k2: var}})

                    i+=1
            else:
                tmp_label = ttk.Label(self.config_left_frame, text=f"{key}", font=self.custom_font)
                tmp_label.grid(row=i, column=0, sticky="w", padx=5, pady=2)

                curr_label = ttk.Label(self.config_left_frame, text=f"{value}", font=self.custom_font)
                curr_label.grid(row=i, column=7, sticky="w", padx=(135, 1), pady=2)

                var = tk.StringVar(value=str(value))
                dropdown_values = self.cam_config_options_json[key]
                    
                widget = ttk.Combobox(self.config_left_frame, textvariable=var, values=dropdown_values, width=18)
                widget.grid(row=i, column=3, padx=35, pady=2, sticky="w")

                try:
                    self.config_labels_dict[key] = curr_label
                    self.config_entrys_dict[key] = widget
                    self.config_vars[key] = var
                except Exception:
                    self.config_labels_dict.update({key: curr_label})
                    self.config_entrys_dict.update({key: widget})
                    self.config_vars.update({key: var})
            i+=1
        self._update_config_display()

    def _update_config_display(self, event=None):
        serialNumber = self.selected_camera.get()
        if not serialNumber or serialNumber not in self.cameras_dict:
            return # No camera selected or camera not found

        camera = self.cameras_dict[serialNumber]
        if not hasattr(camera, 'cam_config') or not camera.cam_config:
            if camera.is_connected == CameraState.CONNECTED:
                camera.camera_configuration() # Create a default config if it doesn't exist

        config = camera.cam_config

        for key, value in config.items():
            if isinstance(value, dict):
                for k2, v2 in value.items():
                    if key in self.config_vars and k2 in self.config_vars[key]:
                        self.config_vars[key][k2].set(v2)
                    if key in self.config_labels_dict and k2 in self.config_labels_dict[key]:
                        self.config_labels_dict[key][k2].config(text=str(v2))
            else:
                if key in self.config_vars:
                    self.config_vars[key].set(value)
                if key in self.config_labels_dict:
                    self.config_labels_dict[key].config(text=str(value))

    def setup_preview_options(self):
        """Setup the camera preview options with live streaming inside the preview_frame"""

        # --- Configure grid layout for preview tab ---
        self.preview_frame.columnconfigure(0, weight=1)
        self.preview_frame.rowconfigure(2, weight=1)  # live preview area expands

        # --- Title ---
        preview_title = ttk.Label(
            self.preview_frame, text="Camera Preview", font=("Arial", 14, "bold")
        )
        preview_title.grid(row=0, column=0, pady=(10, 5))

        # --- Camera selection ---
        preview_selection_frame = ttk.Frame(self.preview_frame)
        preview_selection_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(5, 10))
        preview_selection_frame.columnconfigure(1, weight=1)

        ttk.Label(preview_selection_frame, text="Select Camera:").grid(
            row=0, column=0, sticky="w", padx=(0, 5)
        )

        # Dropdown for selecting connected cameras
        self.preview_camera = tk.StringVar()
        self.preview_select = ttk.Combobox(
            preview_selection_frame, textvariable=self.preview_camera, state="readonly"
        )
        if len(self.cameras_dict) > 0:
            self.preview_select["values"] = list(self.cameras_dict.keys())
            self.preview_select.current(0)
        else:
            self.preview_select["values"] = []
        self.preview_select.grid(row=0, column=1, sticky="ew")

        # --- Live preview display area ---
        preview_display_frame = ttk.LabelFrame(self.preview_frame, text="Live Preview")
        preview_display_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 10))
        self.preview_canvas = tk.Label(
            preview_display_frame, bg="black", width=640, height=480
        )
        self.preview_canvas.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # Bind resizing event
        self.preview_width = 640
        self.preview_height = 480
        self.preview_canvas.bind("<Configure>", self.on_preview_resize)

        # --- Controls (buttons below the live view) ---
        preview_control_frame = ttk.Frame(self.preview_frame)
        preview_control_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 15))

        start_preview_btn = ttk.Button(
            preview_control_frame, text="Start Preview",
            command=lambda: self.toggle_preview(True)
        )
        start_preview_btn.pack(side=tk.LEFT, padx=5)

        stop_preview_btn = ttk.Button(
            preview_control_frame, text="Stop Preview",
            command=lambda: self.toggle_preview(False)
        )
        stop_preview_btn.pack(side=tk.LEFT, padx=5)

        capture_btn = ttk.Button(
            preview_control_frame, text="Capture Image", command=self.capture_image
        )
        capture_btn.pack(side=tk.LEFT, padx=5)

    def on_preview_resize(self, event):
        """Update stored preview dimensions when the canvas is resized."""
        self.preview_width = event.width
        self.preview_height = event.height

    def setup_notes_display(self):
        """Setup the experiment notes interface"""
        # Title label
        notes_title = ttk.Label(self.notes_frame, text="Experiment Notes", font=("Arial", 14, "bold"))
        notes_title.pack(pady=10)
        
        # Create frame for text area and scrollbar
        text_frame = ttk.Frame(self.notes_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add text area
        self.notes_text = tk.Text(text_frame, height=20, wrap=tk.WORD, 
                                yscrollcommand=scrollbar.set)
        self.notes_text.pack(fill=tk.BOTH, expand=True)
        
        
        # Configure scrollbar
        scrollbar.config(command=self.notes_text.yview)
        
        # Add buttons frame
        button_frame = ttk.Frame(self.notes_frame)
        button_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Add Save and Load buttons
        save_btn = ttk.Button(button_frame, text="Save Header", 
                            command=self.save_fits_header)
        save_btn.pack(side=tk.LEFT, padx=5)
        
        load_btn = ttk.Button(button_frame, text="Load Header", 
                            command=self.load_fits_header)
        load_btn.pack(side=tk.LEFT, padx=5)

    def update_config_options(self, serialNumber = None):
        if not serialNumber:
            serialNumber = self.selected_camera.get()
            
        camera = self.cameras_dict[serialNumber]
        if not hasattr(camera, 'cam_config'):
            camera.camera_configuration()

        tmpReplaceDict = camera.cam_config.copy()

        for key, value in self.config_labels_dict.items():
            if type(value) is dict:
                for k2, v2 in value.items():
                    # Prefer variable-backed value if available
                    tmp_val = None
                    var = None
                    if key in self.config_vars and isinstance(self.config_vars[key], dict):
                        var = self.config_vars[key].get(k2)
                    if var is not None:
                        try:
                            tmp_val = var.get()
                        except Exception:
                            tmp_val = None
                    else:
                        # fallback to widget.get() if possible
                        try:
                            tmp_val = self.config_entrys_dict[key][k2].get()
                        except Exception:
                            tmp_val = None

                    if tmp_val is None:
                        continue
                    if not (type(tmpReplaceDict[key][k2]) == type(tmp_val)):
                        # attempt to coerce numeric strings
                        pass
                    if tmp_val == '':
                        continue
                    v2.config(text = tmp_val)
                    try:
                        tmpReplaceDict[key][k2] = float(tmp_val)
                    except Exception:
                        tmpReplaceDict[key][k2] = tmp_val
            else:
                tmp_val = None
                var = self.config_vars.get(key)
                if var is not None and not isinstance(var, dict):
                    try:
                        tmp_val = var.get()
                    except Exception:
                        tmp_val = None
                else:
                    try:
                        tmp_val = self.config_entrys_dict[key].get()
                    except Exception:
                        tmp_val = None

                if tmp_val is None:
                    continue
                if tmp_val == '':
                    continue
                value.config(text = tmp_val)
                try:
                    tmpReplaceDict[key] = float(tmp_val)
                except Exception:
                    tmpReplaceDict[key] = tmp_val
        self.cameras_dict[serialNumber].cam_config = tmpReplaceDict
        pprint(tmpReplaceDict)

    def toggle_preview(self, start):
        """Start or stop the live preview."""
        serial = self.preview_camera.get()

        if start and not getattr(self, "preview_running", False):
            self.preview_running = True
            self.preview_canvas.config(text=f"Starting preview for camera {serial}...", image="")
            self.preview_select.configure(state="disabled")
            self.start_camera_preview(serial)

        elif not start and getattr(self, "preview_running", False):
            self.preview_running = False
            self.preview_select.configure(state="readonly")
            self.preview_canvas.config(text="Preview stopped", image="")


    def start_camera_preview(self, serial):
        """Start live camera preview loop"""
        try:
            self.preview_cam = self.cameras_dict[serial].cameraObj
            self.preview_cam.set_exposure(0.04)
            self.preview_cam.setup_shutter(mode="open")
            self.preview_cam.set_trigger_mode("int")
            self.preview_cam.set_amp_mode(
                channel=0,
                oamp=0,
                hsspeed=1,
                preamp=2
            )
            self.preview_cam.setup_acquisition(mode="sequence", nframes=100)

            sleep(0.5)
            self.preview_cam.start_acquisition()
            self.preview_thread = threading.Thread(target=self.live_loop, daemon=True)
            self.preview_thread.start()
        except Exception as e:
            self.preview_canvas.config(text=f"Failed to start camera: {e}")
            self.preview_running = False
            return

    def live_loop(self):
        try:
            self.vmin, self.vmax = None, None
            while self.preview_running:
                self.preview_cam.wait_for_frame(timeout=5)
                frame = self.preview_cam.read_newest_image()
                if frame is None:
                    continue

                # Smooth brightness adjustment
                fmin, fmax = np.min(frame), np.max(frame)
                if self.vmin is None:
                    self.vmin, self.vmax = fmin, fmax
                else:
                    self.vmin = 0.9 * self.vmin + 0.1 * fmin
                    self.vmax = 0.9 * self.vmax + 0.1 * fmax

                frame = np.clip(frame, self.vmin, self.vmax)
                norm = (255 * (frame - self.vmin) / (self.vmax - self.vmin + 1e-9)).astype(np.uint8)

                # Convert to displayable image and resize to preview window
                img = Image.fromarray(norm)
                img = img.resize((self.preview_width, self.preview_height), Image.Resampling.LANCZOS)

                imgtk = ImageTk.PhotoImage(image=img)
                self.preview_canvas.after(0, self.update_preview_display, imgtk)
        finally:
            self.preview_cam.stop_acquisition()
            try:
                # Create an empty black image matching the preview area
                blank = np.zeros((self.preview_height, self.preview_width), dtype=np.uint8)
                img = Image.fromarray(blank)
                imgtk = ImageTk.PhotoImage(image=img)

                self.update_preview_display(imgtk)

            except Exception as e:
                print(f"Failed to draw preview: {e}")


    def update_preview_display(self, imgtk):
        self.preview_canvas.imgtk = imgtk
        self.preview_canvas.configure(image=imgtk)

    def array_to_photoimage(self, array):
        """Convert a grayscale numpy array to a Tkinter-compatible PhotoImage"""
        array = np.clip(array, 0, None)  # remove negatives
        norm = 255 * (array - np.min(array)) / (np.ptp(array) + 1e-5)
        img = Image.fromarray(norm.astype(np.uint8), mode="L")
        return ImageTk.PhotoImage(img)

    def capture_image(self):
        """Capture an image from the selected camera"""
        serial = self.preview_camera.get()
        cam = self.cameras_dict[serial].cameraObj

        cam.set_exposure(0.04)
        cam.set_amp_mode(channel=0, oamp=0, hsspeed=1, preamp=2)
        cam.set_vsspeed(vsspeed=3)
        cam.setup_shutter(mode="open")

        # Grab image (ensure it's 2D)
        image = np.squeeze(cam.grab(1))
        print("Captured image shape:", image.shape)

        # Smooth brightness adjustment
        fmin, fmax = np.min(image), np.max(image)
        if not hasattr(self, "vmin") or self.vmin is None:
            self.vmin, self.vmax = fmin, fmax
        else:
            self.vmin = 0.9 * self.vmin + 0.1 * fmin
            self.vmax = 0.9 * self.vmax + 0.1 * fmax

        image = np.clip(image, self.vmin, self.vmax)
        norm = (255 * (image - self.vmin) / (self.vmax - self.vmin + 1e-9)).astype(np.uint8)

        # Convert to displayable image and resize to preview window
        img = Image.fromarray(norm)
        img = img.resize((self.preview_width, self.preview_height), Image.Resampling.LANCZOS)
        imgtk = ImageTk.PhotoImage(image=img)

        self.update_preview_display(imgtk)

    def exit_app(self):
        """Clean exit of the application"""
        try:
            self.disconnect_all_cameras()
        except Exception as e:
            self.logger.critical(f"ERROR: Failed to disconnect all cameras: {e}")




        self.monitoring = False
        try:
            if self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=1.0)
        except Exception as e:
            print(f"Error stopping monitoring thread: {e}")
        
        self.root.destroy()
        
    def start_monitoring(self):
        """Start the monitoring thread"""
        if not self.monitor_thread or not self.monitor_thread.is_alive():
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self.update_acquisition_status, daemon=True)
            self.monitor_thread.start()
            print("Camera monitoring started")

    def stop_monitoring(self):
        """Stop the monitoring thread"""
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1.0)
            print("Camera monitoring stopped")

    def start_experiment(self):
        """Called when starting an experiment"""
        self.stop_monitoring()  # Stop monitoring during experiment
        self.running_experiment = True
        print("Experiment started")

        # Your experiment code here
        '''
        When we run our experiment we have some rules to follow. 
        
        1. Check if the cameras are connected and working properly.
        2. Configure the acquisition parameters.
        3. Configure the cameras for acquisition.
        4. Start the acquisition.
        5. Wait for the acquisition to finish.
        6. Stop the acquisition.
        7. Process the data for header generation.
        8. Save the data to a file.
        9. Close the cameras.
        '''
        
       # Setup workers if not already done
        if not self.camera_workers:
            self.setup_camera_workers()
        
        # Check camera connections
        for camera in self.cameras:
            if not camera.connection_status():
                messagebox.showerror("Error", f"Camera {camera.serialNumber} is not connected")
                return
        
        
        for camera in self.cameras:
            try:    
                camera.camera_configuration()
                # camera.acquisition_configuration()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to configure camera {camera.serialNumber}: {str(e)}")
                return
        # Start all workers
        for worker in self.camera_workers.values():
            worker.start_worker()
            
        # Start acquisition on all cameras
        for queue in self.camera_queues.values():
            queue.put({'action': 'start_acquisition'})
            
        # Start progress monitoring
        self.root.after(1000, self.check_experiment_progress)
        
    def check_experiment_progress(self):
        """Monitor experiment progress"""
        if not self.running_experiment:
            return
            
        all_complete = True
        for worker in self.camera_workers.values():
            if worker.acquisition_count < worker.total_acquisitions:
                all_complete = False
                break
                
        if all_complete:
            self.end_experiment()
        else:
            self.root.after(1000, self.check_experiment_progress)

    def end_experiment(self):
        """End the experiment and cleanup"""
        # Stop all workers
        for worker in self.camera_workers.values():
            worker.stop_worker()
            
        self.running_experiment = False
        self.start_monitoring()
        messagebox.showinfo("Complete", "Experiment completed successfully!")
    
    def _setup_logging(self, debugLogging):
        logger = log.getLogger(f"CameraApplication")
        if(debugLogging):
            logger.setLevel(log.DEBUG)
        else:
            logger.setLevel(log.INFO)
        if not logger.handlers:
            dir_path = os.path.dirname(os.path.realpath(__file__))
            if not os.path.exists(f"{dir_path}/logs"):
                os.makedirs(f"{dir_path}/logs")
            save_path = f"{dir_path}/logs"
            handler = log.FileHandler(f'{save_path}/cameraApplication.log')
            
            if(debugLogging):
                handler.setLevel(log.DEBUG)
            else:
                handler.setLevel(log.INFO)
            
            
            formatter = log.Formatter('[%(asctime)s] %(name)s:%(levelname)s:%(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.info(f"Logging level set to {'DEBUG' if debugLogging else 'INFO'}")
        return logger

    def check_camera_conection(self):
        """
        A method to periodically check the camera's connection.
        """
        print("Checking camera connection...")  # For demonstration

        serials = list(self.cameras_dict.keys())  # we grab the serials from the dict because that dict contains all the cameras that are connected.
        for serial in serials:
            try:
                cam = self.cameras_dict[serial]
                if cam.connection_status():
                    self.camera_status_labels[serial]["status_label"].config(text="Connected", fg="green")
                    self.camera_status_labels[serial]["serial_label"].config(fg="green")
                else:
                    self.camera_status_labels[serial]["status_label"].config(text="Disconnected", fg="red")
                    self.camera_status_labels[serial]["serial_label"].config(fg="red")
            except Exception as e:
                self.logger.error(f"Failed to refresh camera status for {serial}. Might be disconnected: {e}")
                print(f"Failed to refresh camera status for {serial}. Might be disconnected.")

        # Schedule the next check in 2 seconds (2000 ms)
        self.root.after(ms=2000, func=self.check_camera_conection)

def main():
    args = sys.argv #pass in command line arguments.
    if len(args) > 1 and (args[1] == "--help" or args[1] == '-h' or args[1] == '-H'):
        print("Usage: python main.py [-d]")
        print("Options:")
        print("  -d    Enable debug logging")
        return
    
    
    debug_mode = "-d" in args 
    
    with open(path_to_config_options_json, "r") as f:
        cam_config_options_json = json.load(f)
    
    
    root = tk.Tk()
    app = CameraMonitorApp(root, debugLogging=debug_mode, cam_config_options_json=cam_config_options_json)
    root.mainloop()


if __name__ == "__main__":
    main()