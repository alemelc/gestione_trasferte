# seed_amministrazione.py

import sys
from werkzeug.security import generate_password_hash
from flask import Flask

# Assicurati che l'importazione funzioni, come nel tuo script precedente
# Se i tuoi modelli sono in 'models.py', questo dovrebbe funzionare:
from models import db, Dipendente 

# Dati del nuovo utente Amministrazione (per i test)
ADMIN_NOME = 'Ugo'
ADMIN_COGNOME = 'Verdi'
ADMIN_EMAIL = 'ugo.verdi@admin.it' # Usa un'email chiara per l'amministrazione
ADMIN_RUOLO = 'Amministrazione'
ADMIN_PASSWORD = 'Amministrazione123' # !!! CAMBIA QUESTA PASSWORD DOPO IL TEST !!!

def create_amministrazione_user():
    """Crea l'utente Amministrazione direttamente nel DB."""
    
    # 1. Trova l'istanza dell'applicazione
    try:
        # Importiamo l'istanza 'app' direttamente da app.py
        from app import app
    except ImportError:
        print("Errore: Impossibile importare l'istanza 'app' da app.py.")
        print("Assicurati che 'app' sia definita ed esposta nel file app.py.")
        return

    with app.app_context():
        # 2. Controlla se l'utente esiste già
        if Dipendente.query.filter_by(email=ADMIN_EMAIL).first():
            print(f"Utente '{ADMIN_EMAIL}' (Amministrazione) esiste già. Nessuna creazione necessaria.")
            return

        # 3. Hash della password (Usiamo lo stesso metodo del tuo script precedente)
        hashed_pwd = generate_password_hash(ADMIN_PASSWORD, method='pbkdf2:sha256')

        # 4. Crea l'oggetto Dipendente
        admin_user = Dipendente(
            nome=ADMIN_NOME,
            cognome=ADMIN_COGNOME,
            email=ADMIN_EMAIL,
            # NOTA: Usiamo password_hash come nel tuo modello
            password_hash=hashed_pwd, 
            ruolo=ADMIN_RUOLO,
            # id_dirigente = None, poiché l'Amministrazione non è gestita da un dirigente
            id_dirigente=None 
        )

        # 5. Aggiungi e salva
        db.session.add(admin_user)
        db.session.commit()
        
        print("\n" + "="*50)
        print(f"✅ UTENTE {ADMIN_RUOLO} CREATO CON SUCCESSO!")
        print(f"   Nome: {ADMIN_NOME} {ADMIN_COGNOME}")
        print(f"   Email: {ADMIN_EMAIL}")
        print(f"   Password: {ADMIN_PASSWORD}")
        print("="*50)

if __name__ == '__main__':
    create_amministrazione_user()