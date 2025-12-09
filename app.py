from flask import Flask, render_template, request, url_for, redirect, flash
from models import db, Dipendente, Trasferta, Delegato # Assicurati di importare tutti i modelli
from flask_login import LoginManager, login_user, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_login import current_user, login_required

# --- Configurazione Base ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'la_tua_chiave_segreta_e_complessa' # Fondamentale per la sicurezza
# Configura il database SQLite (il file si chiamerà app.db)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inizializza i moduli
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # La funzione a cui reindirizzare se non loggato

# --- Funzioni di Login Manager ---
@login_manager.user_loader
def load_user(user_id):
    # Questa funzione recupera l'utente corrente dalla sessione
    return Dipendente.query.get(int(user_id))

# --- Istruzioni per la creazione del database ---
def create_db():
    with app.app_context():
        # Crea tutte le tabelle definite nei models.py
        db.create_all()
        print("Database 'app.db' creato con successo.")

# --- Route Principale (Aggiungeremo qui il resto del codice) ---
@app.route('/')
def index():
    # TEST DI RICONOSCIMENTO DEL FILE
    print("--- DEBUG: LA NUOVA FUNZIONE INDEX È STATA ESEGUITA ---") 
    return render_template('index.html')

# Rotta per creare il DB
@app.route('/create_db')
def db_creator():
    create_db()
    return "Database creato! Ora puoi inserire i dati iniziali."

# --- ROTTE DI AUTENTICAZIONE ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index')) # Se già loggato, reindirizza alla homepage

    if request.method == 'POST':
        # 1. Recupera i dati dal form
        nome = request.form.get('nome')
        email = request.form.get('email')
        password = request.form.get('password')
        ruolo = request.form.get('ruolo') or 'Dipendente' # Default a Dipendente

        # 2. Controllo Email e Hashing
        user = Dipendente.query.filter_by(email=email).first()
        if user:
            flash('Email già registrata. Accedi o usa un\'altra email.', 'danger')
            return redirect(url_for('register'))
        
        # Genera l'hash della password (sicurezza fondamentale)
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        # 3. Creazione del nuovo utente (Modello Dipendente)
        new_user = Dipendente(
            nome=nome, 
            email=email, 
            password_hash=hashed_password, 
            ruolo=ruolo
        )
        
        # Nota: L'assegnazione di ID_Dirigente_Resp avverrà dopo la registrazione,
        # in un pannello di amministrazione, per semplicità.

        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Account creato con successo! Effettua il login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Errore durante la creazione dell\'account: {e}', 'danger')


    # Se è GET, restituisce il template HTML
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index')) # Se già loggato, reindirizza alla homepage

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # 1. Trova l'utente per email
        user = Dipendente.query.filter_by(email=email).first()

        # 2. Verifica la password
        if user and check_password_hash(user.password_hash, password):
            # Login riuscito!
            login_user(user) # Imposta l'utente nella sessione
            flash(f'Accesso riuscito. Benvenuto, {user.nome}!', 'success')
            # Reindirizzamento alla homepage o alla dashboard
            return redirect(url_for('index')) 
        else:
            # Login fallito
            flash('Accesso fallito. Controlla email e password.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
@login_required # Richiede che l'utente sia loggato per eseguire il logout
def logout():
    logout_user()
    flash('Sei stato disconnesso.', 'info')
    return redirect(url_for('login'))


@app.route('/assegna_dirigenti')
# @login_required # Non lo mettiamo ancora per semplicità di test
def assegna_dirigenti():
    with app.app_context():
        
        # 1. Trova l'ID dell'utente che sarà il dirigente (Mario Rossi)
        # Supponiamo che l'email del dirigente sia mario.rossi@azienda.it
        dirigente_mario = Dipendente.query.filter_by(email='mario.rossi@azienda.it', ruolo='Dirigente').first()
        
        if not dirigente_mario:
            return "Errore: Dirigente 'Mario Rossi' non trovato. Assicurati di averlo registrato con quell'email e ruolo."

        # 2. Trova l'utente che sarà il dipendente (Luigi Bianchi)
        # Supponiamo che l'email del dipendente sia luigi.bianchi@azienda.it
        dipendente_luigi = Dipendente.query.filter_by(email='luigi.bianchi@azienda.it', ruolo='Dipendente').first()

        if not dipendente_luigi:
            return "Errore: Dipendente 'Luigi Bianchi' non trovato. Assicurati di averlo registrato con quell'email e ruolo."

        # 3. Assegna l'ID del dirigente al dipendente
        dipendente_luigi.id_dirigente_resp = dirigente_mario.id
        
        try:
            db.session.commit()
            return f"Successo: {dipendente_luigi.nome} (ID: {dipendente_luigi.id}) ora è sottoposto di {dirigente_mario.nome} (ID: {dirigente_mario.id})."
        except Exception as e:
            db.session.rollback()
            return f"Errore durante l'assegnazione: {e}"


if __name__ == '__main__':
    # Esegui la funzione di creazione del database (opzionale, utile per test iniziali)
    # create_db() 
    app.run(debug=True)