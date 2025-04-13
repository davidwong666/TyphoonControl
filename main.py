# --- START OF FILE main.py ---

from pyjoycon import get_R_id
from joycon_rumble import RumbleJoyCon, RumbleData, clamp
import math
import sys
import time
import atexit
from typing import Tuple, Dict, Optional, TypedDict, Callable
from collections import deque # Used for efficient history tracking (gyro readings)

# Global variable to hold the Joy-Con object
joycon_right: Optional[RumbleJoyCon] = None # Type hint for clarity
# TODO: Left Joy-Con support (if needed) - requires separate initialization and button mapping

# --- Constants for Motion-Based Rumble and Simulation ---

# -- Gyroscope Settings --
GYRO_RUMBLE_THRESHOLD = 6000  # Minimum gyro magnitude (rotational speed) required to start rumbling.
MAX_MOTION_GYRO_MAGNITUDE = 25000 # Gyro magnitude that corresponds to the maximum rumble intensity (1.0) and the highest typhoon category.

# -- Linger Settings (Rumble effect fade-out) --
MAX_LINGER_DURATION = 1.5 # Seconds. The maximum duration the rumble effect will linger after a peak intensity burst (scales with intensity).

# -- Rumble Feel Settings (Main Simulation Loop) --
RUMBLE_LOW_FREQ = 300  # Hz. Low frequency component for the main rumble effect.
RUMBLE_HIGH_FREQ = 800 # Hz. High frequency component for the main rumble effect.

# -- Countdown Rumble Settings --
COUNTDOWN_BASE_FREQ_HZ = 90         # Starting high frequency for the countdown rumble pulse ("3").
COUNTDOWN_FREQ_STEP_HZ = 30         # Amount to increase high frequency for each countdown step ("2", "1", "Start!").
COUNTDOWN_BASE_INTENSITY = 0.3      # Starting rumble intensity for the countdown pulse ("3").
COUNTDOWN_INTENSITY_STEP = 0.1      # Amount to increase intensity for each countdown step.
COUNTDOWN_PULSE_DURATION_S = 0.15   # Duration of the rumble pulse for "3", "2", "1".
COUNTDOWN_START_PULSE_DURATION_S = 0.2 # Duration of the rumble pulse for "Start!".

# -- Timing --
LOOP_SLEEP_TIME = 0.05 # Target time interval (in seconds) for each iteration of the main simulation loop (approx 20 Hz update rate). Affects responsiveness and decay calculations.
SIMULATION_DURATION_S = 10.0 # Total duration (in seconds) the main simulation loop will run for energy accumulation and final strength assessment.

# -- Energy Bar Settings --
ENERGY_HISTORY_DURATION_S = 10.0 # How many seconds of recent gyroscope data to consider for the rolling average calculation.
ENERGY_SMOOTHING_FACTOR = 0.15   # Exponential Moving Average (EMA) like factor (alpha). Smaller values result in smoother but slower energy level changes. Range (0, 1).
ENERGY_DECAY_RATE = 0.6          # Rate (as a fraction per second) at which the energy level decays towards the rolling average when the energy level is currently higher than the average. Prevents energy staying high after motion stops.

# -- Typhoon Classification Thresholds --
# Scales wind speeds (km/h) to gyroscope magnitude values.
# Assumes MAX_MOTION_GYRO_MAGNITUDE corresponds roughly to the wind speed of the highest category (Super Typhoon, 185 km/h).
_SCALE_FACTOR = MAX_MOTION_GYRO_MAGNITUDE / 185.0
TYPHOON_THRESHOLDS = {
    "熱帶低氣壓 (Tropical Depression)": 41 * _SCALE_FACTOR,
    "熱帶風暴 (Tropical Storm)": 63 * _SCALE_FACTOR,
    "強烈熱帶風暴 (Severe Tropical Storm)": 88 * _SCALE_FACTOR,
    "颱風 (Typhoon)": 118 * _SCALE_FACTOR,
    "強颱風 (Severe Typhoon)": 150 * _SCALE_FACTOR,
    "超強颱風 (Super Typhoon)": 185 * _SCALE_FACTOR, # This threshold should approximately equal MAX_MOTION_GYRO_MAGNITUDE
}
# Sort thresholds by magnitude value for efficient lookup during classification.
_SORTED_THRESHOLDS = sorted(TYPHOON_THRESHOLDS.items(), key=lambda item: item[1])

