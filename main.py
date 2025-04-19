'''
Author: Matthew Buchkowski
Department: Physics - Astronomy
Description: Main executable frontend for handing the iXAndor cameras.


'''


import tkinter as tk
from tkinter import filedialog
from tkinter import ttk, messagebox
from tkinter.messagebox import showinfo
import threading
import time
from queue import Queue
from typing import Dict, List
from backend.cameraHandle import *
from backend.cameraConfig import *
from backend.cameraDataHandle import *


save_data_path = ""





class CameraDrivers:
    def get_camera_status(self, serial_number):
        """
        Placeholder function to get camera status.
        Returns True if camera is working, False otherwise.
        Replace with your actual implementation.
        """
        # Simulating random status - replace with your actual implementation
        import random
        return random.choice([True, False])
    
    def get_camera_serial_numbers(self):
        """
        Placeholder function to get all camera serial numbers.
        Replace with your actual implementation.
        """
        # Simulating 4 camera serial numbers - replace with your actual implementation
        return ["1234567", "7654321", "9876543", "5432109"]
    
    def capture_image(self, serial_number):
        """
        Placeholder function to capture image from a specific camera.
        Replace with your actual implementation.
        """
        print(f"Capturing image from camera {serial_number}")
        # Simulating success - replace with your actual implementation
        return True
    
    def configure_camera(self, serial_number, settings):
        """
        Placeholder function to configure a specific camera.
        Replace with your actual implementation.
        """
        print(f"Configuring camera {serial_number} with settings: {settings}")
        # Simulating success - replace with your actual implementation
        return True

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
    def __init__(self, root):
        self.root = root
        self.root.title("Camera Monitoring System")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)
        
        # Initialize camera drivers: TODO Change this to the actual camera driver library.
        # self.camera1 = AndoriXonCamera(camIndex=0, serialNumber=13703)
        # self.camera2 = AndoriXonCamera(camIndex=1, serialNumber=12345)
        # self.camera3 = AndoriXonCamera(camIndex=2, serialNumber=67890)
        # self.camera4 = AndoriXonCamera(camIndex=3, serialNumber=13579)
        # self.cameras = [self.camera1, self.camera2, self.camera3, self.camera4]
        self.cameras = [] #TODO remove this later.
        # Get camera serial numbers: TODO change this to search for all connected devices and find the cameras that way
        # self.camera_serials = [self.camera1.serialNumber, self.camera2.serialNumber, self.camera3.serialNumber, self.camera4.serialNumber]
        self.camera_serials = ["1234567", "7654321", "9876543", "5432109"]
        # Create UI elements
        self.create_ui()
        
        
        self.monitoring = True
        self.monitor_thread = None
        
        self.camera_queues: Dict[str, Queue] = {}
        self.camera_workers: Dict[str, CameraWorker] = {}
        self.running_experiment = False
        self.running_acquisition = False
        
        self.has_run_experiment = False

        self.queryingConnection = False
        
    def setup_camera_workers(self):
        """Initialize worker threads for each camera"""
        for camera in self.cameras:
            queue = Queue()
            worker = CameraWorker(camera, queue)
            self.camera_queues[camera.serialNumber] = queue
            self.camera_workers[camera.serialNumber] = worker
            
    def create_ui(self):
        """Create the main UI elements"""
        # Create the main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create notebook for different views
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create the camera status tab
        self.status_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.status_frame, text="Camera Status")
        
        # Create camera configuration tab
        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text="Camera Configuration")
        
        self.notes_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.notes_frame, text="FITS Header")
        
        
        # # Create camera preview tab: TODO may add this back later as a sanity check when using the cameras right before a run.
        # self.preview_frame = ttk.Frame(self.notebook)
        # self.notebook.add(self.preview_frame, text="Camera Preview")
        
        # Setup the camera status display
        self.setup_status_display()
        
        # Setup the camera configuration options
        self.setup_config_options()
        
        self.setup_notes_display()
        
        # # Setup the camera preview options
        # self.setup_preview_options()
        
        # Button frame at the bottom
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.pack(fill=tk.X, pady=10)
        
        # Refresh button
        self.refresh_btn = ttk.Button(self.button_frame, text="Refresh", command=self.refresh_all)
        self.refresh_btn.pack(side=tk.RIGHT, padx=5)
        
        # Exit button
        self.exit_btn = ttk.Button(self.button_frame, text="Exit", command=self.exit_app)
        self.exit_btn.pack(side=tk.RIGHT, padx=5)
        
        #Save Button
        self.save_btn = ttk.Button(self.button_frame, text="Save", command=self.save_data)
        self.save_btn.pack(side=tk.RIGHT, padx=5)
        
    def save_data(self):
        if self.has_run_experiment:
            attempt, result_str = False, ""
            try:
                save_data_path = filedialog.askdirectory(
                    title="Select Directory to Save Data",
                    initialdir="."  # Starts in current directory
                )
                
                curr_header = self.notes_text.get("1.0", tk.END)
                curr_data = [cam.data for cam in self.cameras]
                
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
                else:
                    messagebox.showerror("Error", result_str)
        else:
            messagebox.showerror("Error", "No experiment data to save. Please run an experiment first.")


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
            self.camera_labels (dict): A dictionary mapping each camera's serial number to its
                                       corresponding labels for serial and status.
        Note:
            This method assumes that `self.status_frame` is a valid tkinter frame and that
            `self.camera_serials` is a list of camera serial numbers.
        """
        """Setup the camera status display"""
        # Title label
        status_title = ttk.Label(self.status_frame, text="Camera Status Monitor", font=("Arial", 14, "bold"))
        status_title.pack(pady=10)
        
        # Frame for camera status
        status_display_frame = ttk.Frame(self.status_frame)
        status_display_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Create labels for each camera
        self.camera_labels = {}
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
            
            self.camera_labels[serial] = {
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
        camera_select.bind('<<ComboboxSelected>>', self.on_camera_selected)
        
        # Settings frame
        settings_frame = ttk.LabelFrame(self.config_frame, text="Camera Settings")
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Example settings - replace with your actual camera settings
        # Exposure
        exposure_frame = ttk.Frame(settings_frame)
        exposure_frame.pack(fill=tk.X, pady=5)
        ttk.Label(exposure_frame, text="Exposure:").pack(side=tk.LEFT, padx=5)
        self.exposure_var = tk.DoubleVar(value=10.0)
        
        self.exposure_text = ttk.Entry(exposure_frame, text = "Enter your text here: ")
        # exposure_scale = ttk.Scale(exposure_frame, from_=0.1, to=100.0, variable=self.exposure_var, orient=tk.HORIZONTAL, length=300)
        self.exposure_text.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Label(exposure_frame, textvariable=self.exposure_var).pack(side=tk.LEFT, padx=5)
        
        # Gain
        gain_frame = ttk.Frame(settings_frame)
        gain_frame.pack(fill=tk.X, pady=5)
        ttk.Label(gain_frame, text="Gain:").pack(side=tk.LEFT, padx=5)
        self.gain_var = tk.DoubleVar(value=1.0)
        gain_scale = ttk.Scale(gain_frame, from_=0.0, to=10.0, variable=self.gain_var, orient=tk.HORIZONTAL, length=300)
        gain_scale.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Label(gain_frame, textvariable=self.gain_var).pack(side=tk.LEFT, padx=5)
        
        # Save settings button
        save_btn = ttk.Button(settings_frame, text="Apply Settings", command=self.apply_settings)
        save_btn.pack(pady=10)
    
    def setup_preview_options(self):
        """Setup the camera preview options"""
        # Title label
        preview_title = ttk.Label(self.preview_frame, text="Camera Preview", font=("Arial", 14, "bold"))
        preview_title.pack(pady=10)
        
        # Camera selection frame
        preview_selection_frame = ttk.Frame(self.preview_frame)
        preview_selection_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(preview_selection_frame, text="Select Camera:").pack(side=tk.LEFT, padx=5)
        
        # Camera selection combobox
        self.preview_camera = tk.StringVar()
        preview_select = ttk.Combobox(preview_selection_frame, textvariable=self.preview_camera)
        preview_select['values'] = self.camera_serials
        preview_select.current(0)
        preview_select.pack(side=tk.LEFT, padx=5)
        
        # Preview frame
        preview_display_frame = ttk.LabelFrame(self.preview_frame, text="Live Preview")
        preview_display_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Placeholder for camera preview (you would replace this with actual preview)
        self.preview_placeholder = tk.Label(preview_display_frame, text="No Preview Available", 
                                          bg="black", fg="white", height=20)
        self.preview_placeholder.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)
        
        # Preview control buttons
        preview_control_frame = ttk.Frame(self.preview_frame)
        preview_control_frame.pack(fill=tk.X, pady=10, padx=20)
        
        start_preview_btn = ttk.Button(preview_control_frame, text="Start Preview", 
                                     command=lambda: self.toggle_preview(True))
        start_preview_btn.pack(side=tk.LEFT, padx=5)
        
        stop_preview_btn = ttk.Button(preview_control_frame, text="Stop Preview", 
                                    command=lambda: self.toggle_preview(False))
        stop_preview_btn.pack(side=tk.LEFT, padx=5)
        
        capture_btn = ttk.Button(preview_control_frame, text="Capture Image", 
                               command=self.capture_image)
        capture_btn.pack(side=tk.LEFT, padx=5)
    
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
                            command=self.save_notes)
        save_btn.pack(side=tk.LEFT, padx=5)
        
        load_btn = ttk.Button(button_frame, text="Load Header", 
                            command=self.load_notes)
        load_btn.pack(side=tk.LEFT, padx=5)

    def save_notes(self):
        """Save the notes to a file using file dialog"""
        file_path = filedialog.asksaveasfilename(
            title="Save Notes As",
            defaultextension=".txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ],
            initialdir="."  # Starts in current directory
        )
        
        if file_path:  # Only proceed if a file path was selected (not cancelled)
            notes_content = self.notes_text.get("1.0", tk.END)
            try:
                with open(file_path, "w") as f:
                    f.write(notes_content)
                messagebox.showinfo("Success", "Notes saved successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save notes: {str(e)}")

    def load_notes(self):
        """Load notes from a file using file dialog"""
        file_path =  filedialog.askopenfilename(
            title="Select Notes File",
            filetypes=[
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ],
            initialdir="."  # Starts in current directory
        )
        
        if file_path:  # Only proceed if a file was selected (not cancelled)
            try:
                with open(file_path, "r") as f:
                    content = f.read()
                    self.notes_text.delete("1.0", tk.END)
                    self.notes_text.insert("1.0", content)
                messagebox.showinfo("Success", "Notes loaded successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load notes: {str(e)}")

    def update_acquisition_status(self):
        """Update the status of each camera periodically"""
        if(self.running_experiment):
            self.monitoring = False
            return
        
        while self.monitoring:
            for serial in self.camera_serials:
                status = self.camera_drivers.get_camera_status(serial)
                
                # Use after() to update UI from the main thread
                self.root.after(0, self.refresh_all())

            # Sleep for a while before next update
            time.sleep(2)

    def update_camera_ui(self, serial, status):
        """Update the UI elements for a camera based on its status"""
        if serial in self.camera_labels:
            labels = self.camera_labels[serial]

            # Update serial number color based on status
            if status:
                labels["serial_label"].config(fg="green")
                labels["status_label"].config(text="Connected")
            else:
                labels["serial_label"].config(fg="red")
                val = labels["status_label"]
                val.config(text="Disconnected")


    def refresh_all(self):
        """Refresh all camera statuses"""
        self.queryingConnection = True
        for i, serial in enumerate(self.camera_serials):
            try:
                self.update_camera_ui(serial, self.cameras[i].connection_status())
            except Exception as e:
                self.update_camera_ui(serial, False)
        self.queryingConnection = False
        self.status_frame.update()


    def connect_all_cameras(self):
        """Connect to all cameras - placeholder function"""
        
        for i, serial in enumerate(self.camera_serials):
                            
            try:
                tmp_cam = AndoriXonCamera(camIndex=i, serialNumber=serial)
                if tmp_cam.connect():
                    self.cameras[i] = tmp_cam
                else:
                    messagebox.showerror("Error", f"Failed to connect to camera {serial}")
                    continue
            except Exception as e:
                messagebox.showerror("Error", f"Failed to connect to camera {serial}: {str(e)}")
                continue    
        
        self.refresh_all()
                
    def disconnect_all_cameras(self):
        """Disconnect all cameras - placeholder function"""
        
        for i, serial in enumerate(self.camera_serials):
            try:
                self.camera_labels[serial]['status_label'].config(text="Disconnected")
                self.camera_labels[serial]['serial_label'].config(fg="red")             
                self.cameras[i].disconnect()
            except Exception as e: 
                messagebox.showerror("Error", f"Failed to disconnect camera {serial}: {str(e)}")
                continue        

        self.refresh_all()
        
    def on_camera_selected(self, event):
        """Handle camera selection change"""
        # Load the settings for the selected camera - implement this with your actual logic
        serial = self.selected_camera.get()
        messagebox.showinfo("Camera Selected", f"Loading settings for camera {serial}")

        # Here you would update the UI elements with the selected camera's settings

    def apply_settings(self):
        """Apply settings to the selected camera"""
        serial = self.selected_camera.get()
        settings = {
        "exposure": self.exposure_text.get(),
        "gain": self.gain_var.get()
        }
        print(settings['exposure'])
        # success = self.camera_drivers.connection_status(serial, settings)

        # if success:
        #     messagebox.showinfo("Success", f"Settings applied to camera {serial}")
        # else:
        #     messagebox.showerror("Error", f"Failed to apply settings to camera {serial}")

    def toggle_preview(self, start):
        """Toggle camera preview on/off"""
        serial = self.preview_camera.get()

        if start:
            self.preview_placeholder.config(text=f"Starting preview for camera {serial}...")
            # Here you would implement the actual preview functionality
        else:
            self.preview_placeholder.config(text="Preview stopped")
            # Here you would stop the preview

    def capture_image(self):
        """Capture an image from the selected camera"""
        serial = self.preview_camera.get()

        success = self.camera_drivers.capture_image(serial)

        if success:
            messagebox.showinfo("Capture", f"Image captured from camera {serial}")
        else:
            messagebox.showerror("Error", f"Failed to capture image from camera {serial}")

    def exit_app(self):
        """Clean exit of the application"""
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
                camera.acquisition_configuration()
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
    
  
def main():
    root = tk.Tk()
    app = CameraMonitorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()