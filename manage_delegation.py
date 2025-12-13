# manage_delegation.py

import sys
from models import db, Delega, Dipendente # Importa tutti i modelli necessari
from sqlalchemy.orm.exc import NoResultFound

try:
    from app import app
except ImportError:
    print("Errore: Impossibile importare l'istanza 'app' da app.py.")
    sys.exit(1)

# ID degli utenti coinvolti nel problema
ID_ROSSI_DELEGANTE = 1  # Mario Rossi
ID_VERDI_DELEGATO = 3   # Andrea Verdi

def manage_delegation_verdi_rossi():
    """Verifica e rimuove la delega problematica."""
    
    with app.app_context():
        print("\n--- GESTIONE DELEGA (ROSSI -> VERDI) ---")
        
        # 1. Carica gli oggetti utente per debug
        rossi = Dipendente.query.get(ID_ROSSI_DELEGANTE)
        verdi = Dipendente.query.get(ID_VERDI_DELEGATO)
        
        if not rossi or not verdi:
             print("Errore: Impossibile trovare Rossi o Verdi nel DB. Controllare gli ID.")
             return

        print(f"Verifica Delega Attiva: {rossi.nome} (ID {rossi.id}) -> {verdi.nome} (ID {verdi.id})")
        
        # 2. Cerca la delega specifica nel DB
        delega_problematica = Delega.query.filter_by(
            id_delegante=ID_ROSSI_DELEGANTE, 
            id_delegato=ID_VERDI_DELEGATO
        ).first()

        if delega_problematica:
            print(f"\n🛑 DELEGA TROVATA! ID Delega: {delega_problematica.id}")
            print(f"   Inizio: {delega_problematica.data_inizio}, Fine: {delega_problematica.data_fine}")
            print("   Questa riga sta causando la visualizzazione errata della missione.")
            
            # 3. Cancella la delega
            try:
                db.session.delete(delega_problematica)
                db.session.commit()
                print("\n✅ CANCELLAZIONE AVVENUTA CON SUCCESSO. La delega è stata rimossa dal DB.")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Errore durante la cancellazione: {e}")
                
        else:
            print("\n✅ NESSUNA DELEGA ATTIVA TROVATA tra Rossi e Verdi. Il problema è altrove.")
            
        print("--- FINE GESTIONE DELEGA ---")

if __name__ == '__main__':
    manage_delegation_verdi_rossi()