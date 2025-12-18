from app import app, db
from models import Dipendente

def fix_dirigente_setup():
    with app.app_context():
        print("--- FIX SETUP DIRIGENTI ---")
        dirigenti = Dipendente.query.filter_by(ruolo='Dirigente').all()
        
        for d in dirigenti:
            print(f"Controllo Dirigente: {d.nome} {d.cognome} (ID: {d.id})")
            
            if d.id_dirigente != d.id:
                print(f" -> CORREZIONE: Imposto id_dirigente da {d.id_dirigente} a {d.id} (SELF)")
                d.id_dirigente = d.id
                db.session.add(d)
        
        try:
            db.session.commit()
            print("[SUCCESS] COMMIT ESEGUITO. Setup corretto.")
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] ERRORE COMMIT: {e}")

if __name__ == "__main__":
    fix_dirigente_setup()