# --- Create Level Mapping (After sorting thresholds) ---
# Assigns a numerical level to each classification name.
_NUM_TYPHOON_LEVELS = len(_SORTED_THRESHOLDS) + 1 # Total number of levels (including Calm at level 0).
_NAME_TO_LEVEL_MAP = {name: i + 1 for i, (name, _) in enumerate(_SORTED_THRESHOLDS)} # Levels 1 to N for storm categories.
_NAME_TO_LEVEL_MAP["無風 (Calm)"] = 0 # Assign level 0 specifically to Calm.

# --- End Constants ---

class Debug:
    """Simple utility class for conditional debug/info/error printing."""
    ENABLED = True # Set to False to disable debug messages
    @staticmethod
    def log(message: str):
        if Debug.ENABLED: print(f"[DEBUG] {message}")
    @staticmethod
    def error(message: str):
        # Always print errors to stderr if enabled
        if Debug.ENABLED: print(f"[ERROR] {message}", file=sys.stderr)
    @staticmethod
    def info(message: str):
        if Debug.ENABLED: print(f"[INFO] {message}")

# --- Type Definitions ---
# Using TypedDict for better code structure and readability when passing complex data.
class SensorData(TypedDict):
    """Structure to hold raw sensor readings and calculated magnitudes."""
    ax: float; ay: float; az: float
    gx: float; gy: float; gz: float
    accel_mag: float
    gyro_mag: float

class LingerState(TypedDict):
    """Structure to hold the state variables for the rumble linger effect."""
    active: bool             # Is a linger effect currently happening?
    peak_intensity: float    # The rumble intensity that triggered the current linger.
    initial_duration: float  # The total duration calculated for this specific linger (based on peak_intensity).
    time_remaining: float    # How much time (in seconds) is left for the current linger effect.

# --- Initialization ---
def initialize_right_joycon() -> Optional[RumbleJoyCon]:
    """
    Attempts to find and initialize the right Joy-Con.
    Enables vibration capability required for rumble effects.
    Returns the RumbleJoyCon object or None if initialization fails.
    """
    global joycon_right
    try:
        # Find the HID device for the right Joy-Con
        joycon_id_right = get_R_id()
        if not joycon_id_right:
            Debug.error("Right Joy-Con not found. Ensure it's paired and connected via Bluetooth.")
            return None
        Debug.info(f"Found Right Joy-Con: vendor_id={joycon_id_right[0]}, product_id={joycon_id_right[1]}, serial={joycon_id_right[2]}")

        # Create the RumbleJoyCon instance
        joycon_right = RumbleJoyCon(*joycon_id_right)

        # Enable vibration (necessary for sending rumble commands)
        try:
            joycon_right.enable_vibration(True)
            time.sleep(0.1)  # Short delay after enabling vibration
            Debug.info("Vibration enabled.")
        except Exception as vib_e:
            # Log error but attempt to continue; rumble might fail later
            Debug.error(f"Failed to explicitly enable vibration during init: {vib_e}")

        Debug.info("Right Joy-Con initialized.")
        time.sleep(0.5)  # Allow time for connection to stabilize before use
        return joycon_right
    except Exception as e:
        Debug.error(f"Error initializing Right Joy-Con: {e}")
        import traceback; traceback.print_exc() # Print full traceback for debugging
        return None

# --- Button Mapping ---
# Maps descriptive button names to lambda functions that call the corresponding
# JoyCon getter method. Lambdas prevent immediate method calls.
BUTTON_METHOD_MAP_RIGHT: Dict[str, Callable[[RumbleJoyCon], bool]] = {
    "A": lambda jc: jc.get_button_a(),
    "B": lambda jc: jc.get_button_b(),
    "X": lambda jc: jc.get_button_x(),
    "Y": lambda jc: jc.get_button_y(),
    "R": lambda jc: jc.get_button_r(),       # Shoulder button
    "ZR": lambda jc: jc.get_button_zr(),      # Trigger button
    "PLUS": lambda jc: jc.get_button_plus(),  # '+' button
    "HOME": lambda jc: jc.get_button_home(),  # Home button
    "R_STICK": lambda jc: jc.get_button_r_stick(), # Press down on right stick
    "SL": lambda jc: jc.get_button_right_sl(), # Small side button (when detached)
    "SR": lambda jc: jc.get_button_right_sr(), # Small side button (when detached)
}

