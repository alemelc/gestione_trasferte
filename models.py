from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

# ====================================================================
# CLASSE DIPENDENTE (Utente)
# ====================================================================

class Dipendente(UserMixin, db.Model):
    # Rimuoviamo il problema del Mapper definendo esplicitamente il nome della tabella
    __tablename__ = 'dipendente'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    ruolo = db.Column(db.String(50), nullable=False, default='Dipendente') # Dipendente, Dirigente, Amministrazione
    
    # === RELAZIONE RICORSIVA (Dirigente <-> Dipendente) ===
    # id_dirigente: La chiave esterna nel dipendente che punta all'ID del dirigente (che è un altro dipendente)
    id_dirigente = db.Column(db.Integer, db.ForeignKey('dipendente.id'), nullable=True) 

    # dirigente_responsabile: Il dipendente che è il dirigente di questo utente (lato "molti" della relazione)
    dirigente_responsabile = db.relationship(
        'Dipendente', 
        remote_side=[id], 
        # back_populates è più chiaro di backref in relazioni ricorsive
        back_populates='sottoposti', 
        foreign_keys=[id_dirigente]
    )
    
    # sottoposti: La lista dei dipendenti che questo utente supervisiona (lato "uno" della relazione)
    sottoposti = db.relationship(
        'Dipendente', 
        back_populates='dirigente_responsabile',
        lazy='dynamic', 
        foreign_keys=[id_dirigente]
    )
    
    # === RELAZIONE CON TRASFERTA (PER LE RICHIESTE INVIATE) ===
    # trasferte_richieste: Tutte le trasferte inviate da questo dipendente
    trasferte_richieste = db.relationship(
        'Trasferta', 
        back_populates='richiedente', 
        foreign_keys='Trasferta.id_dipendente', # Specificare la foreign key qui aiuta a prevenire conflitti
        lazy=True
    )
    
    # Logica di autenticazione richiesta da Flask-Login
    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f"Dipendente('{self.nome}', '{self.ruolo}')"


# ====================================================================
# CLASSE TRASFERTA
# ====================================================================

class Trasferta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # Chiave esterna verso il dipendente richiedente
    id_dipendente = db.Column(db.Integer, db.ForeignKey('dipendente.id'), nullable=False)
    
    # Stato e gestione Pre-Missione
    data_richiesta = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    giorno_missione = db.Column(db.Date, nullable=False)
    inizio_missione_ora = db.Column(db.Time, nullable=False)
    missione_presso = db.Column(db.String(255), nullable=False)
    motivo_missione = db.Column(db.Text, nullable=False)
    utilizzo_mezzo = db.Column(db.String(50), nullable=False) # Esempio: PROPRIO, PUBBLICO, AMMINISTRAZIONE
    
    # Autorizzazioni Straordinario (Pre-missione)
    aut_extra_orario = db.Column(db.String(10), nullable=False, default='no')
    aut_timbratura_entrata = db.Column(db.Time, nullable=True)
    aut_timbratura_uscita = db.Column(db.Time, nullable=True)
    motivo_timbratura = db.Column(db.Text, nullable=True)
    
    # Stato di approvazione Pre-Missione
    stato_pre_missione = db.Column(db.String(50), default='In attesa') # In attesa, Approvata, Rifiutata
    id_approva_pre = db.Column(db.Integer, db.ForeignKey('dipendente.id'), nullable=True) # Chi ha approvato/rifiutato
    data_pre_approvazione = db.Column(db.DateTime, nullable=True)
    
    # === RELAZIONE CON DIPENDENTE (richiedente) ===
    # richiedente: La relazione al dipendente che ha inviato la richiesta
    richiedente = db.relationship(
        'Dipendente', 
        back_populates='trasferte_richieste', 
        foreign_keys=[id_dipendente] # Usa solo id_dipendente per evitare conflitti
    )
    
    # === RELAZIONE CON APPROVATORE PRE-MISSIONE ===
    # approvatore_pre: La relazione a chi ha gestito l'approvazione pre-missione
    approvatore_pre = db.relationship(
        'Dipendente', 
        foreign_keys=[id_approva_pre],
        # Questo è un backref semplice che non interferisce con la ricorsiva
        backref=db.backref('trasferte_approvate', lazy='dynamic')
    )

    def __repr__(self):
        return f"Trasferta(ID:{self.id}, Stato:{self.stato_pre_missione}, Dipendente:{self.id_dipendente})"