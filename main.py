from pyjoycon import get_R_id, get_L_id
from joycon_rumble import RumbleJoyCon, RumbleData, clamp
import math
import sys
import time
import atexit
from typing import Tuple, Dict, Optional, TypedDict, Callable

joycon_right: Optional[RumbleJoyCon] = None # Type hint for clarity

# --- Constants for Motion-Based Rumble ---

# -- Gyroscope Settings --
# Resting gyro magnitude is low (~20), but we only want rumble for significant rotation.
GYRO_RUMBLE_THRESHOLD = 8000  # Minimum gyro magnitude to START rumbling.
MAX_MOTION_GYRO_MAGNITUDE = 30000 # Gyro magnitude that corresponds to MAXIMUM rumble intensity (1.0).

# -- Accelerometer Settings (Not used for rumble calculation in this version, but kept for reference/printing) --
RESTING_ACCEL_MAGNITUDE = 4500  # Estimated magnitude of acceleration vector due to gravity when at rest.
MAX_MOTION_ACCEL_MAGNITUDE = 40000 # How much acceleration magnitude *above resting* corresponds to full rumble intensity?

# -- Linger Settings --
# This is now the *maximum* duration for a 1.0 intensity burst.
MAX_LINGER_DURATION = 1.5 # Seconds

# -- Rumble Feel Settings --
RUMBLE_LOW_FREQ = 300  # Hz - Adjusted slightly for potentially different feel
RUMBLE_HIGH_FREQ = 800 # Hz - Adjusted slightly

# -- Timing --
LOOP_SLEEP_TIME = 0.05 # Update rate (20 Hz). Important for decay calculation.

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

# --- Type Definitions ---
class SensorData(TypedDict):
    ax: float; ay: float; az: float
    gx: float; gy: float; gz: float
    accel_mag: float
    gyro_mag: float

class LingerState(TypedDict):
    active: bool             # Is a linger effect currently happening?
    peak_intensity: float    # The intensity that triggered the current linger
    initial_duration: float  # The total duration calculated for this specific linger
    time_remaining: float    # How much time is left for the current linger

# --- Initialization ---
def initialize_right_joycon() -> Optional[RumbleJoyCon]:
    """Initializes the right Joy-Con."""
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
        Debug.info("Right Joy-Con initialized.")
        time.sleep(0.5) # Allow connection to stabilize
        return joycon_right
    except Exception as e:
        Debug.error(f"Error initializing Right Joy-Con: {e}"); import traceback; traceback.print_exc()
        return None

# --- Button Mapping ---
BUTTON_METHOD_MAP_RIGHT: Dict[str, Callable[[RumbleJoyCon], bool]] = {
    "A": lambda jc: jc.get_button_a(),
    "B": lambda jc: jc.get_button_b(),
    "X": lambda jc: jc.get_button_x(),
    "Y": lambda jc: jc.get_button_y(),
    "R": lambda jc: jc.get_button_r(),
    "ZR": lambda jc: jc.get_button_zr(),
    "PLUS": lambda jc: jc.get_button_plus(),
    "HOME": lambda jc: jc.get_button_home(),
    "R_STICK": lambda jc: jc.get_button_r_stick(),
    "SL": lambda jc: jc.get_button_right_sl(),
    "SR": lambda jc: jc.get_button_right_sr(),
}

