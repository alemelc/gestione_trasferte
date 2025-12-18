from app import app, db
from models import Dipendente

def debug_users_setup():
    with app.app_context():
        print("--- VERIFICA SETUP UTENTI ---")
        users = Dipendente.query.all()
        for u in users:
            dirigente = Dipendente.query.get(u.id_dirigente) if u.id_dirigente else None
            dirigente_str = f"{dirigente.nome} {dirigente.cognome} (ID: {dirigente.id})" if dirigente else "None"
            
            print(f"ID: {u.id} | Nome: {u.nome} {u.cognome} | Ruolo: {u.ruolo} | ID Dirigente FK: {u.id_dirigente} -> Dirigente: {dirigente_str}")
            
            if u.ruolo == 'Dirigente':
                if u.id_dirigente == u.id:
                    print(f"[OK]: Il Dirigente {u.nome} {u.cognome} si auto-approva.")
                else:
                    print(f"[ERROR]: Il Dirigente {u.nome} {u.cognome} (ID {u.id}) NON punta a se stesso (ID Dir: {u.id_dirigente}).")
    

if __name__ == "__main__":
    debug_users_setup()