# --- Button Detection Function ---
def wait_for_button_press(joycon: RumbleJoyCon, target_button: str) -> bool:
    """
    Continuously monitors button states until the specified 'target_button'
    registers a press event (transition from not pressed to pressed).

    Args:
        joycon: The initialized RumbleJoyCon object.
        target_button: The string name of the button to wait for (must be a key in BUTTON_METHOD_MAP_RIGHT).

    Returns:
        True if the target button was pressed successfully.
        False if waiting was cancelled (Ctrl+C) or an error occurred (e.g., disconnection).
    """
    # Input validation
    if not joycon:
        Debug.error("Invalid JoyCon object passed to wait_for_button_press.")
        return False
    if target_button not in BUTTON_METHOD_MAP_RIGHT:
        Debug.error(f"Target button '{target_button}' not defined in BUTTON_METHOD_MAP_RIGHT.")
        return False

    print(f"\n--- Waiting for '{target_button}' press (Press Ctrl+C to cancel) ---")
    print(f"Press the '{target_button}' button on the right Joy-Con to start the simulation...")

    # Stores the state of each button from the *previous* loop iteration
    previous_button_states: Dict[str, bool] = {name: False for name in BUTTON_METHOD_MAP_RIGHT}
    target_getter = BUTTON_METHOD_MAP_RIGHT[target_button] # Get the specific method for the target button

    try:
        # Loop indefinitely until the target button is pressed or interrupted
        while True:
            try:
                # Check the target button's current state
                is_pressed_now = target_getter(joycon)

                # Detect press: Currently pressed AND wasn't pressed previously
                if is_pressed_now and not previous_button_states.get(target_button, False):
                    print(f"\n[BUTTON PRESS] {target_button} detected!")
                    # Update state immediately to prevent re-triggering if loop is very fast
                    previous_button_states[target_button] = True
                    return True # Signal success and exit

                # Update the previous state for the target button for the next iteration
                # Handles both release and continued holding (prevents re-trigger)
                previous_button_states[target_button] = is_pressed_now

            except AttributeError:
                # Likely Joy-Con disconnected or not fully initialized
                Debug.error("\nError accessing button state. Joy-Con likely disconnected.")
                time.sleep(1) # Pause before potentially exiting
                return False # Signal failure
            except Exception as e:
                # Catch other potential errors during button reading
                Debug.error(f"\nUnexpected error reading button state: {e}")
                time.sleep(0.5) # Pause before retrying
                continue # Continue the loop

            # Short sleep to prevent high CPU usage while polling
            time.sleep(0.03)

    except KeyboardInterrupt:
        # User pressed Ctrl+C
        print("\nButton waiting cancelled by user.")
        return False # Signal cancellation
    finally:
        # Executes regardless of whether the loop exited normally or via exception/return
        print("--- Button waiting finished. ---")

# --- Rumble Pulse Function ---
def rumble_pulse(joycon: RumbleJoyCon, low_freq: float, high_freq: float, intensity: float, duration: float):
    """
    Sends a single, short rumble pulse with specified parameters and then stops the rumble.
    Used for distinct feedback like the countdown.

    Args:
        joycon: The initialized RumbleJoyCon object.
        low_freq: Low frequency component (Hz).
        high_freq: High frequency component (Hz).
        intensity: Rumble intensity (0.0 to 1.0).
        duration: Duration of the pulse (in seconds).
    """
    if not joycon: return # Don't proceed if joycon is invalid
    try:
        # Clamp input values to safe/valid ranges for the rumble hardware/API
        low_freq = clamp(low_freq, 41, 626)
        high_freq = clamp(high_freq, 82, 1253)
        intensity = clamp(intensity, 0.0, 1.0)
        duration = max(0.01, duration) # Ensure a minimal duration to prevent issues

        # Generate the rumble data packet
        rumble_data_gen = RumbleData(low_freq, high_freq, intensity)
        rumble_bytes = rumble_data_gen.GetData()

        # Send the rumble command
        joycon._send_rumble(rumble_bytes)

        # Wait for the specified pulse duration
        time.sleep(duration)

        # Explicitly stop the rumble after the pulse
        joycon.rumble_stop()

    except Exception as e:
        Debug.error(f"Error during rumble pulse: {e}")
        # Attempt to stop rumble even if an error occurred during the pulse
        try:
            if joycon: joycon.rumble_stop()
        except: pass # Ignore errors during emergency stop


