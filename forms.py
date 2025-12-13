from flask_wtf import FlaskForm
from wtforms import SelectField, DateField, SubmitField
from wtforms.validators import DataRequired, Optional
#from wtforms.ext.dateutil.fields import DateField # Potrebbe essere necessario per la gestione delle date

class DelegaForm(FlaskForm):
    # L'opzione 'coerce=int' trasforma la scelta in intero per l'ID
    delegato_id = SelectField('Dipendente Delegato', coerce=int, validators=[DataRequired()])
    data_inizio = DateField('Data Inizio', format='%Y-%m-%d', validators=[DataRequired()])
    data_fine = DateField('Data Fine (Opzionale)', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('Crea Delega')