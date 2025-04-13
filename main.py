from pyjoycon import get_R_id, get_L_id
from joycon_rumble import RumbleJoyCon, RumbleData, clamp
import math
import sys
import time
import atexit
from typing import Tuple, Dict, Optional

joycon_right: Optional[RumbleJoyCon] = None # Type hint for clarity

# --- Constants for Motion-Based Rumble ---

# -- Gyroscope Settings --
# Resting gyro magnitude is low (~20), but we only want rumble for significant rotation.
GYRO_RUMBLE_THRESHOLD = 5000  # Minimum gyro magnitude to START rumbling.
MAX_MOTION_GYRO_MAGNITUDE = 20000 # Gyro magnitude that corresponds to MAXIMUM rumble intensity (1.0).

# -- Accelerometer Settings (Not used for rumble calculation in this version, but kept for reference/printing) --
RESTING_ACCEL_MAGNITUDE = 4500  # Estimated magnitude of acceleration vector due to gravity when at rest.
MAX_MOTION_ACCEL_MAGNITUDE = 40000 # How much acceleration magnitude *above resting* corresponds to full rumble intensity?

# -- Linger Settings --
LINGER_DURATION = 0.7  # How many seconds the rumble should linger/decay after a strong burst (>= MAX_MOTION_GYRO_MAGNITUDE).
LINGER_START_INTENSITY = 1.0 # Intensity to start the linger decay from.

# -- Rumble Feel Settings --
RUMBLE_LOW_FREQ = 300  # Hz - Adjusted slightly for potentially different feel
RUMBLE_HIGH_FREQ = 800 # Hz - Adjusted slightly

# -- Timing --
LOOP_SLEEP_TIME = 0.05 # Update rate (20 Hz). Important for decay calculation.

# --- Calculated Constants ---
# How much intensity to decrease per loop iteration during decay
# Avoid division by zero if duration is zero or negative
if LINGER_DURATION > 0:
    LINGER_DECAY_STEP = (LINGER_START_INTENSITY / LINGER_DURATION) * LOOP_SLEEP_TIME
else:
    LINGER_DECAY_STEP = LINGER_START_INTENSITY # Decay immediately if duration is invalid

# --- End Constants ---

class Debug:
    ENABLED = True
    @staticmethod
    def log(message):
        if Debug.ENABLED: print(f"[DEBUG] {message}")
    @staticmethod
    def error(message):
        if Debug.ENABLED: print(f"[ERROR] {message}", file=sys.stderr)
    @staticmethod
    def info(message):
        if Debug.ENABLED: print(f"[INFO] {message}")


def initialize_right_joycon() -> Optional[RumbleJoyCon]:
    """Initializes the right Joy-Con with rumble capabilities."""
    global joycon_right
    try:
        joycon_id_right = get_R_id()
        if not joycon_id_right:
            Debug.error("Right Joy-Con not found. Ensure it's paired and connected via Bluetooth.")
            return None
        Debug.info(f"Found Right Joy-Con: vendor_id={joycon_id_right[0]}, product_id={joycon_id_right[1]}, serial={joycon_id_right[2]}")
        joycon_right = RumbleJoyCon(*joycon_id_right)
        joycon_right.enable_vibration(True)
        time.sleep(0.1)
        Debug.info("Right Joy-Con initialized for rumble.")
        time.sleep(0.5)
        return joycon_right
    except Exception as e:
        Debug.error(f"Error initializing Right Joy-Con: {e}"); import traceback; traceback.print_exc()
        return None

SensorData = Dict[str, float] # Type alias for sensor data dictionary

def read_sensor_data(joycon: RumbleJoyCon) -> Optional[SensorData]:
    """Reads accelerometer and gyroscope data and calculates magnitudes."""
    try:
        accel_x = joycon.get_accel_x(); accel_y = joycon.get_accel_y(); accel_z = joycon.get_accel_z()
        gyro_x = joycon.get_gyro_x(); gyro_y = joycon.get_gyro_y(); gyro_z = joycon.get_gyro_z()

        # Return None if any sensor value is None (might happen during initialization/disconnection)
        if None in (accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z):
             Debug.log("Incomplete sensor data received.")
             return None

        accel_magnitude = math.sqrt(accel_x**2 + accel_y**2 + accel_z**2)
        gyro_magnitude = math.sqrt(gyro_x**2 + gyro_y**2 + gyro_z**2)

        return {
            "ax": float(accel_x), "ay": float(accel_y), "az": float(accel_z),
            "gx": float(gyro_x), "gy": float(gyro_y), "gz": float(gyro_z),
            "accel_mag": accel_magnitude,
            "gyro_mag": gyro_magnitude
        }
    except AttributeError as e:
        # Handle case where joycon object methods aren't available yet
        if "'NoneType' object has no attribute" in str(e):
            Debug.log("Sensor methods not available yet, waiting...")
        else:
            Debug.error(f"AttributeError reading sensors: {e}")
        return None
    except Exception as e:
        Debug.error(f"Unexpected error reading sensors: {e}")
        import traceback; traceback.print_exc()
        return None


