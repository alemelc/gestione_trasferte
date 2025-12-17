import sys
import os
from app import app, db
from models import Trasferta

def verify_dashboard_query():
    print("--- Verifying Dashboard Query Fix ---")
    with app.app_context():
        # Define the states we are interested in
        target_states = ['Rimborso Concesso', 'Pronto per Rimborso']
        
        # Replicate the fixed query logic
        missions = Trasferta.query.filter(
            Trasferta.stato_post_missione.in_(target_states),
            Trasferta.stato_approvazione_finale == None
        ).order_by(Trasferta.giorno_missione.asc()).all()

        print(f"Querying for states: {target_states}")
        print(f"Found {len(missions)} missions pending administration approval.")

        for m in missions:
            print(f" - ID: {m.id}, Stato Post: '{m.stato_post_missione}', Dipendente ID: {m.id_dipendente}, Giorno: {m.giorno_missione}")
            
        # Check if we have at least one 'Pronto per Rimborso' which was previously missing
        pronto_count = sum(1 for m in missions if m.stato_post_missione == 'Pronto per Rimborso')
        if pronto_count > 0:
            print(f"\nSUCCESS: Found {pronto_count} missions with 'Pronto per Rimborso'. The fix is working.")
        else:
            print("\nWARNING: No 'Pronto per Rimborso' missions found. Either none exist in DB or the query is still wrong.")
            # Let's check if any exist in the DB at all to be sure
            all_pronto = Trasferta.query.filter_by(stato_post_missione='Pronto per Rimborso').count()
            print(f"Total 'Pronto per Rimborso' missions in DB (regardless of final approval): {all_pronto}")

if __name__ == "__main__":
    verify_dashboard_query()
