# utils.py


# ... (altre importazioni) ...

from pathlib import Path
import time

# Import dei nostri moduli

import socket
import config  # <-- ECCO LA CORREZIONE! MANCAVA QUESTA RIGA.
import shared_state
from ai_client import AIClient



def generate_and_save_notes(session_id: str, ai_client: AIClient) -> bool:
    """
    Genera gli appunti in italiano, li salva, poi li traduce e salva la versione inglese.
    """
    transcript_filepath = Path(config.TRANSCRIPTS_DIR) / f"trascrizione_{session_id}.txt"

    if not transcript_filepath.exists():
        print(f"❌ File trascrizione non trovato per generare gli appunti: {transcript_filepath}")
        return False

    with open(transcript_filepath, "r", encoding="utf-8") as f:
        transcript_text = f.read()

    print(f"⏳ Elaborazione appunti in italiano per {session_id}...")
    italian_notes = ai_client.summarize_transcript(transcript_text)

    if italian_notes:
        # Salva gli appunti in italiano
        notes_it_filepath = Path(config.NOTES_DIR) / f"appunti_{session_id}.txt"
        with open(notes_it_filepath, "w", encoding="utf-8") as f:
            f.write(italian_notes)
        print(f"✅ Appunti in italiano salvati in {notes_it_filepath}")

        # Traduci e salva gli appunti in inglese
        print(f"⏳ Traduzione degli appunti in inglese per {session_id}...")
        english_notes = ai_client.translate(italian_notes)
        if english_notes:
            notes_en_filepath = Path(config.NOTES_DIR) / f"notes_{session_id}.txt"
            with open(notes_en_filepath, "w", encoding="utf-8") as f:
                f.write(english_notes)
            print(f"✅ Appunti in inglese salvati in {notes_en_filepath}")
        
        return True
    else:
        print(f"❌ Errore durante l'elaborazione degli appunti per {session_id}.")
        return False

def cleanup_old_audio_files(hours=24):
    """Pulisce i file audio più vecchi di un certo numero di ore."""
    audio_dir = Path(config.AUDIO_DIR)
    if not audio_dir.exists():
        return
        
    now = time.time()
    for file in audio_dir.iterdir():
        if file.is_file() and (now - file.stat().st_mtime) > (hours * 3600):
            try:
                file.unlink()
                print(f"🗑️ Rimosso file audio vecchio: {file.name}")
            except Exception as e:
                print(f"❌ Errore nella rimozione di {file.name}: {e}")

# in utils.py



# -------------------------------------------------------------------
# ▼▼▼ AGGIUNGI QUESTA NUOVA FUNZIONE IN FONDO AL FILE ▼▼▼
# -------------------------------------------------------------------
def save_transcript_to_file(session_id: str) -> str | None:
    """
    Formatta la trascrizione e la salva in un file permanente.
    Restituisce il percorso del file.
    """
    session_data = shared_state.session_transcripts.get(session_id)
    if not session_data or not session_data.get("transcripts"):
        return None

    lines = [f"[{r.get('timestamp', '')}] IT: {r.get('italian', '')}\nEN: {r.get('english', '')}\n" for r in session_data["transcripts"]]
    transcript_text = "\n".join(lines)
    
    # Salva nella nuova cartella 'transcripts'
    filepath = Path(config.TRANSCRIPTS_DIR) / f"trascrizione_{session_id}.txt"
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(transcript_text)
        print(f"✅ Trascrizione permanente salvata in: {filepath}")
        return str(filepath)
    except Exception as e:
        print(f"❌ Errore nel salvataggio della trascrizione: {e}")
        return None
    
    # ____________________________________________________________________
# ▼▼▼ AGGIUNGI QUESTA NUOVA FUNZIONE IN FONDO AL FILE utils.py ▼▼▼
# ____________________________________________________________________
def get_local_ip() -> str:
    """
    Trova l'indirizzo IP locale del computer sulla rete.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # non è necessario che sia raggiungibile
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1' # In caso di errore, usa l'indirizzo di loopback
    finally:
        s.close()
    return IP