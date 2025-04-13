from pyjoycon import get_R_id
from joycon_rumble import RumbleJoyCon, RumbleData, clamp
import math
import sys
import time
import atexit
from typing import Tuple, Dict, Optional, TypedDict, Callable
from collections import deque

joycon_right: Optional[RumbleJoyCon] = None # Type hint for clarity

# --- Constants for Motion-Based Rumble ---

# -- Gyroscope Settings --
GYRO_RUMBLE_THRESHOLD = 8000
MAX_MOTION_GYRO_MAGNITUDE = 30000 # Corresponds to ~ Super Typhoon (185 km/h+)

# -- Accelerometer Settings (Not used for rumble calculation in this version, but kept for reference/printing) --
# RESTING_ACCEL_MAGNITUDE = 4500  # Estimated magnitude of acceleration vector due to gravity when at rest.
# MAX_MOTION_ACCEL_MAGNITUDE = 40000 # How much acceleration magnitude *above resting* corresponds to full rumble intensity?

# -- Linger Settings --
# This is now the *maximum* duration for a 1.0 intensity burst.
MAX_LINGER_DURATION = 1.5 # Seconds

# -- Rumble Feel Settings (Main Loop) --
RUMBLE_LOW_FREQ = 300  # Hz - Adjusted slightly for potentially different feel
RUMBLE_HIGH_FREQ = 800 # Hz - Adjusted slightly

# -- Countdown Rumble Settings --
COUNTDOWN_BASE_FREQ_HZ = 90; COUNTDOWN_FREQ_STEP_HZ = 30
COUNTDOWN_BASE_INTENSITY = 0.3; COUNTDOWN_INTENSITY_STEP = 0.1
COUNTDOWN_PULSE_DURATION_S = 0.15; COUNTDOWN_START_PULSE_DURATION_S = 0.2

# -- Timing --
LOOP_SLEEP_TIME = 0.05 # Update rate (20 Hz). Important for decay calculation.
SIMULATION_DURATION_S = 10.0 # Total duration for energy accumulation

# -- Energy Bar Settings --
ENERGY_HISTORY_DURATION_S = 10.0 # Duration for rolling average calculation
ENERGY_SMOOTHING_FACTOR = 0.15 # EMA alpha (smaller = smoother, slower response)
ENERGY_DECAY_RATE = 0.6 # Rate (fraction/sec) energy decays towards average when overshooting

# -- Typhoon Classification Thresholds (Approx. scaled from km/h to Gyro Mag) --
# Assuming MAX_MOTION_GYRO_MAGNITUDE (30000) ~= 185 km/h
_SCALE_FACTOR = MAX_MOTION_GYRO_MAGNITUDE / 185.0
TYPHOON_THRESHOLDS = {
    "熱帶低氣壓 (Tropical Depression)": 41 * _SCALE_FACTOR,     # ~6642
    "熱帶風暴 (Tropical Storm)": 63 * _SCALE_FACTOR,           # ~10206
    "強烈熱帶風暴 (Severe Tropical Storm)": 88 * _SCALE_FACTOR, # ~14256
    "颱風 (Typhoon)": 118 * _SCALE_FACTOR,                      # ~19116
    "強颱風 (Severe Typhoon)": 150 * _SCALE_FACTOR,             # ~24324
    "超強颱風 (Super Typhoon)": 185 * _SCALE_FACTOR,          # ~30000
}
# Sort thresholds for easier lookup
_SORTED_THRESHOLDS = sorted(TYPHOON_THRESHOLDS.items(), key=lambda item: item[1])

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
        # Enable vibration early - needed for countdown and main loop
        try:
            joycon_right.enable_vibration(True)
            time.sleep(0.1)  # Short delay after enabling
            Debug.info("Vibration enabled.")
        except Exception as vib_e:
            Debug.error(f"Failed to enable vibration during init: {vib_e}")
        Debug.info("Right Joy-Con initialized.")
        time.sleep(0.5)  # Allow connection to stabilize
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
def wait_for_button_press(joycon: RumbleJoyCon, target_button: str) -> bool | None:
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

# --- Rumble Pulse Function ---
def rumble_pulse(joycon: RumbleJoyCon, low_freq: float, high_freq: float, intensity: float, duration: float):
    """Sends a short, fixed rumble pulse and then stops."""
    if not joycon: return
    try:
        # Clamp inputs for safety
        low_freq = clamp(low_freq, 41, 626)
        high_freq = clamp(high_freq, 82, 1253)
        intensity = clamp(intensity, 0.0, 1.0)
        duration = max(0.01, duration) # Ensure minimum duration

        rumble_data_gen = RumbleData(low_freq, high_freq, intensity)
        rumble_bytes = rumble_data_gen.GetData()
        joycon._send_rumble(rumble_bytes)
        time.sleep(duration)
        joycon.rumble_stop()
    except Exception as e:
        Debug.error(f"Error during rumble pulse: {e}")
        # Ensure rumble stops even if error occurs mid-pulse
        try:
            if joycon: joycon.rumble_stop()
        except: pass

