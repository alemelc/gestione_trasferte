import sys
from werkzeug.security import generate_password_hash
from flask import Flask
from models import db, Dipendente, Delega # <--- AGGIUNGI DELEGA
from datetime import date # <--- AGGIUNGI DATETIME

# Assicurati che l'importazione funzioni
from models import db, Dipendente 

# --- DATI DI BASE ---
USERS_DATA = {
    # UTENTE 1: Superuser
    'admin': ('Super', 'Admin', 'admin@super.it', 'adminpassword', 'Amministrazione', None),
    # UTENTE 2: Dirigente (D)
    'dirigente': ('Mario', 'Rossi', 'mario.rossi@test.it', 'password', 'Dirigente', 1),
    # UTENTE 3: Delegato (L) - sarà assegnato al dirigente in seguito
    'delegato': ('Andrea', 'Verdi', 'andrea.verdi@test.it', 'password', 'Dipendente', 2),
    # UTENTE 4: Sottoposto (S) - sarà assegnato al dirigente in seguito
    'sottoposto': ('Luigi', 'Bianchi', 'luigi.bianchi@test.it', 'password', 'Dipendente', 2),
}

def setup_database_and_users():
    """Cancella, ricrea il DB e popola con utenti di base."""
    try:
        from app import app
    except ImportError:
        print("Errore: Impossibile importare l'istanza 'app'. Assicurati che app.py esista.")
        return

    with app.app_context():
        print("--- INIZIO SETUP DATABASE ---")
        
        # 1. DROP e CREATE TABLE (cancella TUTTI i dati)
        print("Cancellazione tabelle esistenti...")
        db.drop_all()
        print("Ricreazione tabelle...")
        db.create_all()
        
        # Dizionario per tracciare gli utenti creati e assegnare i dirigenti in seguito
        user_objects = {}

        # 2. Creazione Utenti
        for key, (nome, cognome, email, raw_pwd, ruolo, id_dirigente) in USERS_DATA.items():
            hashed_pwd = generate_password_hash(raw_pwd, method='scrypt')
            
            new_user = Dipendente(
                nome=nome,
                cognome=cognome,
                email=email,
                password_hash=hashed_pwd,
                ruolo=ruolo,
                id_dirigente=id_dirigente 
            )
            db.session.add(new_user)
            user_objects[key] = new_user # Salva l'oggetto per l'assegnazione
            print(f"Creato utente: {ruolo} ({cognome})")

        db.session.commit()
        print("\n✅ ASSEGNAZIONE GERARCHICA INIZIALE COMPLETATA:")
        print(f"  Delegato e Sottoposto sono stati assegnati a {user_objects['dirigente'].cognome}.")

        # --- AGGIUNTA LOGICA DELEGA PER IL TEST (NUOVA SEZIONE) ---
        
        # Mario Rossi (dirigente) delega a Andrea Verdi (delegato)
        print("\n⏳ CREAZIONE DELEGA ATTIVA (ROSSI -> VERDI)...")
        
        delega = Delega(
            id_delegante=user_objects['dirigente'].id, 
            id_delegato=user_objects['delegato'].id, 
            data_inizio=date.today(), # Delega attiva da oggi
            data_fine=None # Indeterminata
        )
        db.session.add(delega)
        db.session.commit()
        print("✅ Delega creata e attiva.")

        print("\n--- SETUP COMPLETATO ---")
        print(f"Credenziali Amministrazione: {USERS_DATA['admin'][2]} / {USERS_DATA['admin'][3]}")
        print("Inizia i test loggandoti come Amministrazione.")

if __name__ == '__main__':
    setup_database_and_users()