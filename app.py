# app.py

# ====================================================================
# 1. IMPORTAZIONI DELLE LIBRERIE
# ====================================================================
import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from models import db, Dipendente, Trasferta, Delega, Spesa
from sqlalchemy import or_, and_, text, func
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, date, time
from sqlalchemy.orm import joinedload, selectinload # Importa joinedload
from functools import wraps

# ====================================================================
# 2. CONFIGURAZIONE E CREAZIONE ISTANZE PRINCIPALI
# ====================================================================
basedir = os.path.abspath(os.path.dirname(__file__))

# 1. CARICA VARIABILI D'AMBIENTE
load_dotenv()

# 3. CREA ISTANZA FLASK E IMPOSTA LA CONFIGURAZIONE
app = Flask(__name__, instance_relative_config=True)

def is_authorized_approver(trasferta):
    """
    Verifica se l'utente loggato è l'approvatore diretto (dirigente)
    o il delegato attivo.

    NUOVO CONTROLLO: Il delegato NON può approvare le missioni del proprio delegante (dirigente).
    """
    if not current_user.is_authenticated:
        return False

    dirigente_approvatore_id = trasferta.id_dirigente

    if not dirigente_approvatore_id:
        return False
        
    # =========================================================
    # 1. CASO BASE: L'utente è il Dirigente diretto della missione?
    # =========================================================
    if current_user.id == dirigente_approvatore_id:
        return True # Il dirigente diretto può sempre approvare (se non è la sua missione, vedi punto 3)

    # =========================================================
    # 2. CASO DELEGATO ATTIVO
    # =========================================================
    today = date.today()
    
    delega_attiva = Delega.query.filter(
        Delega.id_delegante == dirigente_approvatore_id,
        Delega.id_delegato == current_user.id,
        Delega.data_inizio <= today,
        (Delega.data_fine.is_(None) | (Delega.data_fine >= today))
    ).first()

    if delega_attiva:
        # CONTROLLO CRITICO: Un delegato (current_user) non può approvare 
        # una missione richiesta dal suo delegante (il dirigente approvatore).
        
        # Se la missione è stata richiesta dal Dirigente che ci ha delegato, NEGA l'autorizzazione.
        if trasferta.id_dipendente == dirigente_approvatore_id:
            # La missione è stata richiesta dal delegante (il capo)
            return False 
        
        return True # Delegato autorizzato per tutti gli altri dipendenti

    # =========================================================
    # 3. CONTROLLO SPECIALE: L'utente è un dirigente che approva la PROPRIA missione?
    #    (Solo per la fase di rendiconto, dove deve essere negato)
    # =========================================================
    # Se il richiedente è lo stesso dell'approvatore, e siamo in una fase di spesa/rendiconto,
    # qui dovrebbe subentrare un'approvazione di livello superiore (Amministrazione/HR).
    # Se non è già gestito da un filtro di stato (es. la missione del dirigente va subito ad HR),
    # è meglio bloccare l'auto-approvazione delle spese a questo livello.
    
    # Per ora, manteniamo la logica di approvazione solo sulla delega.
    # L'auto-approvazione del dirigente è stata discussa come "necessaria" per il pre-missione, 
    # ma deve essere bloccata se la missione è post-missione/spesa e il richiedente è il dirigente.
    
    # Se vuoi bloccare anche l'auto-approvazione del rendiconto (Fase Post) per il dirigente:
    if trasferta.id_dipendente == current_user.id and trasferta.id_dirigente == current_user.id:
        if trasferta.stato_post_missione in ['In attesa', 'Compilata']:
             return False # Dirigente non può auto-approvare le proprie spese
        
    return False

# Registra la funzione per renderla disponibile GLOBALMENTE in tutti i template Jinja2
app.jinja_env.globals.update(is_authorized_approver=is_authorized_approver)
# 2. DETERMINA L'URI DEL DATABASE
# DATABASE_URL viene fornito automaticamente da Render
# POSTGRES_URL viene fornito automaticamente da Vercel Postgres
db_url = os.environ.get("DATABASE_URL")

if not db_url:
    # Supporto nativo per Vercel Postgres
    db_url = os.environ.get("POSTGRES_URL")

if db_url:
    # Fix per SQLAlchemy: Render/Vercel usano 'postgres://' ma SQLAlchemy vuole 'postgresql://'
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
else:
    # Fallback locale a SQLite
    db_url = 'sqlite:///' + os.path.join(basedir, 'trasferte.db')

# Configura SECRET_KEY e DATABASE_URI
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'la_tua_chiave_segreta_e_complessa_fallback') # Usa ENV o fallback
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

try:
    os.makedirs(app.instance_path)
except OSError:
    pass


# 4. INIZIALIZZAZIONE DELLE ESTENSIONI
db.init_app(app) # Collega l'istanza 'db' importata
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)

def dirigente_required(f):
    """
    Decorator personalizzato per limitare l'accesso alle rotte solo agli utenti con ruolo 'Dirigente'.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.ruolo != 'Dirigente':
            # Potresti reindirizzare a una pagina di errore o alla dashboard principale
            flash('Accesso negato. Questa funzione è riservata ai Dirigenti.', 'danger')
            return redirect(url_for('mie_trasferte')) # Assicurati che 'mie_trasferte' sia un endpoint valido
        return f(*args, **kwargs)
    return decorated_function

def amministrazione_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Accesso consentito SOLO all'Amministrazione (Contabilità) e al Superuser (opzionale, ma spesso utile)
        # Qui manteniamo l'accesso al Superuser per debug/controllo, ma puoi rimuoverlo se vuoi separazione netta.
        if current_user.ruolo not in ['Amministrazione', 'Superuser']:
            flash('Accesso negato. Area riservata all\'Amministrazione.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def presenze_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.ruolo not in ['Presenze', 'Superuser']:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def superuser_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.ruolo != 'Superuser':
            flash('Accesso negato. Area riservata al Superuser.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


def ruolo_richiesto(ruoli_consentiti):
    """
    Limita l'accesso alla rotta solo agli utenti con i ruoli specificati.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Devi effettuare il login per accedere a questa pagina.', 'warning')
                return redirect(url_for('login')) # Assumendo tu abbia una rotta 'login'

            if current_user.ruolo not in ruoli_consentiti:
                flash(f'Accesso negato. Sono richiesti i ruoli: {", ".join(ruoli_consentiti)}.', 'danger')
                return redirect(url_for('dashboard')) # Reindirizza a una rotta generica
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator




