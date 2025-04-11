from pyjoycon import get_R_id, get_L_id
from joycon_rumble import RumbleJoyCon, RumbleData, clamp
import math
import sys
import time
import atexit

joycon_right = None

# --- Constants for Motion-Based Rumble ---
# Estimated magnitude of acceleration vector due to gravity when at rest
# Calculated from your example: sqrt(566^2 + (-383)^2 + (-4517)^2) ≈ 4568
# TODO: Adjust this based on observation if needed.
RESTING_ACCEL_MAGNITUDE = 4500
RESTING_GYRO_MAGNITUDE = 20


# How much acceleration magnitude *above resting* corresponds to full rumble intensity?
# This requires tuning. Higher value means you need to shake harder for max rumble.
MAX_MOTION_ACCEL_MAGNITUDE = 40000
MAX_MOTION_GYRO_MAGNITUDE = 15000

# TODO: Rumble frequencies (can be adjusted for different feel)
RUMBLE_LOW_FREQ = 80  # Hz
RUMBLE_HIGH_FREQ = 160 # Hz

# TODO: Minimum intensity threshold to activate rumble (prevents constant low rumble)
RUMBLE_INTENSITY_THRESHOLD = 0.05
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


def read_and_print_calculated_motion(joycon):
    """Continuously reads sensor data, calculates magnitudes, and prints them."""
    if not joycon:
        Debug.error("Joy-Con object is invalid.")
        return

    print("\n--- Reading & Calculating Motion Data (Press Ctrl+C to stop) ---")
    try:
        while True:
            try:
                accel_x = joycon.get_accel_x()
                accel_y = joycon.get_accel_y()
                accel_z = joycon.get_accel_z()

                gyro_x = joycon.get_gyro_x()
                gyro_y = joycon.get_gyro_y()
                gyro_z = joycon.get_gyro_z()

                # --- Calculations ---
                # Calculate the magnitude of the acceleration vector
                accel_magnitude = math.sqrt(accel_x ** 2 + accel_y ** 2 + accel_z ** 2)

                # Calculate the magnitude of the gyroscope vector (angular velocity magnitude)
                gyro_magnitude = math.sqrt(gyro_x ** 2 + gyro_y ** 2 + gyro_z ** 2)

                # Calculate acceleration magnitude excluding estimated gravity (motion intensity)
                # This is a simplified approach; true separation requires sensor fusion (more complex)
                motion_accel_magnitude = abs(accel_magnitude - RESTING_ACCEL_MAGNITUDE)

                # --- Printing ---
                # Print raw data and calculated magnitudes on a single updating line
                print(f"\rAcc:({accel_x: 5d},{accel_y: 5d},{accel_z: 5d}) Mag:{accel_magnitude: >6.1f} | "
                      f"Gyr:({gyro_x: 5d},{gyro_y: 5d},{gyro_z: 5d}) Mag:{gyro_magnitude: >6.1f} | "
                      f"Motion Acc Mag:{motion_accel_magnitude: >6.1f}   ",
                      end="")
                sys.stdout.flush()

            except AttributeError as e:
                # Catch cases where sensor data might not be ready immediately
                if "'NoneType' object has no attribute" in str(e):
                    Debug.log("Sensor data not available yet, waiting...")
                    time.sleep(0.1)  # Wait a bit longer if data isn't ready
                    continue
                else:
                    Debug.error(f"\nAttributeError reading sensor data: {e}")
                    break  # Exit on other AttributeErrors
            except Exception as e:
                Debug.error(f"\nError reading/calculating sensor data: {e}")
                break

            # Control the update rate (e.g., 10 times per second)
            # Faster gives smoother view of changes, but uses more CPU
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nStopping data reading.")
    finally:
        # Clear the line on exit
        print("\r" + " " * 120 + "\r", end="")  # Clear a wider space


