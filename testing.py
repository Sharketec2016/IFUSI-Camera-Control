import traceback

from pylablib.devices import Andor
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Qt5Agg')
import time

def live_camera_display(exposure=0.040, roi=None):
    """
    Continuously grab images from the Andor iXon camera and display them in real time.
    """
    # Connect to camera
    cam = Andor.AndorSDK2Camera()

    try:
        # Configure camera

        cam.set_exposure(exposure)
        cam.set_trigger_mode("int")
        val = cam.get_all_amp_modes()


        cam.set_amp_mode(
            channel=0,
            oamp=0,
            hsspeed=1,
            preamp=1
        )


        cam.setup_shutter(mode="open")

        # Setup for continuous acquisition
        cam.setup_acquisition(mode="sequence")
        cam.start_acquisition()
        acquisition_started = True
        print(f"Started acquisition with exposure = {exposure*1000:.1f} ms")

        # Grab first frame for initialization
        cam.wait_for_frame(timeout=5)
        frame = cam.read_oldest_image()
        if frame is None:
            raise RuntimeError("No initial frame received")


        fig, ax = plt.subplots()
        im = ax.imshow(frame, cmap='gray', vmin=np.min(frame), vmax=np.max(frame))
        ax.set_title(f"Live camera (exposure = {exposure*1000:.1f} ms)")
        ax.axis('off')
        plt.colorbar(im, ax=ax)
        plt.show(block=False)
        plt.pause(0.1)

        while plt.fignum_exists(fig.number):
            try:
                # Wait for the next available frame
                cam.wait_for_frame(timeout=5)
                frame = cam.read_oldest_image()
                if frame is None:
                    continue

                im.set_data(frame)
                im.set_clim(vmin=np.min(frame), vmax=np.max(frame))
                plt.pause(0.001)
            except Exception as e:
                print("Error during frame acquistion")
                traceback.print_exc()
                time.sleep(0.1)
                continue

    except KeyboardInterrupt:
        print("🔹 Interrupted by user.")
    except Exception as e:
        print("❌ Unexpected error:", e)
        traceback.print_exc()
    finally:
        print("Stopping acquisition and closing camera.")
        if cam is not None:
            try:
                if acquisition_started:
                    cam.stop_acquisition()
                    print("Acquisition stopped")
            except Exception as e:
                print("Warning while stopping acquisition:", e)
            try:
                cam.close()
                print("Camera closed successfully")
            except Exception as e:
                print("Error while closing camera:", e)
        plt.close('all')

if __name__ == '__main__':
    live_camera_display(exposure=0.040)
