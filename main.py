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
        # joycon_id_left = get_L_id()

        Debug.info(f"Right Joy-Con: vendor_id={joycon_id_right[0]},"
        f"product_id={joycon_id_right[1]},"
        f"serial={joycon_id_right[2]}")
        # Debug.info(f"Left Joy-Con: vendor_id={joycon_id_left[0]},"
        # f"product_id={joycon_id_left[1]},"
        # f"serial={joycon_id_left[2]}")

        joycon_right = RumbleJoyCon( * joycon_id_right)
        # joycon_left = RumbleJoyCon( * joycon_id_left)

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
        # side = "Unknown"
        # if hasattr(joycon, "is_left"):
            # side = "Left" if joycon.is_left else "Right"
        side = "Right"

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

# def test_right_joycon_rumble():
#     """Test rumble specifically on the right Joy-Con with detailed debugging"""
#     global joycon_right
#
#     if not joycon_right:
#         print("Right Joy-Con not detected.")
#         return False
#
#     print("\n=== Testing Right Joy-Con Rumble ===")
#
#     # 1. Check Joy-Con status and properties
#     print("\nStep 1: Checking Joy-Con properties")
#     Debug.info(f"Joy-Con object type: {type(joycon_right)}")
#     Debug.info(f"Available methods: {[m for m in dir(joycon_right) if not m.startswith('__')]}")
#
#     # 2. Check if rumble needs to be enabled first
#     print("\nStep 2: Enabling rumble (if method exists)")
#     if hasattr(joycon_right, "enable_rumble"):
#         try:
#             joycon_right.enable_rumble()
#             Debug.info("Rumble explicitly enabled")
#         except Exception as e:
#             Debug.error(f"Error enabling rumble: {e}")
#
#     # 3. Test with different rumble patterns
#     print("\nStep 3: Testing different rumble patterns")
#
#     # Pattern 1: Short, strong pulse
#     print("\nPattern 1: Short, strong pulse")
#     provide_rumble_feedback(joycon_right, intensity=1.0, duration=0.5)
#     import time
#     time.sleep(1.0)  # Wait between tests
#
#     # Pattern 2: Medium, longer rumble
#     print("\nPattern 2: Medium, longer rumble")
#     provide_rumble_feedback(joycon_right, intensity=0.5, duration=1.0)
#     time.sleep(1.0)
#
#     # Pattern 3: Gentle rumble
#     print("\nPattern 3: Gentle rumble")
#     provide_rumble_feedback(joycon_right, intensity=0.2, duration=1.5)
#     time.sleep(1.0)
#
#     # 4. Try direct method calls if available
#     print("\nStep 4: Trying direct method calls")
#
#     try:
#         if hasattr(joycon_right, "rumble"):
#             Debug.info("Calling joycon_right.rumble(1.0) directly")
#             joycon_right.rumble(1.0)
#             time.sleep(1.0)
#             Debug.info("Stopping rumble")
#             if hasattr(joycon_right, "rumble_stop"):
#                 joycon_right.rumble_stop()
#             else:
#                 joycon_right.rumble(0)
#         elif hasattr(joycon_right, "_send_rumble"):
#             Debug.info("Trying low-level _send_rumble method")
#             # Try different rumble data patterns
#             for data in [
#                 bytes([0x00, 0x01, 0x40, 0x40, 0x00, 0x01, 0x40, 0x40]),  # Strong
#                 bytes([0x00, 0x01, 0x10, 0x10, 0x00, 0x01, 0x10, 0x10])  # Medium
#             ]:
#                 Debug.info(f"Sending rumble data: {data.hex()}")
#                 joycon_right._send_rumble(data)
#                 time.sleep(1.0)
#                 # Stop rumble
#                 joycon_right._send_rumble(bytes([0x00] * 8))
#                 time.sleep(0.5)
#     except Exception as e:
#         Debug.error(f"Error during direct rumble calls: {e}")
#
#     # 5. Check if there's any special initialization needed
#     print("\nStep 5: Checking for special initialization methods")
#     special_methods = ["initialize", "setup", "prepare", "calibrate"]
#     for method_name in special_methods:
#         if hasattr(joycon_right, method_name):
#             try:
#                 Debug.info(f"Calling {method_name}() method")
#                 method = getattr(joycon_right, method_name)
#                 method()
#                 Debug.info(f"Called {method_name}(), trying rumble again")
#                 provide_rumble_feedback(joycon_right, 1.0, 1.0)
#             except Exception as e:
#                 Debug.error(f"Error calling {method_name}(): {e}")
#
#     print("\nRight Joy-Con rumble testing completed.")
#     return True

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

    if joycon_right:
        # test_right_joycon_rumble()
        provide_rumble_feedback(joycon_right, 0.5, 1.0)
        # Print detailed information about the Joy-Con object
        # print("\nDetailed Right Joy-Con Information:")
        # for attr in dir(joycon_right):
        #     if not attr.startswith("__"):
        #         try:
        #             value = getattr(joycon_right, attr)
        #             if callable(value):
        #                 print(f"  - {attr}: [Method]")
        #             else:
        #                 print(f"  - {attr}: {value}")
        #         except:
        #             print(f"  - {attr}: [Error accessing]")
    else:
        print("Right Joy-Con not initialized successfully.")