# --- Button Detection Function ---
def wait_for_button_press(joycon: RumbleJoyCon, target_button: str) -> bool:
    """
    Monitors buttons until the target_button is pressed.
    Returns True if the target button was pressed, False otherwise (e.g., Ctrl+C).
    """
    if not joycon:
        Debug.error("Invalid JoyCon object passed to wait_for_button_press.")
        return False
    if target_button not in BUTTON_METHOD_MAP_RIGHT:
        Debug.error(f"Target button '{target_button}' not defined in BUTTON_METHOD_MAP_RIGHT.")
        return False

    print(f"\n--- Waiting for '{target_button}' press (Press Ctrl+C to cancel) ---")
    print(f"Press the '{target_button}' button on the right Joy-Con to start the rumble sequence...")

    previous_button_states: Dict[str, bool] = {name: False for name in BUTTON_METHOD_MAP_RIGHT}
    target_getter = BUTTON_METHOD_MAP_RIGHT[target_button]

    try:
        while True:
            target_pressed = False
            try:
                # Check the target button first for efficiency
                is_pressed_now = target_getter(joycon)
                if is_pressed_now and not previous_button_states.get(target_button, False):
                    print(f"\n[BUTTON PRESS] {target_button} detected!")
                    target_pressed = True
                    # Update state immediately so we don't re-trigger on next check if loop is fast
                    previous_button_states[target_button] = True
                    return True # Exit the loop and function successfully

                # Optional: Check and print other buttons without exiting
                # for name, getter_method in BUTTON_METHOD_MAP_RIGHT.items():
                #     if name == target_button: continue # Already checked
                #     state_now = getter_method(joycon)
                #     if state_now and not previous_button_states.get(name, False):
                #          print(f"({name} pressed)") # Indicate other presses
                #     previous_button_states[name] = state_now # Update state

                # Necessary: Update state for the target button if it wasn't pressed or was released
                previous_button_states[target_button] = is_pressed_now

            except AttributeError:
                Debug.error("\nError accessing button state. Joy-Con likely disconnected.")
                time.sleep(1); return False # Exit if disconnected
            except Exception as e:
                Debug.error(f"\nUnexpected error reading button state: {e}")
                time.sleep(0.5); continue # Try again

            time.sleep(0.03) # Check frequently

    except KeyboardInterrupt:
        print("\nButton waiting cancelled by user.")
        return False # Indicate cancellation
    finally:
        print("--- Button waiting finished. ---")

# --- Countdown Function ---
def perform_countdown():
    """Prints a 3-2-1-Start countdown to the console."""
    print("Starting in...")
    time.sleep(0.5)
    print("3", flush=True)
    time.sleep(1)
    print("2", flush=True)
    time.sleep(1)
    print("1", flush=True)
    time.sleep(1)
    print("Start!", flush=True)
    time.sleep(0.2) # Short pause after start

# --- Core Calculation Functions ---
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

def calculate_decaying_intensity(state: LingerState) -> float:
    """Calculates the current rumble intensity based on the linger state."""
    if not state["active"] or state["initial_duration"] <= 0:
        return 0.0 # Not lingering or invalid state

    # Intensity decays linearly from peak_intensity to 0 over initial_duration
    decay_factor = state["time_remaining"] / state["initial_duration"]
    intensity = state["peak_intensity"] * decay_factor
    return max(0.0, intensity) # Ensure non-negative

def update_linger_state(current_state: LingerState, target_intensity: float, delta_time: float) -> LingerState:
    """Updates the lingering state based on current motion intensity and time elapsed."""
    new_state = current_state.copy()

    # Calculate the intensity the *current* linger would have *now* if it continued decaying
    potential_decaying_intensity = calculate_decaying_intensity(current_state)

    # --- Trigger/Reset Condition ---
    # Start a new linger if:
    # 1. The target intensity from current motion is positive AND
    # 2. It's greater than the intensity the current linger would have decayed to.
    if target_intensity > 0 and target_intensity >= potential_decaying_intensity:
        new_state["active"] = True
        new_state["peak_intensity"] = target_intensity
        # Scale duration based on this burst's intensity
        new_state["initial_duration"] = target_intensity * MAX_LINGER_DURATION
        # Reset remaining time to the full duration for this new burst
        new_state["time_remaining"] = new_state["initial_duration"]
        # Debug.log(f"Linger Trigger/Reset: Peak={target_intensity:.2f}, InitDur={new_state['initial_duration']:.2f}")

    # --- Decay Condition ---
    # Otherwise, if a linger is already active, decay its remaining time
    elif new_state["active"]:
        new_state["time_remaining"] -= delta_time
        if new_state["time_remaining"] <= 0:
            # Linger has ended, reset the state
            new_state["active"] = False
            new_state["time_remaining"] = 0.0
            new_state["peak_intensity"] = 0.0
            new_state["initial_duration"] = 0.0
            # Debug.log("Linger Ended")
        # else:
            # Debug.log(f"Lingering: Remain={new_state['time_remaining']:.2f}")

    # If no new trigger and not active, state remains inactive
    return new_state

def determine_final_intensity(target_intensity: float, decaying_intensity: float) -> float:
    """Determines the final rumble intensity by taking the max of target and decaying linger."""
    return max(target_intensity, decaying_intensity)

def send_rumble_command(joycon: RumbleJoyCon, intensity: float):
    """Generates rumble data and sends the command to the Joy-Con."""
    try:
        rumble_data_generator = RumbleData(RUMBLE_LOW_FREQ, RUMBLE_HIGH_FREQ, intensity)
        rumble_bytes = rumble_data_generator.GetData()
        joycon._send_rumble(rumble_bytes)
    except Exception as e:
        Debug.error(f"Failed to generate or send rumble command: {e}")

