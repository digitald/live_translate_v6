# app.py

import os
import sys
import time
import threading
from pathlib import Path
from datetime import datetime

from flask import Flask, send_from_directory, Response, request
from flask_socketio import SocketIO, emit

# Importa dai nostri moduli
import config
import shared_state
from ai_client import AIClient
from audio_worker import SimpleTranslatorWorker
from gui import launch_gui


from utils import generate_and_save_notes, cleanup_old_audio_files, save_transcript_to_file # Aggiungi la nuova funzione



# ------------------------
# Inizializzazione Flask + SocketIO
# ------------------------
app = Flask(__name__, static_folder=".", static_url_path="")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ------------------------
# Routes Flask
# ------------------------
@app.route("/")
def home():
    return send_from_directory(".", "index.html")

# ▼▼▼ AGGIUNGI QUESTA NUOVA ROTTA ▼▼▼
@app.route("/teacher")
def teacher_page():
    return send_from_directory(".", "teacher.html")

@app.route("/audio/<path:filename>")
def serve_audio(filename):
    return send_from_directory(config.AUDIO_DIR, filename)

@app.route("/download_transcript")
def download_transcript():
    session_id = request.args.get("session_id")
    if not session_id:
        return "ID sessione non specificato.", 400

    # ✅ CORREZIONE: Cerca il file direttamente nella cartella, invece che in memoria.
    transcript_filename = f"trascrizione_{session_id}.txt"
    transcript_filepath = Path(config.TRANSCRIPTS_DIR) / transcript_filename

    if not transcript_filepath.exists():
        # Controlla se è la sessione attiva (il cui file non è ancora stato salvato)
        if session_id == shared_state.current_session_id and shared_state.session_active:
             # Genera il contenuto al volo per la sessione live
            session_data = shared_state.session_transcripts.get(session_id)
            if session_data and session_data.get("transcripts"):
                lines = [f"[{r.get('timestamp', '')}] IT: {r.get('italian', '')}\nEN: {r.get('english', '')}\n" for r in session_data["transcripts"]]
                text = "\n".join(lines)
                return Response(text, mimetype="text/plain", headers={"Content-Disposition": f"attachment;filename={transcript_filename}"})

        return "File della trascrizione non trovato. Potrebbe non essere ancora stato salvato.", 404
    
    # Se il file esiste, lo serve per il download.
    return send_from_directory(config.TRANSCRIPTS_DIR, transcript_filename, as_attachment=True)

@app.route("/download_notes/<session_id>")
def download_notes(session_id):
    notes_filename = f"appunti_{session_id}.txt"
    if not (Path(config.NOTES_DIR) / notes_filename).exists():
        return "Appunti non trovati. Prova prima a generarli.", 404
    return send_from_directory(config.NOTES_DIR, notes_filename, as_attachment=True)

@app.route("/download_notes_en/<session_id>")
def download_notes_en(session_id):
    """Scarica gli appunti elaborati in INGLESE."""
    notes_filename = f"notes_{session_id}.txt"
    if not (Path(config.NOTES_DIR) / notes_filename).exists():
        return "File degli appunti in inglese non trovato.", 404
    return send_from_directory(config.NOTES_DIR, notes_filename, as_attachment=True)

@app.route("/process_session/<session_id>")
def process_session(session_id):
    if generate_and_save_notes(session_id, ai_client):
        return {"success": True, "message": "Trascrizione elaborata con successo"}
    else:
        return {"error": "Errore nell'elaborazione o sessione non trovata"}, 500

# in app.py

# in app.py

@app.route("/session_list")
def session_list():
    """
    Analizza le cartelle, trova le ultime 6 sessioni e ne restituisce i dati formattati.
    """
    sessions_found = {}
    
    transcript_files = Path(config.TRANSCRIPTS_DIR).glob("trascrizione_*.txt")
    notes_files = Path(config.NOTES_DIR).glob("appunti_*.txt")

    # Estrae i dati dai nomi dei file
    for f in transcript_files:
        session_id = f.stem.replace("trascrizione_", "")
        parts = session_id.split('_')
        if len(parts) < 4: continue # Salta ID malformati

        # Estrae le singole parti
        docente = parts[0]
        materia = " ".join(parts[1:-2]) # La materia può contenere spazi (che erano underscore)
        data_str = parts[-2]
        ora_str = parts[-1]
        
        # Formatta data e ora per una migliore leggibilità
        try:
            data_formatted = f"{data_str[6:8]}/{data_str[4:6]}/{data_str[0:4]}"
            ora_formatted = f"{ora_str[0:2]}:{ora_str[2:4]}"
            timestamp_for_sorting = data_str + ora_str
        except IndexError:
            continue

        sessions_found[session_id] = {
            'id': session_id,
            'docente': docente,
            'materia': materia,
            'data': data_formatted,
            'ora': ora_formatted,
            'timestamp': timestamp_for_sorting,
            'processed': False
        }

    for f in notes_files:
        session_id = f.stem.replace("appunti_", "")
        if session_id in sessions_found:
            sessions_found[session_id]['processed'] = True

    sorted_sessions = sorted(sessions_found.values(), key=lambda s: s['timestamp'], reverse=True)
    
    return {"sessions": sorted_sessions[:6]}


