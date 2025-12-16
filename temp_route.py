
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
        # Reuse logic from nuova_trasferta mostly, but UPDATE instead of CREATE
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
            trasferta.giorno_missione = datetime.strptime(giorno_missione_str, '%Y-%m-%d').date()
            if request.form.get('inizio_missione_ora'):
                 trasferta.inizio_missione_ora = datetime.strptime(request.form.get('inizio_missione_ora'), '%H:%M').time()
            
            trasferta.missione_presso = missione_presso
            trasferta.motivo_missione = motivo_missione
            trasferta.utilizzo_mezzo = utilizzo_mezzo
            trasferta.extra_orario = aut_extra_orario
            trasferta.note_premissione = note_premissione
            trasferta.motivo_autorizzazione_timbratura = motivo_timbratura
            
            # Helper for time conversion
            def convert_time(t_str):
                return datetime.strptime(t_str, '%H:%M').time() if t_str else None
                
            trasferta.aut_timbratura_entrata = convert_time(aut_timbratura_entrata_str)
            trasferta.aut_timbratura_uscita = convert_time(aut_timbratura_uscita_str)
            
            db.session.commit()
            flash('Modifiche alla richiesta di trasferta salvate con successo.', 'success')
            return redirect(url_for('mie_trasferte'))
            
        except ValueError as e:
            flash(f'Errore nei dati: {e}', 'danger')
            return render_template('nuova_trasferta.html', trasferta=trasferta)

    return render_template('nuova_trasferta.html', trasferta=trasferta)