# --- Countdown Function ---
def perform_countdown_with_rumble(joycon: RumbleJoyCon):
    """
    Prints a 3-2-1-Start countdown sequence to the console, accompanied by
    distinct rumble pulses with increasing intensity and frequency for each step.
    """
    if not joycon:
        Debug.error("Cannot perform countdown: invalid JoyCon object.")
        return

    print("\nStarting simulation in...")
    time.sleep(0.5) # Initial brief pause before countdown starts

    # Define parameters for each step of the countdown (text, high freq, intensity, duration)
    countdown_steps = [
        ("3", COUNTDOWN_BASE_FREQ_HZ + 0 * COUNTDOWN_FREQ_STEP_HZ, COUNTDOWN_BASE_INTENSITY + 0 * COUNTDOWN_INTENSITY_STEP, COUNTDOWN_PULSE_DURATION_S),
        ("2", COUNTDOWN_BASE_FREQ_HZ + 1 * COUNTDOWN_FREQ_STEP_HZ, COUNTDOWN_BASE_INTENSITY + 1 * COUNTDOWN_INTENSITY_STEP, COUNTDOWN_PULSE_DURATION_S),
        ("1", COUNTDOWN_BASE_FREQ_HZ + 2 * COUNTDOWN_FREQ_STEP_HZ, COUNTDOWN_BASE_INTENSITY + 2 * COUNTDOWN_INTENSITY_STEP, COUNTDOWN_PULSE_DURATION_S),
    ]
    # Define the "Start!" step separately (potentially different duration/intensity)
    start_step = ("Start!", COUNTDOWN_BASE_FREQ_HZ + 3 * COUNTDOWN_FREQ_STEP_HZ, COUNTDOWN_BASE_INTENSITY + 3 * COUNTDOWN_INTENSITY_STEP, COUNTDOWN_START_PULSE_DURATION_S)

    # Execute the "3", "2", "1" steps
    for text, hf, intensity, duration in countdown_steps:
        # Calculate a suitable low frequency (e.g., related to high freq, but clamped)
        lf = max(41.0, hf * 0.6) # Ensure low freq is within valid range
        # Send the rumble pulse for this step
        rumble_pulse(joycon, lf, hf, intensity, duration)
        # Print the countdown number immediately after the pulse starts
        print(text, flush=True) # flush=True ensures it appears without waiting for newline
        # Pause between steps, accounting for the time the rumble pulse already took
        # Aims for roughly a 1-second interval between the *start* of each step's print/rumble
        time.sleep(max(0.0, 1.0 - duration))

    # Execute the final "Start!" step
    lf_start = max(41.0, start_step[1] * 0.6) # Calculate low frequency for "Start!"
    rumble_pulse(joycon, lf_start, start_step[1], start_step[2], start_step[3])
    print(start_step[0], flush=True)
    # Short pause after "Start!" before the main simulation loop begins
    time.sleep(max(0.0, 0.2 - start_step[3]))


# --- Core Calculation Functions ---
def read_sensor_data(joycon: RumbleJoyCon) -> Optional[SensorData]:
    """
    Reads accelerometer and gyroscope data from the Joy-Con.
    Calculates the vector magnitudes for both sensors.

    Returns:
        A SensorData dictionary containing raw axes and magnitudes,
        or None if reading fails or data is incomplete.
    """
    try:
        # Get raw sensor values
        accel_x = joycon.get_accel_x(); accel_y = joycon.get_accel_y(); accel_z = joycon.get_accel_z()
        gyro_x = joycon.get_gyro_x(); gyro_y = joycon.get_gyro_y(); gyro_z = joycon.get_gyro_z()

        # Check if any sensor reading failed (might return None)
        if None in (accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z):
             Debug.log("Incomplete sensor data received.")
             return None

        # Calculate magnitude of acceleration vector (includes gravity)
        accel_magnitude = math.sqrt(accel_x**2 + accel_y**2 + accel_z**2)
        # Calculate magnitude of gyroscope vector (angular velocity)
        gyro_magnitude = math.sqrt(gyro_x**2 + gyro_y**2 + gyro_z**2)

        # Return data packed in a dictionary, ensuring float types
        return {
            "ax": float(accel_x), "ay": float(accel_y), "az": float(accel_z),
            "gx": float(gyro_x), "gy": float(gyro_y), "gz": float(gyro_z),
            "accel_mag": accel_magnitude,
            "gyro_mag": gyro_magnitude
        }
    except AttributeError as e:
        # Handle cases where the Joy-Con object might be invalid or methods don't exist
        if "'NoneType' object has no attribute" in str(e):
            Debug.log("Sensor methods not available yet (Joy-Con might be None).")
        else:
            Debug.error(f"AttributeError reading sensors: {e}")
        return None
    except Exception as e:
        # Catch any other unexpected errors during sensor reading
        Debug.error(f"Unexpected error reading sensors: {e}")
        import traceback; traceback.print_exc()
        return None

