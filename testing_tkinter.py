import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import numpy as np
import threading, time, traceback
from pylablib.devices import Andor


class AndorViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Andor Live Viewer")
        self.root.geometry("800x600")

        # Camera state
        self.cam = None
        self.running = False
        self.thread = None

        # --- UI setup ---
        control_frame = ttk.Frame(root)
        control_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        ttk.Label(control_frame, text="Camera Index:").pack(side=tk.LEFT, padx=5)
        self.cam_index = ttk.Combobox(control_frame, values=[0, 1, 2], width=5)
        self.cam_index.set("0")
        self.cam_index.pack(side=tk.LEFT)

        ttk.Button(control_frame, text="Connect", command=self.connect_camera).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Disconnect", command=self.disconnect_camera).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Start Live", command=self.start_live).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Stop Live", command=self.stop_live).pack(side=tk.LEFT, padx=5)

        self.image_label = ttk.Label(root)
        self.image_label.pack(expand=True, fill=tk.BOTH)

    # ---------------------------
    def connect_camera(self):
        try:
            idx = int(self.cam_index.get())
            self.cam = Andor.AndorSDK2Camera(idx=idx)
            self.cam.set_exposure(0.04)
            self.cam.setup_shutter(mode="open")
            self.cam.set_trigger_mode("int")
            self.cam.set_amp_mode(
                channel=0,
                oamp=0,
                hsspeed=1,
                preamp=1
            )

            self.cam.setup_acquisition(mode="sequence")
            messagebox.showinfo("Camera", f"Connected to camera {idx}")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to connect: {e}")

    def disconnect_camera(self):
        try:
            self.stop_live()
            messagebox.showinfo("Camera", "Disconnected camera")
        except Exception as e:
            messagebox.showerror("Error", f"Disconnect failed: {e}")
        self.cam.close()
    # ---------------------------
    def start_live(self):
        if not self.cam:
            messagebox.showwarning("Warning", "No camera connected")
            return
        if self.running:
            return
        self.cam.setup_acquisition(mode="sequence")
        self.cam.start_acquisition()
        self.running = True
        self.thread = threading.Thread(target=self.live_loop, daemon=True)
        self.thread.start()

    def stop_live(self):
        self.running = False


    def live_loop(self):
        try:
            while self.running:
                self.cam.wait_for_frame(timeout=5)
                frame = self.cam.read_newest_image()  # ← Solis-style “latest only”
                if frame is None:
                    continue

                # Fixed contrast normalization
                if not hasattr(self, "vmin"):
                    self.vmin, self.vmax = np.min(frame), np.max(frame)
                frame = np.clip(frame, self.vmin, self.vmax)
                norm = (255 * (frame - self.vmin) / (self.vmax - self.vmin + 1e-9)).astype(np.uint8)

                # Display on Tkinter label
                img = Image.fromarray(norm)
                imgtk = ImageTk.PhotoImage(image=img)
                self.image_label.after(0, self.update_display, imgtk)

        finally:
            self.cam.stop_acquisition()

    def update_display(self, imgtk):
        self.image_label.imgtk = imgtk
        self.image_label.configure(image=imgtk)

    # ---------------------------
    def on_close(self):
        self.stop_live()
        if self.cam:
            try:
                self.cam.stop_acquisition()
                self.cam.close()
            except Exception:
                pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = AndorViewerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
