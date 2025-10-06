from pylablib.devices import Andor
import time
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Qt5Agg')
def live_camera_display(exposure=0.040, roi=None):
    """
    Continuously grab images from the camera and display them in real time.

    :param exposure: Exposure time in seconds (e.g. 0.040 for 40 ms)
    :param roi: Optional ROI spec (e.g. (xmin, xmax, ymin, ymax) or as required by your camera API)
    """
    # Instantiate your camera (replace with your camera class)
    cam = Andor.AndorSDK2Camera(idx=0)
    cam.open()
    try:
        # Optionally set ROI if your camera supports it
        if roi is not None:
            # You may need to adapt this call depending on your camera API
            cam.set_roi(*roi)

        # Set exposure
        cam.set_exposure(exposure)

        # Optionally setup acquisition buffer etc.
        cam.setup_acquisition(mode="sequence", nframes=100)  # buffer of 100 frames
        cam.start_acquisition()

        # Prepare matplotlib figure
        fig, ax = plt.subplots()
        # Acquire one initial frame to define the plot
        cam.wait_for_frame()
        frame0 = cam.read_oldest_image()
        im = ax.imshow(frame0, cmap='gray', vmin=np.min(frame0), vmax=np.max(frame0))
        ax.set_title(f"Live camera (exposure = {exposure*1000:.1f} ms)")
        ax.axis('off')
        plt.colorbar(im, ax=ax)

        # Continuous loop
        while True:
            # Wait for the next frame
            cam.wait_for_frame()
            frame = cam.read_oldest_image()
            if frame is None:
                # If no frame, skip
                continue

            # Update the image display
            im.set_data(frame)
            # Optionally adjust contrast scaling if dynamic range changes
            im.set_clim(vmin=np.min(frame), vmax=np.max(frame))
            plt.pause(0.001)  # small pause to allow GUI event loop to update

            # If you want a breaking condition, you could check keyboard or time
            # Here’s an example to break on close of window:
            if not plt.fignum_exists(fig.number):
                break
    except KeyboardInterrupt:
        print('Closing camera')
    finally:
        # Clean up
        try:
            cam.stop_acquisition()
        except Exception:
            pass
        cam.close()
        plt.close(fig)


if __name__ == '__main__':
    # Example usage: run live display with 40 ms exposure
    live_camera_display(exposure=0.040, roi=None)
