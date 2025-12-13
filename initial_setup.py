# initial_setup.py

from app import app, db
from models import Dipendente
from werkzeug.security import generate_password_hash
import os

# Credenziali hardcoded (o lette da ENV, meglio)
ADMIN_USERNAME = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASS", "PasswordSicura123")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@tuodominio.it")

def create_admin_user():
    with app.app_context():
        # Controlla se l'utente esiste già
        if Dipendente.query.filter_by(username=ADMIN_USERNAME).first():
            print(f"Utente amministratore '{ADMIN_USERNAME}' esiste già.")
            return

        print(f"Creazione utente amministratore '{ADMIN_USERNAME}'...")
        
        # Crea l'utente
        hashed_password = generate_password_hash(ADMIN_PASSWORD)
        admin = Dipendente(
            username=ADMIN_USERNAME,
            password_hash=hashed_password,
            nome="Admin",
            cognome="System",
            email=ADMIN_EMAIL,
            ruolo='Admin',
            is_attivo=True # Assicurati che l'utente sia attivo
        )
        db.session.add(admin)
        db.session.commit()
        print("Utente amministratore creato con successo!")

if __name__ == '__main__':
    create_admin_user()