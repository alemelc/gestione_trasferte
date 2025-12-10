# app.py

# ====================================================================
# 1. IMPORTAZIONI DELLE LIBRERIE
# ====================================================================
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from sqlalchemy import func 
from sqlalchemy.orm import joinedload # Importa joinedload
# NOTA: Qui NON importiamo Dipendente, Trasferta, ecc.

# ====================================================================
# 2. CONFIGURAZIONE E CREAZIONE ISTANZE PRINCIPALI
# ====================================================================
app = Flask(__name__)
# Le configurazioni del DB devono essere qui, subito dopo aver creato l'app.
app.config['SECRET_KEY'] = 'la_tua_chiave_segreta_e_complessa' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ====================================================================
# 3. IMPORTAZIONE DEI MODELLI E DI 'db' (PLACEHOLDER)
# ====================================================================
# Importiamo i modelli e l'oggetto 'db' (definito in models.py come placeholder).
from models import db, Dipendente, Trasferta
# Questo risolve il ciclo di importazione!

# ====================================================================
# 4. INIZIALIZZAZIONE DEGLI OGGETTI TRAMITE init_app
# ====================================================================
# Collega l'oggetto 'db' all'app configurata.
db.init_app(app) 

# Inizializzazione di LoginManager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Funzione per il caricamento dell'utente di Flask-Login
@login_manager.user_loader
def load_user(user_id):
    # Carica il Dipendente e contemporaneamente la sua relazione 'dirigente_responsabile'
    return Dipendente.query.options(
        joinedload(Dipendente.dirigente_responsabile)
    ).get(int(user_id))

# ====================================================================
# ROTTE DI GESTIONE E AUTENTICAZIONE
# ====================================================================

