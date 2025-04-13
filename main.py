from pyjoycon import get_R_id, get_L_id
from joycon_rumble import RumbleJoyCon, RumbleData, clamp
import math
import sys
import time
import atexit

joycon_right = None

# --- Constants for Motion-Based Rumble ---

# -- Gyroscope Settings --
# Resting gyro magnitude is low (~20), but we only want rumble for significant rotation.
GYRO_RUMBLE_THRESHOLD = 5000  # Minimum gyro magnitude to START rumbling.
MAX_MOTION_GYRO_MAGNITUDE = 20000 # Gyro magnitude that corresponds to MAXIMUM rumble intensity (1.0).

# -- Accelerometer Settings (Not used for rumble calculation in this version, but kept for reference/printing) --
RESTING_ACCEL_MAGNITUDE = 4500  # Estimated magnitude of acceleration vector due to gravity when at rest.
MAX_MOTION_ACCEL_MAGNITUDE = 40000 # How much acceleration magnitude *above resting* corresponds to full rumble intensity?

# -- Rumble Feel Settings --
RUMBLE_LOW_FREQ = 300  # Hz - Adjusted slightly for potentially different feel
RUMBLE_HIGH_FREQ = 800 # Hz - Adjusted slightly
# RUMBLE_INTENSITY_THRESHOLD = 0.05 # This concept is now handled by GYRO_RUMBLE_THRESHOLD

# --- End Constants ---

class Debug:
    ENABLED = True

    @staticmethod
    def log(message):
        if Debug.ENABLED:
            print(f"[DEBUG] {message}")

    @staticmethod
    def error(message):
        if Debug.ENABLED:
            print(f"[ERROR] {message}")

    @staticmethod
    def info(message):
        if Debug.ENABLED:
            print(f"[INFO] {message}")


def initialize_right_joycon():
    """Initializes the right Joy-Con."""
    global joycon_right

    try :
        joycon_id_right = get_R_id()

        if not joycon_id_right:
            Debug.error("Right Joy-Con not found. Ensure it's paired and connected via Bluetooth.")
            return None

        Debug.info(f"Found Right Joy-Con: vendor_id={joycon_id_right[0]}, "
                   f"product_id={joycon_id_right[1]}, "
                   f"serial={joycon_id_right[2]}")

        joycon_right = RumbleJoyCon(*joycon_id_right)

        # Optional: Enable vibration explicitly if needed, though _send_rumble might handle it
        joycon_right.enable_vibration(True)
        time.sleep(0.1) # Short delay after enabling vibration

        Debug.info("Right Joy-Con initialized for rumble.")
        time.sleep(0.5)  # Allow connection to stabilize
        return joycon_right
    except Exception as e:
        Debug.error(f"Error initializing Right Joy-Con: {e}")
        import traceback
        traceback.print_exc()
        return None


def calculate_gyro_rumble_intensity(gyro_magnitude):
    """Calculates rumble intensity based on gyroscope magnitude, threshold, and max value."""

    if gyro_magnitude < GYRO_RUMBLE_THRESHOLD:
        # Below the minimum rotation speed needed for rumble
        return 0.0

    # Calculate how far the current magnitude is into the active range (Threshold to Max)
    active_range_size = MAX_MOTION_GYRO_MAGNITUDE - GYRO_RUMBLE_THRESHOLD
    value_in_range = gyro_magnitude - GYRO_RUMBLE_THRESHOLD

    if active_range_size <= 0:
        # Avoid division by zero/negative if threshold is >= max
        # If above threshold, intensity is max (1.0) in this edge case
        return 1.0

    # Scale the value within the range to [0.0, 1.0]
    intensity = value_in_range / active_range_size

    # Clamp the intensity to the valid range [0.0, 1.0]
    # This handles cases where gyro_magnitude exceeds MAX_MOTION_GYRO_MAGNITUDE
    return clamp(intensity, 0.0, 1.0)


