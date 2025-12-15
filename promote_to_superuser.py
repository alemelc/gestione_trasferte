from app import app
from models import db, Dipendente

def promote_to_superuser():
    with app.app_context():
        # Modifica qui l'email se necessario
        # Lista di email da promuovere a Superuser
        target_emails = ['admin@tuodominio.it', 'admin@super.it']
        
        for target_email in target_emails:
            user = Dipendente.query.filter_by(email=target_email).first()
            
            if user:
                print(f"Utente {target_email} trovato. Ruolo attuale: {user.ruolo}")
                if user.ruolo != 'Superuser':
                    user.ruolo = 'Superuser'
                    db.session.commit()
                    print(f"✅ SUCCESSO: {target_email} è ora un SUPERUSER.")
                else:
                    print(f"L'utente {target_email} è già Superuser.")
            else:
                print(f"⚠️ Utente {target_email} non trovato (ignorato).")

if __name__ == '__main__':
    promote_to_superuser()
