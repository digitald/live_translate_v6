# audio_worker.py

import threading
import time
import numpy as np
import sounddevice as sd
import soundfile as sf
import io
from pathlib import Path
from datetime import datetime

import config
import shared_state

class CircularBuffer:
    # ... (Il codice della classe CircularBuffer rimane identico) ...
    def __init__(self, size):
        self.buffer = np.zeros(size, dtype=np.float32)
        self.size = size
        self.index = 0
        self.filled = False
        
    def add_data(self, data):
        data_len = len(data)
        if data_len > self.size:
            data = data[-self.size:]
            
        if self.index + data_len > self.size:
            part1 = self.size - self.index
            self.buffer[self.index:self.index+part1] = data[:part1]
            self.buffer[0:data_len-part1] = data[part1:]
            self.index = data_len - part1
        else:
            self.buffer[self.index:self.index+data_len] = data
            self.index = (self.index + data_len) % self.size
            
        if not self.filled and self.index == 0:
            self.filled = True
            
    def get_data(self):
        if self.filled:
            return np.concatenate([self.buffer[self.index:], self.buffer[:self.index]])
        return self.buffer[:self.index]


# in audio_worker.py

class SimpleTranslatorWorker(threading.Thread):
    def __init__(self, ai_client, socketio, chunk_duration=4, sample_rate=16000):
        super().__init__(daemon=True)
        self.ai_client = ai_client
        self.socketio = socketio
        self.chunk_duration = chunk_duration
        self.sample_rate = sample_rate
        self.samples_per_chunk = int(sample_rate * chunk_duration)
        self.running = False
        self.processing = False
        # Use a larger buffer to ensure we don't miss audio while processing
        self.audio_buffer = CircularBuffer(sample_rate * (chunk_duration * 3))
        self.lock = threading.Lock()
        self.last_chunk_time = 0

    def audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"Audio status: {status}")
        if self.running and shared_state.session_active:
            with self.lock:
                self.audio_buffer.add_data(indata[:, 0])

    def run(self):
        self.running = True
        print("▶️ Worker avviato e in attesa di una sessione...")
        with sd.InputStream(
            samplerate=self.sample_rate, channels=1, dtype="float32",
            callback=self.audio_callback, blocksize=self.sample_rate # Get new audio every second
        ):
            while self.running:
                if not shared_state.session_active or self.processing:
                    time.sleep(0.1)
                    continue

                with self.lock:
                    buffered_data = self.audio_buffer.get_data()

                # Check if we have a full chunk of NEW audio since last time
                if len(buffered_data) >= self.samples_per_chunk:
                    self.processing = True
                    
                    # Process the most recent chunk of audio
                    audio_chunk = buffered_data[-self.samples_per_chunk:]
                    
                    # Run the processing in a separate thread to not block the audio callback
                    threading.Thread(target=self.process_chunk, args=(audio_chunk,)).start()

        print("⏹️ Worker fermato")

    def process_chunk(self, audio_data):
        try:
            print("🎤 Chunk audio acquisito, avvio elaborazione...")
            
            wav_bytes = io.BytesIO()
            sf.write(wav_bytes, audio_data, self.sample_rate, format='WAV')
            wav_bytes.seek(0)
            wav_bytes.name = "stream.wav"
            
            italian_text = self.ai_client.transcribe(wav_bytes)
            if not italian_text:
                print("... Trascrizione vuota, scarto il chunk ...")
                return

            print(f"📥 IT: {italian_text}")
            english_text = self.ai_client.translate(italian_text)
            if not english_text:
                return
            
            print(f"🌍 EN: {english_text}")
            audio_filename = f"tts_{int(time.time() * 1000)}.mp3"
            audio_file_path = Path(config.AUDIO_DIR) / audio_filename
            
            audio_url = None
            if self.ai_client.text_to_speech(english_text, str(audio_file_path)):
                audio_url = f"/audio/{audio_filename}"

            timestamp = datetime.now().strftime("%H:%M:%S")
            result = {
                "italian": italian_text, "english": english_text,
                "audio_url": audio_url, "timestamp": timestamp
            }
            
            if shared_state.current_session_id in shared_state.session_transcripts:
                shared_state.session_transcripts[shared_state.current_session_id]["transcripts"].append(result)
            
            self.socketio.emit("new_translation", result)
            print("✅ Chunk processato e inviato.")

        except Exception as e:
            print(f"❌ Errore durante l'elaborazione del chunk: {e}")
        finally:
            self.processing = False # Allow the next chunk to be processed

    def stop(self):
        self.running = False

