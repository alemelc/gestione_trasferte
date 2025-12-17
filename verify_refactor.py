import sys
import os
from app import app, db
from models import Trasferta, Spesa

def verify_refactor_and_data():
    print("--- Verifying Refactored Mission Logic & Data Consistency ---")
    with app.app_context():
        # 1. Dashboard Admin Query Check
        print("\n1. Checking Dashboard Admin Query (Should only see 'Pronto per Rimborso')")
        missions = Trasferta.query.filter(
            Trasferta.stato_post_missione == 'Pronto per Rimborso',
            Trasferta.stato_approvazione_finale == None
        ).all()
        
        print(f"Found {len(missions)} missions in 'Pronto per Rimborso'.")

        # 2. Check for 'Rimborso Concesso' (Old State)
        # These should logically have 0 expenses. If they have expenses, they are 'stranded' and should be migrated to 'Pronto per Rimborso'.
        old_state_missions = Trasferta.query.filter_by(stato_post_missione='Rimborso Concesso').all()
        print(f"\n2. Checking existing 'Rimborso Concesso' missions (Legacy state)")
        print(f"Found {len(old_state_missions)} missions.")
        
        stranded_count = 0
        for m in old_state_missions:
            total_expenses = sum(s.importo for s in m.spese if s.importo)
            if total_expenses > 0:
                print(f" [WARNING] Mission {m.id} is 'Rimborso Concesso' but has expenses: {total_expenses}. Should be 'Pronto per Rimborso'.")
                stranded_count += 1
            else:
                print(f" [OK] Mission {m.id} is 'Rimborso Concesso' and has 0 expenses. (Could be 'Conclusa')")
        
        if stranded_count > 0:
            print(f"\nCRITICAL: Found {stranded_count} missions that qualify for reimbursement but are hidden in the old 'Rimborso Concesso' state.")
        else:
            print("\nData looks consistent. No hidden reimbursable missions in 'Rimborso Concesso'.")

if __name__ == "__main__":
    verify_refactor_and_data()
