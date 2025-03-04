from pyjoycon import JoyCon, get_R_id, get_L_id
from joycon_rumble import RumbleJoyCon, RumbleData
import json, time

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


def initialize_joycons():
    joycon_id_right = get_R_id()
    joycon_id_left = get_L_id()

    joycon_right = RumbleJoyCon(joycon_id_right)
    joycon_left = RumbleJoyCon(joycon_id_left)

    print("vendor_id: ", joycon_id_right[0])
    print("product_id: ", joycon_id_right[1])
    print("serial: ", joycon_id_right[2])

    joycon_right.get_status()
    print(json.dumps(joycon_right.get_status(), indent=4))

    return joycon_right, joycon_left


# Example function to add rumble feedback to your application
def provide_rumble_feedback(joycon, intensity=0.5, duration=0.5):
    """
    Provide haptic feedback through Joy-Con

    Args:
        joycon: RumbleJoyCon instance
        intensity: Vibration intensity from 0.0 to 1.0
        duration: Duration in seconds
    """
    # Create rumble data with specified intensity
    rumble_data = RumbleData(160, 320, intensity)

    # Send rumble command
    joycon._send_rumble(rumble_data.GetData())

    # Wait for specified duration
    time.sleep(duration)

    # Stop rumble
    joycon.rumble_stop()

# Add these functions to your main.py

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

# Add this to your main function
import atexit
atexit.register(cleanup)  # Register cleanup function to run at exit

if __name__ == '__main__':
    joycon_right, joycon_left = initialize_joycons()

    # provide_rumble_feedback(joycon_right, 0.7, 0.3)



