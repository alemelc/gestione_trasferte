import os
from dotenv import load_dotenv
from app import app
from models import db, Dipendente
from werkzeug.security import generate_password_hash

# Carica le variabili d'ambiente (per Render e ambiente locale)
load_dotenv()

# Legge le credenziali con fallback (meglio usare le variabili d'ambiente su Render!)
ADMIN_USERNAME = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASS", "PasswordSicura123")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@tuodominio.it")

def create_admin_user():
    """Crea l'utente amministratore se non esiste già."""
    with app.app_context():
        
        # 1. Controlla se l'utente esiste già (Ricerca per email, che è corretto)
        existing_admin = Dipendente.query.filter_by(email=ADMIN_EMAIL).first()
        if existing_admin:
            # Utente trovato, non fare nulla (questa è la logica di sicurezza)
            print(f"Utente amministratore '{existing_admin.email}' esiste già. Nessuna azione necessaria.")
            return
            
        print(f"Creazione utente amministratore '{ADMIN_EMAIL}' e hashing password...")
        
        # 2. Crea l'utente da zero
        hashed_password = generate_password_hash(ADMIN_PASSWORD)
        admin = Dipendente(
            password_hash=hashed_password,
            nome="Admin",
            cognome="System",
            email=ADMIN_EMAIL, # Usa questa email per il login!
            ruolo='Amministrazione', # Ruolo corretto per l'app
            # Se hai aggiunto il campo is_attivo al modello, lascialo.
            # Altrimenti, DEVE essere rimosso (come da ultima correzione).
            # Dato che hai detto che funziona, lo lasciamo.
            # is_attivo=True 
        )
        
        # Aggiungi e committa
        db.session.add(admin)
        db.session.commit()
        print("Utente amministratore creato con successo!")

if __name__ == '__main__':
    create_admin_user()