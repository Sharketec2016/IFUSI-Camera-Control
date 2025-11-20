'''
Author: Matthew Buchkowski
Department: Physics - Astronomy
Description: Main executable frontend for handing the iXAndor cameras.


'''

import tkinter as tk
import cv2
from tkinter import filedialog
import numpy as np
from time import sleep
from tkinter.font import Font
from tkinter import ttk, messagebox
from PIL import ImageTk, Image
import threading
import time
from queue import Queue
from typing import Dict
from backend.cameraConfig import *
from backend.cameraDataHandle import *
import logging as log
import sys
from pprint import pprint
import json
import pylablib as pll
pll.par["devices/dlls/andor_sdk2"] = r"./Andor_Driver_Pack_2"
import pylablib.devices.Andor as Andor


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
            except Exception as e:
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

        self.cameras = []
        self.__identify_cameras__()
        self.cameras_dict = {}
        self.camera_serials = ["13703", "12606", "12574", "13251"]


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

        self.config_dir = os.path.join(os.getcwd(), "configs")
        os.makedirs(self.config_dir, exist_ok=True)
        self.create_ui()
        # self.checking_connected_cams_temp()
        # self.check_camera_conection()

    def __identify_cameras__(self):
        try:
            num_cameras = Andor.get_cameras_number_SDK2()
            print(f"Number of cameras detected: {num_cameras}")
            self.logger.info(f"Number of cameras detected: {num_cameras}")
            if(num_cameras == 0):
                self.cameras = None
                return None

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

        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text="Camera Configuration")

        self.experiment_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.experiment_frame, text="Experiment")

        # Setup the tabs
        self.setup_status_display()
        self.setup_notes_display()
        self.setup_preview_options()
        self.setup_config_display()
        self.setup_experiment_tab()

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

    def setup_config_display(self):
        """Build the Camera Configuration tab with a more organized tabbed layout."""
        self.logger.info("Setting up redesigned camera configuration tab")

        # --- Top toolbar (unchanged) ---
        top_frame = ttk.Frame(self.config_frame, padding=(5, 5))
        top_frame.pack(fill="x", pady=(10, 5), padx=10)
        ttk.Label(top_frame, text="Select Camera:", font=("Helvetica", 12, "bold")).pack(side="left", padx=(0, 5))
        self.selected_camera_var = tk.StringVar(value=None)
        self.camera_selector = ttk.Combobox(
            top_frame, textvariable=self.selected_camera_var, values=list(self.cameras_dict.keys()),
            state="readonly", width=20
        )
        self.camera_selector.pack(side="left", padx=(0, 10))
        self.camera_selector.bind("<<ComboboxSelected>>", self._update_current_camera_display)
        apply_btn = ttk.Button(top_frame, text="Apply to Camera", command=self._apply_camera_config)
        apply_btn.pack(side="left", padx=(0, 5))
        reset_btn = ttk.Button(top_frame, text="Reset to Defaults", command=self._reset_camera_config)
        reset_btn.pack(side="left")

        # --- Two-column main layout (unchanged) ---
        content_frame = ttk.Frame(self.config_frame)
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)
        content_frame.columnconfigure(0, weight=2)
        content_frame.columnconfigure(1, weight=1)

        # --- Left column: New Tabbed Notebook for settings ---
        left_frame = ttk.LabelFrame(content_frame, text="Configuration Editor", padding=10)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        config_notebook = ttk.Notebook(left_frame)
        config_notebook.pack(fill="both", expand=True)

        # Create the individual tabs
        tab_acq = ttk.Frame(config_notebook, padding=10)
        tab_shift = ttk.Frame(config_notebook, padding=10)
        tab_gain = ttk.Frame(config_notebook, padding=10)
        tab_cooling = ttk.Frame(config_notebook, padding=10)

        config_notebook.add(tab_acq, text="Acquisition")
        config_notebook.add(tab_shift, text="Shift/Image")
        config_notebook.add(tab_gain, text="Gain/Shutter")
        config_notebook.add(tab_cooling, text="Cooling")

        # --- Right column: Current camera config viewer (unchanged) ---
        right_frame = ttk.LabelFrame(content_frame, text="Current Camera Configuration", padding=10)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.camera_config_text = tk.Text(right_frame, wrap="none", height=30, state="disabled")
        self.camera_config_text.pack(fill="both", expand=True)
        self._display_camera_config_text("No camera selected")

        # --- Helper function to create a widget ---
        def create_widget(parent, key, value, prefix=""):
            full_key = f"{prefix}.{key}" if prefix else key
            frame = ttk.Frame(parent)
            frame.pack(fill="x", pady=2)
            
            label_text = key.replace("_", " ").title()
            ttk.Label(frame, text=label_text, width=20).pack(side="left", anchor="w")

            if isinstance(value, list):
                var = tk.StringVar(value=value[0])
                self.config_vars[full_key] = var
                ttk.Combobox(frame, textvariable=var, values=value, state="readonly").pack(side="left", fill="x", expand=True)
            elif isinstance(value, dict):
                # For nested dicts, create a sub-frame
                sub_frame = ttk.LabelFrame(parent, text=label_text, padding=10)
                sub_frame.pack(fill="x", expand=True, pady=5, padx=5)
                for sub_key, sub_value in value.items():
                    create_widget(sub_frame, sub_key, sub_value, prefix=full_key)
            else: # String, int, float
                var_type = tk.DoubleVar if isinstance(value, float) else (tk.IntVar if isinstance(value, int) else tk.StringVar)
                var = var_type(value=value)
                self.config_vars[full_key] = var
                ttk.Entry(frame, textvariable=var).pack(side="left", fill="x", expand=True)

        # --- Populate the tabs with widgets ---
        if self.cam_config_options_json:
            # Define which top-level keys go into which tab
            tab_map = {
                "acquisitionMode": tab_acq, "triggeringMode": tab_acq, "readoutMode": tab_acq,
                "exposureTime": tab_acq, "acquisitionNumber": tab_acq, "KineticSeriesLength": tab_acq,
                "KineticCycleTime": tab_acq,
                
                "frameTransfer": tab_shift, "verticalShift": tab_shift, "horizontalShift": tab_shift,
                "baselineClamp": tab_shift,

                "emGain": tab_gain, "shutterSettings": tab_gain,

                "fanLevel": tab_cooling, "temperatureSetpoint": tab_cooling
            }
            
            for key, value in self.cam_config_options_json.items():
                parent_tab = tab_map.get(key)
                if parent_tab:
                    create_widget(parent_tab, key, value)
        else:
            ttk.Label(config_notebook, text="No configuration JSON loaded").pack(pady=20)

    def check_if_idx_connected_already(self, cam_index : int):
        for sn, cam in self.cameras_dict.items():
            if cam.idx == cam_index and cam.is_opened():
                return True
        return False

    def _display_camera_config_text(self, text: str):
        """Helper to safely update the right-side text box."""
        self.camera_config_text.config(state="normal")
        self.camera_config_text.delete(1.0, tk.END)
        self.camera_config_text.insert(tk.END, text)
        self.camera_config_text.config(state="disabled")

    def setup_experiment_tab(self):
        """Sets up the UI for the Experiment tab."""
        self.logger.info("Setting up experiment tab")

        # --- Title ---
        experiment_title = ttk.Label(self.experiment_frame, text="Parallel Camera Experiment", font=("Arial", 14, "bold"))
        experiment_title.pack(pady=10)

        # --- Status Display ---
        status_frame = ttk.LabelFrame(self.experiment_frame, text="Camera Status", padding=10)
        status_frame.pack(fill="x", padx=20, pady=10)

        self.experiment_status_labels = {}
        for i, serial in enumerate(self.camera_serials):
            frame = ttk.Frame(status_frame)
            frame.pack(fill=tk.X, pady=5)
            
            label = ttk.Label(frame, text=f"Camera {i+1} ({serial}):")
            label.pack(side=tk.LEFT, padx=5)
            
            status_label = ttk.Label(frame, text="Not Ready", font=("Arial", 12))
            status_label.pack(side=tk.LEFT, padx=20)
            
            self.experiment_status_labels[serial] = status_label

        # --- Controls ---
        control_frame = ttk.Frame(self.experiment_frame)
        control_frame.pack(fill="x", padx=20, pady=10)

        self.run_experiment_btn = ttk.Button(control_frame, text="Run Experiment", command=self.run_experiment)
        self.run_experiment_btn.pack(side=tk.LEFT, padx=5)

        ttk.Label(control_frame, text="Acquisition Mode:").pack(side=tk.LEFT, padx=(10, 5))
        self.acq_mode_var = tk.StringVar(value="Kinetic Series")
        acq_mode_cb = ttk.Combobox(control_frame, textvariable=self.acq_mode_var, values=["Single Scan", "Kinetic Series"], state="readonly", width=15)
        acq_mode_cb.pack(side=tk.LEFT)
        acq_mode_cb.bind("<<ComboboxSelected>>", self._on_acq_mode_change)


        self.num_frames_label = ttk.Label(control_frame, text="Number of Frames:")
        self.num_frames_label.pack(side=tk.LEFT, padx=(10, 5))
        self.num_frames_var = tk.StringVar(value="10")
        self.num_frames_entry = ttk.Entry(control_frame, textvariable=self.num_frames_var, width=10)
        self.num_frames_entry.pack(side=tk.LEFT)

        # --- Log Area ---
        log_frame = ttk.LabelFrame(self.experiment_frame, text="Experiment Log", padding=10)
        log_frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.experiment_log = tk.Text(log_frame, height=10, wrap=tk.WORD, state="disabled")
        self.experiment_log.pack(fill="both", expand=True)

    def _on_acq_mode_change(self, event=None):
        """Handles changes in the acquisition mode dropdown."""
        mode = self.acq_mode_var.get()
        if mode == "Single Scan":
            self.num_frames_entry.config(state="disabled")
            self.num_frames_var.set("1")
        else: # Kinetic Series
            self.num_frames_entry.config(state="normal")

    def run_experiment(self):
        """Runs the parallel camera acquisition experiment."""
        self.run_experiment_btn.config(state="disabled")
        self._log_experiment("Starting experiment...")

        if not self._pre_experiment_check():
            self._log_experiment("Pre-experiment check failed. Aborting.")
            self.run_experiment_btn.config(state="normal")
            return

        self._log_experiment("All cameras are ready. Starting acquisition threads...")

        threads = []
        for serial, camera in self.cameras_dict.items():
            thread = threading.Thread(target=self._acquisition_thread_worker, args=(camera,), daemon=True)
            threads.append(thread)
            thread.start()

        # We can optionally add a thread to monitor the completion of all acquisition threads
        monitor_thread = threading.Thread(target=self._monitor_experiment_completion, args=(threads,), daemon=True)
        monitor_thread.start()

    def _pre_experiment_check(self):
        """Checks if all cameras are connected and configured."""
        self._log_experiment("Performing pre-experiment check...")
        all_ready = True
        
        # if len(self.cameras_dict) != 4:
        #     self._log_experiment(f"Error: Expected 4 connected cameras, but found {len(self.cameras_dict)}.")
        #     all_ready = False

        for serial, label in self.experiment_status_labels.items():
            if serial in self.cameras_dict:
                camera = self.cameras_dict[serial]
                if camera.connection_status == CameraState.CONNECTED and camera.is_configured == CameraState.CONFIGURED:
                    label.config(text="Ready", foreground="green")
                else:
                    status_text = f"Not Ready (Connected: {camera.connection_status.name}, Configured: {camera.is_configured.name})"
                    label.config(text=status_text, foreground="red")
                    all_ready = False
            else:
                label.config(text="Not Connected", foreground="red")
                all_ready = False
        
        # return all_ready
        return True #TODO remove this after debugging. Update this function to allow for only the cameras ready to go
    def _acquisition_thread_worker(self, camera):
        """The function that each camera thread will execute."""
        serial = camera.serialNumber
        try:
            self._log_experiment(f"[{serial}] Starting acquisition.")
            self.experiment_status_labels[serial].config(text="Acquiring", foreground="orange")

            acq_mode = self.acq_mode_var.get()

            if acq_mode == "Kinetic Series":
                try:
                    num_frames = int(self.num_frames_var.get())
                    if num_frames <= 0:
                        raise ValueError("Number of frames must be positive.")
                except ValueError as e:
                    self._log_experiment(f"[{serial}] Invalid number of frames: {self.num_frames_var.get()}. Aborting. Error: {e}")
                    self.experiment_status_labels[serial].config(text="Error", foreground="red")
                    return

                camera.setup_acquisition(mode="kinetic", nframes=num_frames)
                camera.start_acquisition()
                
                # Wait for acquisition to finish by polling
                for i in range(num_frames):
                    camera.wait_for_frame()
                
                self._log_experiment(f"[{serial}] Acquisition finished. Reading {num_frames} frames...")

                # Read all frames from buffer
                frames = []
                for i in range(num_frames):
                    frame = camera.read_newest_image(return_info=False)
                    if frame is not None:
                        frames.append(frame)
                
                if not frames:
                    raise RuntimeError("Acquired no frames from the camera.")

                data = np.stack(frames)

            elif acq_mode == "Single Scan":
                camera.setup_acquisition(mode="single", nframes=1)
                self._log_experiment(f"[{serial}] Snapping single image...")
                data = camera.snap(timeout=5) # 10 second timeout for a single snap
                print(f"size of data image: {data.shape} | serial: {serial}")
                self._log_experiment(f"[{serial}] Single image snapped.")

            else:
                raise ValueError(f"Unknown acquisition mode: {acq_mode}")

            
            self._log_experiment(f"[{serial}] Saving data to FITS file.")
            
            header_text = self.notes_text.get("1.0", tk.END)
            save_path = os.path.join(os.getcwd(), "Data")
            os.makedirs(save_path, exist_ok=True)
            
            save_fits_data(data, savepath=save_path, header_text=header_text, serial=serial)
            
            self.experiment_status_labels[serial].config(text="Finished", foreground="blue")
            self._log_experiment(f"[{serial}] Data saved successfully.")

        except Exception as e:
            self.experiment_status_labels[serial].config(text="Error", foreground="red")
            self._log_experiment(f"[{serial}] Error: {e}")
        
    def _monitor_experiment_completion(self, threads):
        """Waits for all acquisition threads to complete."""
        for thread in threads:
            thread.join()
        
        self._log_experiment("All cameras have finished their tasks. Experiment complete.")
        self.run_experiment_btn.config(state="normal")

    def _log_experiment(self, message):
        """Logs a message to the experiment log text widget."""
        self.experiment_log.config(state="normal")
        self.experiment_log.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
        self.experiment_log.see(tk.END)
        self.experiment_log.config(state="disabled")

    def _update_current_camera_display(self, event=None):
        """When a camera is selected, load its JSON file (or create one if missing) and display."""
        serial = self.selected_camera_var.get()
        if not serial:
            self._display_camera_config_text("No camera selected.")
            return

        cfg_path = os.path.join(self.config_dir, f"{serial}_config.json")

        # Load or create config file
        if os.path.exists(cfg_path):
            with open(cfg_path, "r") as f:
                cam_cfg = json.load(f)
            self.logger.info(f"Loaded config for camera {serial}")
        else:
            # Create a new config from template defaults
            cam_cfg = self._get_default_config_from_template(self.cam_config_options_json)
            with open(cfg_path, "w") as f:
                json.dump(cam_cfg, f, indent=2)
            self.logger.info(f"Created new config file for camera {serial}")

        # Populate UI fields
        self._populate_config_fields_from_dict(cam_cfg)

        #update the selected camera with the config settings
        self.cameras_dict[serial].camera_configuration(configDict = cam_cfg)
        if(self.cameras_dict[serial].is_configured != CameraState.CONFIGURED):
            self._display_camera_config_text(f"ERROR: Camera {serial} was not configured upon selection. Please continue with camera configuration.")
        else:
            self._display_camera_config_text(json.dumps(cam_cfg, indent=2))

    def _apply_camera_config(self):
        """Apply current UI settings and save to camera-specific JSON file."""
        serial = self.selected_camera_var.get()
        if not serial:
            messagebox.showwarning("No Camera", "Please select a camera first.")
            return

        cfg_path = os.path.join(self.config_dir, f"{serial}_config.json")

        # Gather all config values from UI
        all_values = {key: var.get() for key, var in self.config_vars.items()}
        # Convert from dot notation back to nested JSON
        new_cfg = self._unflatten_config(all_values)

        # Save to file
        with open(cfg_path, "w") as f:
            json.dump(new_cfg, f, indent=2)

        self.logger.info(f"Saved updated config for camera {serial}")
        self._display_camera_config_text(json.dumps(new_cfg, indent=2))

        self.cameras_dict[serial].camera_configuration(configDict = new_cfg)

    def _unflatten_config(self, flat_dict):
        """Convert {'a.b.c': 1} back into nested dict structure."""
        result = {}
        for compound_key, value in flat_dict.items():
            parts = compound_key.split(".")
            d = result
            for part in parts[:-1]:
                d = d.setdefault(part, {})
            d[parts[-1]] = value
        return result

    def _reset_camera_config(self):
        """Reset UI fields to the default JSON-provided values."""
        for key, var in self.config_vars.items():
            parts = key.split(".")
            data = self.cam_config_options_json
            try:
                for part in parts:
                    data = data[part]
                if isinstance(data, (list, tuple)):
                    var.set(data[0])
                else:
                    var.set(data)
            except Exception:
                pass
        self.logger.info("Reset configuration UI to defaults.")

    def _populate_config_fields_from_dict(self, config_dict, prefix=""):
        """Recursively populate UI fields from a dict (based on dot notation keys)."""
        for key, value in config_dict.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                self._populate_config_fields_from_dict(value, full_key)
            else:
                var = self.config_vars.get(full_key)
                if var is not None:
                    try:
                        var.set(value)
                    except Exception:
                        pass

    def _get_default_config_from_template(self, template_dict):
        """Return a concrete config dict (choose first item from lists, use numbers/strings as-is)."""
        result = {}
        for key, value in template_dict.items():
            if isinstance(value, list):
                result[key] = value[0]
            elif isinstance(value, dict):
                result[key] = self._get_default_config_from_template(value)
            else:
                result[key] = value
        return result

    def get_camera_config(self):
        """Return a dict of all current config values."""
        result = {}
        for key, var in self.config_vars.items():
            result[key] = var.get()
        return result

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
            if hasattr(self, "camera_selector"):
                self.camera_selector['values'] = camera_list
                if camera_list:
                    self.camera_selector.current(0)
                else:
                    self.camera_selector.set("")
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
            if num_cameras > 0:
                for i in range(num_cameras):
                    if not self.check_if_idx_connected_already(i):
                        cam = Camera(idx=i, temperature=-25, fan_mode='full', amp_mode=None)
                        if cam.connection_status == CameraState.CONNECTED:
                            try:
                                info = cam.get_device_info()
                                cam.serialNumber = str(info[2])
                                cam.head_model = info[1]
                                cam.controller_mode = info[0]
                                self.cameras.append(cam)
                                self.cameras_dict.update( {cam.serialNumber: cam} )


                                self.camera_status_labels[cam.serialNumber]["status_label"].config(text="Connected", foreground="green")
                                self.camera_status_labels[cam.serialNumber]["serial_label"].config(fg="green")
                                self.logger.info(f"Camera {cam.serialNumber} connected successfully.")

                                self.logger.info(f"Successfully identified camera {cam.idx}")
                                self.logger.info(f"     Serial number: {cam.serialNumber}")
                                self.logger.info(f"     Model: {cam.head_model}")
                                self.logger.info(f"     Controller Mode: {cam.controller_mode}")
                            except Exception as e:
                                self.logger.error(f"Error connecting to camera at index {i}: {e}")
                                cam.close()
                        else:
                            self.logger.error(f"Failed to connect to camera {cam.serialNumber}.")
        except Exception as e:
            self.logger.error(f"Failed within connecting to all cameras {e}")
            if self.logger.level == log.DEBUG:
                print(f"Failed to connect cameras: {e}")
        self.update_UI_elements()

    def disconnect_all_cameras(self):
        """Disconnect all cameras and update their status."""
        self.logger.info("Disconnecting all cameras...")
        serials = list(self.cameras_dict.keys())
        for serial in serials:
            cam = self.cameras_dict[serial]
            try:
                if cam.disconnect():
                    self.camera_status_labels[serial]["status_label"].config(text="Disconnected", foreground="black")
                    self.camera_status_labels[serial]["serial_label"].config(fg="red")
                    self.logger.info(f"Camera {serial} disconnected.")
                    self.cameras_dict.pop(serial)
                else:
                    self.camera_status_labels[serial]["status_label"].config(text="Error", foreground="black")
                    self.camera_status_labels[serial]["serial_label"].config(fg="red")
            except Exception as e:
                self.camera_status_labels[serial]["status_label"].config(text="Error", fg="red")
                self.logger.error(f"Error disconnecting from camera {serial}: {e}")
        self.update_UI_elements()

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
                    self.config_labels_dict[key][k2].config(text=new_val)
                    self.cameras_dict[serialNumber].cam_config[key][k2] = new_val
            # else:
            #     try:
            #         var = self.config_vars.get(key, None)
            #         if var is not None and not isinstance(var, dict):
            #             new_val = var.get()
            #         else:
            #             new_val = self.config_entrys_dict[key].get()
            #     except Exception:
            #         new_val = self.config_entrys_dict[key].get()

                self.config_labels_dict[key].config(text=new_val)
                self.cameras_dict[serialNumber].cam_config[key] = new_val

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

    def toggle_preview(self, start):
        """Start or stop the live preview."""
        serial = self.preview_camera.get()

        if start and not getattr(self, "preview_running", False):
            self.preview_running = True
            self.preview_canvas.config(text=f"Starting preview for camera {serial}...", image="")
            self.preview_select.configure(state="disabled")
            self.start_camera_preview(serial)

        elif not start and getattr(self, "preview_running", True):
            self.preview_running = False
            self.preview_select.configure(state="readonly")
            self.preview_canvas.config(text="Preview stopped", image="")

    def start_camera_preview(self, serial):
        """Start live camera preview loop"""
        self.preview_cam = self.cameras_dict[serial]
        try:
            self.preview_cam.start_acquisition()
            self.preview_thread = threading.Thread(target=self.live_loop, daemon=True)
            self.preview_thread.start()
        except Exception as e:
            self.preview_canvas.config(text=f"Failed to start camera: {e}")
            self.preview_running = False
            return

    def _handle_captured_image(self, frame):
        # --- Fast min/max normalization ---
        fmin = frame.min()
        fmax = frame.max()
        if fmax - fmin < 1:
            fmax = fmin + 1
        frame_8 = ((frame - fmin) / (fmax - fmin) * 255).astype(np.uint8)

        # --- Fast rotate using OpenCV ---
        frame_rot = cv2.rotate(frame_8, cv2.ROTATE_90_COUNTERCLOCKWISE)

        # --- Fast resize using OpenCV ---
        frame_small = cv2.resize(frame_rot, (self.preview_width, self.preview_height))

        # --- Convert to Tkinter object ---
        imgtk = ImageTk.PhotoImage(Image.fromarray(frame_small))

        return imgtk, Image.fromarray(frame_rot)

    def live_loop(self):
        try:
            while self.preview_running:
                self.preview_cam.wait_for_frame(timeout=5)
                frame = self.preview_cam.read_newest_image()
                if frame is None:
                    continue

                imgtk, _ = self._handle_captured_image(frame)
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

    def capture_image(self):
        """Capture an image from the selected camera"""
        serial = self.preview_camera.get()
        cam = self.cameras_dict[serial]
        self.vmin, self.vmax = None, None

        if not cam.acquisition_in_progress():
            # Grab image (ensure it's 2D)
            cam.setup_acquisition(mode="snap", nframes=1)
            image = np.squeeze(cam.snap())
            print("Captured image shape:", image.shape)


            imgtk, img = self._handle_captured_image(frame=image)
            self.update_preview_display(imgtk)

        else:
            self.logger.warning(f"Camera {cam.serialNumber} is already acquiring an image")
            messagebox.showwarning(f"Camera {cam.serialNumber} is already acquiring an image. Please wait")

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
                if cam.get_camera_connetion_status == CameraState.CONNECTED:
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

    def checking_connected_cams_temp(self):
        print("#-------Camera Temperatures-------#")
        for serial, cam in self.cameras_dict.items():
            print(f"     Cam {cam.serialNumber} --> {cam.get_temperature()} C | Setpoint : {cam.temperature_setpoint} C")
        self.root.after(ms=2000, func=self.checking_connected_cams_temp)




