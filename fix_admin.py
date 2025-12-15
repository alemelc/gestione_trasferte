from app import app
from models import db, Dipendente

def fix_admin_role():
    with app.app_context():
        # Cerca l'admin per email
        admin_email = 'admin@tuodominio.it' 
        admin = Dipendente.query.filter_by(email=admin_email).first()
        
        if admin:
            print(f"Utente {admin_email} trovato. Ruolo attuale: {admin.ruolo}")
            if admin.ruolo != 'Amministrazione':
                admin.ruolo = 'Amministrazione'
                db.session.commit()
                print(f"✅ SUCCESSO: Ruolo aggiornato a 'Amministrazione'.")
            else:
                print("Il ruolo è già corretto.")
        else:
            print(f"❌ ERRORE: Utente {admin_email} non trovato.")

if __name__ == '__main__':
    fix_admin_role()