# --- Countdown Function ---
def perform_countdown_with_rumble(joycon: RumbleJoyCon):
    """Prints a 3-2-1-Start countdown with corresponding rumble pulses."""
    if not joycon:
        Debug.error("Cannot perform countdown: invalid JoyCon object.")
        return

    print("\nStarting in...")
    time.sleep(0.5) # Initial pause

    countdown_steps = [
        ("3", COUNTDOWN_BASE_FREQ_HZ + 0 * COUNTDOWN_FREQ_STEP_HZ, COUNTDOWN_BASE_INTENSITY + 0 * COUNTDOWN_INTENSITY_STEP, COUNTDOWN_PULSE_DURATION_S),
        ("2", COUNTDOWN_BASE_FREQ_HZ + 1 * COUNTDOWN_FREQ_STEP_HZ, COUNTDOWN_BASE_INTENSITY + 1 * COUNTDOWN_INTENSITY_STEP, COUNTDOWN_PULSE_DURATION_S),
        ("1", COUNTDOWN_BASE_FREQ_HZ + 2 * COUNTDOWN_FREQ_STEP_HZ, COUNTDOWN_BASE_INTENSITY + 2 * COUNTDOWN_INTENSITY_STEP, COUNTDOWN_PULSE_DURATION_S),
    ]
    start_step = ("Start!", COUNTDOWN_BASE_FREQ_HZ + 3 * COUNTDOWN_FREQ_STEP_HZ, COUNTDOWN_BASE_INTENSITY + 3 * COUNTDOWN_INTENSITY_STEP, COUNTDOWN_START_PULSE_DURATION_S)

    # Do the 3, 2, 1 steps
    for text, hf, intensity, duration in countdown_steps:
        # Low frequency can be derived or fixed, let's derive (e.g., ~0.6 * hf)
        lf = max(41.0, hf * 0.6) # Ensure low freq is within valid range
        rumble_pulse(joycon, lf, hf, intensity, duration)
        print(text, flush=True)
        # Pause *after* printing, accounting for rumble time
        time.sleep(max(0.0, 1.0 - duration)) # Wait roughly 1 second total per step

    # Do the "Start!" step
    lf_start = max(41.0, start_step[1] * 0.6)
    rumble_pulse(joycon, lf_start, start_step[1], start_step[2], start_step[3])
    print(start_step[0], flush=True)
    # Shorter pause after start before main loop begins
    time.sleep(max(0.0, 0.2 - start_step[3]))

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

# --- Energy Bar & Classification Functions ---
def update_gyro_history(history: deque, current_time: float, gyro_mag: float):
    """Adds current reading and removes old ones from the history deque."""
    # Add current reading
    history.append((current_time, gyro_mag))
    # Remove entries older than the history duration
    while history and current_time - history[0][0] > ENERGY_HISTORY_DURATION_S:
        history.popleft()

def calculate_average_gyro(history: deque) -> float:
    """Calculates the average gyro magnitude from the history."""
    if not history:
        return 0.0
    total_mag = sum(mag for ts, mag in history)
    return total_mag / len(history)

def update_energy_level(current_energy: float, target_gyro_mag: float, average_gyro: float, delta_time: float) -> float:
    """Calculates the next energy level with smoothing and decay."""
    # 1. Smooth towards target (EMA-like approach using factor)
    # A simpler linear interpolation might be easier to tune:
    # max_increase = MAX_ENERGY_INCREASE_PER_SEC * delta_time
    # max_decrease = MAX_ENERGY_DECREASE_PER_SEC * delta_time
    # diff = target_gyro_mag - current_energy
    # change = clamp(diff, -max_decrease, max_increase)
    # next_energy = current_energy + change

    # Let's use the EMA factor approach for now:
    next_energy = (ENERGY_SMOOTHING_FACTOR * target_gyro_mag) + \
                  ((1.0 - ENERGY_SMOOTHING_FACTOR) * current_energy)

    # 2. Apply decay if energy is higher than the recent average
    if next_energy > average_gyro:
        decay_amount = (next_energy - average_gyro) * ENERGY_DECAY_RATE * delta_time
        next_energy -= decay_amount
        # Ensure decay doesn't overshoot below the average in one step
        next_energy = max(next_energy, average_gyro)

    # 3. Clamp the final energy level
    return clamp(next_energy, 0.0, MAX_MOTION_GYRO_MAGNITUDE * 1.1) # Allow slight overshoot visually? Or clamp strictly? Let's clamp strictly for now.
    # return clamp(next_energy, 0.0, MAX_MOTION_GYRO_MAGNITUDE)

def get_typhoon_classification(magnitude: float) -> str:
    """Returns the typhoon classification based on magnitude."""
    if magnitude <= 0:
        return "無風 (Calm)"
    # Iterate through sorted thresholds
    for name, threshold in _SORTED_THRESHOLDS:
        if magnitude <= threshold:
            return name
    # If magnitude is above the highest threshold
    return _SORTED_THRESHOLDS[-1][0] # Return highest category name

