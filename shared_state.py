# shared_state.py

# Dati condivisi tra i vari moduli dell'applicazione.
# Questo approccio semplice evita complesse gestioni dello stato per un'app di queste dimensioni.

session_transcripts = {}
current_session_id = None
session_active = False   # <-- L'ERRORE DICE CHE QUESTA RIGA MANCA O E' SCRITTA MALE
transcript_log = []      # Log completo di tutte le sessioni (potrebbe essere rimosso se non serve)