import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_dance.contrib.google import make_google_blueprint, google
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.secret_key = os.getenv('SECRET_KEY', 'dev')

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    name = db.Column(db.String(200))

class Ingredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    quantity = db.Column(db.Float, default=0)
    critical_quantity = db.Column(db.Float, default=0)
    image_path = db.Column(db.String(200))

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredient.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(20))  # purchase or consume
    quantity = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    image_path = db.Column(db.String(200))

    ingredient = db.relationship('Ingredient', backref=db.backref('transactions', lazy=True))
    user = db.relationship('User', backref=db.backref('transactions', lazy=True))

def recognize_ingredient(image_path: str):
    """Placeholder for AI recognition of ingredient from image."""
    return None

google_bp = make_google_blueprint(
    client_id=os.getenv('GOOGLE_OAUTH_CLIENT_ID', ''),
    client_secret=os.getenv('GOOGLE_OAUTH_CLIENT_SECRET', ''),
    scope=['profile', 'email'],
    redirect_to='inventory.ingredients'
)
app.register_blueprint(google_bp, url_prefix='/login')

from flask import Blueprint
inventory = Blueprint('inventory', __name__, template_folder='templates')

@inventory.route('/')
def home():
    return redirect(url_for('inventory.ingredients'))

@inventory.route('/login')
def login():
    if not google.authorized:
        return redirect(url_for('google.login'))
    resp = google.get('/oauth2/v2/userinfo')
    if not resp.ok:
        flash('Login failed')
        return redirect(url_for('inventory.ingredients'))
    info = resp.json()
    user = User.query.filter_by(email=info['email']).first()
    if not user:
        user = User(email=info['email'], name=info.get('name'))
        db.session.add(user)
        db.session.commit()
    session['user_id'] = user.id
    flash('Přihlášeno')
    return redirect(url_for('inventory.ingredients'))

@inventory.route('/logout')
def logout():
    session.pop('user_id', None)
    if google_bp.token:
        del google_bp.token
    flash('Odhlášeno')
    return redirect(url_for('inventory.ingredients'))

@inventory.route('/ingredients', methods=['GET'])
def ingredients():
    items = Ingredient.query.all()
    return render_template('inventory/ingredients.html', ingredients=items)

@inventory.route('/ingredients', methods=['POST'])
def add_ingredient():
    if 'user_id' not in session:
        return redirect(url_for('inventory.login'))
    name = request.form['name']
    quantity = float(request.form['quantity'])
    critical = float(request.form['critical'])
    image = request.files.get('image')
    image_path = None
    if image and image.filename:
        filename = secure_filename(image.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(path)
        image_path = path
    ing = Ingredient(name=name, quantity=quantity, critical_quantity=critical, image_path=image_path)
    db.session.add(ing)
    db.session.commit()
    db.session.add(Transaction(ingredient=ing, user_id=session.get('user_id'), action='purchase', quantity=quantity, image_path=image_path))
    db.session.commit()
    flash('Surovina přidána')
    return redirect(url_for('inventory.ingredients'))

@inventory.route('/purchase', methods=['GET', 'POST'])
def purchase():
    if request.method == 'POST':
        if 'user_id' not in session:
            return redirect(url_for('inventory.login'))
        name = request.form['name']
        quantity = float(request.form['quantity'])
        image = request.files.get('image')
        image_path = None
        if image and image.filename:
            filename = secure_filename(image.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(path)
            image_path = path
            # TODO: implement receipt parsing
        ing = Ingredient.query.filter_by(name=name).first()
        if not ing:
            ing = Ingredient(name=name, quantity=0, critical_quantity=0)
            db.session.add(ing)
        ing.quantity += quantity
        db.session.add(Transaction(ingredient=ing, user_id=session.get('user_id'), action='purchase', quantity=quantity, image_path=image_path))
        db.session.commit()
        flash('Nákup uložen')
        return redirect(url_for('inventory.ingredients'))
    return render_template('inventory/purchase.html')

@inventory.route('/consume', methods=['GET', 'POST'])
def consume():
    if request.method == 'POST':
        if 'user_id' not in session:
            return redirect(url_for('inventory.login'))
        name = request.form['name']
        quantity = float(request.form['quantity'])
        image = request.files.get('image')
        image_path = None
        if image and image.filename:
            filename = secure_filename(image.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(path)
            image_path = path
            detected = recognize_ingredient(path)
            if detected:
                name = detected
        ing = Ingredient.query.filter_by(name=name).first()
        if not ing:
            flash('Surovina nenalezena')
            return redirect(url_for('inventory.consume'))
        ing.quantity -= quantity
        db.session.add(Transaction(ingredient=ing, user_id=session.get('user_id'), action='consume', quantity=quantity, image_path=image_path))
        db.session.commit()
        flash('Spotřeba uložena')
        return redirect(url_for('inventory.ingredients'))
    return render_template('inventory/consume.html')

@inventory.route('/critical')
def critical():
    items = Ingredient.query.filter(Ingredient.quantity <= Ingredient.critical_quantity).all()
    return render_template('inventory/critical.html', items=items)

@inventory.route('/activity')
def activity():
    transactions = Transaction.query.order_by(Transaction.timestamp.desc()).all()
    return render_template('inventory/activity.html', transactions=transactions)

app.register_blueprint(inventory)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0')