def display_energy_bar(energy: float, max_energy: float, width: int = 30) -> str:
    """Creates a simple text-based energy bar string."""
    if max_energy <= 0: return "[ ]"
    fill_level = clamp(energy / max_energy, 0.0, 1.0)
    filled_width = int(fill_level * width)
    bar = "#" * filled_width + "-" * (width - filled_width)
    return f"[{bar}]"

# --- Main Loop and Cleanup ---
def simulation_loop(joycon: RumbleJoyCon):
    """Main simulation loop including rumble and energy bar."""
    if not joycon:
        Debug.error("Invalid JoyCon object passed to rumble_loop.")
        return

    print("\n--- Starting Typhoon Simulation (Press Ctrl+C to stop) ---")
    print(f"Sim Duration: {SIMULATION_DURATION_S:.1f}s | Max Gyro Mag: {MAX_MOTION_GYRO_MAGNITUDE}")

    # Initialize states
    linger_state: LingerState = {"active": False, "peak_intensity": 0.0, "initial_duration": 0.0, "time_remaining": 0.0}
    current_energy: float = 0.0
    gyro_history: deque[Tuple[float, float]] = deque()  # Stores (timestamp, gyro_mag)

    loop_start_time = time.monotonic()
    last_time = loop_start_time
    final_average_gyro = 0.0  # To store the result

    try:
        while True:
            current_time = time.monotonic()
            delta_time = max(0.001, current_time - last_time)
            last_time = current_time

            # Check if simulation time is up
            if current_time - loop_start_time >= SIMULATION_DURATION_S:
                print("\n--- Simulation Time Ended ---")
                final_average_gyro = calculate_average_gyro(gyro_history)
                break  # Exit the main loop

            # 1. Read Sensors
            sensor_data = read_sensor_data(joycon)
            if sensor_data is None: time.sleep(0.05); continue
            gyro_mag = sensor_data['gyro_mag']

            # --- Rumble Calculation & Sending ---
            target_intensity = calculate_target_intensity(gyro_mag)
            linger_state = update_linger_state(linger_state, target_intensity, delta_time)
            current_decaying_intensity = calculate_decaying_intensity(linger_state)
            final_rumble_intensity = determine_final_intensity(target_intensity, current_decaying_intensity)
            send_rumble_command(joycon, final_rumble_intensity)  # Rumble happens based on its own logic

            # --- Energy Bar Calculation ---
            update_gyro_history(gyro_history, current_time, gyro_mag)
            average_gyro_10s = calculate_average_gyro(gyro_history)
            current_energy = update_energy_level(current_energy, gyro_mag, average_gyro_10s, delta_time)
            current_classification = get_typhoon_classification(current_energy)
            energy_bar_str = display_energy_bar(current_energy, MAX_MOTION_GYRO_MAGNITUDE)

            # --- Printing Status ---
            time_elapsed = current_time - loop_start_time
            print(f"\rTime: {time_elapsed: >4.1f}s | Gyro Now:{gyro_mag: >7.1f} Avg:{average_gyro_10s: >7.1f} | "
                  f"Energy:{current_energy: >7.1f} {energy_bar_str} | "
                  f"Rumble:{final_rumble_intensity: >4.2f} | {current_classification}        ",
                  end="")  # Added spaces to clear line
            sys.stdout.flush()

            # --- Accurate Sleep ---
            elapsed_this_iter = time.monotonic() - current_time
            sleep_duration = max(0.0, LOOP_SLEEP_TIME - elapsed_this_iter)
            time.sleep(sleep_duration)
    except KeyboardInterrupt:
        print("\nSimulation interrupted by user.")
        final_average_gyro = calculate_average_gyro(gyro_history)  # Calculate average even if interrupted
    finally:
        # --- Final Output ---
        print("\n--- Final Results ---")
        print(f"Average Gyro Magnitude over last {ENERGY_HISTORY_DURATION_S:.1f}s (or less): {final_average_gyro:.1f}")
        final_classification = get_typhoon_classification(final_average_gyro)
        print(f"Final Estimated Strength: {final_classification}")

        # Stop rumble
        try:
            print("Stopping final rumble...")
            if joycon: joycon.rumble_stop()
        except Exception as e:
            Debug.error(f"Error stopping rumble on exit: {e}")
        print("\r" + " " * 150 + "\r", end="")  # Clear the line

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
        print("\nFailed to initialize Right Joy-Con. Exiting.")
        sys.exit(1)

    start_signal_received = wait_for_button_press(joycon_right, target_button="A")

    if start_signal_received:
        perform_countdown_with_rumble(joycon_right)
        simulation_loop(joycon_right)
    else:
        print("\nStart signal not received (cancelled or error). Exiting.")

    # Uncomment to print detailed Joy-Con info
    # print_jc_info(joycon_right)

    print("Script finished.")