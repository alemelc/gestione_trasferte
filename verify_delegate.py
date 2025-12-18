from app import app, db, is_authorized_approver
from models import Dipendente, Trasferta, Delega
from datetime import date
from unittest.mock import MagicMock
import sys

def verify_delegate_restrictions():
    with app.app_context():
        print("--- VERIFICA RESTRIZIONI DELEGATO ---")
        
        # 1. Recupera Utenti
        rossi = Dipendente.query.get(1) # Dirigente
        bianchi = Dipendente.query.get(2) # Dipendente
        verdi = Dipendente.query.get(3) # Delegato
        
        if not all([rossi, bianchi, verdi]):
            print("Errore: Utenti mancanti (1, 2, 3).")
            return

        print(f"Dirigente: {rossi.nome} (ID {rossi.id})")
        print(f"Dipendente: {bianchi.nome} (ID {bianchi.id})")
        print(f"Delegato: {verdi.nome} (ID {verdi.id})")

        # 2. Crea/Assicura Delega da Rossi a Verdi
        delega = Delega.query.filter_by(id_delegante=rossi.id, id_delegato=verdi.id).first()
        if not delega:
            print("Creazione delega temporanea per il test...")
            delega = Delega(id_delegante=rossi.id, id_delegato=verdi.id, data_inizio=date.today())
            db.session.add(delega)
            db.session.commit()
            created_delega = True
        else:
            print("Delega esistente trovata.")
            created_delega = False

        try:
            # 3. MOCK current_user come VERDI (Delegato)
            # Dobbiamo patchare current_user o usare un contesto di request che simuli il login
            # Ma is_authorized_approver usa 'current_user' importato da flask_login.
            # Per questo test semplice, sovrascriviamo temporaneamente la variabile nel modulo app (brutto ma efficace per script)
            # OPPURE, usiamo 'login_user' in un request context.
            
            # Approccio MOCK
            mock_user = MagicMock()
            mock_user.is_authenticated = True
            mock_user.id = verdi.id
            mock_user.ruolo = verdi.ruolo
            
            # Qui il problema: is_authorized_approver usa 'from flask_login import current_user' dentro app.py
            # Non possiamo facilmente mockarlo da qui senza patch.
            # Proviamo a REPLICARE la logica di controllo nel test per vedere se 'funzionerebbe'
            # o usiamo unittest.mock.patch
            
            from unittest.mock import patch
            
            with patch('app.current_user', mock_user):
                
                # TEST A: Missione di ROSSI (Dirigente Delegante)
                trasferta_rossi = Trasferta(id_dipendente=rossi.id, id_dirigente=rossi.id)
                # Rossi è il dirigente di se stesso (auto-approvazione pre)
                # Ma supponiamo che chieda approvazione (o sia in fase post).
                # Il delegato VERDI può approvare?
                
                can_approve_rossi = is_authorized_approver(trasferta_rossi)
                print(f"TEST A: Delegato Verdi può approvare Dirigente Rossi? -> {can_approve_rossi}")
                if can_approve_rossi == False:
                    print("[SUCCESS] Il delegato non puo' approvare il proprio dirigente.")
                else:
                    print("[FAILURE] Il delegato PUO' approvare il proprio dirigente!")

                # TEST B: Missione di BIANCHI (Dipendente di Rossi)
                trasferta_bianchi = Trasferta(id_dipendente=bianchi.id, id_dirigente=rossi.id)
                
                can_approve_bianchi = is_authorized_approver(trasferta_bianchi)
                print(f"TEST B: Delegato Verdi puo' approvare Dipendente Bianchi (Sottoposto a Rossi)? -> {can_approve_bianchi}")
                if can_approve_bianchi == True:
                    print("[SUCCESS] Il delegato puo' approvare gli altri dipendenti.")
                else:
                    print(f"[FAILURE] Il delegato NON PUO' approvare gli altri dipendenti! (Delega attiva: {delega.data_inizio})")

        finally:
            # Pulizia
            if created_delega:
                print("Rimozione delega temporanea...")
                db.session.delete(delega)
                db.session.commit()

if __name__ == "__main__":
    verify_delegate_restrictions()
