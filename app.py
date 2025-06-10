from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///energy.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Meter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(80), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    tenant = db.Column(db.String(80), nullable=False)

class Reading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    meter_id = db.Column(db.Integer, db.ForeignKey('meter.id'), nullable=False)
    month = db.Column(db.String(7), nullable=False)  # YYYY-MM
    value = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    meter = db.relationship('Meter', backref=db.backref('readings', lazy=True))

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return redirect(url_for('meters'))

@app.route('/meters', methods=['GET', 'POST'])
def meters():
    if request.method == 'POST':
        nickname = request.form['nickname']
        type_ = request.form['type']
        tenant = request.form['tenant']
        meter = Meter(nickname=nickname, type=type_, tenant=tenant)
        db.session.add(meter)
        db.session.commit()
        return redirect(url_for('meters'))

    meters = Meter.query.all()
    return render_template('meters.html', meters=meters)

@app.route('/meters/<int:meter_id>/edit', methods=['GET', 'POST'])
def edit_meter(meter_id):
    meter = Meter.query.get_or_404(meter_id)
    if request.method == 'POST':
        meter.nickname = request.form['nickname']
        meter.type = request.form['type']
        meter.tenant = request.form['tenant']
        db.session.commit()
        return redirect(url_for('meters'))
    return render_template('edit_meter.html', meter=meter)

@app.route('/readings', methods=['GET', 'POST'])
def readings():
    month = request.args.get('month') or datetime.utcnow().strftime('%Y-%m')
    type_ = request.args.get('type') or 'electricity'
    meters = Meter.query.filter_by(type=type_).all()
    existing = {r.meter_id: r.value for r in Reading.query.filter_by(month=month).all()}
    if request.method == 'POST':
        for meter in meters:
            field = f'reading_{meter.id}'
            if field in request.form and request.form[field]:
                value = float(request.form[field])
                reading = Reading.query.filter_by(meter_id=meter.id, month=month).first()
                if reading:
                    reading.value = value
                else:
                    reading = Reading(meter_id=meter.id, month=month, value=value)
                    db.session.add(reading)
        db.session.commit()
        return redirect(url_for('readings', month=month, type=type_))
    return render_template('readings.html', meters=meters, month=month, type=type_, readings=existing)

@app.route('/invoices')
def invoices():
    month = request.args.get('month') or datetime.utcnow().strftime('%Y-%m')
    type_ = request.args.get('type') or 'electricity'
    invoices = []
    meters = Meter.query.filter_by(type=type_).all()
    for meter in meters:
        current = Reading.query.filter_by(meter_id=meter.id, month=month).first()
        last = Reading.query.filter(Reading.meter_id==meter.id, Reading.month < month).order_by(Reading.month.desc()).first()
        if current:
            last_value = last.value if last else 0
            diff = current.value - last_value
            invoices.append({
                'tenant': meter.tenant,
                'nickname': meter.nickname,
                'last': last_value,
                'current': current.value,
                'diff': diff
            })
    return render_template('invoices.html', invoices=invoices, month=month, type=type_)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
