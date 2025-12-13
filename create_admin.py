# create_admin.py

import sys
from werkzeug.security import generate_password_hash
from flask import Flask

# IMPORTANTE: Aggiungi il percorso per importare i tuoi modelli se non sono in sys.path
# sys.path.append('.') 
from models import db, Dipendente # Assicurati che l'importazione funzioni

# Dati del nuovo utente Amministrazione
ADMIN_NOME = 'Super'
ADMIN_COGNOME = 'Amministrazione'
ADMIN_EMAIL = 'admin@super.it'
ADMIN_RUOLO = 'Amministrazione'
ADMIN_PASSWORD = 'adminpassword' # CAMBIALA!

def create_superuser():
    """Crea l'utente Amministrazione direttamente nel DB."""
    # 1. Trova l'istanza dell'applicazione (assumiamo che sia in app.py)
    # Importiamo app qui per evitare dipendenze circolari
    try:
        from app import app
    except ImportError:
        print("Errore: Impossibile importare l'istanza 'app' da app.py. Assicurati che app.py esista.")
        return

    with app.app_context():
        # 2. Controlla se l'utente Amministrazione esiste già per evitare duplicati
        if Dipendente.query.filter_by(email=ADMIN_EMAIL).first():
            print(f"Utente '{ADMIN_NOME}' esiste già. Nessuna creazione necessaria.")
            return

        # 3. Hash della password
        hashed_pwd = generate_password_hash(ADMIN_PASSWORD, method='pbkdf2:sha256')

        # 4. Crea l'oggetto Dipendente
        admin_user = Dipendente(
            nome=ADMIN_NOME,
            cognome=ADMIN_COGNOME,
            email=ADMIN_EMAIL,
            password_hash=hashed_pwd,
            ruolo=ADMIN_RUOLO,
            id_dirigente=None 
        )

        # 5. Aggiungi e salva
        db.session.add(admin_user)
        db.session.commit()
        print(f"\n✅ UTENTE {ADMIN_RUOLO} CREATO CON SUCCESSO!")
        print(f"   Nome: {ADMIN_NOME}")
        print(f"   Email: {ADMIN_EMAIL}")
        print(f"   Password: {ADMIN_PASSWORD}")

if __name__ == '__main__':
    create_superuser()