from app import app
from models import db, Dipendente

def promote_to_superuser():
    with app.app_context():
        # Modifica qui l'email se necessario
        target_email = 'admin@tuodominio.it' 
        
        user = Dipendente.query.filter_by(email=target_email).first()
        
        if user:
            print(f"Utente {target_email} trovato. Ruolo attuale: {user.ruolo}")
            if user.ruolo != 'Superuser':
                user.ruolo = 'Superuser'
                db.session.commit()
                print(f"✅ SUCCESSO: {target_email} è ora un SUPERUSER.")
            else:
                print("L'utente è già Superuser.")
        else:
            print(f"❌ ERRORE: Utente {target_email} non trovato. Controlla l'email.")

if __name__ == '__main__':
    promote_to_superuser()
