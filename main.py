from pyjoycon import JoyCon, get_R_id, get_L_id
from joycon_rumble import RumbleJoyCon, RumbleData
import json, time
import atexit

"""
Archi of status:
{
    "battery": {
        "charging": int,  // 0 (not charging) or 1 (charging)
        "level": int      // Battery level (0-4)
    },
    
    "buttons": {
        "right": {
            "y": int,     // 0 (not pressed) or 1 (pressed)
            "x": int,
            "b": int,
            "a": int,
            "sr": int,
            "sl": int,
            "r": int,
            "zr": int
        },
        "shared": {
            "minus": int,
            "plus": int,
            "r-stick": int,
            "l-stick": int,
            "home": int,
            "capture": int,
            "charging-grip": int
        },
        "left": {
            "down": int,
            "up": int,
            "right": int,
            "left": int,
            "sr": int,
            "sl": int,
            "l": int,
            "zl": int
        }
    },
    
    "analog-sticks": {
        "left": {
            "horizontal": int,  // Position values (range varies)
            "vertical": int
        },
        "right": {
            "horizontal": int,
            "vertical": int
        }
    },
    
    "accel": {
        "x": int,  // Accelerometer values
        "y": int,
        "z": int
    },
    
    "gyro": {
        "x": int,  // Gyroscope values
        "y": int,
        "z": int
    }
}
"""

joycon_right = None
joycon_left = None

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

def initialize_joycons():
    global joycon_right, joycon_left

    try :
        joycon_id_right = get_R_id()
        joycon_id_left = get_L_id()

        Debug.info(f"Right Joy-Con: vendor_id={joycon_id_right[0]},"
        f"product_id={joycon_id_right[1]},"
        f"serial={joycon_id_right[2]}")
        Debug.info(f"Left Joy-Con: vendor_id={joycon_id_left[0]},"
        f"product_id={joycon_id_left[1]},"
        f"serial={joycon_id_left[2]}")

        joycon_right = RumbleJoyCon( * joycon_id_right)
        joycon_left = RumbleJoyCon( * joycon_id_left)

        print("Joy-Cons initialized with rumble capability")
        return joycon_right, joycon_left
    except Exception as e:
        Debug.error(f"Error initializing Joy-Cons: {e}")
        return None, None

# def provide_rumble_feedback(joycon, intensity=0.5, duration=0.5):
#     """
#     Provide haptic feedback through Joy-Con
#
#     Args:
#         joycon: RumbleJoyCon instance
#         intensity: Vibration intensity from 0.0 to 1.0
#         duration: Duration in seconds
#     """
#     # Create rumble data with specified intensity
#     rumble_data = RumbleData(160, 320, intensity)
#
#     # Send rumble command
#     joycon._send_rumble(rumble_data.GetData())
#
#     # Wait for specified duration
#     time.sleep(duration)
#
#     # Stop rumble
#     joycon.rumble_stop()