def read_gyro_and_rumble(joycon):
    """Continuously reads sensors, calculates gyro-based rumble, prints, and sends commands."""
    if not joycon or not isinstance(joycon, RumbleJoyCon):
        Debug.error("Invalid RumbleJoyCon object provided.")
        return

    print("\n--- Reading Gyroscope & Applying Rumble (Press Ctrl+C to stop) ---")
    print(f"Settings: GyroThreshold={GYRO_RUMBLE_THRESHOLD}, GyroMax={MAX_MOTION_GYRO_MAGNITUDE}, Freqs=[{RUMBLE_LOW_FREQ},{RUMBLE_HIGH_FREQ}]")

    try:
        while True:
            try:
                # Read sensor data
                accel_x = joycon.get_accel_x() # Read accel for printing/reference
                accel_y = joycon.get_accel_y()
                accel_z = joycon.get_accel_z()
                accel_magnitude = math.sqrt(accel_x ** 2 + accel_y ** 2 + accel_z ** 2)

                gyro_x = joycon.get_gyro_x()
                gyro_y = joycon.get_gyro_y()
                gyro_z = joycon.get_gyro_z()
                gyro_magnitude = math.sqrt(gyro_x ** 2 + gyro_y ** 2 + gyro_z ** 2)

                # --- Rumble Calculation (Based on Gyro) ---
                rumble_intensity = calculate_gyro_rumble_intensity(gyro_magnitude)

                # Create rumble data packet
                rumble_data_generator = RumbleData(RUMBLE_LOW_FREQ, RUMBLE_HIGH_FREQ, rumble_intensity)
                rumble_bytes = rumble_data_generator.GetData()

                # Send the rumble command - this overwrites the previous one
                joycon._send_rumble(rumble_bytes)

                # --- Printing ---
                print(f"\rGyr:({gyro_x: 5d},{gyro_y: 5d},{gyro_z: 5d}) Mag:{gyro_magnitude: >6.1f} | "
                      f"Rumble Intensity: {rumble_intensity: >4.2f} | "
                      # Optional: Print Accel data too for comparison
                      f"Acc Mag:{accel_magnitude: >6.1f}    ",
                      end="")
                sys.stdout.flush()

            except AttributeError as e:
                 if "'NoneType' object has no attribute" in str(e):
                     Debug.log("Sensor data not available yet, waiting...")
                     time.sleep(0.1); continue
                 else: Debug.error(f"\nAttributeError reading sensor data: {e}"); break
            except Exception as e:
                Debug.error(f"\nError during loop: {e}")
                break # Exit loop on error

            # Control the update rate (adjust as needed for responsiveness vs performance)
            time.sleep(0.05) # e.g., 20 updates per second

    except KeyboardInterrupt:
        print("\nStopping data reading and rumble.")
    finally:
        # Ensure rumble stops on exit
        try:
            print("\nStopping final rumble...")
            joycon.rumble_stop()
        except Exception as e:
            Debug.error(f"Error stopping rumble on exit: {e}")
        print("\r" + " " * 120 + "\r", end="") # Clear the line


def print_jc_info(joycon):
    if joycon:
        print("\nDetailed Joy-Con Information: ")
        for attr in dir(joycon):
            if not attr.startswith("__"):
                try:
                    value = getattr(joycon, attr)
                    if callable(value):
                        print(f"  - {attr}: [Method]")
                    else:
                        print(f"  - {attr}: {value}")
                except:
                    print(f"  - {attr}: [Error accessing]")


# --- Utility and Cleanup functions ---
def cleanup():
    """Perform cleanup when exiting"""
    global joycon_right
    print("\nExiting script...")
    try:
        if joycon_right and hasattr(joycon_right, 'rumble_stop'):
            # Stop rumble just in case it was left on by manual testing etc.
            Debug.info("Ensuring Joy-Con rumble is stopped...")
            joycon_right.rumble_stop()
        # Optional: Disconnect
        # if joycon_right and hasattr(joycon_right, 'disconnect_device'):
        #    Debug.info("Disconnecting Joy-Con...")
        #    joycon_right.disconnect_device()
        Debug.info("Cleanup complete.")
    except Exception as e:
        Debug.error(f"Error during cleanup: {e}")


if __name__ == "__main__":
    # Register cleanup function to run on exit
    atexit.register(cleanup)

    print("Initializing Joy-Cons...")
    joycon_right = initialize_right_joycon()

    if joycon_right:
        read_gyro_and_rumble(joycon_right)

        # Optional: Print detailed information about the Joy-Con
        # print_jc_info(joycon_right)
    else:
        print("Failed to initialize Right Joy-Con. Exiting.")

    # The script will wait in read_and_print_motion_data until Ctrl+C is pressed
    # or an error occurs. The cleanup function runs automatically upon exit.
    print("Script finished.")