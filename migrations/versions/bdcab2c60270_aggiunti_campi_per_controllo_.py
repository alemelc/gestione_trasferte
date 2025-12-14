"""Aggiunti campi per controllo finanziario finale su spese sostenute

Revision ID: bdcab2c60270
Revises: ba5b690a8515
Create Date: 2025-12-14 21:39:12.155583

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bdcab2c60270'
down_revision = 'ba5b690a8515'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('trasferta', schema=None) as batch_op:
        # Aggiungi la colonna id_approvatore_finale
        batch_op.add_column(sa.Column('id_approvatore_finale', sa.Integer(), nullable=True))
        
        # Aggiungi la colonna data_approvazione_finale
        batch_op.add_column(sa.Column('data_approvazione_finale', sa.DateTime(), nullable=True))
        
        # Aggiungi il vincolo di Chiave Esterna (Foreign Key)
        # È essenziale dare un nome (fk_approvatore_finale_trasferta)
        batch_op.create_foreign_key(
            'fk_approvatore_finale_trasferta',  # NOME UNIVOCO
            'dipendente',                      # Nome della tabella di riferimento
            ['id_approvatore_finale'],         # Colonna locale
            ['id']                             # Colonna remota
        )


def downgrade():
    with op.batch_alter_table('trasferta', schema=None) as batch_op:
        # Rimuovi il vincolo
        batch_op.drop_constraint('fk_approvatore_finale_trasferta', type_='foreignkey')
        
        # Rimuovi le colonne
        batch_op.drop_column('data_approvazione_finale')
        batch_op.drop_column('id_approvatore_finale')

    # ### end Alembic commands ###
