from app import app, db
from models import Trasferta
from sqlalchemy import text

def run_migration():
    with app.app_context():
        print("Inizio migrazione stato: 'Pronto per Rimborso' -> 'Pronta per rimborso'")
        
        # Method 1: Bulk Update via SQL for speed and safety
        query = text("UPDATE trasferta SET stato_post_missione = 'Pronta per rimborso' WHERE stato_post_missione = 'Pronto per Rimborso'")
        result = db.session.execute(query)
        db.session.commit()
        
        rows_affected = result.rowcount
        print(f"Migrazione completata. Aggiornate {rows_affected} trasferte.")

if __name__ == "__main__":
    run_migration()