def calculate_target_intensity(gyro_magnitude: float) -> float:
    """
    Calculates the target rumble intensity (0.0 to 1.0) based solely on the
    current gyroscope magnitude, using the defined threshold and maximum constants.
    This represents the intensity desired *right now* due to motion.
    """
    # No rumble if below the activation threshold
    if gyro_magnitude < GYRO_RUMBLE_THRESHOLD:
        return 0.0

    # Calculate the effective range for scaling intensity
    active_range_size = MAX_MOTION_GYRO_MAGNITUDE - GYRO_RUMBLE_THRESHOLD
    # Calculate how far the current magnitude is into this active range
    value_in_range = gyro_magnitude - GYRO_RUMBLE_THRESHOLD

    # Handle edge case where threshold might be >= max (shouldn't happen with valid constants)
    if active_range_size <= 0:
        return 1.0 if gyro_magnitude >= GYRO_RUMBLE_THRESHOLD else 0.0

    # Scale the value within the range linearly to [0.0, 1.0]
    intensity = value_in_range / active_range_size

    # Clamp the result to ensure it's strictly within [0.0, 1.0]
    return clamp(intensity, 0.0, 1.0)

def calculate_decaying_intensity(state: LingerState) -> float:
    """
    Calculates the current rumble intensity based *only* on the linger state.
    Assumes linear decay from the peak intensity over the initial duration.
    """
    # No intensity if linger isn't active or duration is invalid
    if not state["active"] or state["initial_duration"] <= 0:
        return 0.0

    # Calculate the fraction of time remaining for the linger effect
    decay_factor = state["time_remaining"] / state["initial_duration"]
    # Multiply the original peak intensity by the decay factor
    intensity = state["peak_intensity"] * decay_factor

    # Ensure intensity doesn't become negative due to float precision
    return max(0.0, intensity)

def update_linger_state(current_state: LingerState, target_intensity: float, delta_time: float) -> LingerState:
    """
    Updates the rumble linger state based on the current motion (`target_intensity`)
    and the time elapsed since the last update (`delta_time`).
    Handles triggering, resetting, and decaying the linger effect.

    Args:
        current_state: The LingerState dictionary from the previous iteration.
        target_intensity: The intensity calculated from the current gyroscope motion.
        delta_time: Time elapsed since the last update (in seconds).

    Returns:
        A new LingerState dictionary representing the updated state.
    """
    new_state = current_state.copy() # Work on a copy to avoid modifying the original dict directly

    # Calculate what the intensity *would be* if the current linger just continued decaying
    potential_decaying_intensity = calculate_decaying_intensity(current_state)

    # --- Trigger or Reset Linger ---
    # A new linger effect starts (or overrides the current one) if:
    # 1. The current motion intensity is significant (target_intensity > 0)
    # 2. This current motion intensity is stronger than (or equal to) what the
    #    previous linger effect would have decayed to by now. This ensures
    #    stronger bursts override weaker, decaying ones.
    if target_intensity > 0 and target_intensity >= potential_decaying_intensity:
        new_state["active"] = True # Mark linger as active
        new_state["peak_intensity"] = target_intensity # Store the intensity that triggered this linger
        # Calculate the initial duration for *this specific* linger, scaled by its intensity
        new_state["initial_duration"] = target_intensity * MAX_LINGER_DURATION
        # Reset the remaining time to the full calculated duration
        new_state["time_remaining"] = new_state["initial_duration"]
        # Debug.log(f"Linger Trigger/Reset: Peak={target_intensity:.2f}, InitDur={new_state['initial_duration']:.2f}")

    # --- Decay Existing Linger ---
    # If no new trigger occurred, but a linger was already active, decay it.
    elif new_state["active"]:
        # Reduce remaining time by the time elapsed since last update
        new_state["time_remaining"] -= delta_time
        # Check if the linger duration has run out
        if new_state["time_remaining"] <= 0:
            # Linger has ended, reset the state to inactive
            new_state["active"] = False
            new_state["time_remaining"] = 0.0
            new_state["peak_intensity"] = 0.0
            new_state["initial_duration"] = 0.0
            # Debug.log("Linger Ended")
        # else:
            # Optional: Log remaining time during decay
            # Debug.log(f"Lingering: Remain={new_state['time_remaining']:.2f}")

    # If no new trigger and not currently active, the state remains inactive.
    return new_state # Return the updated state dictionary

