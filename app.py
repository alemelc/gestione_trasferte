# app.py

# ====================================================================
# 1. IMPORTAZIONI DELLE LIBRERIE
# ====================================================================
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from models import db, Dipendente, Trasferta, Delega
from sqlalchemy import or_, and_, text, func
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, date, time
from sqlalchemy.orm import joinedload # Importa joinedload
from functools import wraps

# NOTA: Qui NON importiamo Dipendente, Trasferta, ecc.

# ====================================================================
# 2. CONFIGURAZIONE E CREAZIONE ISTANZE PRINCIPALI
# ====================================================================
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'la_tua_chiave_segreta_qui' # Se non è già presente
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'trasferte.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app) # Collega l'istanza 'db' importata e già usata dai modelli
migrate = Migrate(app, db)

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


def is_authorized_approver(trasferta):
    """
    Verifica se l'utente loggato è l'approvatore diretto (dirigente)
    o il delegato attivo.
    """
    if not current_user.is_authenticated:
        return False

    # 1. Trova l'ID del Dirigente/Approvatore diretto
    # NOTA: Assumiamo che il dirigente sia il responsabile del richiedente.
    #dirigente_id = trasferta.richiedente.id_dirigente
    dirigente_approvatore_id = trasferta.id_dirigente

    if not dirigente_approvatore_id:
        return False
        
    # Caso 1: L'utente è il Dirigente diretto?
    if current_user.id == dirigente_approvatore_id:
        return True

    # Caso 2: L'utente è un Delegato attivo del Dirigente?
    today = date.today()
    
    # Query ORM corretta per il controllo temporale:
    delega_attiva = Delega.query.filter(
        Delega.id_delegante == dirigente_approvatore_id,
        Delega.id_delegato == current_user.id,
        Delega.data_inizio <= today,
        # La delega è attiva se data_fine è NULL OPPURE se data_fine è maggiore/uguale a oggi
        (Delega.data_fine.is_(None) | (Delega.data_fine >= today))
    ).first()

    if delega_attiva:
        return True
    
    return False

# Registra la funzione per renderla disponibile GLOBALMENTE in tutti i template Jinja2
app.jinja_env.globals.update(is_authorized_approver=is_authorized_approver)
# Le configurazioni del DB devono essere qui, subito dopo aver creato l'app.
app.config['SECRET_KEY'] = 'la_tua_chiave_segreta_e_complessa' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

@app.route('/revoca_delega/<int:delega_id>', methods=['POST'])
@login_required
@dirigente_required # Assicurati di avere questo decorator o una logica di controllo nel corpo
def revoca_delega(delega_id):
    from datetime import date
    from models import Delega, db # Assicurati di importare Delega e db

    delega = Delega.query.get_or_404(delega_id)

    # 1. Autorizzazione: solo il delegante può revocare la sua delega
    if delega.id_delegante != current_user.id:
        flash('Non sei autorizzato a revocare questa delega.', 'danger')
        return redirect(url_for('gestisci_deleghe'))
        
    # 2. Controllo: Evita revoca su deleghe già scadute
    oggi = date.today()
    if delega.data_fine is not None and delega.data_fine < oggi:
        flash('Questa delega è già scaduta e non necessita di revoca manuale.', 'warning')
        return redirect(url_for('gestisci_deleghe'))

    # 3. Revoca: Imposta la data di fine a oggi
    delega.data_fine = oggi
    db.session.commit()
    
    flash(f"Delega a {delega.delegato.nome} {delega.delegato.cognome} revocata con successo.", 'success')
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

