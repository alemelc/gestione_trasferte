import sys
from datetime import date, datetime
from app import app, db
from models import Dipendente, Trasferta, Spesa

def verify_post_mission():
    print("--- INIZIO VERIFICA POST MISSIONE (Simulazione) ---")
    
    mario_id = None
    mission_id = None
    
    with app.app_context():
        # 1. Recupera Mario Rossi (Dirigente ID 2)
        mario = Dipendente.query.get(2)
        if not mario or mario.ruolo != 'Dirigente':
            print("Errore: Mario Rossi (ID 2) non trovato o non è Dirigente.")
            return

        print(f"Utente Test: {mario.nome} {mario.cognome}, ID: {mario.id}, ID Dirigente: {mario.id_dirigente}")
        mario_id = mario.id
        
        # 2. Crea Missione di Test
        mission_date = date.today()
        t = Trasferta(
            id_dipendente=mario.id, 
            id_dirigente=mario.id, # Auto-approvazione Pre
            stato_pre_missione='Approvata',
            giorno_missione=mission_date,
            missione_presso="Test Auto Approvazione Modal",
            stato_post_missione='In attesa' # Initial state
        )
        db.session.add(t)
        db.session.commit()
        print(f"Missione creata: ID {t.id}")
        mission_id = t.id

        # 2.1 Aggiungi Spese ESISTENTI (come se salvate in precedenza)
        s1 = Spesa(id_trasferta=t.id, categoria="Vitto", descrizione="Pranzo", importo=50.0, data_spesa=mission_date)
        s2 = Spesa(id_trasferta=t.id, categoria="Trasporto", descrizione="Taxi", importo=25.0, data_spesa=mission_date)
        db.session.add_all([s1, s2])
        db.session.commit()
        print("Spese pre-salvate nel DB.")

    # 3. Usa Test Client per inviare il rendiconto (SIMULAZIONE MODALE - NO ARRAY SPESE)
    with app.test_client() as client:
        # Force Login tramite sessione
        with client.session_transaction() as sess:
            sess['_user_id'] = str(mario_id)
            sess['_fresh'] = True
        
        print(f"Login simulato effettuato per User ID {mario_id}.")

        # Data form per le spese (VUOTO per le spese)
        form_data = {
            'ora_inizio_effettiva': '09:00',
            'ora_fine_effettiva': '18:00',
            'km_percorsi': '10',
            'azione': 'invia',
            # Simula assenza di input array
            # 'spesa_categoria[]': ... OMESSO
        }

        # POST Request
        print(f"Invio POST a /invia_rendiconto/{mission_id} (DAL MODALE)...")
        response = client.post(f'/invia_rendiconto/{mission_id}', data=form_data, follow_redirects=True)
        
        if response.status_code != 200:
            print(f"Errore HTTP: {response.status_code}")
        
        # 4. Verifica risultato nel DB
        with app.app_context():
            updated_t = Trasferta.query.get(mission_id)
            print(f"Stato Finale Missione: {updated_t.stato_post_missione}")
            
            # Pulizia Manuale (Cascade mancante)
            if updated_t.spese:
                for s in updated_t.spese:
                    db.session.delete(s)
            db.session.delete(updated_t) 
            db.session.commit()
            print("Missione di test rimossa.")

            if updated_t.stato_post_missione == 'Pronta per rimborso':
                print("[SUCCESS] Lo stato è corretto.")
            else:
                print(f"[FAILURE] Lo stato è '{updated_t.stato_post_missione}' (Atteso: 'Pronta per rimborso')")

if __name__ == '__main__':
    verify_post_mission()
