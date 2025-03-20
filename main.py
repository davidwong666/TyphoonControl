from pyjoycon import get_R_id, get_L_id
from joycon_rumble import RumbleJoyCon, RumbleData
import time, atexit

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
    global joycon_right

    try :
        joycon_id_right = get_R_id()

        Debug.info(f"Right Joy-Con: vendor_id={joycon_id_right[0]},"
        f"product_id={joycon_id_right[1]},"
        f"serial={joycon_id_right[2]}")

        joycon_right = RumbleJoyCon( * joycon_id_right)

        Debug.info("Joy-Cons initialized with rumble capability")
        return joycon_right
    except Exception as e:
        Debug.error(f"Error initializing Joy-Cons: {e}")
        return None


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
    """Stop all rumble and perform cleanup when exiting"""
    try:
        if 'joycon_right' in globals():
            joycon_right.rumble_stop()
        # if 'joycon_left' in globals():
        #     joycon_left.rumble_stop()
        print("Joy-Con rumble stopped")
    except Exception as e:
        print(f"Error during cleanup: {e}")


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
    print("Initializing Joy-Cons...")
    joycon_right = initialize_right_joycon()

    atexit.register(cleanup)

    if joycon_right:
        test_right_joycon_rumble()
        print_jc_info(joycon_right)
    else:
        print("Right Joy-Con not initialized!!!")