def calculate_target_intensity(gyro_magnitude: float) -> float:
    """Calculates rumble intensity based *only* on current gyroscope magnitude."""
    if gyro_magnitude < GYRO_RUMBLE_THRESHOLD:
        return 0.0
    active_range_size = MAX_MOTION_GYRO_MAGNITUDE - GYRO_RUMBLE_THRESHOLD
    value_in_range = gyro_magnitude - GYRO_RUMBLE_THRESHOLD
    if active_range_size <= 0: # Handle edge case where threshold >= max
        return 1.0 if gyro_magnitude >= GYRO_RUMBLE_THRESHOLD else 0.0
    intensity = value_in_range / active_range_size
    return clamp(intensity, 0.0, 1.0)


def update_linger_state(gyro_magnitude: float, current_linger_intensity: float) -> float:
    """Updates the lingering intensity based on current motion and decay."""
    new_linger_intensity = current_linger_intensity # Start with the current value

    if gyro_magnitude >= MAX_MOTION_GYRO_MAGNITUDE:
        # Trigger/reset linger
        new_linger_intensity = LINGER_START_INTENSITY
    elif current_linger_intensity > 0:
        # Decay existing linger
        new_linger_intensity -= LINGER_DECAY_STEP
        new_linger_intensity = max(0.0, new_linger_intensity) # Ensure it doesn't go below zero

    return new_linger_intensity


def determine_final_intensity(target_intensity: float, linger_intensity: float) -> float:
    """Determines the final rumble intensity by taking the max of target and linger."""
    return max(target_intensity, linger_intensity)


def send_rumble_command(joycon: RumbleJoyCon, intensity: float):
    """Generates rumble data and sends the command to the Joy-Con."""
    try:
        rumble_data_generator = RumbleData(RUMBLE_LOW_FREQ, RUMBLE_HIGH_FREQ, intensity)
        rumble_bytes = rumble_data_generator.GetData()
        joycon._send_rumble(rumble_bytes)
    except Exception as e:
        Debug.error(f"Failed to generate or send rumble command: {e}")


def print_status(sensor_data: SensorData, target_intensity: float, linger_intensity: float, final_intensity: float):
    """Prints the current motion and rumble status to the console."""
    print(f"\rGyrMag:{sensor_data.get('gyro_mag', 0.0): >6.1f} | "
          f"TargetInt:{target_intensity: >4.2f} | "
          f"LingerInt:{linger_intensity: >4.2f} | "
          f"SentInt:{final_intensity: >4.2f}   ", end="")
    sys.stdout.flush()


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


def rumble_loop(joycon: RumbleJoyCon):
    """Main loop: reads sensors, calculates/updates rumble, prints status, and sleeps."""
    if not joycon:
        Debug.error("Invalid JoyCon object passed to rumble_loop.")
        return

    print("\n--- Reading Gyroscope & Applying Rumble w/ Linger (Refactored) (Press Ctrl+C to stop) ---")
    print(f"Settings: GyroThr={GYRO_RUMBLE_THRESHOLD}, GyroMax={MAX_MOTION_GYRO_MAGNITUDE}, LingerDur={LINGER_DURATION:.2f}s")

    lingering_intensity = 0.0 # Initialize linger state

    try:
        while True:
            start_time = time.monotonic()

            # 1. Read Sensors
            sensor_data = read_sensor_data(joycon)
            if sensor_data is None:
                time.sleep(0.1) # Wait longer if sensor data is bad
                continue

            gyro_mag = sensor_data['gyro_mag']

            # 2. Calculate Target Intensity (based on current motion)
            target_intensity = calculate_target_intensity(gyro_mag)

            # 3. Update Linger State (handles trigger and decay)
            lingering_intensity = update_linger_state(gyro_mag, lingering_intensity)

            # 4. Determine Final Intensity
            final_intensity = determine_final_intensity(target_intensity, lingering_intensity)

            # 5. Send Rumble Command
            send_rumble_command(joycon, final_intensity)

            # 6. Print Status
            print_status(sensor_data, target_intensity, lingering_intensity, final_intensity)

            # 7. Accurate Sleep
            elapsed_time = time.monotonic() - start_time
            # FIX: Use max(0.0, ...) to ensure float comparison
            sleep_duration = max(0.0, LOOP_SLEEP_TIME - elapsed_time)
            time.sleep(sleep_duration)

    except KeyboardInterrupt:
        print("\nStopping data reading and rumble.")
    # No need for explicit exception handling here if component functions handle theirs
    finally:
        try:
            print("\nStopping final rumble...")
            if joycon: # Ensure joycon object still exists
                joycon.rumble_stop()
        except Exception as e:
            Debug.error(f"Error stopping rumble on exit: {e}")
        print("\r" + " " * 120 + "\r", end="") # Clear the line


def cleanup():
    """Perform cleanup when exiting"""
    global joycon_right
    print("\nExiting script...")
    try:
        # Ensure joycon is valid and has rumble_stop before calling
        if joycon_right and hasattr(joycon_right, 'rumble_stop') and callable(joycon_right.rumble_stop):
            Debug.info("Ensuring Joy-Con rumble is stopped...")
            joycon_right.rumble_stop()
        Debug.info("Cleanup complete.")
    except Exception as e:
        Debug.error(f"Error during cleanup: {e}")


if __name__ == "__main__":
    atexit.register(cleanup)
    print("Initializing Right Joy-Con...")
    joycon_right = initialize_right_joycon()
    if joycon_right:
        # Call the main refactored loop function
        rumble_loop(joycon_right)
        print_jc_info(joycon_right)
    else:
        print("Failed to initialize Right Joy-Con. Exiting.")
    print("Script finished.")