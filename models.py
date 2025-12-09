from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

# Inizializziamo SQLAlchemy (verrà inizializzato correttamente in app.py)
db = SQLAlchemy()

# --- Modello 1: Dipendenti (Utenti) ---
# Usiamo UserMixin per le funzionalità di login
class Dipendente(db.Model, UserMixin):
    __tablename__ = 'dipendenti'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    ruolo = db.Column(db.String(50), default='Dipendente') # 'Dipendente', 'Dirigente', 'Amministratore'

    # Chiave Esterna: Chi è il mio dirigente responsabile
    id_dirigente_resp = db.Column(db.Integer, db.ForeignKey('dipendenti.id'), nullable=True)
    
    # Definiamo le relazioni (opzionali, ma utili per l'ORM)
  # Relazione 1: Trasferte richieste da questo dipendente (Usa id_dipendente)
    trasferte_richieste = db.relationship(
        'Trasferta', 
        foreign_keys='Trasferta.id_dipendente', # <-- Usa la FK del richiedente
        backref=db.backref('richiedente', lazy=True), 
        lazy='dynamic'
    )
    
    # Relazione 2: Trasferte approvate da questo dipendente (Usa id_approva_effettivo)
    trasferte_approvate = db.relationship(
        'Trasferta', 
        foreign_keys='Trasferta.id_approva_effettivo', # <-- Usa la FK dell'approvatore
        backref=db.backref('approvatore_effettivo', lazy=True), 
        lazy='dynamic'
    )

    # Relazione 3: Gerarchia (Sottoposti)
    sottoposti = db.relationship(
        'Dipendente', 
        foreign_keys='Dipendente.id_dirigente_resp', # <-- Usa la FK self-join
        backref=db.backref('dirigente_responsabile', remote_side=[id], lazy=True), 
        lazy='dynamic'
    )
    

    def __repr__(self):
        return f"Dipendente('{self.nome}', '{self.ruolo}')"


# --- Modello 2: Trasferte (Richieste) ---
class Trasferta(db.Model):
    __tablename__ = 'trasferte'
    id = db.Column(db.Integer, primary_key=True)

    # Chiavi Esterne (Devono rimanere!)
    id_dipendente = db.Column(db.Integer, db.ForeignKey('dipendenti.id'), nullable=False)
    id_approva_effettivo = db.Column(db.Integer, db.ForeignKey('dipendenti.id'), nullable=True)

    destinazione = db.Column(db.String(255), nullable=False)
    data_inizio = db.Column(db.Date, nullable=False)
    data_fine = db.Column(db.Date, nullable=False)
    scopo = db.Column(db.Text, nullable=False)
    costo_stimato = db.Column(db.Float, nullable=False)
    data_richiesta = db.Column(db.DateTime, default=datetime.utcnow)
    stato = db.Column(db.String(50), default='In attesa') # 'In attesa', 'Approvata', 'Rifiutata'


    
    def __repr__(self):
        return f"Trasferta('{self.destinazione}', '{self.stato}')"


# --- Modello 3: Delegati (Permessi di Approvazione) ---
class Delegato(db.Model):
    __tablename__ = 'deleghe'
    id = db.Column(db.Integer, primary_key=True)
    
    data_inizio = db.Column(db.Date, default=datetime.utcnow().date)
    data_fine = db.Column(db.Date, nullable=True)
    attiva = db.Column(db.Boolean, default=True) # Per disattivare la delega senza cancellare il record

    # Relazione 1: Il dirigente che delega
    id_dirigente = db.Column(db.Integer, db.ForeignKey('dipendenti.id'), nullable=False)
    dirigente = db.relationship('Dipendente', foreign_keys=[id_dirigente], backref='deleghe_concesse')

    # Relazione 2: Il delegato
    id_delegato = db.Column(db.Integer, db.ForeignKey('dipendenti.id'), nullable=False)
    delegato = db.relationship('Dipendente', foreign_keys=[id_delegato], backref='deleghe_ricevute')   
    
    def __repr__(self):
        return f"Delega(Dirigente ID: {self.id_dirigente} a Delegato ID: {self.id_delegato})"