def provide_rumble_feedback(joycon, intensity=0.5, frequency=160, duration=0.5):
    """
    Provide haptic feedback through Joy-Con rumble with simplified parameters

    Args:
        joycon: RumbleJoyCon instance
        intensity: Rumble intensity from 0.0 to 1.0
        frequency: Rumble frequency in Hz (recommended range: 40-320)
        duration: Duration of rumble in seconds

    Returns:
        bool: True if rumble was successful, False otherwise
    """
    if not joycon or not isinstance(joycon, RumbleJoyCon):
        print("Error: Invalid Joy-Con provided")
        return False

    try:
        # Ensure vibration is enabled
        joycon.enable_vibration(True)

        # Clamp values to safe ranges
        intensity = clamp(intensity, 0.0, 1.0)
        frequency = clamp(frequency, 40, 320)

        # Create rumble data with the specified parameters
        # Using both high and low frequency for a fuller rumble feel
        rumble_data = RumbleData(frequency / 2, frequency, intensity)

        # Send the rumble command
        joycon._send_rumble(rumble_data.GetData())

        # Wait for the specified duration
        time.sleep(duration)

        # Stop the rumble
        joycon.rumble_stop()

        return True

    except Exception as e:
        print(f"Rumble error: {str(e)}")
        return False


def test_right_joycon_rumble():
    """Test rumble specifically on the right Joy-Con using the available methods"""
    global joycon_right

    if not joycon_right:
        print("Right Joy-Con not detected.")
        return False

    print("\n=== Testing Right Joy-Con Rumble ===")

    try:
        # Step 1: Enable vibration first
        print("Step 1: Enabling vibration...")
        joycon_right.enable_vibration()
        print("Vibration enabled")

        # Step 2: Test rumble_simple method (no parameters)
        print("\nStep 2: Testing rumble_simple method...")
        print("Starting rumble...")
        joycon_right.rumble_simple()  # No parameters here

        import time
        print("Rumbling for 2 seconds...")
        time.sleep(2.0)

        # Step 3: Stop rumble
        print("\nStep 3: Stopping rumble...")
        joycon_right.rumble_stop()
        print("Rumble stopped")

        # Step 4: Try using RumbleData for custom rumble patterns
        print("\nStep 4: Testing custom rumble with RumbleData (low intensity)...")
        low_rumble = RumbleData(80, 160, 0.3)  # low freq, high freq, amplitude
        joycon_right._send_rumble(low_rumble.GetData())
        print("Low intensity rumbling for 2 seconds...")
        time.sleep(2.0)
        joycon_right.rumble_stop()
        print("Rumble stopped")

        # Step 5: Try higher intensity rumble
        print("\nStep 5: Testing higher intensity rumble...")
        high_rumble = RumbleData(120, 240, 0.7)  # stronger rumble
        joycon_right._send_rumble(high_rumble.GetData())
        print("Higher intensity rumbling for 2 seconds...")
        time.sleep(2.0)
        joycon_right.rumble_stop()
        print("Rumble stopped")

        print("\nRumble testing completed.")
        return True

    except Exception as e:
        print(f"Error during rumble testing: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


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


if __name__ == "__main__":
    # Register cleanup function to run on exit
    atexit.register(cleanup)

    print("Initializing Joy-Cons...")
    joycon_right = initialize_right_joycon()

    if joycon_right:
        # test_right_joycon_rumble()
        # print_jc_info(joycon_right)
        read_and_print_calculated_motion(joycon_right)

        # --- Optional: Uncomment to run tests or print info AFTER the main loop finishes ---
        # print("\nSensor reading finished.")
        # test_right_joycon_rumble()
        # print_jc_info(joycon_right)
        # --- End Optional ---
    else:
        print("Failed to initialize Right Joy-Con. Exiting.")

    # The script will wait in read_and_print_motion_data until Ctrl+C is pressed
    # or an error occurs. The cleanup function runs automatically upon exit.
    print("Script finished.")