# TyphoonControl
This Python script uses a Nintendo Switch Right Joy-Con connected via Bluetooth to simulate a "typhoon" energy bar and provide corresponding haptic (rumble) feedback based on the controller's rotational speed (gyroscope data).

## Overview

The script connects to a Right Joy-Con, waits for the 'A' button press, performs a countdown sequence with rumble feedback, and then enters a simulation loop. During the simulation:

1.  It reads gyroscope data to determine the intensity of rotation.
2.  It controls the Joy-Con's HD Rumble feature, making it vibrate more intensely as the rotation speed increases.
3.  It implements a "linger" effect, where strong rumble bursts fade out gradually rather than stopping abruptly. The linger duration scales with the burst intensity.
4.  It simulates an "Energy Bar" that gradually increases based on the current rotation intensity and decreases towards a rolling average if the user stops rotating intensely.
5.  It classifies the current energy level into typhoon categories (from Tropical Depression to Super Typhoon) based on scaled thresholds.
6.  It displays the simulation status (time remaining, gyro magnitude, energy bar, rumble intensity, classification) in the terminal.
7.  The simulation runs for a fixed duration (default: 10 seconds).
8.  After the simulation ends (or is interrupted), it displays the final estimated typhoon strength based on the average rotational intensity over the last 10 seconds of the simulation.

## Features

*   **Real-time Rumble:** Haptic feedback intensity directly linked to gyroscope magnitude.
*   **Variable Rumble Linger:** Stronger rotational bursts result in longer-lasting rumble fade-outs (up to `MAX_LINGER_DURATION`).
*   **Typhoon Energy Bar:** Visual simulation of energy accumulation based on motion.
    *   **Smoothing:** Energy changes gradually follow input intensity.
    *   **Decay Rule:** Energy decays towards the recent average if current energy exceeds it, preventing artificially high sustained levels.
*   **Typhoon Classification:** Real-time and final classification based on established categories, scaled to gyroscope magnitude.
*   **Interactive Countdown:** Rumble pulses with increasing intensity/frequency accompany the "3-2-1-Start!" countdown.
*   **Button Activation:** Starts the simulation sequence only after pressing the 'A' button.
*   **Configurable Parameters:** Key thresholds, durations, frequencies, and smoothing factors can be easily adjusted via constants in the script.

## Requirements

*   **Hardware:**
    *   A Nintendo Switch **Right** Joy-Con controller.
    *   A computer (Linux, macOS, Windows) with Bluetooth support.
*   **Software:**
    *   Python 3.7+
    *   `pyjoycon` library: Handles communication with the Joy-Con.
    *   `hidapi` library: Low-level HID communication library (dependency for `pyjoycon`). **Setup can be OS-specific.**

## Usage

1.  **Save the Code:** Save the provided Python code as a file named `main.py`. (Ensure the `joycon_rumble.py` code is also present if you kept it as a separate file, although the final version integrated it).
2.  **Run the Script:** Open your terminal or command prompt, navigate to the directory where you saved the file, and run:
    ```bash
    python main.py
    ```
3.  **Connect:** The script will attempt to initialize the Right Joy-Con. Watch for any error messages.
4.  **Press 'A':** If initialization is successful, it will prompt you to press the 'A' button on the Joy-Con.
5.  **Countdown:** Upon pressing 'A', a 3-2-1 countdown with rumble pulses will occur.
6.  **Simulate:** After "Start!", rotate/spin the Joy-Con. The terminal will display the simulation status, and the controller will rumble based on your rotation speed.
7.  **Duration:** The simulation runs for the time specified by `SIMULATION_DURATION_S` (default 10 seconds).
8.  **Results:** After the time is up, the script prints the final average intensity and estimated typhoon strength.
9.  **Stop Early:** Press `Ctrl+C` in the terminal at any time to interrupt the script (button waiting, countdown, or simulation). It will attempt to stop rumble and print final results based on data collected so far.

## Customization

Many parameters can be adjusted by modifying the constants near the top of the `main.py` file:

*   `GYRO_RUMBLE_THRESHOLD`: Minimum rotation speed to trigger rumble.
*   `MAX_MOTION_GYRO_MAGNITUDE`: Rotation speed corresponding to max rumble (1.0 intensity) and the highest typhoon level.
*   `MAX_LINGER_DURATION`: Max duration (in seconds) for the rumble fade-out effect.
*   `RUMBLE_LOW_FREQ`, `RUMBLE_HIGH_FREQ`: Frequencies controlling the *feel* of the main rumble.
*   `COUNTDOWN_*` Constants: Modify the rumble feedback during the countdown.
*   `SIMULATION_DURATION_S`: Change the total runtime of the simulation phase.
*   `ENERGY_HISTORY_DURATION_S`: Affects the window for the rolling average calculation.
*   `ENERGY_SMOOTHING_FACTOR`: Controls how quickly the energy bar reacts (0 to 1, smaller is slower).
*   `ENERGY_DECAY_RATE`: Controls how fast energy drops towards the average when overshooting.

## Acknowledgements

*   This script relies heavily on the [pyjoycon](https://github.com/tocoteron/joycon-python) library for Joy-Con communication.
*   Rumble encoding logic derived from work in the JoyconLib project for Unity.

## License

MIT License