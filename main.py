from pyjoycon import JoyCon, get_R_id, get_L_id
import json

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



if __name__ == '__main__':
    joycon_ids = get_R_id()

    joycon = JoyCon(*joycon_ids)
    joycon.get_status()

    print("vendor_id: ", joycon_ids[0])
    print("product_id: ", joycon_ids[1])
    print("serial: ", joycon_ids[2])

    print(json.dumps(joycon.get_status(), indent=4))

    joycon.set_vibration(1.0, 320, 0.6, 160)