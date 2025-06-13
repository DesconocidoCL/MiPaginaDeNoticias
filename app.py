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
# Cambia esta clave secreta en el futuro por seguridad
app.config['SECRET_KEY'] = 'una-clave-secreta-muy-dificil-de-adivinar'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Configuración de Directorios para Render (MUY IMPORTANTE) ---
# Render usa un disco persistente para que los archivos no se borren en cada actualización.
if os.environ.get('RENDER'):
    # En el servidor de Render, usamos el disco persistente
    data_dir = '/var/data/eldesconocido_data'
else:
    # Para pruebas en tu propio computador, usamos una carpeta local
    data_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')

# Rutas para la base de datos y las imágenes
db_path = os.path.join(data_dir, 'site.db')
upload_path = os.path.join(data_dir, 'uploads')

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
login_manager.login_message = "Debes iniciar sesión para acceder a esta página."
login_manager.login_message_category = "info"

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

class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(100), nullable=True)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

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
    title = StringField('Título', validators=[DataRequired(), Length(min=5, message="El título debe tener al menos 5 caracteres.")])
    category = SelectField('Categoría', choices=[('LA REGION', 'La Región'), ('POLITICA', 'Política'), ('OPINION', 'Opinión'), ('CIENCIA Y TECNOLOGIA', 'Ciencia y Tecnología')], validators=[DataRequired()])
    author = StringField('Autor')
    content = TextAreaField('Contenido', validators=[DataRequired(message="El contenido no puede estar vacío.")])
    image_file = FileField('Imagen (.png, .jpg, .jpeg)')
    delete_image = BooleanField('Eliminar imagen actual')
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
            flash('Acceso no autorizado.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Rutas Públicas ---
@app.route('/')
def index():
    try:
        region_news = NewsArticle.query.filter_by(category='LA REGION').order_by(NewsArticle.date_posted.desc()).limit(4).all()
        politica_news = NewsArticle.query.filter_by(category='POLITICA').order_by(NewsArticle.date_posted.desc()).limit(4).all()
        opinion_news = NewsArticle.query.filter_by(category='OPINION').order_by(NewsArticle.date_posted.desc()).limit(4).all()
        ciencia_tecnologia_news = NewsArticle.query.filter_by(category='CIENCIA Y TECNOLOGIA').order_by(NewsArticle.date_posted.desc()).limit(4).all()
    except Exception as e:
        print(f"Error al consultar la base de datos: {e}")
        region_news, politica_news, opinion_news, ciencia_tecnologia_news = [], [], [], []
        flash('No se pudieron cargar las noticias. La base de datos puede estar inicializándose.', 'info')
    return render_template('index.html', region_news=region_news, politica_news=politica_news, opinion_news=opinion_news, ciencia_tecnologia_news=ciencia_tecnologia_news)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# (Otras rutas públicas como /news/<id>, /contacto, etc. van aquí)

# --- Rutas Admin ---
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html')

@app.route('/admin/news')
@admin_required
def admin_news():
    news_articles = NewsArticle.query.order_by(NewsArticle.date_posted.desc()).all()
    return render_template('admin_news.html', news_articles=news_articles)

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
    elif request.method == 'POST':
        flash('El formulario tiene errores. Revisa los campos.', 'danger')
    return render_template('admin_news_form.html', title='Añadir Noticia', form=form)

# (Otras rutas de admin como /edit, /delete, etc. van aquí)

# ==============================================================================
# 5. INICIALIZACIÓN (SOLO PARA ARRANQUE DEL SERVIDOR)
# ==============================================================================
with app.app_context():
    try:
        db.create_all()
        if not User.query.first():
            admin_username = 'eldesconocido'
            admin_password = 'passwordseguro123'
            hashed_password = generate_password_hash(admin_password)
            admin_user = User(username=admin_username, password_hash=hashed_password, is_admin=True)
            db.session.add(admin_user)
            db.session.commit()
            print(f"Usuario administrador '{admin_username}' creado exitosamente.")
    except Exception as e:
        print(f"ERROR AL INICIALIZAR LA BASE DE DATOS: {e}")

if __name__ == '__main__':
    app.run(debug=True)