def print_status(sensor_data: SensorData, target_intensity: float, current_decay_intensity: float, final_intensity: float, linger_state: LingerState):
    """Prints the current motion and rumble status to the console."""
    linger_time_str = f"{linger_state['time_remaining']:.2f}s" if linger_state['active'] else " Off"
    print(f"\rGyrMag:{sensor_data.get('gyro_mag', 0.0): >7.1f} | "
          f"Target:{target_intensity: >4.2f} | "
          f"Decay:{current_decay_intensity: >4.2f} | "
          f"Sent:{final_intensity: >4.2f} | "
          f"Linger:{linger_time_str}  ", end="")
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

# --- Main Loop and Cleanup ---
def rumble_loop(joycon: RumbleJoyCon):
    """Main loop: reads sensors, calculates/updates rumble, prints status, and sleeps."""
    if not joycon:
        Debug.error("Invalid JoyCon object passed to rumble_loop.")
        return

    # Ensure vibration is enabled before starting rumble loop
    try:
        joycon.enable_vibration(True)
        Debug.info("Vibration enabled for rumble loop.")
    except Exception as e:
        Debug.error(f"Failed to enable vibration before rumble loop: {e}")
        # Continue anyway, _send_rumble might still work

    print("\n--- Reading Gyroscope & Applying Rumble w/ Linger (Refactored) (Press Ctrl+C to stop) ---")
    print(f"Settings: GyroThr={GYRO_RUMBLE_THRESHOLD}, GyroMax={MAX_MOTION_GYRO_MAGNITUDE}, MaxLinger={MAX_LINGER_DURATION:.2f}s")

    # Initialize linger state
    linger_state: LingerState = {
        "active": False,
        "peak_intensity": 0.0,
        "initial_duration": 0.0,
        "time_remaining": 0.0
    }

    try:
        last_time = time.monotonic()  # For calculating delta_time

        while True:
            current_time = time.monotonic()
            delta_time = max(0.001, current_time - last_time)
            last_time = current_time
            sensor_data = read_sensor_data(joycon)
            if sensor_data is None: time.sleep(0.05); continue
            gyro_mag = sensor_data['gyro_mag']
            target_intensity = calculate_target_intensity(gyro_mag)
            linger_state = update_linger_state(linger_state, target_intensity, delta_time)
            current_decaying_intensity = calculate_decaying_intensity(linger_state)
            final_intensity = determine_final_intensity(target_intensity, current_decaying_intensity)
            send_rumble_command(joycon, final_intensity)
            print_status(sensor_data, target_intensity, current_decaying_intensity, final_intensity, linger_state)
            elapsed_since_loop_start = time.monotonic() - current_time
            sleep_duration = max(0.0, LOOP_SLEEP_TIME - elapsed_since_loop_start)
            time.sleep(sleep_duration)
    except KeyboardInterrupt:
        print("\nStopping data reading and rumble.")
    finally:
        try:
            print("\nStopping final rumble...")
            if joycon: joycon.rumble_stop()
        except Exception as e:
            Debug.error(f"Error stopping rumble on exit: {e}")
        print("\r" + " " * 120 + "\r", end="") # Clear the line

def cleanup():
    """Perform cleanup when exiting"""
    global joycon_right
    print("\nExiting script...")
    try:
        if joycon_right and hasattr(joycon_right, 'rumble_stop') and callable(joycon_right.rumble_stop):
            Debug.info("Ensuring Joy-Con rumble is stopped...")
            joycon_right.rumble_stop()
        Debug.info("Cleanup complete.")
    except Exception as e:
        Debug.error(f"Error during cleanup: {e}")

# Main entry point
if __name__ == "__main__":
    atexit.register(cleanup)
    print("Initializing Right Joy-Con...")
    joycon_right = initialize_right_joycon()

    if not joycon_right:
        print("Failed to initialize Right Joy-Con. Exiting.")

    # 1. Wait for 'A' button press
    start_signal_received = wait_for_button_press(joycon_right, target_button="A")

    # 2. If 'A' was pressed, perform countdown and start rumble loop
    if start_signal_received:
        perform_countdown()
        rumble_loop(joycon_right)
    else:
        print("\nStart signal not received (cancelled or error). Exiting.")

    # Uncomment to print detailed Joy-Con info
    print_jc_info(joycon_right)

    print("Script finished.")