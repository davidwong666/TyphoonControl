import math
from pyjoycon import JoyCon
import sys # For printing errors

# Use slightly clearer variable names in clamp
def clamp(value, min_val, max_val):
    """Clamps value between min_val and max_val."""
    if (value < min_val): return min_val;
    if (value > max_val): return max_val;
    return value;

class RumbleJoyCon(JoyCon):
    def __init__(self, *args, **kwargs):
        JoyCon.__init__(self, *args, **kwargs)

    def _send_rumble(self, data=b'\x00\x00\x00\x00\x00\x00\x00\x00'):
        try:
            # Basic check for data length
            if len(data) != 8:
                 print(f"[RumbleJoyCon Error] Invalid rumble data length: {len(data)}. Using default off.", file=sys.stderr)
                 data = b'\x00\x01\x40\x40\x00\x01\x40\x40' # Default off packet
            self._RUMBLE_DATA = data
            self._write_output_report(b'\x10', b'', b'')
        except Exception as e:
            print(f"[RumbleJoyCon Error] Failed to send rumble: {e}", file=sys.stderr)
            # Avoid crashing the main loop if rumble sending fails

    def enable_vibration(self, enable=True):
        """Sends enable or disable command for vibration."""
        try:
            self._write_output_report(b'\x01', b'\x48', b'\x01' if enable else b'\x00')
        except Exception as e:
             print(f"[RumbleJoyCon Error] Failed to enable/disable vibration: {e}", file=sys.stderr)

    def rumble_simple(self):
        """Rumble for approximately 1.5 seconds. Repeat sending to keep rumbling."""
        self._send_rumble(b'\x98\x1e\xc6\x47\x98\x1e\xc6\x47')

    def rumble_stop(self):
        """Instantly stops the rumble"""
        self._send_rumble(b'\x00\x01\x40\x40\x00\x01\x40\x40') # Use official off packet


# derived from https://github.com/Looking-Glass/JoyconLib/blob/master/Packages/com.lookingglass.joyconlib/JoyconLib_scripts/Joycon.cs
class RumbleData:
    # __init__ using set_vals for consistency
    def __init__(self, low_freq, high_freq, amplitude, time=0):
        self.set_vals(low_freq, high_freq, amplitude, time)

    def set_vals(self, low_freq, high_freq, amplitude, time=0):
        # Store the original values if needed, but calculations use clamped versions
        self.h_f = high_freq;
        self.amp = amplitude;
        self.l_f = low_freq;
        self.timed_rumble = False; # Timed rumble not implemented in _send_rumble loop
        self.t = 0;
        if time != 0:
            self.t = time / 1000.0;
            self.timed_rumble = True;

    def GetData(self):
        """Calculates and returns the 8-byte rumble data packet."""
        rumble_data = [0] * 8 # Initialize with 0s (safer than None)
        # Default "off" packet structure
        default_off = [0, 1, 64, 64, 0, 1, 64, 64]

        try: # Wrap calculations in try-except for robustness
            # Ensure amplitude is clamped 0.0-1.0 before the check
            clamped_amp = clamp(self.amp, 0.0, 1.0)

            if (clamped_amp == 0.0):
                rumble_data = default_off # Use default off packet
            else:
                # Clamp frequencies and amplitude for calculations
                l_f = clamp(self.l_f, 40.875885, 626.286133);
                amp = clamped_amp # Use already clamped amplitude
                h_f = clamp(self.h_f, 81.75177, 1252.572266);

                # Calculate encoded high frequency components
                hf = int((round(32.0 * math.log(h_f * 0.1, 2)) - 0x60) * 4);
                # Calculate encoded low frequency components
                lf = int(round(32.0 * math.log(l_f * 0.1, 2)) - 0x40);

                # Calculate high frequency amplitude component
                hf_amp = 0 # Default
                if amp < 0.117: hf_amp = int(((math.log(amp * 1000, 2) * 32) - 0x60) / (5 - pow(amp, 2)) - 1);
                elif amp < 0.23: hf_amp = int(((math.log(amp * 1000, 2) * 32) - 0x60) - 0x5c)
                else: hf_amp = int((((math.log(amp * 1000, 2) * 32) - 0x60) * 2) - 0xf6);
                # Ensure hf_amp is non-negative
                hf_amp = max(0, hf_amp)

                # Calculate low frequency amplitude component (encoded)
                lf_amp_intermediate = int(round(hf_amp) * .5);
                parity = int(lf_amp_intermediate % 2);
                if (parity > 0):
                    lf_amp_intermediate -= 1

                # Ensure non-negative before shift
                lf_amp_intermediate = max(0, lf_amp_intermediate)
                lf_amp_intermediate = int(lf_amp_intermediate >> 1);
                lf_amp_intermediate += 0x40;
                if (parity > 0):
                    # Ensure lf_amp doesn't exceed 16 bits even with parity (shouldn't happen with calc)
                    lf_amp_intermediate |= 0x8000;

                encoded_lf_amp = lf_amp_intermediate

                # --- Assemble the bytes ---
                # Calculate base byte values (before adding amplitudes)
                byte0 = int(hf & 0xff)
                byte1_base = int((hf >> 8) & 0xff) # Extract potential high byte of hf
                byte2_base = lf # lf calculation result should fit in a byte
                byte3 = int(encoded_lf_amp & 0xff) # Extract low byte of encoded lf_amp

                # Add amplitude components to base bytes
                byte1_final_raw = byte1_base + hf_amp
                byte2_final_raw = byte2_base + int((encoded_lf_amp >> 8) & 0xff) # Add high byte of lf_amp

                # --- FIX: Clamp the combined results to the valid byte range [0, 255] ---
                rumble_data[0] = clamp(byte0, 0, 255)
                rumble_data[1] = clamp(byte1_final_raw, 0, 255) # Clamp result after adding hf_amp
                rumble_data[2] = clamp(byte2_final_raw, 0, 255) # Clamp result after adding lf_amp high byte
                rumble_data[3] = clamp(byte3, 0, 255)

            # Copy bytes 0-3 to 4-7 for the full packet
            for i in range(4):
                rumble_data[4 + i] = rumble_data[i];

            # Final check (optional, but good for sanity)
            for i, val in enumerate(rumble_data):
                if not (0 <= val <= 255):
                    print(f"[RumbleData Critical Error] Post-clamp value out of range: rumble_data[{i}] = {val}. Falling back to 'off'.", file=sys.stderr)
                    rumble_data = default_off
                    break

            return bytes(rumble_data)

        except Exception as e:
            print(f"[RumbleData Error] Exception during GetData calculation: {e}. Falling back to 'off'.", file=sys.stderr)
            import traceback
            traceback.print_exc()
            # Return safe default rumble (off) packet if any error occurs
            return bytes(default_off)