def determine_final_intensity(target_intensity: float, decaying_intensity: float) -> float:
    """
    Determines the final rumble intensity to be sent to the Joy-Con.
    It takes the higher value between the intensity demanded by the current
    motion (`target_intensity`) and the intensity from the decaying linger effect.
    This ensures the rumble feels responsive to new motion even during a fade-out.
    """
    return max(target_intensity, decaying_intensity)

def send_rumble_command(joycon: RumbleJoyCon, intensity: float):
    """
    Generates the 8-byte rumble data packet based on the final intensity
    and the configured low/high frequencies, then sends it to the Joy-Con.
    """
    try:
        # Create the RumbleData object (handles frequency/amplitude encoding)
        rumble_data_generator = RumbleData(RUMBLE_LOW_FREQ, RUMBLE_HIGH_FREQ, intensity)
        # Get the encoded byte packet
        rumble_bytes = rumble_data_generator.GetData()
        # Send the packet via the Joy-Con's internal method
        joycon._send_rumble(rumble_bytes)
    except Exception as e:
        # Catch potential errors during data generation or HID communication
        Debug.error(f"Failed to generate or send rumble command: {e}")

# --- Energy Bar & Classification Functions ---
def update_gyro_history(history: deque, current_time: float, gyro_mag: float):
    """
    Maintains a time-windowed history of gyroscope magnitudes using a deque.
    Adds the latest reading and removes readings older than ENERGY_HISTORY_DURATION_S.

    Args:
        history: The deque object storing (timestamp, magnitude) tuples.
        current_time: The timestamp of the current reading (e.g., from time.monotonic()).
        gyro_mag: The gyroscope magnitude from the current reading.
    """
    # Add the new reading (timestamp, value) to the right end of the deque
    history.append((current_time, gyro_mag))
    # Remove old entries from the left end until the oldest entry is within the history duration
    while history and (current_time - history[0][0] > ENERGY_HISTORY_DURATION_S):
        history.popleft() # popleft() is efficient for deques

def calculate_average_gyro(history: deque) -> float:
    """Calculates the simple moving average of gyroscope magnitudes in the history deque."""
    if not history: # Handle empty history (e.g., at the very beginning)
        return 0.0
    # Sum all magnitude values in the history
    total_mag = sum(mag for ts, mag in history)
    # Divide by the number of entries to get the average
    return total_mag / len(history)

def update_energy_level(current_energy: float, target_gyro_mag: float, average_gyro: float, delta_time: float) -> float:
    """
    Calculates the energy level for the next iteration based on current energy,
    target motion, recent average motion, and time elapsed.
    Applies smoothing and decay rules.

    Args:
        current_energy: The energy level from the previous iteration.
        target_gyro_mag: The gyroscope magnitude from the current sensor reading.
        average_gyro: The rolling average gyroscope magnitude over the history window.
        delta_time: Time elapsed since the last update.

    Returns:
        The calculated energy level for the current iteration, clamped to valid range.
    """
    # 1. Smooth towards the current target gyro magnitude (Exponential Moving Average -like)
    # The energy level moves a fraction (ENERGY_SMOOTHING_FACTOR) of the way
    # from its current value towards the target value in each step.
    next_energy = (ENERGY_SMOOTHING_FACTOR * target_gyro_mag) + \
                  ((1.0 - ENERGY_SMOOTHING_FACTOR) * current_energy)

    # 2. Apply Decay Rule: If the smoothed energy is higher than the recent average,
    #    make it decay towards that average to simulate energy dissipation.
    if next_energy > average_gyro:
        # Calculate how much energy to dissipate this step
        decay_amount = (next_energy - average_gyro) * ENERGY_DECAY_RATE * delta_time
        # Subtract the decay amount
        next_energy -= decay_amount
        # Ensure the decay doesn't pull the energy *below* the average in a single step
        next_energy = max(next_energy, average_gyro)

    # 3. Clamp the final energy level to the valid range [0, MAX_MOTION_GYRO_MAGNITUDE]
    # This prevents energy from exceeding the defined maximum scale.
    return clamp(next_energy, 0.0, MAX_MOTION_GYRO_MAGNITUDE)

