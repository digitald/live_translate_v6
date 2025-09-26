# gui.py

import tkinter as tk
from tkinter import messagebox, Listbox, Scrollbar
import subprocess
import sys
import os
import threading
from pathlib import Path
import requests
import qrcode
from PIL import Image, ImageTk

import config
import shared_state
from utils import generate_and_save_notes, get_local_ip, save_transcript_to_file

# ... (tutti gli import esistenti) ...

def launch_gui(ai_client):
    root = tk.Tk()
    root.title("Controller Server Traduttore")
    root.geometry("650x500") # Allargata leggermente per il nuovo pulsante

    # Lista per mantenere la corrispondenza tra testo visualizzato e ID reale
    displayed_session_ids = []

    def refresh_sessions_list():
        nonlocal displayed_session_ids
        session_listbox.delete(0, tk.END)
        displayed_session_ids.clear()
        transcript_files = Path(config.TRANSCRIPTS_DIR).glob("trascrizione_*.txt")
        sessions_found = {}
        for f in transcript_files:
            session_id = f.stem.replace("trascrizione_", "")
            parts = session_id.split('_')
            if len(parts) < 4: continue
            try:
                timestamp_str = parts[-2] + parts[-1]
                sessions_found[session_id] = timestamp_str
            except IndexError:
                continue
        sorted_ids = sorted(sessions_found, key=sessions_found.get, reverse=True)
        displayed_session_ids.extend(sorted_ids)
        for session_id in sorted_ids:
            parts = session_id.split('_')
            docente = parts[0]
            materia = " ".join(parts[1:-2])
            data_str, ora_str = parts[-2], parts[-1]
            display_text = f'{materia} - {docente} ({data_str[6:8]}/{data_str[4:6]}/{data_str[0:4]} {ora_str[0:2]}:{ora_str[2:4]})'
            session_listbox.insert(tk.END, display_text)

    def get_selected_session_id():
        selected_indices = session_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Nessuna Selezione", "Per favore, seleziona una sessione dalla lista.")
            return None
        return displayed_session_ids[selected_indices[0]]

    def generate_and_view_notes_gui():
        session_id = get_selected_session_id()
        if not session_id: return
        
        notes_filepath = Path(config.NOTES_DIR) / f"appunti_{session_id}.txt"
        if not notes_filepath.exists():
            if not messagebox.askyesno("Conferma", f"Appunti per la sessione selezionata non trovati. Generarli ora? (Verranno create entrambe le versioni IT/EN)"):
                return
            status_label.config(text=f"Stato: Genero appunti per {session_id}...", fg="orange")
            root.update_idletasks()
            def run_generation():
                response = requests.get(f"http://127.0.0.1:8000/process_session/{session_id}")
                if response.ok and response.json().get("success"):
                    status_label.config(text="Stato: Appunti generati!", fg="blue")
                    open_file(notes_filepath)
                else:
                    status_label.config(text="Stato: Errore generazione appunti", fg="red")
                    messagebox.showerror("Errore", "Impossibile generare gli appunti.")
            threading.Thread(target=run_generation, daemon=True).start()
        else:
            open_file(notes_filepath)

    # ==========================================================
    # ===== NUOVA FUNZIONE PER VISUALIZZARE APPUNTI IN INGLESE =====
    # ==========================================================
    def view_english_notes_gui():
        session_id = get_selected_session_id()
        if not session_id: return

        # Cerca il file degli appunti in inglese
        filepath = Path(config.NOTES_DIR) / f"notes_{session_id}.txt"
        
        if filepath.exists():
            open_file(filepath)
        else:
            messagebox.showerror("Errore", f"File appunti in inglese non trovato. Prova prima a generarli dal pulsante 'Vedi Appunti (IT)'.")

    def view_transcript_gui():
        session_id = get_selected_session_id()
        if not session_id: return

        filepath = Path(config.TRANSCRIPTS_DIR) / f"trascrizione_{session_id}.txt"
        if filepath.exists():
            open_file(filepath)
        else:
            messagebox.showerror("Errore", f"File trascrizione non trovato per la sessione {session_id}.")

    # ... (le funzioni prompt_for_session_details, start_session_gui, stop_session_gui, ecc. rimangono invariate) ...
    def prompt_for_session_details():
        dialog = tk.Toplevel(root)
        dialog.title("Dettagli Nuova Sessione")
        dialog.config(padx=15, pady=15)
        dialog.resizable(False, False)
        tk.Label(dialog, text="Docente:").grid(row=0, column=0, sticky='w', pady=5)
        docente_entry = tk.Entry(dialog, width=30)
        docente_entry.grid(row=0, column=1, pady=5)
        docente_entry.focus_set()
        tk.Label(dialog, text="Materia:").grid(row=1, column=0, sticky='w', pady=5)
        materia_entry = tk.Entry(dialog, width=30)
        materia_entry.grid(row=1, column=1, pady=5)
        def on_submit():
            docente = docente_entry.get().strip()
            materia = materia_entry.get().strip()
            if not docente or not materia:
                messagebox.showerror("Errore", "I campi 'Docente' e 'Materia' non possono essere vuoti.", parent=dialog)
                return
            docente_safe = docente.replace(" ", "_")
            materia_safe = materia.replace(" ", "_")
            dialog.destroy()
            start_session_with_details(docente_safe, materia_safe)
        submit_button = tk.Button(dialog, text="Avvia Sessione", command=on_submit)
        submit_button.grid(row=2, column=0, columnspan=2, pady=15)
        dialog.transient(root)
        dialog.grab_set()
        root.wait_window(dialog)

    def start_session_with_details(docente, materia):
        try:
            url = f"http://127.0.0.1:8000/_start_session?docente={docente}&materia={materia}"
            requests.get(url)
            status_label.config(text="Stato: Sessione ATTIVA", fg="green")
            show_connection_info()
        except requests.exceptions.ConnectionError:
            messagebox.showerror("Errore", "Impossibile connettersi al server. È in esecuzione?")

    def start_session_gui():
        prompt_for_session_details()

    def stop_session_gui():
        try:
            requests.get("http://127.0.0.1:8000/_stop_session")
            status_label.config(text="Stato: Sessione FERMATA", fg="red")
            refresh_sessions_list()
        except requests.exceptions.ConnectionError:
            messagebox.showerror("Errore", "Impossibile connettersi al server.")

    def show_connection_info():
        ip_address = get_local_ip()
        connect_url = f"http://{ip_address}:8000"
        popup = tk.Toplevel(root)
        popup.title("Informazioni di Connessione")
        popup.config(padx=20, pady=20)
        popup.resizable(False, False)
        tk.Label(popup, text="Inquadra il QR Code o digita l'indirizzo:", font=("Arial", 12)).pack(pady=10)
        url_entry = tk.Entry(popup, font=("Courier", 14), justify='center')
        url_entry.insert(0, connect_url)
        url_entry.config(state='readonly')
        url_entry.pack(pady=10, fill='x', ipady=5)
        qr_img = qrcode.make(connect_url)
        qr_img = qr_img.resize((250, 250))
        photo = ImageTk.PhotoImage(qr_img)
        qr_label = tk.Label(popup, image=photo)
        qr_label.image = photo
        qr_label.pack(pady=10)
        tk.Button(popup, text="Chiudi", command=popup.destroy).pack(pady=10)
        popup.update_idletasks()
        x = root.winfo_x() + (root.winfo_width() // 2) - (popup.winfo_width() // 2)
        y = root.winfo_y() + (root.winfo_height() // 2) - (popup.winfo_height() // 2)
        popup.geometry(f"+{x}+{y}")
        popup.transient(root)
        popup.grab_set()

    def open_file(filepath):
        try:
            if sys.platform == "win32":
                os.startfile(filepath)
            elif sys.platform == "darwin":
                subprocess.run(["open", filepath], check=True)
            else:
                subprocess.run(["xdg-open", filepath], check=True)
        except Exception as e:
            messagebox.showerror("Errore Apertura File", f"Impossibile aprire il file:\n{e}")

    def shutdown_application():
        if messagebox.askyesno("Conferma Uscita", "Sei sicuro di voler chiudere completamente il server?"):
            print("🛑 Arresto forzato dell'applicazione...")
            os._exit(0)
    
    # --- Struttura della GUI ---
    main_frame = tk.Frame(root, padx=10, pady=10)
    main_frame.pack(fill=tk.BOTH, expand=True)

    live_controls_frame = tk.LabelFrame(main_frame, text="Controllo Sessione Live", padx=10, pady=10)
    live_controls_frame.pack(fill=tk.X, pady=5)
    
    tk.Button(live_controls_frame, text="▶ Avvia Sessione", command=start_session_gui, bg="#d4edda", fg="#155724").pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
    tk.Button(live_controls_frame, text="⏹ Ferma Sessione", command=stop_session_gui, bg="#f8d7da", fg="#721c24").pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

    past_sessions_frame = tk.LabelFrame(main_frame, text="Gestione Sessioni Passate", padx=10, pady=10)
    past_sessions_frame.pack(fill=tk.BOTH, expand=True, pady=10)
    
    list_frame = tk.Frame(past_sessions_frame)
    list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
    
    scrollbar = Scrollbar(list_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    session_listbox = Listbox(list_frame, yscrollcommand=scrollbar.set)
    session_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=session_listbox.yview)

    buttons_frame = tk.Frame(past_sessions_frame)
    buttons_frame.pack(fill=tk.X, pady=5)

    tk.Button(buttons_frame, text="🔄 Ricarica Lista", command=refresh_sessions_list).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
    
    # ==========================================================
    # ===== MODIFICHE AI PULSANTI DEGLI APPUNTI =====
    # ==========================================================
    tk.Button(buttons_frame, text="📝 Vedi Appunti (IT)", command=generate_and_view_notes_gui).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
    tk.Button(buttons_frame, text="📝 Vedi Appunti (EN)", command=view_english_notes_gui).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2) # <-- NUOVO
    tk.Button(buttons_frame, text="📜 Vedi Trascrizione", command=view_transcript_gui).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

    status_label = tk.Label(main_frame, text="Stato: Inattivo", fg="gray", bd=1, relief=tk.SUNKEN, anchor=tk.W)
    status_label.pack(side=tk.BOTTOM, fill=tk.X)
    
    tk.Button(main_frame, text="Esci e Chiudi Server", command=shutdown_application, bg="#6c757d", fg="white").pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0), ipady=4)

    root.protocol("WM_DELETE_WINDOW", shutdown_application)
    
    refresh_sessions_list()
    root.mainloop()