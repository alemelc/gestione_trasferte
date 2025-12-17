import sys
import os
from app import app, db
from models import Dipendente

def check_roles():
    print("--- User Roles ---")
    with app.app_context():
        users = Dipendente.query.all()
        for u in users:
            print(f"ID: {u.id}, Email: {u.email}, Ruolo: '{u.ruolo}'")

if __name__ == "__main__":
    check_roles()