def get_typhoon_classification(magnitude: float) -> str:
    """
    Maps a gyroscope magnitude value to a typhoon classification string,
    including a formatted level (e.g., "Level 3/6: Typhoon").

    Args:
        magnitude: The gyroscope magnitude value (can be current energy or average).

    Returns:
        A formatted string representing the typhoon classification and level.
    """
    classification_name = "無風 (Calm)" # Default classification

    # Determine the name based on thresholds only if magnitude is positive
    if magnitude > 0:
        found_category = False
        # Iterate through the *sorted* thresholds
        for name, threshold in _SORTED_THRESHOLDS:
            # Find the first category whose threshold is >= the magnitude
            if magnitude <= threshold:
                classification_name = name
                found_category = True
                break
        # If magnitude exceeds the highest threshold, assign the highest category name
        if not found_category:
             classification_name = _SORTED_THRESHOLDS[-1][0]

    # Look up the numerical level corresponding to the determined name
    # Uses the pre-calculated _NAME_TO_LEVEL_MAP for efficiency
    level = _NAME_TO_LEVEL_MAP.get(classification_name, 0) # Default to level 0 if name somehow isn't found

    # Format the final output string (Level X / TotalLevels: Name)
    # Note: (_NUM_TYPHOON_LEVELS - 1) gives the max storm level number (excluding Calm)
    return f"Level {level}/{_NUM_TYPHOON_LEVELS - 1}: {classification_name}"

def display_energy_bar(energy: float, max_energy: float, width: int = 30) -> str:
    """
    Generates a simple text-based progress bar string to visualize the energy level.

    Args:
        energy: The current energy value.
        max_energy: The maximum possible energy value (used for scaling).
        width: The desired character width of the bar itself (excluding brackets).

    Returns:
        A string representing the energy bar (e.g., "[#########-----------]").
    """
    if max_energy <= 0: return "[ ]" # Handle zero or negative max energy
    # Calculate the fill ratio (0.0 to 1.0)
    fill_level = clamp(energy / max_energy, 0.0, 1.0)
    # Calculate how many '#' characters to display
    filled_width = int(fill_level * width)
    # Create the bar string
    bar = "#" * filled_width + "-" * (width - filled_width)
    return f"[{bar}]" # Return the bar enclosed in brackets

