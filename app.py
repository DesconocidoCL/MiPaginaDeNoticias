import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, FileField, BooleanField, SelectField
from wtforms.validators import DataRequired, Length
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ==============================================================================
# 1. CONFIGURACIÓN DE LA APLICACIÓN
# ==============================================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'una-clave-secreta-muy-dificil-de-adivinar-y-larga'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- CONFIGURACIÓN DE DIRECTORIOS PARA RENDER (MUY IMPORTANTE) ---
# ! CORRECCIÓN: Se especifica un subdirectorio dentro de /var/data para evitar errores de permiso.
if os.environ.get('RENDER'):
    # En el servidor de Render, usamos un subdirectorio en el disco persistente
    data_dir = '/var/data/eldesconocido_data' 
else:
    # Para pruebas en tu propio computador, usamos una carpeta local
    data_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')

# Rutas para la base de datos y las imágenes
upload_path = os.path.join(data_dir, 'uploads')
db_path = os.path.join(data_dir, 'site.db')

# Crear los directorios si no existen
os.makedirs(upload_path, exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['UPLOAD_FOLDER'] = upload_path

# ==============================================================================
# 2. EXTENSIONES Y MODELOS DE BASE DE DATOS (TODO EN UN LUGAR)
# ==============================================================================
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class NewsArticle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(100))
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    image_filename = db.Column(db.String(100), nullable=True)

# (El resto de los modelos de BD, si los hubiera, irían aquí)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==============================================================================
# 3. FORMULARIOS (TODO EN UN LUGAR)
# ==============================================================================
class LoginForm(FlaskForm):
    username = StringField('Nombre de Usuario', validators=[DataRequired()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    submit = SubmitField('Iniciar Sesión')

class NewsForm(FlaskForm):
    title = StringField('Título', validators=[DataRequired(), Length(min=5)])
    category = SelectField('Categoría', choices=[('LA REGION', 'La Región'), ('POLITICA', 'Política'), ('OPINION', 'Opinión'), ('CIENCIA Y TECNOLOGIA', 'Ciencia y Tecnología')])
    author = StringField('Autor')
    content = TextAreaField('Contenido', validators=[DataRequired()])
    image_file = FileField('Imagen (.png, .jpg, .jpeg)')
    submit = SubmitField('Guardar Noticia')

# ==============================================================================
# 4. RUTAS Y LÓGICA DE LA APLICACIÓN
# ==============================================================================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# (Todas las rutas como @app.route('/') van aquí. El código es el mismo que el anterior)
@app.route('/')
def index():
    try:
        # ... (código de index) ...
        region_news = NewsArticle.query.filter_by(category='LA REGION').order_by(NewsArticle.date_posted.desc()).limit(4).all()
        return render_template('index.html', region_news=region_news)
    except Exception:
        return render_template('index.html', region_news=[]) # Si falla, muestra la página vacía

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/admin/news/add', methods=['GET', 'POST'])
@admin_required
def add_news():
    form = NewsForm()
    if form.validate_on_submit():
        try:
            filename = None
            if form.image_file.data:
                file = form.image_file.data
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                else:
                    flash('Error: Tipo de archivo no válido.', 'danger')
                    return render_template('admin_news_form.html', title='Añadir Noticia', form=form)

            new_article = NewsArticle(title=form.title.data, category=form.category.data, content=form.content.data, author=form.author.data, image_filename=filename)
            db.session.add(new_article)
            db.session.commit()
            flash('¡Noticia creada con éxito!', 'success')
            return redirect(url_for('admin_news'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al guardar en la base de datos: {e}', 'danger')
    return render_template('admin_news_form.html', title='Añadir Noticia', form=form)

# (Aquí irían todas las demás rutas: login, logout, edit_news, etc.)

# ==============================================================================
# 5. INICIALIZACIÓN (SOLO PARA ARRANQUE DEL SERVIDOR)
# ==============================================================================
with app.app_context():
    db.create_all()
    if not User.query.first():
        hashed_password = generate_password_hash('password123')
        admin_user = User(username='admin', password_hash=hashed_password, is_admin=True)
        db.session.add(admin_user)
        db.session.commit()
        print("Usuario admin creado.")