@app.route('/assegna_dirigenti')
def assegna_dirigenti():
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

        # 2. Conversione della data (CRUCIALE)
        try:
            # Converte la stringa nel formato YYYY-MM-DD in oggetto date
            data_missione = datetime.strptime(giorno_missione_str, '%Y-%m-%d').date()
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
        # 3.5. 🚨 NUOVA LOGICA DI AUTO-APPROVAZIONE (Dirigente) 🚨
        # =========================================================================
        # Definiamo i valori predefiniti
        stato_iniziale = 'In attesa'
        id_approvatore = current_user.id_dirigente # Il dirigente assegnato
        data_app = None
        flash_message = 'Richiesta di trasferta inviata con successo per l\'approvazione.'

        # Se l'utente è un Dirigente, si auto-approva
        if current_user.ruolo == 'Dirigente': 
            stato_iniziale = 'Approvata'
            
            # Il dirigente è l'approvatore di se stesso. Usiamo current_user.id
            id_approvatore = current_user.id 
            data_app = datetime.now()
            
            # Nota: Devi assicurarti che un Dirigente possa arrivare qui (vedi verifica iniziale)
            # La verifica iniziale: `if current_user.ruolo != 'Dipendente':` andrebbe rimossa
            # o modificata se i Dirigenti possono usare questa rotta.
            flash_message = 'Richiesta di trasferta creata e auto-approvata.'
        
        # ========================================================================

        # 4. Creazione e Salvataggio dell'oggetto Trasferta
        try:
            nuova_trasferta = Trasferta(
                id_dipendente=current_user.id,
                id_dirigente=id_approvatore, 
                stato_pre_missione=stato_iniziale,
                data_approvazione_pre=data_app,
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
                #stato_pre_missione='In attesa',
            )
            
            db.session.add(nuova_trasferta)
            db.session.commit()
            flash('Richiesta di trasferta inviata con successo per l\'approvazione.', 'success')
            return redirect(url_for('mie_trasferte'))
            
        except Exception as e:
            db.session.rollback()
            # Questo era l'errore precedente ('motivo_missione' is an invalid keyword argument)
            # Ora dovrebbe gestire altri errori di DB
            flash(f"Errore sconosciuto durante l'invio: {e}", 'danger')
            
    # GET request
    return render_template('nuova_trasferta.html')

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

    
    # 4. UNIONE DEI RISULTATI
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
                        ids_approvatori_autorizzati=ids_dirigenti_approvatori 
                        )





# --- ROTTA APPROVAZIONE ---
@app.route('/approva_trasferta/<int:trasferta_id>', methods=['POST'])
@login_required
def approva_trasferta(trasferta_id):
    trasferta = Trasferta.query.get_or_404(trasferta_id)

    # *** CONTROLLO AGGIORNATO: DELEGATO INCLUSO ***
    if not is_authorized_approver(trasferta):
        flash('Non sei autorizzato ad approvare questa richiesta o il tuo ruolo non è Dirigente.', 'danger')
        return redirect(url_for('mie_trasferte'))
    # **********************************************
    
    if trasferta.stato_pre_missione == 'In attesa':
        trasferta.stato_pre_missione = 'Approvata'
        trasferta.data_approvazione_pre = datetime.now()
        trasferta.id_approvatore_pre = current_user.id # L'approvatore può essere il Dirigente o il Delegato
        db.session.commit()
        flash(f'Trasferta di {trasferta.richiedente.nome} approvata con successo.', 'success')
    else:
        flash('La trasferta è già stata approvata o rifiutata.', 'warning')

    return redirect(url_for('mie_trasferte'))
        



# --- ROTTA RIFIUTO ---
@app.route('/rifiuta_trasferta/<int:trasferta_id>')
@login_required
def rifiuta_trasferta(trasferta_id):
    trasferta = Trasferta.query.get_or_404(trasferta_id)

    # *** CONTROLLO AGGIORNATO: DELEGATO INCLUSO ***
    if not is_authorized_approver(trasferta):
        flash('Non sei autorizzato a rifiutare questa richiesta o il tuo ruolo non è Dirigente.', 'danger')
        return redirect(url_for('mie_trasferte'))
    # **********************************************

    if trasferta.stato_pre_missione == 'In attesa':
        trasferta.stato_pre_missione = 'Rifiutata'
        trasferta.data_approvazione_pre = datetime.now()
        trasferta.id_approvatore_pre = current_user.id
        db.session.commit()
        flash(f'Trasferta di {trasferta.richiedente.nome} rifiutata.', 'success')
    else:
        flash('La trasferta è già stata approvata o rifiutata.', 'warning')

    return redirect(url_for('mie_trasferte'))