def check_dll_files(path, dll_names):
    """
    Check whether specified DLL files exist in a given directory.

    Args:
        path (str): Directory path to check.
        dll_names (list[str]): List of DLL file names (e.g. ['atmcd64d.dll', 'atcore.dll']).

    Returns:
        dict[str, bool]: Dictionary mapping each DLL name to True (found) or False (missing).
    """
    results = {}
    if not os.path.isdir(path):
        print(f"❌ Directory not found: {path}")
        return {dll: False for dll in dll_names}

    for dll in dll_names:
        dll_path = os.path.join(path, dll)
        results[dll] = os.path.isfile(dll_path)

    # Print a simple summary
    print(f"\nChecking DLLs in: {path}")
    for dll, exists in results.items():
        status = "✅ Found" if exists else "❌ Missing"
        print(f"  {dll:<20} {status}")

    return results


def main():
    args = sys.argv #pass in command line arguments.
    if len(args) > 1 and (args[1] == "--help" or args[1] == '-h' or args[1] == '-H'):
        print("Usage: python main.py [-d]")
        print("Options:")
        print("  -d    Enable debug logging")
        return
    
    
    debug_mode = "-d" in args 


    required_dll = ["atmcd64d.dll", "ATMCD64CS.dll"]
    project_dir = os.path.dirname(os.path.abspath(__file__))
    dll_dir = os.path.join(project_dir, "Andor_Driver_Pack_2")
    if not check_dll_files(dll_dir, required_dll):
        raise Exception(f"DLL files NOT found in {dll_dir}. Program will not work without. Please specify the absolute path to dll's.")

    with open(path_to_config_options_json, "r") as f:
        cam_config_options_json = json.load(f)
    
    
    root = tk.Tk()
    app = CameraMonitorApp(root, debugLogging=debug_mode, cam_config_options_json=cam_config_options_json)
    root.mainloop()


if __name__ == "__main__":
    main()