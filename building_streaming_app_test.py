import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import numpy as np
from pylablib.devices import Andor
from backend.cameraConfig import *
from backend.cameraDataHandle import *

class SimpleCameraApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Simple Camera Capture")
        self.root.geometry("800x600")

        # Initialize cameras as SDK2 objects
        self.cameras = []
        # try:
        #     num = Andor.get_cameras_number_SDK2()
        #     for i in range(num):
        #         cam = Andor.AndorSDK2Camera(idx=i)
        #         self.cameras.append(cam)
        # except Exception as e:
        #     messagebox.showerror("Error", f"Failed to enumerate cameras: {e}")
        self.cam = AndoriXonCamera()
        self.cam.connect(0)
        self.cameras.append(self.cam)

        # Populate combobox with camera serial numbers
        self.camera_var = tk.StringVar()
        serials = "13703"
        self.camera_select = ttk.Combobox(root, textvariable=self.camera_var, state="readonly")
        self.camera_select['values'] = serials
        self.camera_select.pack(pady=10)

        self.connect_btn = ttk.Button(root, text="Connect and Capture", command=self.connect_and_capture)
        self.connect_btn.pack(pady=10)

        self.image_label = tk.Label(root, text="No Image Captured", bg="black", fg="white", width=80, height=25)
        self.image_label.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        self.current_cam = None  # Will hold the selected AndorSDK2Camera instance

    def connect_and_capture(self):

        try:
            self.current_cam = self.cam.cameraObj
            # Configure camera
            self.current_cam.set_exposure(0.04)  # 40 ms exposure
            self.current_cam.setup_acquisition(mode="sequence", nframes=100)
            self.current_cam.start_acquisition()
            # Grab one frame
            # frame = self.current_cam.acquire_frame()  # SDK2: acquire_frame() returns a numpy array
            self.current_cam.wait_for_frame()
            frame = self.current_cam.read_oldest_frame()
            if frame is not None:
                photo = self.array_to_photoimage(frame)
                self.image_label.config(image=photo, text="")
                self.image_label.image = photo  # keep ref to avoid GC
            else:
                messagebox.showerror("Error", "Failed to read image from camera")

            self.current_cam.stop_acquisition()
            self.cam.disconnect()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to capture image: {e}")

    def array_to_photoimage(self, array):
        """Convert NumPy grayscale image to Tkinter PhotoImage"""
        array = np.clip(array, 0, None)
        norm = 255 * (array - np.min(array)) / (np.ptp(array) + 1e-5)
        img = Image.fromarray(norm.astype(np.uint8), mode="L")
        img = img.resize((600, 450), Image.ANTIALIAS)  # Resize for display
        return ImageTk.PhotoImage(img)


if __name__ == "__main__":
    root = tk.Tk()
    app = SimpleCameraApp(root)
    root.mainloop()
