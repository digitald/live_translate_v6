# test_mic.py

import sounddevice as sd
import numpy as np

SAMPLE_RATE = 16000
DURATION = 3  # seconds

print("--- Microphone Test ---")
print(f"Attempting to record for {DURATION} seconds...")
print("Please speak into your microphone now.")

try:
    # Query devices to see what's available
    print("\nAvailable audio devices:")
    print(sd.query_devices())
    
    # Record audio
    recording = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype='float32')
    sd.wait()  # Wait until recording is finished

    # Check if the recording is just silence
    rms = np.sqrt(np.mean(recording**2))
    
    print("\n--- Test Results ---")
    if rms > 0.001: # A very low threshold to check for any signal at all
        print("✅ SUCCESS: Audio was recorded successfully!")
        print(f"Signal RMS (volume): {rms:.4f}")
    else:
        print("⚠️ WARNING: Recording appears to be silent.")
        print("The microphone might be muted, permissions might be denied, or the wrong device is selected.")

except Exception as e:
    print("\n--- Test Results ---")
    print(f"❌ FAILURE: An error occurred while trying to access the microphone.")
    print(f"Error details: {e}")

print("\n--- End of Test ---")