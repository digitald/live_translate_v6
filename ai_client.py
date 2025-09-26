# ai_client.py

import openai
from pathlib import Path

class AIClient:
    def __init__(self, api_key: str):
        openai.api_key = api_key
        self.client = openai

    def transcribe(self, file_object) -> str:
        try:
            transcript = self.client.audio.transcriptions.create(
                model="gpt-4o-transcribe", file=file_object
            )
            return transcript.text.strip()
        except Exception as e:
            print(f"❌ Errore trascrizione: {e}")
            return ""

    def translate(self, text: str) -> str:
        if not text.strip():
            return ""
            
        # ==========================================================
        # ===== NUOVO PROMPT DI SISTEMA PIÙ ROBUSTO =====
        # ==========================================================
        nuovo_prompt_di_sistema = """
Sei un motore di traduzione automatica, non un assistente conversazionale.
La tua unica funzione è tradurre il testo fornito dall'italiano all'inglese.
Segui queste regole in modo ferreo e senza eccezioni:
1.  **TRADUCI E BASTA:** Il tuo output deve contenere *solo e soltanto* la traduzione in inglese.
2.  **NON ESSERE CONVERSAZIONALE:** Non fare mai domande, non chiedere la lingua, non scusarti, non dire che non hai capito e non aggiungere commenti o frasi introduttive come "Ecco la traduzione:".
3.  **GESTISCI INPUT IMPERFETTI:** Se il testo in input non è in italiano, è incompleto o poco chiaro, tenta comunque la migliore traduzione possibile senza commentare. Se il testo non ha alcun senso (es. "asdfasdf"), restituisci una stringa vuota.
"""
        # ==========================================================
            
        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": nuovo_prompt_di_sistema}, # <-- Usiamo il nuovo prompt
                    {"role": "user", "content": text},
                ],
                max_tokens=500,
                temperature=0 # Riduciamo la "creatività" al minimo per traduzioni più dirette
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ Errore traduzione: {e}")
            return ""

    def text_to_speech(self, text: str, output_path: str) -> bool:
        if not text.strip():
            return False
        try:
            response = self.client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=text,
            )
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(response.content)
            return True
        except Exception as e:
            print(f"❌ Errore TTS: {e}")
            return False

    def summarize_transcript(self, transcript_text: str) -> str:
        if not transcript_text.strip():
            return ""
        try:
            prompt = f"""
Trasforma questa trascrizione di una lezione in appunti universitari ben strutturati. 
Organizza il contenuto in sezioni logiche con titoli e punti elenco, 
evidenzia i concetti chiave e rendi il tutto coerente e facile da studiare.

Trascrizione:
{transcript_text}

Appunti strutturati:
"""
            resp = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Sei un assistente specializzato nella creazione di appunti universitari ben strutturati e organizzati."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2000,
                temperature=0.7
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ Errore nell'elaborazione della trascrizione: {e}")
            return ""