# ------------------------
# Routes di controllo per la GUI
# ------------------------
# ------------------------
# Routes di controllo per la GUI
# ------------------------
@app.route("/_start_session")
def trigger_start_session():
    # Leggiamo i nuovi parametri dall'URL
    docente = request.args.get('docente', 'NessunDocente')
    materia = request.args.get('materia', 'NessunaMateria')
    handle_start_session(docente, materia) # Passiamo i dati alla funzione principale
    return "OK"

@app.route("/_stop_session")
def trigger_stop_session():
    handle_stop_session()
    return "OK"


@socketio.on("start_session")
def handle_start_session(docente: str = 'DefaultDocente', materia: str = 'DefaultMateria'):
    if not shared_state.session_active:
        shared_state.session_active = True
        
        # Creiamo il nuovo ID sessione descrittivo 🆔
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M")
        session_id = f"{docente}_{materia}_{timestamp}"
        
        shared_state.current_session_id = session_id
        
        # Salviamo i nuovi metadati insieme alla sessione
        shared_state.session_transcripts[session_id] = {
            "docente": docente,
            "materia": materia,
            "start_time": now.isoformat(), 
            "transcripts": [], 
            "notes": None
        }
        print(f"▶️ Sessione avviata: {shared_state.current_session_id}")
        socketio.emit("session_status", {"active": True, "session_id": shared_state.current_session_id})


@socketio.on("stop_session")
def handle_stop_session():
    if shared_state.session_active and shared_state.current_session_id:
        session_id = shared_state.current_session_id
        print(f"⏹️  Sessione fermata: {session_id}")

        # Salva la trascrizione su file
        save_transcript_to_file(session_id)

        shared_state.session_active = False
        shared_state.current_session_id = None
        socketio.emit("session_status", {"active": False, "session_id": session_id})
    else:
        print("⏹️  Comando di stop ricevuto, ma nessuna sessione attiva trovata.")

# ------------------------
# Main
# ------------------------

# in app.py

# in app.py

# ------------------------
# Main
# ------------------------
if __name__ == "__main__":
    os.makedirs(config.AUDIO_DIR, exist_ok=True)
    os.makedirs(config.NOTES_DIR, exist_ok=True)
    os.makedirs(config.TRANSCRIPTS_DIR, exist_ok=True) # <-- AGGIUNGI
    
    cleanup_old_audio_files()
    ## load_existing_sessions() # <-- AGGIUNGI
    
    api_key = os.getenv("OPENAI_API_KEY", config.OPENAI_API_KEY)
    if not api_key or api_key == "sk-...":
        print("❌ API key di OpenAI non trovata o non configurata in config.py")
        sys.exit(1)
        
    ai_client = AIClient(api_key)
    worker = SimpleTranslatorWorker(ai_client, socketio)
    worker_thread = threading.Thread(target=worker.run, daemon=True)
    worker_thread.start()

    # ====================================================================
    # ===== BLOCCO DI VERIFICA: CONTROLLA SE VEDI QUESTO MESSAGGIO =====
    # ====================================================================
    print("\n" + "#"*60)
    print("### STAI ESEGUENDO LA VERSIONE CORRETTA DEL FILE app.py ###")
    
    # Creiamo gli argomenti in una variabile separata per il debug
    gui_args = (ai_client,)
    print(f"### Argomenti preparati per la GUI: {gui_args} ###")
    print("#"*60 + "\n")
    # ====================================================================

    # Avvia la GUI in un altro thread
    gui_thread = threading.Thread(target=launch_gui, args=gui_args, daemon=True)
    gui_thread.start()

    try:
        print("🚀 Server in avvio su http://0.0.0.0:8000")
        print("💡 Usa la GUI per avviare/fermare la sessione")
        socketio.run(app, host="0.0.0.0", port=8000, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("\n⏹️ Arresto del server...")
        worker.stop()
        sys.exit(0)