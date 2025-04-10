from pyjoycon import get_R_id, get_L_id
from joycon_rumble import RumbleJoyCon, RumbleData
import time, atexit, sys

joycon_right = None

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

        Debug.info("Right Joy-Con initialized.")

        # Give it a moment to stabilize after connection
        time.sleep(0.5)

        return joycon_right
    except Exception as e:
        Debug.error(f"Error initializing Right Joy-Con: {e}")
        import traceback
        traceback.print_exc()
        return None


def read_and_print_motion_data(joycon):
    """Continuously reads and prints motion data from the Joy-Con."""
    if not joycon:
        Debug.error("Joy-Con object is invalid.")
        return

    print("\n--- Reading Right Joy-Con Motion Data (Press Ctrl+C to stop) ---")
    try:
        while True:
            try:
                accel_x = joycon.get_accel_x()
                accel_y = joycon.get_accel_y()
                accel_z = joycon.get_accel_z()

                gyro_x = joycon.get_gyro_x()
                gyro_y = joycon.get_gyro_y()
                gyro_z = joycon.get_gyro_z()

                # Print data on a single line, overwriting the previous line
                print(f"\rAccel: X={accel_x: 5d}, Y={accel_y: 5d}, Z={accel_z: 5d} | "
                      f"Gyro: X={gyro_x: 5d}, Y={gyro_y: 5d}, Z={gyro_z: 5d}   ",
                      end="")
                sys.stdout.flush() # Ensure the line is updated immediately

            except Exception as e:
                # Handle potential errors during data reading (e.g., disconnection)
                Debug.error(f"\nError reading sensor data: {e}")
                # Optionally break the loop or try to reconnect
                break

            # Control the update rate (e.g., 10 times per second)
            time.sleep(0.2)

    except KeyboardInterrupt:
        print("\nStopping data reading.")
    finally:
        # Clear the line on exit
        print("\r" + " " * 80 + "\r", end="")


def clamp(value, min_value, max_value):
    """
    Clamps a value between a minimum and maximum value.

    Args:
        value: The value to clamp
        min_value: The minimum allowed value
        max_value: The maximum allowed value

    Returns:
        The clamped value (between min_value and max_value)
    """
    return max(min_value, min(max_value, value))


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


def cleanup():
    """Perform cleanup when exiting"""
    global joycon_right
    print("Exiting script...")
    # Although we aren't using rumble now, stopping it is harmless
    # and good practice if the JoyCon object supports it.
    try:
        if joycon_right and hasattr(joycon_right, 'rumble_stop'):
            Debug.info("Stopping any potential Joy-Con rumble...")
            joycon_right.rumble_stop()
        # Optional: Explicitly disconnect if needed, though pyjoycon often handles this
        if joycon_right and hasattr(joycon_right, 'disconnect_device'):
           Debug.info("Disconnecting Joy-Con...")
           joycon_right.disconnect_device()
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


# def rumble_alert_pattern(joycon):
#     """Provide an alert pattern - three short pulses"""
#     for _ in range(3):
#         provide_rumble_feedback(joycon, 0.8, 0.1)
#         time.sleep(0.1)
#
#
# def rumble_success_pattern(joycon):
#     """Provide a success pattern - increasing intensity"""
#     for i in range(5):
#         intensity = (i + 1) / 5
#         provide_rumble_feedback(joycon, intensity, 0.1)
#         time.sleep(0.05)
#
#
# def rumble_error_pattern(joycon):
#     """Provide an error pattern - strong long pulse"""
#     provide_rumble_feedback(joycon, 1.0, 0.7)


if __name__ == "__main__":
    # Register cleanup function to run on exit
    atexit.register(cleanup)

    print("Initializing Joy-Cons...")
    joycon_right = initialize_right_joycon()

    if joycon_right:
        # test_right_joycon_rumble()
        print_jc_info(joycon_right)
        read_and_print_motion_data(joycon_right)
    else:
        print("Right Joy-Con not initialized!!!")

    # The script will wait in read_and_print_motion_data until Ctrl+C is pressed
    # or an error occurs. The cleanup function runs automatically upon exit.
    print("Script finished.")