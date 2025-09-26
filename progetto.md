├── app.py              # ✅ Il file principale: avvia il server e la GUI.
├── config.py           # ⚙️ Le tue configurazioni (API key, nomi cartelle).
├── shared_state.py     # 📦 Stato condiviso tra i moduli (es. se la sessione è attiva).
├── ai_client.py        # 🤖 Tutta la logica per parlare con OpenAI.
├── audio_worker.py     # 🎧 La classe che ascolta il microfono ed elabora l'audio.
├── gui.py              # 🖥️ La finestra di controllo del server (Tkinter).
├── utils.py            # 🛠️ Funzioni di utilità (es. generare e salvare appunti).
└── index.html          # 📄 Il frontend per il client (rimane invariato).