@app.route('/')
def index():
    if current_user.is_authenticated:
        dirigente = None
        
        if current_user.ruolo == 'Dipendente':
            
            # --- TENTATIVO 1: VECCHIA RELAZIONE FALLITA ---
            # if current_user.dirigente_responsabile:
            #     dirigente = current_user.dirigente_responsabile
            
            # --- TENTATIVO 2: SOLUZIONE BRUTE-FORCE AGGIORNATA ---
            if current_user.id_dirigente:
                # Esegui la query più semplice possibile per recuperare l'oggetto Dirigente
                # La usiamo sempre, per essere certi che la variabile sia popolata
                dirigente = Dipendente.query.get(current_user.id_dirigente)
            
        # Passiamo l'oggetto Dirigente al template con il nome "dirigente_assegnato"
        return render_template('index.html', user=current_user, dirigente_assegnato=dirigente) 
        
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = Dipendente.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Credenziali non valide. Riprova.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sei stato disconnesso.', 'success')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        password = request.form.get('password')
        ruolo = request.form.get('ruolo', 'Dipendente') # Default a Dipendente

        if Dipendente.query.filter_by(email=email).first():
            flash('Email già registrata.', 'warning')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='scrypt')
        new_user = Dipendente(nome=nome, email=email, password_hash=hashed_password, ruolo=ruolo)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash(f'{ruolo} {nome} registrato con successo!', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Errore durante la registrazione: {e}', 'danger')
            
    return render_template('register.html')

@app.route('/create_db')
def create_db():
    try:
        # L'app context è necessario con init_app
        with app.app_context():
            db.create_all()
        return "Database e tabelle create con successo! Ora registra gli utenti e assegna i dirigenti."
    except Exception as e:
        return f"Errore durante la creazione del database: {e}"

# app.py

# app.py

@app.route('/assegna_dirigenti')
def assegna_dirigenti():
    # Trova il Dirigente (Mario Rossi, presumibilmente ID 1)
    dirigente = Dipendente.query.filter_by(ruolo='Dirigente').order_by(Dipendente.id.asc()).first()
    
    # Trova il Dipendente (Luigi Bianchi, presumibilmente ID 2)
    dipendente = Dipendente.query.filter(
        Dipendente.ruolo == 'Dipendente',
        Dipendente.id != dirigente.id if dirigente else True 
    ).order_by(Dipendente.id.asc()).first()
    
    if dirigente is None or dipendente is None:
        return "Assicurati di aver registrato almeno un Dirigente e un Dipendente."

    try:
        # --- FORZA L'ASSEGNAZIONE E IL COMMIT ---
        
        # 1. Imposta l'ID del dirigente sul dipendente
        dipendente.id_dirigente = int(dirigente.id) # Forza a INT per sicurezza
        
        # 2. Aggiunge e salva (questo è il blocco cruciale)
        db.session.add(dipendente)
        db.session.commit()
        
        # 3. Verifica per l'utente
        dipendente_verificato = Dipendente.query.get(dipendente.id)
        
        return f"✅ ASSEGNAZIONE RIUSCITA DEFINITIVA: {dirigente.nome} (ID: {dirigente.id}) assegnato a {dipendente.nome} (ID: {dipendente.id})." \
               f" VERIFICA: id_dirigente è ora {dipendente_verificato.id_dirigente}"
    
    except Exception as e:
        db.session.rollback()
        return f"❌ Errore FATALE durante il salvataggio: {e}"

# ====================================================================
# ROTTE APPLICATIVE (TRASFERTE)
# ====================================================================

@app.route('/nuova_trasferta', methods=['GET', 'POST'])
@login_required 
def nuova_trasferta():
    if current_user.ruolo != 'Dipendente':
        flash('Solo i dipendenti possono inviare richieste di trasferta.', 'warning')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            # --- RACCOLTA DATI DAL FORM (SONO TUTTE STRINGHE O VALORI BOOLEANI) ---
            giorno_missione_str = request.form.get('giorno_missione') # Es. '2025-12-25'
            missione_presso = request.form.get('missione_presso')
            motivo_missione = request.form.get('motivo_missione')
            inizio_missione_ora_str = request.form.get('inizio_missione_ora') # Es. '09:00'
            utilizzo_mezzo = request.form.get('utilizzo_mezzo')
            
            aut_extra_orario = request.form.get('aut_extra_orario') == 'si' # Converte in True/False
            
            aut_timbratura_entrata_str = request.form.get('aut_timbratura_entrata')
            aut_timbratura_uscita_str = request.form.get('aut_timbratura_uscita')
            motivo_timbratura = request.form.get('motivo_timbratura')

            # --- VALIDAZIONE BASE ---
            if not giorno_missione_str or not inizio_missione_ora_str or not missione_presso:
                raise ValueError("Campi obbligatori mancanti.")

            # --- CONVERSIONE DEI TIPI DI DATI PER SQLALCHEMY ---
            
            # 1. Conversione Data (Stringa -> datetime.date)
            giorno_missione = datetime.strptime(giorno_missione_str, '%Y-%m-%d').date()

            # 2. Conversione Ora (Stringa -> datetime.time)
            # Assumiamo il formato HH:MM (es. 14:30)
            inizio_missione_ora = datetime.strptime(inizio_missione_ora_str, '%H:%M').time() 
            
            # 3. Conversione Ore di Timbratura (Se presenti, altrimenti rimangono None)
            aut_timbratura_entrata = None
            if aut_timbratura_entrata_str:
                aut_timbratura_entrata = datetime.strptime(aut_timbratura_entrata_str, '%H:%M').time()
            
            aut_timbratura_uscita = None
            if aut_timbratura_uscita_str:
                aut_timbratura_uscita = datetime.strptime(aut_timbratura_uscita_str, '%H:%M').time()

            # --- CREAZIONE E SALVATAGGIO OGGETTO TRASFERTA ---
            nuova_richiesta = Trasferta(
                id_dipendente=current_user.id,
                
                # FASE 1 (Dati Base)
                giorno_missione=giorno_missione, 
                missione_presso=missione_presso,
                motivo_missione=motivo_missione,
                inizio_missione_ora=inizio_missione_ora,
                utilizzo_mezzo=utilizzo_mezzo,
                
                # Autorizzazioni
                aut_extra_orario=aut_extra_orario, # Valore booleano True/False
                aut_timbratura_entrata=aut_timbratura_entrata, 
                aut_timbratura_uscita=aut_timbratura_uscita,
                motivo_timbratura=motivo_timbratura,
            )

            db.session.add(nuova_richiesta)
            db.session.commit()
            flash('Richiesta di trasferta PRE-MISSIONE inviata con successo! (In attesa di approvazione)', 'success')
            return redirect(url_for('mie_trasferte'))

        except ValueError as e:
            # Cattura errori di conversione data/ora (es. formato sbagliato)
            flash(f'Errore nel formato dei dati inseriti: {e}', 'danger')
            db.session.rollback()
        except Exception as e:
            # Cattura altri errori generici (es. problemi di commit)
            flash(f'Errore sconosciuto durante l\'invio: {e}', 'danger')
            db.session.rollback()

    return render_template('nuova_trasferta.html')


# Aggiungi questa rotta in app.py, preferibilmente vicino alle altre rotte principali

# app.py

# app.py

# app.py

@app.route('/mie_trasferte')
@login_required
def mie_trasferte():
    if current_user.ruolo == 'Dipendente':
        # ... (Logica Dipendente invariata) ...
        # ...
        trasferte = Trasferta.query.filter_by(id_dipendente=current_user.id).all()
        titolo = "Le Mie Richieste di Trasferta Inviate"
    
    elif current_user.ruolo == 'Dirigente':
    
        dirigente_id = current_user.id
        stato_atteso = 'In attesa'
    
        # === NUOVO BLOCCO DEBUG CRUCIALE ===
        # Controlla tutti i dipendenti che dovrebbero essere sotto questo dirigente
        sottoposti_debug = db.session.query(Dipendente.id, Dipendente.nome, Dipendente.id_dirigente).filter(
            Dipendente.id_dirigente == dirigente_id
        ).all()
    
        print(f"DEBUG EXTREME: Dirigente loggato ID: {dirigente_id}")
        print(f"DEBUG EXTREME: Dipendenti sotto ID {dirigente_id}: {sottoposti_debug}")
        # === FINE NUOVO BLOCCO DEBUG ===
    
        # Esegue la query che non funziona (usiamo .ilike() come fallback sicuro)
        trasferte = db.session.query(Trasferta).join(Dipendente, Trasferta.id_dipendente == Dipendente.id).filter(
            Dipendente.id_dirigente == dirigente_id,
            Trasferta.stato_pre_missione.ilike(stato_atteso)
        ).all()
        
    print(f"DEBUG: Numero di trasferte trovate per Dirigente: {len(trasferte)}")
        # === FINE BLOCCO DEBUG ESTREMO ===

    titolo = f"Richieste dei Subordinati da Approvare ({len(trasferte)} richieste)"

    # ... (il resto della rotta) ...
    return render_template('mie_trasferte.html', trasferte=trasferte, titolo=titolo)
# app.py

@app.route('/approva_trasferta/<int:trasferta_id>')
@login_required
def approva_trasferta(trasferta_id):
    # 1. Verifica che l'utente sia un Dirigente
    if current_user.ruolo not in ['Dirigente', 'Amministrazione']:
        flash('Non autorizzato ad approvare le richieste.', 'danger')
        return redirect(url_for('mie_trasferte'))

    # 2. Trova la Trasferta
    trasferta = Trasferta.query.get(trasferta_id)

    if not trasferta:
        flash('Richiesta di trasferta non trovata.', 'danger')
        return redirect(url_for('mie_trasferte'))

    # 3. Verifica l'autorizzazione (solo se il richiedente è un suo sottoposto)
    if trasferta.richiedente.id_dirigente != current_user.id:
        flash('Non sei il dirigente responsabile per questa richiesta.', 'danger')
        return redirect(url_for('mie_trasferte'))

    try:
        # --- LOGICA DI APPROVAZIONE PRE-MISSIONE ---
        trasferta.stato_pre_missione = 'Approvata'
        trasferta.data_pre_approvazione = datetime.utcnow()
        trasferta.id_approva_pre = current_user.id # Registra l'ID dell'approvatore

        db.session.commit()
        flash(f'Richiesta di trasferta ID {trasferta_id} approvata con successo! Il dipendente è stato notificato.', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante l\'approvazione: {e}', 'danger')

    return redirect(url_for('mie_trasferte'))


@app.route('/rifiuta_trasferta/<int:trasferta_id>')
@login_required
def rifiuta_trasferta(trasferta_id):
    # 1. Verifica che l'utente sia un Dirigente
    if current_user.ruolo not in ['Dirigente', 'Amministrazione']:
        flash('Non autorizzato a rifiutare le richieste.', 'danger')
        return redirect(url_for('mie_trasferte'))
    
    # 2. Trova la Trasferta
    trasferta = Trasferta.query.get(trasferta_id)

    if not trasferta:
        flash('Richiesta di trasferta non trovata.', 'danger')
        return redirect(url_for('mie_trasferte'))

    # 3. Verifica l'autorizzazione (solo se il richiedente è un suo sottoposto)
    if trasferta.richiedente.id_dirigente != current_user.id:
        flash('Non sei il dirigente responsabile per questa richiesta.', 'danger')
        return redirect(url_for('mie_trasferte'))

    try:
        # --- LOGICA DI RIFIUTO PRE-MISSIONE ---
        trasferta.stato_pre_missione = 'Rifiutata'
        # Non registriamo l'approvatore qui, ma possiamo registrare la data
        trasferta.data_pre_approvazione = datetime.utcnow()
        trasferta.id_approva_pre = current_user.id # Registra l'ID di chi ha gestito la richiesta

        db.session.commit()
        flash(f'Richiesta di trasferta ID {trasferta_id} rifiutata.', 'warning')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante il rifiuto: {e}', 'danger')

    return redirect(url_for('mie_trasferte'))


# Aggiungi queste rotte placeholder in app.py

@app.route('/dettagli_trasferta/<int:trasferta_id>')
@login_required
def dettagli_trasferta(trasferta_id):
    # La logica dettagliata verrà aggiunta dopo
    trasferta = Trasferta.query.get_or_404(trasferta_id)
    # Questa rotta DEVE ancora essere completata con il suo template
    flash(f'Visualizzazione dettagli per la trasferta ID: {trasferta.id}. (Pagina dettagli da creare)', 'info')
    return redirect(url_for('mie_trasferte'))






if __name__ == '__main__':
    # Rimuovi questa riga se usi 'flask run'
    app.run(debug=True)
    pass