# --- Main Simulation Loop ---
def simulation_loop(joycon: RumbleJoyCon):
    """
    The main execution loop for the typhoon simulation.
    Handles sensor reading, rumble feedback (including linger), energy bar updates,
    classification, status printing, and timing control for a fixed duration.
    """
    if not joycon:
        Debug.error("Invalid JoyCon object passed to simulation_loop.")
        return

    print("\n--- Starting Typhoon Simulation (Press Ctrl+C to stop) ---")
    print(f"Sim Duration: {SIMULATION_DURATION_S:.1f}s | Target Max Gyro Mag: {MAX_MOTION_GYRO_MAGNITUDE}")

    # Initialize state variables for this simulation run
    linger_state: LingerState = {"active": False, "peak_intensity": 0.0, "initial_duration": 0.0, "time_remaining": 0.0}
    current_energy: float = 0.0
    gyro_history: deque[Tuple[float, float]] = deque()  # Stores (timestamp, gyro_mag)

    # Timing variables
    loop_start_time = time.monotonic() # Record the absolute start time of the loop
    last_time = loop_start_time        # Timestamp of the previous loop iteration start
    final_average_gyro = 0.0           # Variable to store the final result

    try:
        # Main simulation loop
        while True:
            current_time = time.monotonic() # Get timestamp at the start of this iteration
            # Calculate time elapsed since the *last iteration* (delta_time)
            delta_time = max(0.001, current_time - last_time) # Ensure dt is positive
            last_time = current_time # Update last_time for the next iteration

            # --- Check simulation end time ---
            time_elapsed = current_time - loop_start_time  # Calculate elapsed time first
            if time_elapsed >= SIMULATION_DURATION_S:
                print("\n--- Simulation Time Ended ---")
                final_average_gyro = calculate_average_gyro(gyro_history)
                break  # Exit the main loop

            # --- Calculate remaining time for display ---
            # Ensure it doesn't display negative time if loop runs slightly over
            time_remaining = max(0.0, SIMULATION_DURATION_S - time_elapsed)

            # --- Sensor Reading ---
            sensor_data = read_sensor_data(joycon)
            if sensor_data is None: time.sleep(LOOP_SLEEP_TIME); continue
            gyro_mag = sensor_data['gyro_mag']

            # --- Rumble Calculation & Sending ---
            target_intensity = calculate_target_intensity(gyro_mag)
            linger_state = update_linger_state(linger_state, target_intensity, delta_time)
            current_decaying_intensity = calculate_decaying_intensity(linger_state)
            final_rumble_intensity = determine_final_intensity(target_intensity, current_decaying_intensity)
            send_rumble_command(joycon, final_rumble_intensity)

            # --- Energy Bar Calculation ---
            update_gyro_history(gyro_history, current_time, gyro_mag)
            average_gyro_10s = calculate_average_gyro(gyro_history)
            current_energy = update_energy_level(current_energy, gyro_mag, average_gyro_10s, delta_time)
            current_classification_str = get_typhoon_classification(current_energy)
            energy_bar_str = display_energy_bar(current_energy, MAX_MOTION_GYRO_MAGNITUDE)

            # --- Printing Status (Modified Time Display) ---
            # Display remaining time instead of elapsed time
            print(
                f"\rTime Left: {time_remaining: >4.1f}s | Gyro Now:{gyro_mag: >7.1f} Avg:{average_gyro_10s: >7.1f} | "  # <-- MODIFIED LABEL AND VARIABLE
                f"Energy:{current_energy: >7.1f} {energy_bar_str} | "
                f"Rumble:{final_rumble_intensity: >4.2f} | {current_classification_str}        ",
                end="")
            sys.stdout.flush()

            # --- Accurate Sleep ---
            elapsed_this_iter = time.monotonic() - current_time
            sleep_duration = max(0.0, LOOP_SLEEP_TIME - elapsed_this_iter)
            time.sleep(sleep_duration)

    except KeyboardInterrupt:
        # User pressed Ctrl+C to interrupt the loop
        print("\nSimulation interrupted by user.")
        # Calculate the average based on history collected so far
        final_average_gyro = calculate_average_gyro(gyro_history)
    finally:
        # This block executes whether the loop finished normally or was interrupted

        # --- Final Output ---
        print("\n--- Final Results ---")
        # Print the average gyro magnitude calculated (either at end or interruption)
        print(f"Average Gyro Magnitude over last {ENERGY_HISTORY_DURATION_S:.1f}s (or duration run): {final_average_gyro:.1f}")
        # Determine and print the final classification based on the average
        final_classification_str = get_typhoon_classification(final_average_gyro)
        print(f"Final Estimated Strength: {final_classification_str}")

        # --- Stop Rumble ---
        # Ensure rumble is stopped cleanly on exit
        try:
            print("Stopping final rumble...")
            if joycon: joycon.rumble_stop() # Check if joycon object exists
        except Exception as e:
            Debug.error(f"Error stopping rumble on exit: {e}")
        # Clear the last status line from the console
        print("\r" + " " * 150 + "\r", end="") # Print enough spaces to overwrite typical status line length


def cleanup():
    """Performs cleanup actions when the script exits (registered with atexit)."""
    global joycon_right
    print("\nExiting script...")
    try:
        # Check if joycon object exists and has the necessary method before calling
        if joycon_right and hasattr(joycon_right, 'rumble_stop') and callable(joycon_right.rumble_stop):
            Debug.info("Ensuring Joy-Con rumble is stopped...")
            joycon_right.rumble_stop() # Stop any lingering rumble
        # Potentially add disconnection logic here if needed
        Debug.info("Cleanup complete.")
    except Exception as e:
        Debug.error(f"Error during cleanup: {e}")

# --- Main Entry Point ---
if __name__ == "__main__":
    # Register the cleanup function to be called automatically upon script exit
    atexit.register(cleanup)

    # Initialize the Joy-Con
    print("Initializing Right Joy-Con...")
    joycon_right = initialize_right_joycon()

    # Proceed only if initialization was successful
    if joycon_right:
        # 1. Wait for the user to press the 'A' button to start
        start_signal_received = wait_for_button_press(joycon_right, target_button="A")

        # 2. If 'A' was pressed, perform the countdown and start the main simulation
        if start_signal_received:
            perform_countdown_with_rumble(joycon_right)
            simulation_loop(joycon_right) # Start the main simulation loop
        else:
            # User cancelled waiting (Ctrl+C) or an error occurred
            print("\nStart signal not received (cancelled or error). Exiting.")

    else:
        # Initialization failed
        print("\nFailed to initialize Right Joy-Con. Exiting.")
        sys.exit(1) # Exit with a non-zero code to indicate failure

    # Script execution finished (either normally or after simulation/cancellation)
    print("Script finished.")

# --- END OF FILE main.py ---