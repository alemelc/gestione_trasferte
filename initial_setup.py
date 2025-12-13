import os
from dotenv import load_dotenv
from app import app
from models import db, Dipendente # Assicurati che db e Dipendente siano importati correttamente
from werkzeug.security import generate_password_hash

# Credenziali (usa quelle che hai provato)
ADMIN_USERNAME = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASS", "PasswordSicura123")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@tuodominio.it")

def create_admin_user():
    with app.app_context():
        
        # --- BLOCCO DI ELIMINAZIONE FORZATA (TEMPORANEO!) ---
        # 1. Trova l'utente Admin esistente
        existing_admin = Dipendente.query.filter_by(email=ADMIN_EMAIL).first()
        
        # 2. Se l'utente esiste, eliminalo
        if existing_admin:
            print(f"Eliminazione forzata dell'utente '{existing_admin.email}' (ID: {existing_admin.id}) per rigenerazione password.")
            db.session.delete(existing_admin)
            db.session.commit()
            
        print("-------------------------------------------------------------------")
        
        # 3. Controlla di nuovo per assicurarti che non ci siano utenti con quel nome
        if Dipendente.query.filter_by(email=ADMIN_EMAIL).first():
            print(f"ERRORE GRAVE: Utente {ADMIN_EMAIL} non eliminato.")
            return

        # -------------------------------------------------------------------

        print(f"Creazione utente amministratore '{ADMIN_EMAIL}' e hashing password...")
        
        # Crea l'utente da zero
        hashed_password = generate_password_hash(ADMIN_PASSWORD)
        admin = Dipendente(
            #username=ADMIN_USERNAME,
            password_hash=hashed_password,
            nome="Admin",
            cognome="System",
            email=ADMIN_EMAIL, # Usa questa email per il login!
            ruolo='Admin',
            is_attivo=True
        )
        db.session.add(admin)
        db.session.commit()
        print("Utente amministratore creato con successo!")

if __name__ == '__main__':
    create_admin_user()