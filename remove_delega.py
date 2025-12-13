# remove_delega.py

import sys
from models import db, Delega # Assicurati che l'importazione funzioni

# IMPORTANTE: Se il tuo file app.py si chiama diversamente, correggi l'import
try:
    from app import app 
except ImportError:
    print("Errore: Impossibile importare l'istanza 'app' da app.py. Assicurati che app.py esista.")
    sys.exit(1)

# ID del Dirigente (Mario Rossi) da cui rimuovere la delega
ID_DELEGANTE = 1 
# ID del Dipendente (Andrea Verdi) a cui è stata data la delega
ID_DELEGATO = 3

def remove_unneeded_delegation():
    """Rimuove la delega specifica che interferisce con la nuova gerarchia."""

    with app.app_context():
        print("\n--- INIZIO RIMOZIONE DELEGA ---")

        # 1. Identifichiamo e carichiamo la delega
        delega_da_rimuovere = Delega.query.filter(
            Delega.id_delegante == ID_DELEGANTE,
            Delega.id_delegato == ID_DELEGATO
        ).first()

        if delega_da_rimuovere:
            print(f"Trovata delega ID {delega_da_rimuovere.id}: Mario Rossi (ID 1) -> Andrea Verdi (ID 3).")

            # 2. Elimina e salva
            db.session.delete(delega_da_rimuovere)
            db.session.commit()

            print("✅ DELEGA RIMOZIONE COMPLETATA: La riga è stata cancellata dal DB.")
        else:
            print("❌ NESSUNA DELEGA TROVATA: La delega tra Rossi e Verdi non esiste o è già stata rimossa.")

        print("--- FINE RIMOZIONE DELEGA ---")

if __name__ == '__main__':
    remove_unneeded_delegation()