def provide_rumble_feedback(joycon, intensity=0.5, duration=1.0):
    """
    Send rumble command to Joy-Con with detailed debugging

    Args:
        joycon: The Joy-Con object
        intensity: Rumble intensity (0.0-1.0)
        duration: How long to rumble in seconds
    """
    if not joycon:
        Debug.error("No Joy-Con provided to rumble function")
        return False

    try:
        # Check which side this Joy-Con is
        side = "Unknown"
        if hasattr(joycon, "is_left"):
            side = "Left" if joycon.is_left else "Right"

        Debug.info(f"Starting rumble on {side} Joy-Con (intensity={intensity}, duration={duration}s)")

        # Check Joy-Con connection status
        if hasattr(joycon, "get_status"):
            status = joycon.get_status()
            Debug.info(f"{side} Joy-Con status: {status}")

        # Check available methods
        Debug.info(f"Available methods: {[m for m in dir(joycon) if not m.startswith('_') or m == '_send_rumble']}")

        # Try to send rumble command
        if hasattr(joycon, "rumble"):
            Debug.info(f"Using joycon.rumble({intensity}) method")
            joycon.rumble(intensity)
            result = True
        elif hasattr(joycon, "set_rumble"):
            Debug.info(f"Using joycon.set_rumble({intensity}) method")
            joycon.set_rumble(intensity)
            result = True
        elif hasattr(joycon, "_send_rumble"):
            Debug.info("Using joycon._send_rumble() method")
            # This is a lower-level method that might need specific data format
            # Check if we need to create rumble data
            if 'RumbleData' in globals():
                Debug.info(f"Creating RumbleData with intensity {intensity}")
                rumble_data = RumbleData(160, 320, intensity)  # Typical frequencies
                joycon._send_rumble(rumble_data.GetData())
            else:
                Debug.error("RumbleData class not found")
                return False
            result = True
        else:
            Debug.error(f"No rumble methods found on {side} Joy-Con")
            return False

        # Wait for the specified duration
        Debug.info(f"Rumble started, waiting for {duration}s")
        import time
        time.sleep(duration)

        # Stop rumble
        Debug.info(f"Stopping rumble on {side} Joy-Con")
        if hasattr(joycon, "rumble_stop"):
            joycon.rumble_stop()
        elif hasattr(joycon, "set_rumble"):
            joycon.set_rumble(0)
        elif hasattr(joycon, "_send_rumble"):
            # Send empty rumble data
            empty_data = bytes([0x00] * 8)
            joycon._send_rumble(empty_data)

        Debug.info(f"Rumble sequence completed on {side} Joy-Con")
        return result

    except Exception as e:
        Debug.error(f"Error during rumble: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_joycon_rumble():
    """Test rumble on both Joy-Cons with detailed feedback"""
    global joycon_right, joycon_left

    if not joycon_right and not joycon_left:
        print("No Joy-Cons detected. Running in fallback mode without rumble.")
        return False

    success = False

    # Test right Joy-Con
    if joycon_right:
        print("\n=== Testing Right Joy-Con Rumble ===")
        # Test with different intensities
        for intensity in [0.2, 0.5, 1.0]:
            print(f"\nTrying intensity: {intensity}")
            if provide_rumble_feedback(joycon_right, intensity, 1.0):
                success = True
            import time
            time.sleep(0.5)  # Pause between tests

    # Test left Joy-Con
    if joycon_left:
        print("\n=== Testing Left Joy-Con Rumble ===")
        # Test with different intensities
        for intensity in [0.2, 0.5, 1.0]:
            print(f"\nTrying intensity: {intensity}")
            if provide_rumble_feedback(joycon_left, intensity, 1.0):
                success = True
            import time
            time.sleep(0.5)  # Pause between tests

    return success

def rumble_alert_pattern(joycon):
    """Provide an alert pattern - three short pulses"""
    for _ in range(3):
        provide_rumble_feedback(joycon, 0.8, 0.1)
        time.sleep(0.1)

def rumble_success_pattern(joycon):
    """Provide a success pattern - increasing intensity"""
    for i in range(5):
        intensity = (i + 1) / 5
        provide_rumble_feedback(joycon, intensity, 0.1)
        time.sleep(0.05)

def rumble_error_pattern(joycon):
    """Provide an error pattern - strong long pulse"""
    provide_rumble_feedback(joycon, 1.0, 0.7)

def rumble_heartbeat(joycon, duration=5.0):
    """Provide a heartbeat-like pattern for specified duration"""
    start_time = time.time()
    while time.time() - start_time < duration:
        # Strong beat
        provide_rumble_feedback(joycon, 0.7, 0.1)
        time.sleep(0.1)
        # Lighter beat
        provide_rumble_feedback(joycon, 0.3, 0.1)
        time.sleep(0.4)  # Longer pause between heartbeats

def cleanup():
    """Stop all rumble and perform cleanup when exiting"""
    try:
        if 'joycon_right' in globals():
            joycon_right.rumble_stop()
        if 'joycon_left' in globals():
            joycon_left.rumble_stop()
        print("Joy-Con rumble stopped")
    except Exception as e:
        print(f"Error during cleanup: {e}")


if __name__ == "__main__":
    print("Initializing Joy-Cons...")
    joycon_right, joycon_left = initialize_joycons()

    print("\nTesting Joy-Con rumble functionality...")
    if test_joycon_rumble():
        print("\nRumble test completed. Did you feel the rumble?")
    else:
        print("\nRumble test failed. No rumble detected.")

    print("\nDumping Joy-Con information for debugging:")
    if joycon_right:
        print("\nRight Joy-Con attributes:")
        for attr in dir(joycon_right):
            if not attr.startswith("__"):
                print(f"  - {attr}")

    if joycon_left:
        print("\nLeft Joy-Con attributes:")
        for attr in dir(joycon_left):
            if not attr.startswith("__"):
                print(f"  - {attr}")