@app.route('/revoca_delega/<int:delega_id>', methods=['POST'])
@login_required
@dirigente_required
def revoca_delega(delega_id):
    from datetime import date, timedelta
    from models import Delega, db 

    delega = Delega.query.get_or_404(delega_id)

    # 1. Autorizzazione (invariata)
    if delega.id_delegante != current_user.id:
        flash('Non sei autorizzato a revocare questa delega.', 'danger')
        return redirect(url_for('gestisci_deleghe'))
        
    oggi = date.today()
    ieri = oggi - timedelta(days=1)
    
    # ======================================================================
    # 2. LOGICA DI GESTIONE E REVOCA
    # ======================================================================

    try:
        if delega.data_inizio > oggi:
            # CASO A: Delega futura (Non ancora iniziata) -> ANNULLAMENTO COMPLETO
            
            # Annulliamo/Cancelliamo la delega. Questo è più pulito che impostare date finte.
            db.session.delete(delega)
            messaggio = "Delega FUTURA (non ancora iniziata) annullata con successo."
            
        elif delega.data_fine is not None and delega.data_fine < oggi:
            # CASO B: Delega già scaduta
            messaggio = "Questa delega è già scaduta e non necessita di revoca manuale."
            flash(messaggio, 'warning')
            return redirect(url_for('gestisci_deleghe'))

        else:
            # CASO C: Delega Attiva (In corso o Permanente) -> REVOCA IMMEDIATA
            
            # Imposta la data di fine a IERI, in modo che la delega sia inattiva OGGI
            delega.data_fine = ieri
            db.session.commit()
            messaggio = f"Delega a {delega.delegato.nome} revocata con successo e disattivata immediatamente."
        
        # Se siamo nel CASO A o CASO C, esegui il commit
        db.session.commit()
        flash(messaggio, 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Errore nel processo di revoca/annullamento della delega: {e}', 'danger')
        
    return redirect(url_for('gestisci_deleghe'))

# ====================================================================
# 3. IMPORTAZIONE DEI MODELLI E DI 'db' (PLACEHOLDER)
# ====================================================================
# Importiamo i modelli e l'oggetto 'db' (definito in models.py come placeholder).
#from models import db, Dipendente, Trasferta
# Questo risolve il ciclo di importazione!

# ====================================================================
# 4. INIZIALIZZAZIONE DEGLI OGGETTI TRAMITE init_app
# ====================================================================
# Collega l'oggetto 'db' all'app configurata.
#db.init_app(app)

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

@app.route('/get_modale_content/<int:trasferta_id>/<string:fase>')
@login_required
def get_modale_content(trasferta_id, fase):

    trasferta = Trasferta.query.get_or_404(trasferta_id)
    readonly_mode = request.args.get('readonly') == 'true'

    if fase == 'pre':
        return render_template('_modale_pre.html', trasferta=trasferta, fase=fase, readonly_mode=readonly_mode)
        
    elif fase == 'rendiconto':
        # Per il dipendente: mostra dati effettivi e spese da completare/revisionare
        spese = Spesa.query.filter_by(id_trasferta=trasferta_id).all()
        # Calcolo del totale per la visualizzazione nel modale
        totale_spese = sum(spesa.importo for spesa in spese) 
        
        return render_template('_modale_rendiconto.html', 
                               trasferta=trasferta, 
                               spese=spese, 
                               totale_spese=totale_spese, # Variabile passata
                               fase=fase,
                               readonly_mode=readonly_mode)
        
    elif fase == 'rimborso':
        # Per il dirigente: mostra dati effettivi e spese per l'approvazione finale
        spese = Spesa.query.filter_by(id_trasferta=trasferta_id).all()
        
        # Calcolo del totale per l'approvazione finale
        totale_spese = sum(spesa.importo for spesa in spese) # <-- Variabile DEFINITA QUI
        
        return render_template('_modale_rendiconto.html', 
                               trasferta=trasferta, 
                               spese=spese,
                               totale_spese=totale_spese, # Variabile usata qui
                               fase=fase,
                               readonly_mode=readonly_mode)
    
    else:
        return jsonify({'error': 'Fase non riconosciuta.'}), 400


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

@app.route('/cambia_password', methods=['GET', 'POST'])
@login_required
def cambia_password():
    if request.method == 'POST':
        password_attuale = request.form.get('password_attuale')
        nuova_password = request.form.get('nuova_password')
        conferma_password = request.form.get('conferma_password')

        if not check_password_hash(current_user.password_hash, password_attuale):
            flash('La password attuale non è corretta.', 'danger')
            return redirect(url_for('cambia_password'))
        
        if nuova_password != conferma_password:
            flash('Le nuove password non coincidono.', 'warning')
            return redirect(url_for('cambia_password'))

        current_user.password_hash = generate_password_hash(nuova_password, method='scrypt')
        
        try:
            db.session.commit()
            flash('La tua password è stata aggiornata con successo!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f"Errore durante l'aggiornamento: {e}", 'danger')

    return render_template('cambia_password.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nome = request.form.get('nome')
        cognome = request.form.get('cognome')
        email = request.form.get('email')
        password = request.form.get('password')
        ruolo = 'Dipendente' # request.form.get('ruolo', 'Dipendente') -> FORZATO A DIPENDENTE

        if Dipendente.query.filter_by(email=email).first():
            flash('Email già registrata.', 'warning')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='scrypt')
        new_user = Dipendente(nome=nome, cognome=cognome, email=email, password_hash=hashed_password, ruolo=ruolo)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash(f'{ruolo} {nome} registrato con successo!', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Errore durante la registrazione: {e}', 'danger')
            
    return render_template('register.html')

#@app.route('/create_db')
#def create_db():
#    try:
#        # L'app context è necessario con init_app
#        with app.app_context():
#            db.create_all()
#        return "Database e tabelle create con successo! Ora registra gli utenti e assegna i dirigenti."
#    except Exception as e:
#        return f"Errore durante la creazione del database: {e}"

# app.py

# app.py

@app.route('/associa_dirigente.html')
def associa_dirigente_script():
    # Trova gli utenti per ID
    rossi = Dipendente.query.get(1) # Mario Rossi, ID 1 (Dirigente)
    bianchi = Dipendente.query.get(2) # Luigi Bianchi, ID 2
    verdi = Dipendente.query.get(3) # Andrea Verdi, ID 3 (Delegato)

    if rossi and bianchi and verdi:
        # Associazione Bianchi a Rossi (Dovrebbe essere già fatta)
        if bianchi.id_dirigente != rossi.id:
            bianchi.id_dirigente = rossi.id
            db.session.add(bianchi)
            
        # *** ASSOCIAZIONE DI VERDI A ROSSI (NUOVA) ***
        if verdi.id_dirigente != rossi.id:
            verdi.id_dirigente = rossi.id
            db.session.add(verdi)
        # **********************************************
        
        db.session.commit()
        
        return f"""
            <h1>Configurazione Iniziale Completata</h1>
            <p>✅ ASSEGNAZIONE RIUSCITA DEFINITIVA: Mario Rossi (ID: {rossi.id}) assegnato a Luigi Bianchi (ID: {bianchi.id}). VERIFICA: id_dirigente è ora {rossi.id}</p>
            <p>✅ NUOVA ASSOCIAZIONE RIUSCITA: Mario Rossi (ID: {rossi.id}) assegnato a Andrea Verdi (ID: {verdi.id}). VERIFICA: id_dirigente è ora {rossi.id}</p>
            <p><a href="/">Torna alla Home</a></p>
        """
    
    return "Associazione Fallita o Utenti non trovati."


# app.py (Aggiungere la funzione qui)

from datetime import date, datetime # IMPORTANTE: Assicurati che datetime sia importato
# ...

@app.route('/gestisci_deleghe', methods=['GET', 'POST'])
@login_required
def gestisci_deleghe():
    # --- PREPARAZIONE DATI PER IL TEMPLATE (NECESSARI ANCHE IN CASO DI ERRORE POST) ---
    oggi = date.today()
    
    # 1. Inizializzazione del Form
    from forms import DelegaForm # Assicurati che il tuo form sia importato
    form = DelegaForm() 

    # 2. Dipendenti idonei a ricevere la delega (escludiamo se stesso)
    from models import Dipendente 
    potenziali_delegati = Dipendente.query.filter(Dipendente.id != current_user.id).all()
    
    # Popola il campo SelectField del form
    form.delegato_id.choices = [(d.id, f"{d.nome} {d.cognome} ({d.ruolo})") for d in potenziali_delegati]

    # 3. Query per Deleghe (Attive/Future e Scadute)
    from models import Delega 
    
    # Deleghe attive o future
    deleghe_attive = Delega.query.filter(
        Delega.id_delegante == current_user.id,
        (Delega.data_fine.is_(None) | (Delega.data_fine >= oggi))
    ).order_by(Delega.data_inizio.asc()).all()
    
    # Deleghe scadute
    deleghe_scadute = Delega.query.filter(
        Delega.id_delegante == current_user.id,
        Delega.data_fine < oggi
    ).order_by(Delega.data_fine.desc()).all()


    # --- LOGICA DI SICUREZZA e VALIDAZIONE ---
    if current_user.ruolo != 'Dirigente':
        flash('Accesso non autorizzato alla gestione delle deleghe.', 'danger')
        return redirect(url_for('mie_trasferte'))

    if form.validate_on_submit():
        # Creazione nuova Delega
        
        id_delegato = form.delegato_id.data
        data_inizio = form.data_inizio.data
        data_fine = form.data_fine.data
        
        # Controllo base: Data fine deve essere successiva o uguale a data inizio
        if data_fine and data_fine < data_inizio:
            flash('La data di fine delega non può precedere la data di inizio.', 'danger')
            # Non facciamo return, lasciamo che il template venga renderizzato con gli errori del form
        else:
            try:
                nuova_delega = Delega(
                    id_delegante=current_user.id,
                    id_delegato=id_delegato,
                    data_inizio=data_inizio,
                    data_fine=data_fine
                )
                
                db.session.add(nuova_delega)
                db.session.commit()
                flash('Nuova delega creata con successo.', 'success')
                return redirect(url_for('gestisci_deleghe'))

            except Exception as e:
                db.session.rollback()
                flash(f'Errore nel salvataggio della delega: {e}', 'danger')

    # --- RENDER TEMPLATE ---
    # Passiamo tutte le variabili necessarie
    return render_template('gestisci_deleghe.html', 
                            form=form, 
                            deleghe_attive=deleghe_attive, 
                            deleghe_scadute=deleghe_scadute,
                            oggi=oggi)

# ====================================================================
# ROTTE APPLICATIVE (TRASFERTE)
# ====================================================================

@app.route('/nuova_trasferta', methods=['GET', 'POST'])
@login_required
def nuova_trasferta():
    if current_user.ruolo not in ['Dipendente', 'Dirigente']:
        flash('Non sei autorizzato a richiedere trasferte.', 'danger')
        return redirect(url_for('index'))

    if current_user.ruolo == 'Dirigente':
        print(f"DEBUG INIZIO: ID UTENTE: {current_user.id}")
        print(f"DEBUG INIZIO: ID DIRIGENTE ASSEGNATO (DB): {current_user.id_dirigente}")
        # Questo ci dirà il valore ESATTO del campo,
        # che dovrebbe essere 1 per far scattare l'auto-approvazione.


    # Verifica che il dipendente abbia un dirigente assegnato prima di inviare
    if not current_user.id_dirigente:
        flash('Non puoi inviare una richiesta finché non ti è stato assegnato un dirigente responsabile.', 'warning')
        return redirect(url_for('index'))

    if request.method == 'POST':
        # 1. Estrazione dei dati dal form
        giorno_missione_str = request.form.get('giorno_missione')
        missione_presso = request.form.get('missione_presso')
        motivo_missione = request.form.get('motivo_missione') # <-- Campo aggiunto ora
        utilizzo_mezzo = request.form.get('utilizzo_mezzo')
        inizio_missione_ora_str = request.form.get('inizio_missione_ora')
        aut_extra_orario = request.form.get('aut_extra_orario')
        aut_timbratura_entrata_str = request.form.get('aut_timbratura_entrata')
        aut_timbratura_uscita_str = request.form.get('aut_timbratura_uscita')
        motivo_timbratura = request.form.get('motivo_timbratura')
        note_premissione = request.form.get('note_premissione')
        id_dirigente_richiesto = request.form.get('id_dirigente')

        # 1. Validazione dei campi obbligatori
        if not giorno_missione_str or not missione_presso:
            flash('Per favore, compila tutti i campi obbligatori.', 'danger')
            return redirect(url_for('nuova_trasferta'))

        # 1.1 VALIDAZIONE TIMBRATURA (Richiesta User)
        # Se c'è un orario di entrata O di uscita, il motivo è obbligatorio
        if (aut_timbratura_entrata_str or aut_timbratura_uscita_str) and not motivo_timbratura:
            flash("Attenzione: Se indichi un orario per la timbratura (entrata o uscita), devi obbligatoriamente compilare il campo 'Motivo Autorizzazione Timbratura'.", 'danger')
            return redirect(url_for('nuova_trasferta'))

        # 2. Conversione della data (CRUCIALE)
        try:
            # Converte la stringa nel formato YYYY-MM-DD in oggetto date
            data_missione = datetime.strptime(giorno_missione_str, '%Y-%m-%d').date()
            
            # 2.1 CONTROLLO RETROATTIVITÀ
            today = date.today()
            if data_missione < today:
                msg_retroattivo = "Questa trasferta si è svolta senza autorizzazione preventiva"
                flash("Attenzione: La data della missione è antecedente a oggi. Verra' segnalata come 'Svolta senza autorizzazione preventiva'.", 'warning')
                
                # Aggiungi la nota al campo note_premissione
                if note_premissione:
                    note_premissione += f"\n[{msg_retroattivo}]"
                else:
                    note_premissione = f"[{msg_retroattivo}]"
                    
        except ValueError:
            flash('Formato data non valido.', 'danger')
            return redirect(url_for('nuova_trasferta'))

        # 3. Conversione degli orari (CRUCIALE per db.Time)
        def converti_ora(ora_str):
            if ora_str:
                try:
                    # Assumiamo che il formato sia HH:MM (es. 09:30)
                    return datetime.strptime(ora_str, '%H:%M').time()
                except ValueError:
                    # Gestione dell'errore di formato ora se necessario
                    return None # O lanciare un errore
            return None
    
        # Eseguiamo le conversioni sui campi orari
        inizio_missione_ora = converti_ora(inizio_missione_ora_str)
        aut_timbratura_entrata = converti_ora(aut_timbratura_entrata_str)
        aut_timbratura_uscita = converti_ora(aut_timbratura_uscita_str)

        # =========================================================================
        # 3.5. LOGICA DI AUTO-APPROVAZIONE (Dirigente)
        # =========================================================================
        stato_iniziale = 'In attesa'
        id_approvatore_pre = current_user.id_dirigente # Default: il dirigente assegnato
        data_app = None
        final_flash_message = 'Richiesta di trasferta inviata con successo per l\'approvazione.'

        
        # AGGIUNGI QUESTI CONTROLLI DI DEBUG
        print(f"\n--- DEBUG CREAZIONE MISSIONE ---")
        print(f"Current User ID: {current_user.id}")
        print(f"Current User Ruolo: {current_user.ruolo}")
        print(f"Dirigente Assegnato (current_user.id_dirigente): {current_user.id_dirigente}")
        # ------------------------------------



        # === VERO O FALSO: Auto-approvazione? ===
        # Verifichiamo se l'utente è un Dirigente E se è il suo proprio dirigente responsabile.
        is_auto_approving_dirigente = (current_user.ruolo == 'Dirigente' and 
                                    current_user.id == current_user.id_dirigente)

        if is_auto_approving_dirigente:
            # Se il dirigente si sta auto-approvando
            stato_iniziale = 'Approvata'
            id_approvatore_pre = current_user.id_dirigente # L'approvatore pre è se stesso
            data_app = datetime.now()
            final_flash_message = 'Richiesta di trasferta creata e auto-approvata (Dirigente).'
            
            print(f"DEBUG: Auto-approvazione SCATTATA! Nuovo Stato: {stato_iniziale}") # VEDIAMO SE QUESTO SCATTA

        print(f"DEBUG: Valore finale id_approvatore_pre: {id_approvatore_pre}")
        print(f"DEBUG: Valore finale stato_pre_missione: {stato_iniziale}\n")



        # DEBUG CRITICO: Aggiungi un log server-side per confermare che questa sezione è stata raggiunta
        #print(f"DEBUG: Auto-approvazione scattata per utente ID: {current_user.id}") 

        # Se non è auto-approvazione, l'approvatore pre è già impostato a current_user.id_dirigente (default)
        # ========================================================================

        # 4. Creazione e Salvataggio dell'oggetto Trasferta
        try:
            nuova_trasferta = Trasferta(
                id_dipendente=current_user.id,
                # Utilizza id_approvatore (che è current_user.id in caso di auto-approvazione)
                # Se nel tuo modello 'id_dirigente' è il dirigente RESPONSABILE (e non l'approvatore pre):
                # * Se Dirigente, id_dirigente è se stesso.
                # * Se Dipendente, id_dirigente è il suo capo.
                id_dirigente=current_user.id_dirigente, # Mantieni il dirigente assegnato
                
                # USA LE VARIABILI CONDIZIONALI:
                stato_pre_missione=stato_iniziale,
                id_approvatore_pre=id_approvatore_pre, # Aggiungi questo campo per registrare chi ha approvato
                data_approvazione_pre=data_app, # Aggiungi questo campo per registrare la data di approvazione
                giorno_missione=data_missione,
                inizio_missione_ora=inizio_missione_ora,
                missione_presso=missione_presso,
                motivo_missione=motivo_missione,
                utilizzo_mezzo=utilizzo_mezzo,
                aut_extra_orario=aut_extra_orario,
                aut_timbratura_entrata=aut_timbratura_entrata,
                aut_timbratura_uscita=aut_timbratura_uscita,
                motivo_timbratura=motivo_timbratura,
                note_premissione=note_premissione,
            )
            
            db.session.add(nuova_trasferta)
            db.session.commit()
            
            # USA IL MESSAGGIO CONDIZIONALE
            flash(final_flash_message, 'success') 
            
            return redirect(url_for('mie_trasferte'))
            
        except Exception as e:
            db.session.rollback()
            # Questo era l'errore precedente ('motivo_missione' is an invalid keyword argument)
            # Ora dovrebbe gestire altri errori di DB
            flash(f"Errore sconosciuto durante l'invio: {e}", 'danger')
            
    # GET request
    return render_template('nuova_trasferta.html')


@app.route('/modifica_trasferta/<int:trasferta_id>', methods=['GET', 'POST'])
@login_required
def modifica_trasferta(trasferta_id):
    trasferta = Trasferta.query.get_or_404(trasferta_id)
    
    # Check ownership and state
    if trasferta.id_dipendente != current_user.id:
        flash('Non puoi modificare una trasferta che non ti appartiene.', 'danger')
        return redirect(url_for('mie_trasferte'))
        
    if trasferta.stato_pre_missione not in ['In attesa', 'In Attesa']:
        flash(f'Impossibile modificare: la missione è già in stato {trasferta.stato_pre_missione}.', 'danger')
        return redirect(url_for('mie_trasferte'))

    if request.method == 'POST':
        # 1. Estrazione form (similar logic to nuova_trasferta)
        giorno_missione_str = request.form.get('giorno_missione')
        missione_presso = request.form.get('missione_presso')
        motivo_missione = request.form.get('motivo_missione')
        utilizzo_mezzo = request.form.get('utilizzo_mezzo')
        inizio_missione_ora_str = request.form.get('inizio_missione_ora')
        aut_extra_orario = request.form.get('aut_extra_orario')
        aut_timbratura_entrata_str = request.form.get('aut_timbratura_entrata')
        aut_timbratura_uscita_str = request.form.get('aut_timbratura_uscita')
        motivo_timbratura = request.form.get('motivo_timbratura')
        note_premissione = request.form.get('note_premissione')

        # Validation
        if not giorno_missione_str or not missione_presso:
            flash('Compila i campi obbligatori.', 'danger')
            return render_template('nuova_trasferta.html', trasferta=trasferta)

        try:
            # Update fields
            trasferta.giorno_missione = datetime.strptime(giorno_missione_str, '%Y-%m-%d').date()
            trasferta.missione_presso = missione_presso
            trasferta.motivo_missione = motivo_missione
            trasferta.utilizzo_mezzo = utilizzo_mezzo
            trasferta.extra_orario = aut_extra_orario
            trasferta.note_premissione = note_premissione
            trasferta.motivo_autorizzazione_timbratura = motivo_timbratura
            
            # Helper for time
            def convert_time(t_str):
                return datetime.strptime(t_str, '%H:%M').time() if t_str else None
                
            if inizio_missione_ora_str:
                 trasferta.inizio_missione_ora = convert_time(inizio_missione_ora_str)
            
            trasferta.aut_timbratura_entrata = convert_time(aut_timbratura_entrata_str)
            trasferta.aut_timbratura_uscita = convert_time(aut_timbratura_uscita_str)
            
            db.session.commit()
            flash('Modifiche alla richiesta di trasferta salvate con successo.', 'success')
            return redirect(url_for('mie_trasferte'))
            
        except ValueError as e:
            flash(f'Errore nei dati: {e}', 'danger')
            return render_template('nuova_trasferta.html', trasferta=trasferta)

    return render_template('nuova_trasferta.html', trasferta=trasferta)

from datetime import date # Da assicurarsi che sia importato globalmente

# app.py
@app.route('/mie_trasferte')
@login_required
def mie_trasferte():
    from models import Delega, Dipendente, Trasferta, db
    from sqlalchemy import or_, and_, func
    
    trasferte_personali = []
    missioni_da_approvare = []
    
    # 1. TRASFERTE PERSONALI (Per tutti, incluso il Delegato)
    trasferte_personali = Trasferta.query.filter_by(id_dipendente=current_user.id).all()

    # 2. LOGICA DIRIGENTE/DELEGATO (IDENTIFICAZIONE DEGLI ID)
    ids_dirigenti_approvatori = []

    # A) L'utente è un Dirigente principale?
    if current_user.ruolo == 'Dirigente':
        ids_dirigenti_approvatori.append(current_user.id) 

    # B) L'utente è un Delegato attivo? (Usiamo la logica ORM robusta per l'identificazione)
    # Condizione 1: Delega permanente (data_fine è NULL)
    delega_permanente = Delega.query.filter(
        Delega.id_delegato == current_user.id,
        Delega.data_fine == None,
        Delega.data_inizio <= func.current_date()
    )
    
    # Condizione 2: Delega a tempo determinato e non scaduta
    delega_determinata = Delega.query.filter(
        Delega.id_delegato == current_user.id,
        Delega.data_fine != None,
        Delega.data_inizio <= func.current_date(),
        Delega.data_fine >= func.current_date()
    )
    
    active_delegations = delega_permanente.union(delega_determinata).all()
    
    if active_delegations:
        ids_dirigenti_approvatori.extend([d.id_delegante for d in active_delegations])
    
    ids_dirigenti_approvatori = list(set(ids_dirigenti_approvatori))

    # INIZIO BLOCCO DI DEBUG 1 (INCOLLA QUI)
    oggi = date.today()
    user_id = current_user.id
    is_verdi = (current_user.email == 'andrea.verdi@test.it')

    print("-" * 50)
    print(f"DEBUG UTENTE LOGGATO: ID={user_id}, Email={current_user.email}")
    print(f"DEBUG ID DIRIGENTI AUTORIZZATI: {ids_dirigenti_approvatori}")
    print(f"DEBUG DATA OGGI: {oggi}")

    if is_verdi and 2 not in ids_dirigenti_approvatori:
        print("ERRORE: La logica ORM per la Delega NON ha identificato Rossi (ID 2).")
    print("-" * 50)
    # FINE BLOCCO DI DEBUG 1


   # 3. CARICAMENTO DELLE MISSIONI DA APPROVARE (FILTRATE)
    if ids_dirigenti_approvatori:
        
        # 1. Condizione di Approvazione/Delega (id_dirigente deve essere nella lista degli ID coperti)
        condizione_approvatore = Trasferta.id_dirigente.in_(ids_dirigenti_approvatori)
        
        # 2. Condizioni di Stato: TUTTI gli stati che un dirigente/delegato deve vedere
        condizione_stati = or_(
            # Missioni in attesa (AZIONI PENDENTI)
            Trasferta.stato_pre_missione == 'In attesa',
            Trasferta.stato_post_missione == 'In attesa',
            
            # Storico Pre-missione (già Approvate o Rifiutate)
            Trasferta.stato_pre_missione == 'Approvata',
            Trasferta.stato_pre_missione == 'Rifiutata',
            
            # Storico Post-missione (già concluse/decise)
            Trasferta.stato_post_missione == 'Da rimborsare', # Stato di rendicontazione Approvata (ma non ancora pagata)
            Trasferta.stato_post_missione == 'Rimborso Concesso',
            Trasferta.stato_post_missione == 'Rimborso negato'
        )
        
        # Esegui la query combinata: Solo le missioni di cui l'utente è Dirigente/Delegato, 
        # che sono in uno degli stati di interesse (pendenti O concluse)
        missioni_da_approvare = Trasferta.query.filter(
            condizione_approvatore,
            condizione_stati
        ).all()

    # DEBUG FINALE: La missione è stata trovata?
    print(f"DEBUG SQL QUERY (Final ORM con Storico): Trovate {len(missioni_da_approvare)} missioni.")
    # ...

    # 4. CARICAMENTO MISSIONI DA APPROVARE PER L'AMMINISTRAZIONE
    missioni_da_approvare_finale = []
    if current_user.ruolo == 'Amministrazione':
        missioni_da_approvare_finale = Trasferta.query.filter(
            Trasferta.stato_post_missione == 'Pronto per Rimborso'
        ).order_by(Trasferta.data_approvazione_post).all()


    # 5. UNIONE DEI RISULTATI
    # Uniamo temporaneamente le due liste (qui si hanno i duplicati)
    trasferte_combinate = trasferte_personali + missioni_da_approvare
        
    # Rimuoviamo i duplicati basandoci sull'ID della missione (la chiave del dizionario)
    # Questo crea la lista finale UNICA che devi usare
    trasferte_uniche = list({t.id: t for t in trasferte_combinate}.values())
        
    # ORDINAMENTO CRONOLOGICO INVERSO (Più recente prima)
    trasferte_uniche.sort(key=lambda t: t.giorno_missione, reverse=True) 

    # Assegna la lista unica alla variabile finale usata nel codice successivo
    trasferte = trasferte_uniche 

    # DEBUG FINALE: La lista da passare al template contiene la missione da approvare?
    print("-" * 50)
    print(f"DEBUG MISSIONI TOTALI PASSATE AL TEMPLATE ({current_user.email}): {len(trasferte)} missioni")
    for t in trasferte:
        print(f"  ID: {t.id}, Richiedente: {t.richiedente.cognome}, Stato Pre: {t.stato_pre_missione}")
    print("-" * 50)

    # Esegui il render_template con la lista corretta:
    return render_template('mie_trasferte.html', 
                        trasferte=trasferte, # USA SOLO LA LISTA PULITA 'trasferte'
                        ids_approvatori_autorizzati=ids_dirigenti_approvatori,
                        missioni_da_approvare_finale=missioni_da_approvare_finale 
                        )





# --- ROTTA APPROVAZIONE ---
@app.route('/approva_trasferta/<int:trasferta_id>', methods=['POST'])
@login_required
def approva_trasferta(trasferta_id):
    trasferta = Trasferta.query.get_or_404(trasferta_id)

    # 1. Recupero i dati inviati dal MODALE
    azione = request.form.get('azione') # 'approva' o 'rifiuta'
    commento = request.form.get('commento') # Le note del dirigente

    # *** CONTROLLO AUTORIZZATIVO ***
    # Assumendo che 'is_authorized_approver' sia definita altrove
    if not is_authorized_approver(trasferta):
        flash('Non sei autorizzato ad approvare/rifiutare questa richiesta.', 'danger')
        return redirect(url_for('mie_trasferte'))
    # **********************************************
    
    if trasferta.stato_pre_missione != 'In attesa':
        flash('La trasferta è già stata processata.', 'warning')
        return redirect(url_for('mie_trasferte'))
        
    # 2. LOGICA DI APPROVAZIONE O RIFIUTO
    if azione == 'approva':
        trasferta.stato_pre_missione = 'Approvata'
        flash_msg = f'Trasferta di {trasferta.richiedente.nome} approvata con successo.'
        flash_category = 'success'
        
    elif azione == 'rifiuta':
        trasferta.stato_pre_missione = 'Rifiutata'
        flash_msg = f'Trasferta di {trasferta.richiedente.nome} rifiutata.'
        flash_category = 'warning'
        
    else:
        # Azione non riconosciuta
        flash('Azione non valida.', 'danger')
        return redirect(url_for('mie_trasferte'))

    # 3. AGGIORNAMENTO DEI CAMPI DI TRACCIAMENTO
    trasferta.data_approvazione_pre = datetime.now()
    trasferta.id_approvatore_pre = current_user.id 
    trasferta.note_premissione = commento # Salvo il commento nel campo esistente

    try:
        db.session.commit()
        flash(flash_msg, flash_category)
    except Exception as e:
        db.session.rollback()
        flash(f"Errore durante il salvataggio: {e}", 'danger')

    return redirect(url_for('mie_trasferte'))
        






@app.route('/rendiconta_trasferta/<int:trasferta_id>', methods=['GET', 'POST'])
@login_required
def rendiconta_trasferta(trasferta_id):
    # Definizione delle funzioni helper locali (o assicurati che siano globali/importate)
    def safe_float(valore):
        try:
            return float(str(valore).replace(',', '.')) if valore else 0.0
        except ValueError:
            return 0.0
            
    def safe_int(valore):
        try:
            return int(valore) if valore else 0
        except ValueError:
            return 0
            
    trasferta = Trasferta.query.get_or_404(trasferta_id)

    # Controlli preliminari (utente corretto, missione approvata)
    if trasferta.id_dipendente != current_user.id or trasferta.stato_pre_missione != 'Approvata':
        flash('Non puoi rendicontare questa missione o non è nello stato corretto.', 'danger')
        return redirect(url_for('mie_trasferte'))

    # Se la rendicontazione è già stata inviata, si reindirizza (sebbene il GET sia utile per la visualizzazione)
    if trasferta.stato_post_missione == 'In attesa':
        flash(f'Rendicontazione già inviata ({trasferta.stato_post_missione}). Puoi comunque modificarla e reinviarla.', 'warning')
        # In questo caso, lasciamo che la logica POST gestisca il reinvio

    if request.method == 'POST':
        try:
            # --- 1. SALVATAGGIO DATI EFFETTIVI e LOGISTICA ---
            
            ora_inizio_str = request.form.get('ora_inizio_effettiva')
            ora_fine_str = request.form.get('ora_fine_effettiva')
            pausa_dalle_str = request.form.get('pausa_pranzo_dalle')
            pausa_alle_str = request.form.get('pausa_pranzo_alle')
            
            # Conversione Orari (gestione None/vuoto per i Time)
            ora_inizio = datetime.strptime(ora_inizio_str, '%H:%M').time() if ora_inizio_str else None
            ora_fine = datetime.strptime(ora_fine_str, '%H:%M').time() if ora_fine_str else None

            # Calcolo Durata Netta (basato solo sugli orari se la missione è giornaliera)
            durata_netta = timedelta(0)
            if ora_inizio and ora_fine:
                dt_inizio = datetime.combine(date.today(), ora_inizio)
                dt_fine = datetime.combine(date.today(), ora_fine)
                durata_netta = dt_fine - dt_inizio

                # Sottrazione Pausa Pranzo
                if pausa_dalle_str and pausa_alle_str:
                    dt_pausa_inizio = datetime.combine(date.today(), datetime.strptime(pausa_dalle_str, '%H:%M').time())
                    dt_pausa_fine = datetime.combine(date.today(), datetime.strptime(pausa_alle_str, '%H:%M').time())
                    pausa_pranzo_durata = dt_pausa_fine - dt_pausa_inizio
                    durata_netta -= pausa_pranzo_durata

                durata_totale_ore_int = int(durata_netta.total_seconds() / 3600)
                trasferta.durata_totale_ore = durata_totale_ore_int
            
            # AGGIORNAMENTO CAMPI TRASFERTA
            trasferta.ora_inizio_effettiva = ora_inizio
            trasferta.ora_fine_effettiva = ora_fine
            trasferta.km_percorsi = safe_float(request.form.get('km_percorsi'))
            trasferta.mezzo_km_percorsi = request.form.get('mezzo_km_percorsi')
            trasferta.note_rendicontazione = request.form.get('note_rendicontazione')
            
            # Salvataggio Durata Viaggio (usa i setter del Modello per convertire HH:MM -> min)
            trasferta.durata_viaggio_andata_str = request.form.get('durata_viaggio_andata')
            trasferta.durata_viaggio_ritorno_str = request.form.get('durata_viaggio_ritorno')
            
            # Dati Pausa e Extra Orario
            trasferta.pausa_pranzo_dalle = datetime.strptime(pausa_dalle_str, '%H:%M').time() if pausa_dalle_str else None
            trasferta.pausa_pranzo_alle = datetime.strptime(pausa_alle_str, '%H:%M').time() if pausa_alle_str else None
            trasferta.richiesta_pausa_pranzo = request.form.get('richiesta_pausa_pranzo')
            trasferta.extra_orario = request.form.get('extra_orario')
            
            # --- 2. GESTIONE SPESE (Cancellazione e Reinserimento) ---
            
            # B. Gestione Spese:
            # Se il form contiene i dati delle spese (array), allora aggiorniamo (cancella e riscrivi).
            # Se il form NON contiene dati (es. invia da modale), preserviamo le spese esistenti.
            categorie = request.form.getlist('spesa_categoria[]')
            
            totale_spese = 0.0

            if categorie:
                # CI SONO NUOVI DATI: Cancelliamo le vecchie e inseriamo le nuove
                Spesa.query.filter_by(id_trasferta=trasferta_id).delete()
                
                descrizioni = request.form.getlist('spesa_descrizione[]')
                importi = request.form.getlist('spesa_importo[]')
                date_spesa = request.form.getlist('spesa_data[]')

                for i in range(len(categorie)):
                    # Validazione base: ignora righe vuote se necessario
                    if not categorie[i] or not importi[i]:
                        continue
                        
                    valore_importo = float(importi[i])
                    totale_spese += valore_importo
                    
                    # Gestione data (se presente o usa quella della missione)
                    data_s = trasferta.giorno_missione
                    if i < len(date_spesa) and date_spesa[i]:
                        try:
                            data_s = datetime.strptime(date_spesa[i], '%Y-%m-%d').date()
                        except ValueError:
                            pass # Mantieni default

                    nuova_spesa = Spesa(
                        id_trasferta=trasferta_id,
                        categoria=categorie[i],
                        descrizione=descrizioni[i] if i < len(descrizioni) else '',
                        importo=valore_importo,
                        data_spesa=data_s
                    )
                    db.session.add(nuova_spesa)
                
                # Commit necessario se abbiamo modificato le spese
                # (verrà fatto alla fin, ma è parte della logica di "scrittura")
            else:
                # NESSUN DATO SPESA RICEVUTO:
                # Calcoliamo il totale dalle spese ESISTENTI nel DB.
                spese_esistenti = Spesa.query.filter_by(id_trasferta=trasferta_id).all()
                for s in spese_esistenti:
                    totale_spese += s.importo
                
                print(f"DEBUG: Nessuna spesa ricevuta dal form. Spese preservate. Totale DB: {totale_spese}")
                
            # --- 3. LOGICA DI AUTO-APPROVAZIONE POST-MISSIONE E AGGIORNAMENTO STATO ---
            
            # Calcolo Totale Spese per la logica
            totale_spese = sum(s.importo for s in Spesa.query.filter_by(id_trasferta=trasferta_id).all())

            # Valori Default
            stato_post_finale = 'In attesa'
            final_flash_message = 'Rendicontazione (Dati e Spese) salvata e inviata con successo per l\'approvazione del rimborso.'
            
            # Condizione Auto-Approvazione
            if current_user.ruolo == 'Dirigente' and current_user.id == current_user.id_dirigente:
                if totale_spese > 0:
                    stato_post_finale = 'Pronta per rimborso'
                    final_flash_message = 'Rendiconto salvato e auto-approvato (Dirigente). Ora è pronto per il rimborso finanziario.'
                else:
                    stato_post_finale = 'Conclusa'
                    final_flash_message = 'Rendiconto salvato e auto-approvato (Dirigente). Nessuna spesa da rimborsare. Missione conclusa.'
                
                trasferta.id_approvatore_post = current_user.id
                trasferta.data_approvazione_post = datetime.now()

            # AGGIORNAMENTO STATO E COMMIT
            trasferta.stato_post_missione = stato_post_finale
            
            db.session.commit()
            flash(final_flash_message, 'success')
            return redirect(url_for('mie_trasferte'))

        except Exception as e:
            db.session.rollback()
            flash(f'Errore nel salvataggio della rendicontazione: {e}', 'danger')
            # Lascia la possibilità di riprovare nella stessa pagina (GET)

    # --- LOGICA GET (Visualizzazione) ---
    spese_esistenti = Spesa.query.filter_by(id_trasferta=trasferta_id).all()
    totale_spese = sum(spesa.importo for spesa in spese_esistenti)

    return render_template('rendiconta_trasferta.html', 
                           trasferta=trasferta, 
                           spese_esistenti=spese_esistenti,
                           totale_spese=totale_spese)


@app.route('/invia_rendiconto/<int:trasferta_id>', methods=['POST'])
@login_required
def invia_rendiconto(trasferta_id):
    trasferta = Trasferta.query.get_or_404(trasferta_id)
    # ... (Controlli di autorizzazione) ...

    try:
        # --- 1. SALVATAGGIO DATI EFFETTIVI (già fatto) ---
        # ... (Logica per salvare km, orari, pause, extra_orario) ...
        
        # --- 2. GESTIONE SPESE (NUOVA LOGICA) ---
        
        # B. Gestione Spese:
        # Se il form contiene i dati delle spese (array), allora aggiorniamo (cancella e riscrivi).
        # Se il form NON contiene dati (es. invia da modale), preserviamo le spese esistenti.
        categorie = request.form.getlist('spesa_categoria[]')
        
        totale_spese = 0.0

        if categorie:
            # CI SONO NUOVI DATI: Cancelliamo le vecchie e inseriamo le nuove
            Spesa.query.filter_by(id_trasferta=trasferta_id).delete()
            db.session.flush()
            
            descrizioni = request.form.getlist('spesa_descrizione[]')
            importi = request.form.getlist('spesa_importo[]')
            date_spesa = request.form.getlist('spesa_data[]')
            
            if len(categorie) != len(importi):
                raise Exception("Dati spesa non allineati.")

            for i in range(len(categorie)):
                # Validazione base: ignora righe vuote se necessario
                if not categorie[i] or not importi[i]:
                    continue
                    
                valore_importo = float(importi[i])
                totale_spese += valore_importo
                
                # Gestione data (se presente o usa quella della missione)
                data_s = trasferta.giorno_missione
                if i < len(date_spesa) and date_spesa[i]:
                    try:
                        data_s = datetime.strptime(date_spesa[i], '%Y-%m-%d').date()
                    except ValueError:
                        pass # Mantieni default

                nuova_spesa = Spesa(
                    id_trasferta=trasferta_id,
                    categoria=categorie[i],
                    descrizione=descrizioni[i] if i < len(descrizioni) else '',
                    importo=valore_importo,
                    data_spesa=data_s
                )
                db.session.add(nuova_spesa)
            
            # Commit necessario se abbiamo modificato le spese
            # (verrà fatto alla fine, ma è parte della logica di "scrittura")
        else:
            # NESSUN DATO SPESA RICEVUTO:
            # Calcoliamo il totale dalle spese ESISTENTI nel DB.
            spese_esistenti = Spesa.query.filter_by(id_trasferta=trasferta_id).all()
            for s in spese_esistenti:
                totale_spese += s.importo
            
        # ===================================================================================
        # --- 3. LOGICA DI AUTO-APPROVAZIONE POST-MISSIONE E AGGIORNAMENTO STATO ---
        # ===================================================================================
        
        # 3.1. Valori di default (per Dipendenti normali)
        stato_post_finale = 'In attesa'
        id_approvatore_post_finale = None
        data_app_post_finale = None
        final_flash_message = 'Rendiconto salvato e inviato con successo per l\'approvazione post-missione.'

        # 3.2. Condizione di Auto-Approvazione (Dirigente = Proprio Dirigente)
        is_auto_approving_dirigente = (
            current_user.ruolo == 'Dirigente' and 
            current_user.id == current_user.id_dirigente
        )

        if is_auto_approving_dirigente:
            # Sovrascrive i valori di default
            id_approvatore_post_finale = current_user.id
            data_app_post_finale = datetime.now()
            
            # NUOVO: Distinzione basata sulle spese
            if totale_spese > 0:
                stato_post_finale = 'Pronta per rimborso' 
                final_flash_message = 'Rendiconto salvato e auto-approvato (Dirigente). Ora è pronto per il rimborso finanziario.'
            else:
                stato_post_finale = 'Conclusa'
                final_flash_message = 'Rendiconto salvato e auto-approvato (Dirigente). Nessuna spesa da rimborsare. Missione conclusa.'

        # 3.3. Aggiornamento dei campi sulla Trasferta
        trasferta.stato_post_missione = stato_post_finale
        trasferta.id_approvatore_post = id_approvatore_post_finale
        trasferta.data_approvazione_post = data_app_post_finale

        # ===================================================================================

        db.session.commit()
        # Usa il messaggio condizionale
        flash(final_flash_message, 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Errore nel salvataggio del rendiconto e delle spese: {e}', 'danger')
    
    return redirect(url_for('mie_trasferte'))

@app.route('/approva_rendiconto/<int:trasferta_id>', methods=['POST'])
@login_required
def approva_rendiconto(trasferta_id):
    trasferta = Trasferta.query.get_or_404(trasferta_id)
    commento_dirigente = request.form.get('commento_approva')
    
    # ... (1. Verifica Autorizzazione & 2. Verifica Stato Corretto, rimangono invariati) ...
    
    # 3. Aggiorna lo stato e salva i dati
    trasferta.id_approvatore_post = current_user.id
    trasferta.data_approvazione_post = datetime.now()
    trasferta.note_approvazione_post = commento_dirigente
    
    # ==========================================================
    # LOGICA DI BIFORCAZIONE: CON SPESE VS. SENZA SPESE
    # ==========================================================
    
    # Controlla il conteggio delle spese direttamente dal modello Spesa
    numero_spese = db.session.query(func.count(Spesa.id)).filter(Spesa.id_trasferta == trasferta_id).scalar()

    if numero_spese > 0:
        # CASO 1: CI SONO SPESE DA RIMBORSARE (richiede Approvazione Amministrativa)
        trasferta.stato_post_missione = 'Pronta per rimborso'
        flash_message = 'Rendiconto approvato. Missione in attesa di Approvazione Finanziaria.'
    else:
        # CASO 2: NESSUNA SPESA (Trasferta a costo zero o solo indennità non rimborsabili qui)
        # Se non ci sono spese, l'iter di rimborso è concluso.
        trasferta.stato_post_missione = 'Conclusa'
        flash_message = 'Rendiconto approvato. Nessuna spesa da rimborsare. Missione conclusa.'

    try:
        db.session.commit()
        flash(flash_message, 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante l\'aggiornamento: {e}', 'danger')
        
    return redirect(url_for('mie_trasferte'))

# Funzione per il rifiuto del rendiconto (Fase Post)
@app.route('/rifiuta_rendiconto/<int:trasferta_id>', methods=['POST'])
@login_required
def rifiuta_rendiconto(trasferta_id):
    trasferta = Trasferta.query.get_or_404(trasferta_id)
    
    # Recupero il commento del Dirigente
    commento_dirigente = request.form.get('commento_rifiuta')

    # 1. VERIFICA AUTORIZZAZIONE
    if not is_authorized_approver(trasferta):
                flash('Accesso negato: Non sei autorizzato ad approvare il rendiconto per questa missione.', 'danger')
                return redirect(url_for('mie_trasferte'))

    # 2. VERIFICA STATO CORRETTO
    if trasferta.stato_post_missione != 'In attesa':
        flash(f'Impossibile rifiutare: il rendiconto non è in stato di attesa. Stato attuale: {trasferta.stato_post_missione}', 'danger')
        return redirect(url_for('mie_trasferte'))

    # 3. AGGIORNAMENTO STATO
    trasferta.stato_post_missione = 'Rifiutata post' # Ritorna al dipendente per la correzione
    trasferta.id_approvatore_post = current_user.id
    trasferta.data_approvazione_post = datetime.now() # O data di rifiuto

    # Salvataggio del commento (Motivo del rifiuto)
    trasferta.note_approvazione_post = commento_dirigente 

    try:
        db.session.commit()
        flash(f'Rendiconto della trasferta ID {trasferta_id} rifiutato. Lo stato è stato aggiornato a "Rifiutata post".', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante l\'aggiornamento dello stato: {e}', 'danger')
        
    return redirect(url_for('mie_trasferte'))

@app.route('/richiedi_rimborso/<int:trasferta_id>')
@login_required
def richiedi_rimborso(trasferta_id):
    trasferta = Trasferta.query.get_or_404(trasferta_id)
    
    # Verifica che sia il richiedente e che lo stato sia corretto
    if trasferta.id_dipendente != current_user.id or trasferta.stato_post_missione != 'Pronta per rimborso':
        flash('Non puoi richiedere il rimborso in questo stato o per questa missione.', 'danger')
        return redirect(url_for('mie_trasferte'))

    trasferta.stato_post_missione = 'Rimborso Richiesto'
    db.session.commit()
    
    flash('Richiesta di rimborso inviata con successo all\'ufficio finanziario.', 'success')
    return redirect(url_for('mie_trasferte'))


@app.route('/approva_rimborso_finale/<int:trasferta_id>', methods=['POST'])
@login_required
@amministrazione_required
def approva_rimborso_finale(trasferta_id):
    trasferta = Trasferta.query.get_or_404(trasferta_id)
    
    # Verifica che la trasferta sia nello stato corretto (cioè pronta per essere rimborsata)
    if trasferta.stato_post_missione != 'Pronta per rimborso':
         flash(f'Impossibile approvare: la missione non è nello stato corretto. Stato: {trasferta.stato_post_missione}', 'danger')
         return redirect(url_for('mie_trasferte')) # Reindirizza a una pagina della Amministrazione/Dashboard Finanziaria
    
    # Esegui l'approvazione finale
    trasferta.stato_approvazione_finale = 'Rimborsata'  # Importante per lo storico!
    trasferta.stato_post_missione = 'Rimborsata'
    trasferta.id_approvatore_finale = current_user.id
    trasferta.data_approvazione_finale = datetime.now()
    
    try:
        db.session.commit()
        flash('Rimborso confermato e missione conclusa con stato "Rimborsata".', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore nel salvataggio dell\'approvazione finale: {e}', 'danger')
        
    # Reindirizza alla dashboard corretta
    # Reindirizza alla dashboard corretta
    return redirect(url_for('dashboard_amministrazione'))

@app.route('/rifiuta_rimborso_finale/<int:trasferta_id>', methods=['POST'])
@login_required
@amministrazione_required
def rifiuta_rimborso_finale(trasferta_id):
    trasferta = Trasferta.query.get_or_404(trasferta_id)
    
    # Verifica stato
    if trasferta.stato_post_missione != 'Pronta per rimborso':
         flash(f'Impossibile rifiutare: la missione non è nello stato corretto. Stato: {trasferta.stato_post_missione}', 'danger')
         return redirect(url_for('dashboard_amministrazione'))
    
    # Esegui il rifiuto finale
    trasferta.stato_approvazione_finale = 'Non rimborsata' 
    trasferta.stato_post_missione = 'Non rimborsata'
    trasferta.id_approvatore_finale = current_user.id
    trasferta.data_approvazione_finale = datetime.now()
    
    try:
        db.session.commit()
        flash('Rimborso rifiutato. Stato missione impostato su "Non rimborsata".', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore nel rifiuto del rimborso: {e}', 'danger')
        
    return redirect(url_for('dashboard_amministrazione'))




@app.route('/rifiuta_rimborso/<int:trasferta_id>')
@login_required
def rifiuta_rimborso(trasferta_id):
    trasferta = Trasferta.query.get_or_404(trasferta_id)

    # *** CONTROLLO AGGIORNATO: DELEGATO INCLUSO ***
    if not is_authorized_approver(trasferta):
        flash('Non sei autorizzato a rifiutare questo rimborso.', 'danger')
        return redirect(url_for('mie_trasferte'))
    # **********************************************

    # 4. Controllo Stato (deve essere 'In attesa' di approvazione post-missione)
    if trasferta.stato_post_missione != 'In attesa':
        flash(f'La richiesta di rimborso è già stata processata (Stato: {trasferta.stato_post_missione}).', 'warning')
        return redirect(url_for('mie_trasferte'))

    # 5. Aggiornamento dello Stato e dei Campi di Tracciamento
    try:
        trasferta.stato_post_missione = 'Rimborso negato'
        trasferta.data_approvazione_post = datetime.now()
        trasferta.id_approvatore_post = current_user.id # L'approvatore può essere il Dirigente o il Delegato
        
        db.session.commit()
        flash(f'Rimborso della trasferta del giorno {trasferta.giorno_missione.strftime("%Y-%m-%d")} negato con successo.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f"Errore durante il rifiuto del rimborso: {e}", 'danger')

    return redirect(url_for('mie_trasferte'))


@app.route('/associa_dirigente', methods=['GET', 'POST'])
@login_required
# Utilizza il tuo decorator se definito: @ruolo_richiesto(['Amministrazione'])
def associa_dirigente():
    
    # Controllo di Sicurezza (ridondante se il decorator è attivo, ma utile)
    if current_user.ruolo != 'Superuser':
        flash('Accesso negato: solo il Superuser può gestire le associazioni.', 'danger')
        # Assicurati che 'dashboard' sia un endpoint valido
        return redirect(url_for('mie_trasferte')) 

    # --- CARICAMENTO DATI PER IL TEMPLATE (METODO GET) ---
    
    # 1. Dipendenti da listare e assegnare (tutti tranne Amministrazione)
    # Usiamo joinedload per caricare in modo efficiente il dirigente attuale (d.dirigente_responsabile)
    dipendenti = Dipendente.query.options(db.joinedload(Dipendente.dirigente_responsabile)).filter(
        Dipendente.ruolo != 'Amministrazione'
    ).order_by(Dipendente.cognome).all()
    
    # 2. Utenti che possono essere Dirigenti (Target della relazione)
    # Carichiamo anche l'Amministrazione in questa lista, se può approvare
    dirigenti = Dipendente.query.filter(
        Dipendente.ruolo.in_(['Dirigente', 'Amministrazione'])
    ).order_by(Dipendente.cognome).all()

    # ----------------------------------------------------------------------
    
    if request.method == 'POST':
        # 1. Ottieni e converti i dati dal form
        dipendente_id = request.form.get('dipendente_id', type=int) 
        dirigente_id_str = request.form.get('dirigente_id')
        
        dipendente = Dipendente.query.get(dipendente_id)
        
        # 2. Validazione base
        if not dipendente:
            flash('Dipendente selezionato non valido.', 'danger')
            return redirect(url_for('associa_dirigente'))
        
        dipendente_assegnato_nome = f"{dipendente.nome} {dipendente.cognome}" # Nome completo del sottoposto

        dirigente_nome = "Nessuno"
        
        # 3. Logica di Assegnazione/Rimozione
        if dirigente_id_str == '0':
            # Rimuovi l'assegnazione
            dipendente.id_dirigente = None
            # dirigente_nome è già "Nessuno"
        else:
            # Assegna un dirigente
            dirigente_id = int(dirigente_id_str)
            dirigente = Dipendente.query.get(dirigente_id)
            
            if dirigente:
                # Controllo anti-ciclico: un dipendente non può supervisionare sé stesso
                 
                # *** MODIFICA QUI: CONSENTI L'AUTO-ASSEGNAZIONE AI DIRIGENTI ***
                 # 1. L'ID del sottoposto è uguale all'ID del dirigente?
                is_self_assignment = (dipendente.id == dirigente.id)

                # 2. Se è auto-assegnazione, CONTROLLA IL RUOLO
                if is_self_assignment:
                    # Permetti l'auto-assegnazione SOLO se il sottoposto è un Dirigente
                    if dipendente.ruolo == 'Dirigente':
                        # Se è un Dirigente che si auto-assegna, permetti l'azione (Passa)
                        pass 
                    else:
                        # Se è un normale Dipendente che cerca di auto-assegnarsi, blocca
                        flash(f'Errore: {dipendente_assegnato_nome} non può essere il dirigente di sé stesso.', 'danger')
                        return redirect(url_for('associa_dirigente'))

                # Se non c'è stata interruzione, prosegui con l'assegnazione
                dipendente.id_dirigente = dirigente.id
                dirigente_nome = f"{dirigente.nome} {dirigente.cognome}" # Nome completo del dirigente
            else:
                flash('Dirigente selezionato non valido.', 'danger')
                return redirect(url_for('associa_dirigente'))

        # 4. Commit
        try:
            db.session.commit()
            flash(f'{dipendente_assegnato_nome} è stato assegnato al dirigente {dirigente_nome}.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Errore di database durante l\'assegnazione: {e}', 'danger')

        return redirect(url_for('associa_dirigente'))

    # ----------------------------------------------------------------------

    # Metodo GET: Rendering del template
    return render_template('associa_dirigente.html', 
                            dipendenti=dipendenti, 
                            dirigenti=dirigenti)



@app.route('/report_trasferta/<int:trasferta_id>')
@login_required
def report_trasferta(trasferta_id):
    # Usiamo joinedload per caricare in modo efficiente tutte le relazioni necessarie 
    # per il report (richiedente, approvatore pre, approvatore post)
    trasferta = db.session.execute(
        db.select(Trasferta)
        .filter_by(id=trasferta_id)
        .options(
            joinedload(Trasferta.richiedente),
            joinedload(Trasferta.approvatore_pre),
            joinedload(Trasferta.approvatore_post),
            selectinload(Trasferta.spese)
        )
    ).scalar_one_or_none()
    
    if trasferta is None:
        abort(404) # Missione non trovata

    # LOGICA DI AUTORIZZAZIONE (Già corretta)
    # L'utente deve essere il richiedente OPPURE un approvatore autorizzato
    if trasferta.id_dipendente != current_user.id and not is_authorized_approver(trasferta):
        flash('Accesso negato al report.', 'danger')
        return redirect(url_for('mie_trasferte'))

    # CONTROLLO STATO (Report disponibile solo a missione finalizzata)
    STATI_FINALIZZATI = [
        'Da rimborsare', 
        'Rimborso Concesso', 
        'Rimborso negato',
        'Rimborso Approvato e Liquidato', # <--- NUOVO STATO AGGIUNTO QUI
        'Pronta per rimborso', # <--- AGGIUNTO SU RICHIESTA UTENTE
        'Rimborsata',
        'Conclusa'
    ]
    
    if trasferta.stato_post_missione not in STATI_FINALIZZATI:
        flash('Report non disponibile finché la missione non è finalizzata (stato post-missione: {}).'.format(trasferta.stato_post_missione), 'warning')
        return redirect(url_for('mie_trasferte'))
        
    return render_template('report_trasferta.html', trasferta=trasferta)

@app.route('/get_dettagli_trasferta/<int:trasferta_id>')
@login_required
def get_dettagli_trasferta(trasferta_id):
    from models import Trasferta, Spesa # Assumi che Trasferta sia importato
    
    trasferta = Trasferta.query.get_or_404(trasferta_id)
    
    # 1. LOGICA PER I DETTAGLI DI APPROVAZIONE (ROSSI)
    
    # Se la missione è in uno stato post-missione che richiede approvazione (Rimborso Richiesto)
    # o è stata approvata post (Pronto per Rimborso), carichiamo i dati delle spese.
    stati_con_rendiconto = ['Pronta per rimborso', 'Rimborso Richiesto', 'Rimborso Concesso', 'Rimborso Negato', 'Rifiutato Post', 'Rifiutata post']
    
    if trasferta.stato_post_missione in stati_con_rendiconto:
        
        # Recupera tutte le spese associate
        spese = Spesa.query.filter_by(id_trasferta=trasferta_id).all()
        totale_spese = sum(spesa.importo for spesa in spese)
        
        # 🎯 Ritorna il template specifico per la visualizzazione/approvazione del RENDICONTO
        # (Qui dovresti usare il template che mostra la TABELLA delle SPESE)
        return render_template('_dettagli_modale_rendiconto.html', 
                               trasferta=trasferta, 
                               spese=spese, 
                               totale_spese=totale_spese)

    # 2. LOGICA PER L'APPROVAZIONE PRE-MISSIONE (o altri stati non rendicontati)
    elif trasferta.stato_pre_missione in ['In Attesa']: # Aggiungi altri stati pre-missione se necessario
        
        # 🎯 Ritorna il template specifico per la PRE-MISSIONE
        # (Qui non passiamo le spese, usiamo il template base)
        return render_template('_dettagli_modale_pre.html', trasferta=trasferta)
        
    # 3. FALLBACK
    else:
        # Se lo stato non è riconosciuto, potresti mostrare un messaggio di errore
        return f"<p class='text-danger'>Errore: Stato missione non gestito per la visualizzazione: {trasferta.stato_post_missione}</p>"

    




@app.route('/trasferta/<int:trasferta_id>/gestisci_spese', methods=['GET', 'POST'])
@login_required
# Il richiedente (Dirigente o Dipendente) deve poter accedere
def gestisci_spese(trasferta_id):
    trasferta = Trasferta.query.get_or_404(trasferta_id)
    
    # 1. Controllo di sicurezza e stato: Solo il richiedente può gestire le spese.
    # Inoltre, la missione deve essere stata Approvata (pre-missione) per poter procedere.
    if trasferta.id_dipendente != current_user.id:
        flash('Accesso negato: puoi gestire solo le tue richieste.', 'danger')
        return redirect(url_for('dashboard'))
    
    if trasferta.stato_pre_missione != 'Approvata':
        flash('Non puoi gestire le spese di una missione non ancora approvata (o già rifiutata).', 'warning')
        return redirect(url_for('dashboard'))

    # 2. Transizione di stato iniziale (solo se la rendicontazione è già stata chiusa)
    if trasferta.stato_post_missione in ['N/A', 'Compilata']: 
        # Assumiamo che se arriva qui, il rendiconto orario/km sia già stato chiuso.
        # Possiamo forzare lo stato 'Da rimborsare' se non lo è già.
        trasferta.stato_post_missione = 'Da rimborsare'
        db.session.commit()

    # --- METODO GET: Visualizza le spese esistenti e il form ---
    spese_esistenti = Spesa.query.filter_by(id_trasferta=trasferta_id).all()
    
    # Calcolo del totale
    totale_spese = sum(s.importo for s in spese_esistenti)

    if request.method == 'POST':
        # 3. Logica POST: Salva le nuove spese e aggiorna lo stato

        # Le spese sono inviate come liste di campi (es. spesa_categoria[], spesa_importo[], ecc.)
        categorie = request.form.getlist('spesa_categoria[]')
        importi_str = request.form.getlist('spesa_importo[]')
        date_str = request.form.getlist('spesa_data[]')
        descrizioni = request.form.getlist('spesa_descrizione[]')
        
        nuove_spese = []
        
        # Svuotiamo le spese esistenti per sovrascrivere o permettere la cancellazione
        # È più sicuro eliminare e ricreare che fare un update complesso riga per riga
        Spesa.query.filter_by(id_trasferta=trasferta_id).delete()
        
        try:
            for cat, imp_str, data_s_str, desc in zip(categorie, importi_str, date_str, descrizioni):
                # Pulizia e conversione dei dati
                imp = float(imp_str.replace(',', '.')) if imp_str else 0.0
                data_s = datetime.strptime(data_s_str, '%Y-%m-%d').date() if data_s_str else date.today()
                
                if imp > 0:
                    nuova_spesa = Spesa(
                        id_trasferta=trasferta_id,
                        categoria=cat,
                        descrizione=desc,
                        importo=imp,
                        data_spesa=data_s
                    )
                    nuove_spese.append(nuova_spesa)
                    db.session.add(nuova_spesa)
            
            # 4. Aggiornamento dello Stato Trasferta
            if len(nuove_spese) > 0:
                # Se ci sono spese, l'ultima transizione è "Rimborso Richiesto"
                trasferta.stato_post_missione = 'Rimborso Richiesto'
                trasferta.data_richiesta_rimborso = datetime.now()
                flash('Spese salvate. La richiesta di rimborso è stata inviata all\'Amministrazione.', 'success')
            else:
                # Se non ci sono spese (ma il dipendente ha salvato il form), chiudiamo la pratica
                trasferta.stato_post_missione = 'Rimborso Chiuso (Zero Spese)'
                trasferta.data_richiesta_rimborso = datetime.now()
                flash('Nessuna spesa dichiarata. Rendiconto post-missione chiuso.', 'info')

            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            flash(f'Errore durante il salvataggio delle spese: {e}', 'danger')

        return redirect(url_for('report_trasferta', trasferta_id=trasferta_id))

    # --- Ritorno GET ---
    return render_template('gestisci_spese.html', 
                           trasferta=trasferta, 
                           spese_esistenti=spese_esistenti,
                           totale_spese=totale_spese)


@app.route('/dashboard_amministrazione')
@login_required
@amministrazione_required # Proteggi l'accesso
def dashboard_amministrazione():
    from models import Trasferta # Assicurati che sia importato

    # 0. AUTO-MIGRAZIONE DATI LEGACY (Self-Healing)
    # Corregge eventuali vecchi stati 'Pronto per Rimborso' (maschile) in 'Pronta per rimborso' (femminile)
    legacy_updates_1 = Trasferta.query.filter_by(stato_post_missione='Pronto per Rimborso').update({'stato_post_missione': 'Pronta per rimborso'})
    # Corregge 'Rimborso Concesso' in 'Pronta per rimborso' per renderle processabili dall'admin
    legacy_updates_2 = Trasferta.query.filter_by(stato_post_missione='Rimborso Concesso').update({'stato_post_missione': 'Pronta per rimborso'})
    
    if legacy_updates_1 > 0 or legacy_updates_2 > 0:
        db.session.commit()
    
    # 1. Recupera solo le missioni che il Dipartimento Finanziario deve approvare
    # Solo "Pronto per Rimborso" deve apparire qui.
    trasferte_da_approvare = Trasferta.query.filter(
        Trasferta.stato_post_missione == 'Pronta per rimborso',
        Trasferta.stato_approvazione_finale == None
    ).order_by(Trasferta.giorno_missione.asc()).all()

    # 2. Recupera lo storico delle missioni GIA' approvate/processate
    trasferte_storico = Trasferta.query.filter(
        Trasferta.stato_approvazione_finale != None
    ).order_by(Trasferta.data_approvazione_finale.desc()).all()
    
    return render_template('dashboard_amministrazione.html', 
                           trasferte_da_approvare=trasferte_da_approvare,
                           trasferte_storico=trasferte_storico)


@app.route('/dashboard_superuser')
@login_required
@superuser_required
def dashboard_superuser():
    # Dashboard principale: solo menu di navigazione
    return render_template('dashboard_superuser.html')

@app.route('/dashboard_superuser/missioni')
@login_required
@superuser_required
def dashboard_superuser_missioni():
    from models import Trasferta
    trasferte = Trasferta.query.order_by(Trasferta.id.desc()).all()
    return render_template('dashboard_superuser_missioni.html', trasferte=trasferte)

# Compatibilità per URL errati/vecchi
@app.route('/dashboard_superuser_missioni')
@login_required
@superuser_required
def dashboard_superuser_missioni_legacy():
    return redirect(url_for('dashboard_superuser_missioni'))

@app.route('/dashboard_superuser/utenti')
@login_required
@superuser_required
def dashboard_superuser_utenti():
    from models import Dipendente
    dipendenti = Dipendente.query.order_by(Dipendente.cognome.asc()).all()
    return render_template('dashboard_superuser_utenti.html', dipendenti=dipendenti)


@app.route('/aggiorna_ruolo/<int:dipendente_id>', methods=['POST'])
@login_required
@superuser_required
def aggiorna_ruolo(dipendente_id):
    from models import Dipendente
    dipendente = Dipendente.query.get_or_404(dipendente_id)
    
    nuovo_ruolo = request.form.get('nuovo_ruolo')
    if nuovo_ruolo in ['Dipendente', 'Dirigente', 'Amministrazione', 'Presenze', 'Superuser']:
        dipendente.ruolo = nuovo_ruolo
        try:
            db.session.commit()
            flash(f'Ruolo di {dipendente.nome} {dipendente.cognome} aggiornato a {nuovo_ruolo}.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Errore durante l\'aggiornamento: {e}', 'danger')
    else:
        flash('Ruolo non valido.', 'warning')
        
    return redirect(url_for('dashboard_superuser_utenti')) # Correggo anche il redirect qui per tornare alla lista

@app.route('/admin_reset_password/<int:dipendente_id>', methods=['POST'])
@login_required
@superuser_required
def admin_reset_password(dipendente_id):
    from models import Dipendente
    dipendente = Dipendente.query.get_or_404(dipendente_id)
    
    nuova_password = request.form.get('nuova_password')
    
    if nuova_password and len(nuova_password) >= 4:
        dipendente.password_hash = generate_password_hash(nuova_password, method='scrypt')
        try:
            db.session.commit()
            flash(f'Password per {dipendente.nome} {dipendente.cognome} reimpostata con successo.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Errore durante il reset password: {e}', 'danger')
    else:
        flash('Password troppo corta o mancante.', 'warning')
        
    return redirect(url_for('dashboard_superuser_utenti'))


@app.route('/dettagli_trasferta/<int:trasferta_id>')
@login_required
def dettagli_trasferta(trasferta_id):
    trasferta = Trasferta.query.get_or_404(trasferta_id)
    
    # Controllo di Sicurezza (chi può vedere i dettagli?)
    # Solo il richiedente, il dirigente/delegato, l'Amministrazione O IL SUPERUSER.
    is_admin = current_user.ruolo == 'Amministrazione'
    is_superuser = current_user.ruolo == 'Superuser'
    is_approver = is_authorized_approver(trasferta) 
    is_requester = trasferta.id_dipendente == current_user.id
    
    if not (is_admin or is_superuser or is_approver or is_requester):
        flash('Accesso negato. Non sei autorizzato a visualizzare i dettagli di questa trasferta.', 'danger')
        # Reindirizza alla dashboard Amministrazione se è un admin e non ha i permessi per altro
        if is_admin:
             return redirect(url_for('dashboard_amministrazione'))
        return redirect(url_for('mie_trasferte'))

    # Se l'utente ha i permessi, recuperiamo le spese (tramite la relazione ORM)
    spese_associate = trasferta.spese # Accede alla collezione di Spese collegate
    
    # Calcolo del totale (utile per l'Amministrazione)
    totale_rimborso = sum(spesa.importo for spesa in spese_associate)
    
    return render_template('dettagli_trasferta.html', 
                           trasferta=trasferta, 
                           spese=spese_associate,
                           totale_rimborso=totale_rimborso)


@app.route('/export_csv_presenze')
@presenze_required
def export_csv_presenze():
    import csv
    import io
    from flask import make_response

    # Recupera tutte le trasferte con relazioni caricate per performance
    trasferte = Trasferta.query.options(
        joinedload(Trasferta.richiedente),
        joinedload(Trasferta.approvatore_pre),
        joinedload(Trasferta.approvatore_post),
        joinedload(Trasferta.spese)
    ).order_by(Trasferta.giorno_missione.desc()).all()

    # Setup CSV in memoria
    si = io.StringIO()
    cw = csv.writer(si, delimiter=';') # Usa punto e virgola per compatibilità Excel IT

    # Intestazioni Nuove ed Estese
    headers = [
        'ID', 
        'Dipendente', 
        'Data Missione', 
        'Destinazione', 
        'Motivazione',
        
        # Pre-Missione
        'Stato Pre-Missione',
        'Ora Inizio Prevista',
        'Mezzo Previsto',
        'Aut. Extra Orario (Pre)',
        'Timbratura Entrata Aut.',
        'Timbratura Uscita Aut.',
        'Motivo Timbratura',
        'Note Pre-Missione',
        'Approvatore Pre',
        'Data Approvazione Pre',

        # Post-Missione / Rendiconto
        'Stato Post-Missione',
        'Ora Inizio Effettiva', 
        'Ora Fine Effettiva',
        'Durata Totale (Ore)',
        'Pernotto',
        'Durata Viaggio A (min)',
        'Durata Viaggio R (min)',
        'Km Percorsi',
        'Mezzo Utilizzato',
        'Percorso Effettuato',
        'Gestione Pausa Pranzo',
        'Pausa Pranzo Dalle',
        'Pausa Pranzo Alle',
        'Gestione Extra Orario',
        'Note Rendicontazione',
        'Approvatore Post',
        'Data Approvazione Post',
        
        # Presenze Check
        'Gestito Presenze', 
        'NBP',

        # Spese
        'Costo Totale Spese',
        'Dettaglio Spese'
    ]
    cw.writerow(headers)

    # Dati
    for t in trasferte:
        # --- Dipendente ---
        nome_dipendente = "N/D"
        if t.richiedente:
            nome_dipendente = f"{t.richiedente.nome} {t.richiedente.cognome}"
            
        data_ms = t.giorno_missione.strftime('%d/%m/%Y') if t.giorno_missione else ""
        
        # --- Pre Missione helper ---
        ora_inizio_prev = t.inizio_missione_ora.strftime('%H:%M') if t.inizio_missione_ora else ""
        timb_in = t.aut_timbratura_entrata.strftime('%H:%M') if t.aut_timbratura_entrata else ""
        timb_out = t.aut_timbratura_uscita.strftime('%H:%M') if t.aut_timbratura_uscita else ""
        
        app_pre_nome = f"{t.approvatore_pre.nome} {t.approvatore_pre.cognome}" if t.approvatore_pre else ""
        dt_app_pre = t.data_approvazione_pre.strftime('%d/%m/%Y %H:%M') if t.data_approvazione_pre else ""

        # --- Post Missione helper ---
        ora_inizio_eff = t.ora_inizio_effettiva.strftime('%H:%M') if t.ora_inizio_effettiva else ""
        ora_fine_eff = t.ora_fine_effettiva.strftime('%H:%M') if t.ora_fine_effettiva else ""
        
        pp_dalle = t.pausa_pranzo_dalle.strftime('%H:%M') if t.pausa_pranzo_dalle else ""
        pp_alle = t.pausa_pranzo_alle.strftime('%H:%M') if t.pausa_pranzo_alle else ""
        
        # Note rendiconto pulite da newline
        note_rend = t.note_rendicontazione.replace('\n', ' | ').replace('\r', '') if t.note_rendicontazione else ""
        
        app_post_nome = f"{t.approvatore_post.nome} {t.approvatore_post.cognome}" if t.approvatore_post else ""
        dt_app_post = t.data_approvazione_post.strftime('%d/%m/%Y %H:%M') if t.data_approvazione_post else ""

        # --- Spese ---
        costo_totale = 0.0
        dettaglio_spese_list = []
        if t.spese:
            for s in t.spese:
                if s.importo:
                    costo_totale += s.importo
                    d_spesa = s.data_spesa.strftime('%d/%m/%Y') if s.data_spesa else ""
                    dettaglio_spese_list.append(f"[{d_spesa} - {s.categoria} - {s.importo:.2f}€ - {s.descrizione or ''}]")
        
        dettaglio_spese_str = " | ".join(dettaglio_spese_list)

        row = [
            t.id,
            nome_dipendente,
            data_ms,
            t.missione_presso or "",
            t.motivo_missione or "",
            
            # Pre
            t.stato_pre_missione or "",
            ora_inizio_prev,
            t.utilizzo_mezzo or "",
            t.aut_extra_orario or "",
            timb_in,
            timb_out,
            t.motivo_timbratura or "",
            t.note_premissione or "",
            app_pre_nome,
            dt_app_pre,

            # Post
            t.stato_post_missione or "N/A",
            ora_inizio_eff,
            ora_fine_eff,
            t.durata_totale_ore or "",
            'SI' if t.pernotto else 'NO',
            t.durata_viaggio_andata_min or "",
            t.durata_viaggio_ritorno_min or "",
            t.km_percorsi or "",
            t.mezzo_km_percorsi or "",
            t.percorso_effettuato or "",
            t.richiesta_pausa_pranzo or "",
            pp_dalle,
            pp_alle,
            t.extra_orario or "",
            note_rend,
            app_post_nome,
            dt_app_post,

            # Presenze
            'SI' if t.gestito_presenze else 'NO',
            'SI' if t.nbp else 'NO',

            # Spese
            f"{costo_totale:.2f}".replace('.', ','),
            dettaglio_spese_str
        ]
        cw.writerow(row)

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=export_missioni_completo.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8-sig" # UTF-8 con BOM per Excel
    return output

# =========================================================================================
# DASHBOARD PRESENZE
# =========================================================================================
@app.route('/dashboard_presenze')
@login_required
@presenze_required
def dashboard_presenze():
    # Recupera tutte le missioni ordinate per data decrescente
    trasferte = Trasferta.query.order_by(Trasferta.giorno_missione.desc()).all()
    return render_template('dashboard_presenze.html', trasferte=trasferte)

@app.route('/api/update_presenze_status', methods=['POST'])
@login_required
@presenze_required
def update_presenze_status():
    data = request.get_json()
    trasferta_id = data.get('trasferta_id')
    field = data.get('field')
    value = data.get('value')

    if not all([trasferta_id, field]):
        return jsonify({'error': 'Dati mancanti'}), 400

    trasferta = Trasferta.query.get(trasferta_id)
    if not trasferta:
        return jsonify({'success': False, 'error': 'Trasferta non trovata'}), 404

    try:
        if field == 'gestito_presenze':
            trasferta.gestito_presenze = bool(value)
        elif field == 'nbp':
            trasferta.nbp = bool(value)
        else:
            return jsonify({'success': False, 'error': 'Campo non valido'}), 400

        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/superuser/modifica_stato_missione', methods=['POST'])
@login_required
@superuser_required
def superuser_modifica_stato_missione():
    trasferta_id = request.form.get('trasferta_id')
    nuovo_stato_pre = request.form.get('stato_pre_missione')
    nuovo_stato_post = request.form.get('stato_post_missione')

    if not trasferta_id:
        flash('ID Missione mancante.', 'danger')
        return redirect(url_for('dashboard_superuser'))

    trasferta = Trasferta.query.get(trasferta_id)
    if not trasferta:
        flash('Missione non trovata.', 'danger')
        return redirect(url_for('dashboard_superuser'))

    # Logica di aggiornamento
    vecchio_pre = trasferta.stato_pre_missione
    vecchio_post = trasferta.stato_post_missione
    
    trasferta.stato_pre_missione = nuovo_stato_pre
    trasferta.stato_post_missione = nuovo_stato_post
    
    # Opzionale: Aggiungi una nota automatica
    nota_audit = f"\n[SUPERUSER AUDIT {datetime.now().strftime('%Y-%m-%d %H:%M')}] Stati modificati manualmente da {current_user.nome} {current_user.cognome}. Pre: {vecchio_pre}->{nuovo_stato_pre}, Post: {vecchio_post}->{nuovo_stato_post}."
    if trasferta.note_premissione:
        trasferta.note_premissione += nota_audit
    else:
        trasferta.note_premissione = nota_audit

    try:
        db.session.commit()
        flash(f'Stati missione #{trasferta.id} aggiornati con successo. (Pre: {nuovo_stato_pre}, Post: {nuovo_stato_post})', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore aggiornamento stati: {e}', 'danger')

    return redirect(url_for('dashboard_superuser_missioni'))

if __name__ == '__main__':
    # Rimuovi questa riga se usi 'flask run'
    app.run(debug=True)
    pass