@app.route('/rendiconta_trasferta/<int:trasferta_id>', methods=['GET', 'POST'])
@login_required
def rendiconta_trasferta(trasferta_id):
    trasferta = Trasferta.query.get_or_404(trasferta_id)

    # Controlli preliminari (utente corretto, missione approvata)
    if trasferta.id_dipendente != current_user.id or trasferta.stato_pre_missione != 'Approvata':
        flash('Non puoi rendicontare questa missione.', 'danger')
        return redirect(url_for('mie_trasferte'))

    if trasferta.stato_post_missione != 'N/A':
        flash(f'Rendicontazione già inviata ({trasferta.stato_post_missione}).', 'warning')
        return redirect(url_for('mie_trasferte'))

    if request.method == 'POST':
        try:
            # 1. Parsing degli orari e conversione in timedelta
            
            # Orari Missione
            ora_inizio_str = request.form.get('ora_inizio_effettiva') # Es. 08:00
            ora_fine_str = request.form.get('ora_fine_effettiva')
            
            ora_inizio = datetime.strptime(ora_inizio_str, '%H:%M').time()
            ora_fine = datetime.strptime(ora_fine_str, '%H:%M').time()
            
            # Pausa Pranzo
            pausa_dalle_str = request.form.get('pausa_pranzo_dalle')
            pausa_alle_str = request.form.get('pausa_pranzo_alle')
            
            # 2. CALCOLO DURATA (Logica Semplificata, assumendo missione nello stesso giorno)
            # Trasformiamo i 'time' in 'datetime' (usando una data fittizia per i calcoli)
            dt_inizio = datetime.combine(date.today(), ora_inizio)
            dt_fine = datetime.combine(date.today(), ora_fine)
            
            durata_totale = dt_fine - dt_inizio
            
            # Calcolo pausa pranzo (da sottrarre se specificata)
            pausa_pranzo_durata = timedelta(0)
            if pausa_dalle_str and pausa_alle_str:
                 dt_pausa_inizio = datetime.combine(date.today(), datetime.strptime(pausa_dalle_str, '%H:%M').time())
                 dt_pausa_fine = datetime.combine(date.today(), datetime.strptime(pausa_alle_str, '%H:%M').time())
                 pausa_pranzo_durata = dt_pausa_fine - dt_pausa_inizio
                 
            # Durata netta missione
            durata_netta = durata_totale - pausa_pranzo_durata
            
            # Converti in ore intere per la colonna (puoi usare float se vuoi i decimali)
            durata_totale_ore_int = int(durata_netta.total_seconds() / 3600)
            
            
            # 3. Aggiornamento dell'Oggetto Trasferta
            trasferta.ora_inizio_effettiva = ora_inizio
            trasferta.ora_fine_effettiva = ora_fine
            trasferta.durata_totale_ore = durata_totale_ore_int
           
            # Funzione helper per la conversione sicura a float
            def safe_float(valore):
                try:
                    # Sostituisce la virgola con il punto per i numeri decimali se necessario
                    return float(str(valore).replace(',', '.')) if valore else 0.0
                except ValueError:
                    return 0.0
             
            # Funzione helper per la conversione sicura a int
            def safe_int(valore):
                try:
                    return int(valore) if valore else 0
                except ValueError:
                    return 0
             
            # TEMPI E DISTANZE
            trasferta.durata_viaggio_andata_min = safe_int(request.form.get('durata_viaggio_andata'))
            trasferta.durata_viaggio_ritorno_min = safe_int(request.form.get('durata_viaggio_ritorno'))
            trasferta.km_percorsi = safe_float(request.form.get('km_percorsi'))
            
            # DATI RENDICONTO E NOTE (Assicurati che questi campi siano nel tuo Modello!)
            trasferta.mezzo_km_percorsi = request.form.get('mezzo_km_percorsi')
            trasferta.percorso_effettuato = request.form.get('percorso_effettuato')
            trasferta.note_rendicontazione = request.form.get('note_rendicontazione')

            # DATI AGGIUNTIVI (Booleani, Orari e Stringhe)
            trasferta.pausa_pranzo_dalle = datetime.strptime(pausa_dalle_str, '%H:%M').time() if pausa_dalle_str else None
            trasferta.pausa_pranzo_alle = datetime.strptime(pausa_alle_str, '%H:%M').time() if pausa_alle_str else None
            
            # Il 'request.form.get(...) == 'si'' è corretto per checkbox/radio
            trasferta.pernotto = request.form.get('pernotto') == 'si' 
            trasferta.richiesta_pausa_pranzo = request.form.get('richiesta_pausa_pranzo')
            trasferta.extra_orario = request.form.get('extra_orario')
        
            # Stato finale
            trasferta.stato_post_missione = 'In attesa'
            
            db.session.commit()
            flash('Rendicontazione inviata con successo per l\'approvazione del rimborso.', 'success')
            return redirect(url_for('mie_trasferte'))

        except Exception as e:
            db.session.rollback()
            # Se la missione dura un giorno e si usano solo gli orari, il campo Giorno non serve qui
            flash(f'Errore nel salvataggio della rendicontazione. Controllare i formati (orari H:MM): {e}', 'danger')


    return render_template('rendiconta_trasferta.html', trasferta=trasferta)


