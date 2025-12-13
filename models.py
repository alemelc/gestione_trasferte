from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy.ext.hybrid import hybrid_property

db = SQLAlchemy()

# ====================================================================
# CLASSE DIPENDENTE (Utente)
# ====================================================================

class Dipendente(UserMixin, db.Model):
    # Rimuoviamo il problema del Mapper definendo esplicitamente il nome della tabella
    __tablename__ = 'dipendente'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cognome = db.Column(db.String(100), nullable=False)
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

    trasferte_approvate = db.relationship(
        'Trasferta',
        back_populates='approvatore_pre',
        foreign_keys='Trasferta.id_approvatore_pre',
        lazy='dynamic'
    )

    spese_approvate = db.relationship(
        'Trasferta',
        back_populates='approvatore_post', # Deve corrispondere a Trasferta.approvatore_post
        foreign_keys='Trasferta.id_approvatore_post', # Deve corrispondere a Trasferta.id_approvatore_post
        lazy='dynamic'
    )
    
    deleghe_date = db.relationship(
        'Delega', 
        foreign_keys='Delega.id_delegante', 
        back_populates='delegante', 
        lazy='dynamic'
    )
   
    deleghe_ricevute = db.relationship(
        'Delega', 
        foreign_keys='Delega.id_delegato', 
        back_populates='delegato', 
        lazy='dynamic'
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
    __tablename__ = 'trasferta'
    id = db.Column(db.Integer, primary_key=True)
    
    # Dati Missione
    giorno_missione = db.Column(db.Date, nullable=False)
    inizio_missione_ora = db.Column(db.Time, nullable=True)
    missione_presso = db.Column(db.Text, nullable=False)
    motivo_missione = db.Column(db.Text, nullable=True)
    utilizzo_mezzo = db.Column('utilizzo_mezzo', db.String(10), default='No')
    aut_extra_orario = db.Column('aut_extra_orario', db.String(10), default='No')
    aut_timbratura_entrata = db.Column(db.Time, nullable=True)
    aut_timbratura_uscita = db.Column(db.Time, nullable=True)
    motivo_timbratura = db.Column(db.Text, nullable=True)
    note_premissione = db.Column(db.Text, nullable=True)

# --- CAMPI PER LA RENDICONTAZIONE (FASE 2: POST MISSIONE) ---
    
    # Orari della Missione (Data viene dalla Fase 1, qui si aggiungono solo gli orari effettivi)
    ora_inizio_effettiva = db.Column(db.Time, nullable=True) 
    ora_fine_effettiva = db.Column(db.Time, nullable=True) 
    durata_totale_ore = db.Column(db.Integer, nullable=True) # Campo calcolato, lo aggiorneremo dopo
    
    # Logistica
    pernotto = db.Column(db.Boolean, default=False, nullable=True) 
    durata_viaggio_andata_min = db.Column(db.Integer, nullable=True) # Convertito in minuti per semplicità
    durata_viaggio_ritorno_min = db.Column(db.Integer, nullable=True)
    
    # Chilometri e Percorso
    km_percorsi = db.Column(db.Float, nullable=True)
    mezzo_km_percorsi = db.Column(db.String(50), nullable=True) # MEZZI GRATUITI, FERROVIA, MEZZI PROPRI, etc.
    percorso_effettuato = db.Column(db.Text, nullable=True)
    
    # Pausa e Rimborso
    richiesta_pausa_pranzo = db.Column(db.String(50), nullable=True) # NESSUNA, BUONO PASTO, RIMBORSO SPESE
    pausa_pranzo_dalle = db.Column(db.Time, nullable=True) 
    pausa_pranzo_alle = db.Column(db.Time, nullable=True)
    
    # Extra Orario
    extra_orario = db.Column(db.String(50), nullable=True) # PLUS ORARIO, LAVORO STRAORDINARIO, RECUPERO TASTO 4
    
    note_rendicontazione = db.Column(db.Text, nullable=True)

    # Rapporto finale
    rapporto_finale = db.Column(db.Text, nullable=True)
    
    # --- STATO DI APPROVAZIONE SPESA (Fase 2) ---
    stato_post_missione = db.Column(db.String(50), default='N/A', nullable=False) # In attesa, Da rimborsare, Rimborso negato
    data_approvazione_post = db.Column(db.DateTime, nullable=True)
    id_approvatore_post = db.Column(db.Integer, db.ForeignKey('dipendente.id'), nullable=True)
    # --------------------------------------------
    # ------------------------------------------------------------

    # Relazione con il Dipendente richiedente (Dipendente.id)
    id_dipendente = db.Column(db.Integer, db.ForeignKey('dipendente.id'), nullable=False)
    id_dirigente = db.Column(db.Integer, db.ForeignKey('dipendente.id'), nullable=False)
    # --- NUOVI CAMPI PER IL TRACCIAMENTO DEL WORKFLOW ---
    stato_pre_missione = db.Column(db.String(50), default='In attesa', nullable=False)
    data_approvazione_pre = db.Column(db.DateTime, nullable=True) # Quando la decisione è stata presa
    
    # Chi ha approvato/rifiutato (puntiamo a Dipendente.id)
    id_approvatore_pre = db.Column(db.Integer, db.ForeignKey('dipendente.id'), nullable=True)
    # --------------------------------------------------------

    # Relazioni ORM (per le query Python)
    
    # Relazione con il richiedente
    richiedente = db.relationship(
        'Dipendente', 
        back_populates='trasferte_richieste', 
        foreign_keys=[id_dipendente]
    )
    
    # Relazione con l'approvatore (NUOVA)
    approvatore_pre = db.relationship(
        'Dipendente',
        back_populates='trasferte_approvate',
        foreign_keys=[id_approvatore_pre]
    )

    approvatore_post = db.relationship(
        'Dipendente',
        back_populates='spese_approvate',
        foreign_keys=[id_approvatore_post]
    )
    
    def __repr__(self):
        return f"Trasferta(ID: {self.id}, Dipendente: {self.richiedente.nome}, Stato: {self.stato_pre_missione})"


class Delega(db.Model):
    __tablename__ = 'delega'
    id = db.Column(db.Integer, primary_key=True)
    
    id_delegante = db.Column(db.Integer, db.ForeignKey('dipendente.id'), nullable=False)
    id_delegato = db.Column(db.Integer, db.ForeignKey('dipendente.id'), nullable=False)
    
    data_inizio = db.Column(db.Date, nullable=False)
    data_fine = db.Column(db.Date, nullable=True) 
    
    delegante = db.relationship(
        'Dipendente', 
        foreign_keys=[id_delegante], 
        back_populates='deleghe_date'
    )
    delegato = db.relationship(
        'Dipendente', 
        foreign_keys=[id_delegato], 
        back_populates='deleghe_ricevute'
    )
    
    def __repr__(self):
        from datetime import date # Per il repr
        return f"Delega(Delegante: {self.id_delegante}, Delegato: {self.id_delegato}, Attiva: {self.data_fine is None or self.data_fine >= date.today()})"



    