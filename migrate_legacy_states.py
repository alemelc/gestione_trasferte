import sys
import os
from app import app, db
from models import Trasferta

def migrate_legacy():
    print("--- Migrating Legacy Mission Statuses ---")
    with app.app_context():
        # 1. Find 'Rimborso Concesso' missions
        legacy = Trasferta.query.filter_by(stato_post_missione='Rimborso Concesso').all()
        print(f"Found {len(legacy)} missions in 'Rimborso Concesso'.")
        
        migrated_to_pronto = 0
        migrated_to_conclusa = 0
        
        for m in legacy:
            total_expenses = sum(s.importo for s in m.spese if s.importo)
            
            if total_expenses > 0:
                print(f" -> Migrating Mission {m.id} to 'Pronto per Rimborso' (Expenses: {total_expenses})")
                m.stato_post_missione = 'Pronto per Rimborso'
                migrated_to_pronto += 1
            else:
                print(f" -> Migrating Mission {m.id} to 'Conclusa' (Zero Expenses)")
                m.stato_post_missione = 'Conclusa'
                migrated_to_conclusa += 1
        
        if migrated_to_pronto > 0 or migrated_to_conclusa > 0:
            db.session.commit()
            print(f"\nMigration Complete.")
            print(f" - Migrated to 'Pronto per Rimborso': {migrated_to_pronto}")
            print(f" - Migrated to 'Conclusa': {migrated_to_conclusa}")
        else:
            print("\nNo migration needed.")

if __name__ == "__main__":
    migrate_legacy()