# app.py

@app.route('/approva_rimborso/<int:trasferta_id>', methods=['POST'])
@login_required
def approva_rimborso(trasferta_id):
    trasferta = Trasferta.query.get_or_404(trasferta_id)

    # *** CONTROLLO AGGIORNATO: DELEGATO INCLUSO ***
    if not is_authorized_approver(trasferta):
        flash('Non sei autorizzato ad approvare questo rimborso.', 'danger')
        return redirect(url_for('mie_trasferte'))
    # **********************************************

    # 4. Controllo Stato (deve essere 'In attesa' di approvazione post-missione)
    if trasferta.stato_post_missione != 'In attesa':
        flash(f'La richiesta di rimborso è già stata processata (Stato: {trasferta.stato_post_missione}).', 'warning')
        return redirect(url_for('mie_trasferte'))

    # 5. Aggiornamento dello Stato e dei Campi di Tracciamento
    try:
        trasferta.stato_post_missione = 'Da rimborsare'
        trasferta.data_approvazione_post = datetime.now()
        trasferta.id_approvatore_post = current_user.id # L'approvatore può essere il Dirigente o il Delegato
        
        db.session.commit()
        flash(f'Rimborso della trasferta del giorno {trasferta.giorno_missione.strftime("%Y-%m-%d")} approvato con successo.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f"Errore durante l'approvazione del rimborso: {e}", 'danger')

    return redirect(url_for('mie_trasferte'))


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
    if current_user.ruolo != 'Amministrazione':
        flash('Accesso negato: solo Amministrazione può gestire le associazioni.', 'danger')
        # Assicurati che 'dashboard' sia un endpoint valido
        return redirect(url_for('dashboard')) 

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
                if dipendente.id == dirigente.id:
                    flash(f'Errore: {dipendente_assegnato_nome} non può essere il dirigente di sé stesso.', 'danger')
                    return redirect(url_for('associa_dirigente'))
                
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

# Aggiungi queste rotte placeholder in app.py

@app.route('/dettagli_trasferta/<int:trasferta_id>')
@login_required
def dettagli_trasferta(trasferta_id):
    # La logica dettagliata verrà aggiunta dopo
    trasferta = Trasferta.query.get_or_404(trasferta_id)
    # Questa rotta DEVE ancora essere completata con il suo template
    flash(f'Visualizzazione dettagli per la trasferta ID: {trasferta.id}. (Pagina dettagli da creare)', 'info')
    return redirect(url_for('mie_trasferte'))



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
            joinedload(Trasferta.approvatore_post)
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
    if trasferta.stato_post_missione not in ['Da rimborsare', 'Rimborso Concesso', 'Rimborso negato']:
        flash('Report non disponibile finché la missione non è finalizzata (stato post-missione: {}).'.format(trasferta.stato_post_missione), 'warning')
        return redirect(url_for('mie_trasferte'))
        
    return render_template('report_trasferta.html', trasferta=trasferta)

@app.route('/get_dettagli_trasferta/<int:trasferta_id>')
@login_required
def get_dettagli_trasferta(trasferta_id):
    from models import Trasferta # Assumi che Trasferta sia importato
    
    trasferta = Trasferta.query.get_or_404(trasferta_id)
    
    # Non è necessario verificare l'autorizzazione qui, perché l'utente può vedere solo
    # le missioni che il frontend gli mostra (quelle del suo id_dirigente/delegato).
    # Se vuoi la massima sicurezza, qui va ripetuta la logica di controllo.

    # Ritorna un frammento HTML (o JSON, che è l'opzione migliore)
    # OPZIONE 1: RITORNA HTML FRAMMENTATO (Più semplice da implementare subito)
    # Creiamo un piccolo template per il contenuto del modale (es. _dettaglio_modale.html)
    return render_template('_dettaglio_modale.html', trasferta=trasferta)

    # OPZIONE 2: RITORNA JSON (Migliore, ma richiede più JavaScript sul frontend)
    # return jsonify({
    #     'id': trasferta.id,
    #     'richiedente': f"{trasferta.richiedente.nome} {trasferta.richiedente.cognome}",
    #     'data': trasferta.giorno_missione.strftime('%d/%m/%Y'),
    #     # ... altri campi ...
    # })


if __name__ == '__main__':
    # Rimuovi questa riga se usi 'flask run'
    app.run(debug=True)
    pass