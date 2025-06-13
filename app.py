import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

# Importaciones locales
from extensions import db, login_manager
from config import SECRET_KEY
from forms import LoginForm, NewsForm
from models import User, NewsArticle, ContactMessage
from flask_login import login_user, logout_user, login_required, current_user

# --- CONFIGURACIÓN DE LA APLICACIÓN ---
app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- CONFIGURACIÓN DE DIRECTORIOS PARA RENDER ---
# Render utiliza un disco persistente en /var/data para que los archivos no se borren.
# Si el código se está ejecutando en Render, usamos esa ruta. Si no, usa una local.
if os.environ.get('RENDER'):
    data_dir = '/var/data/eldesconocido' # Usamos un subdirectorio para mayor orden
else:
    # Para pruebas en tu propio computador en el futuro
    data_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')

# Rutas para la base de datos y las imágenes subidas
db_path = os.path.join(data_dir, 'site.db')
upload_path = os.path.join(data_dir, 'uploads')

# Crear directorios si no existen
os.makedirs(upload_path, exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['UPLOAD_FOLDER'] = upload_path

# Inicialización de extensiones
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Debes ser administrador para acceder a esta página.', 'danger')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# --- RUTAS DE LA APLICACIÓN ---

@app.route('/')
def index():
    try:
        region_news = NewsArticle.query.filter_by(category='LA REGION').order_by(NewsArticle.date_posted.desc()).limit(4).all()
        politica_news = NewsArticle.query.filter_by(category='POLITICA').order_by(NewsArticle.date_posted.desc()).limit(4).all()
        opinion_news = NewsArticle.query.filter_by(category='OPINION').order_by(NewsArticle.date_posted.desc()).limit(4).all()
        ciencia_tecnologia_news = NewsArticle.query.filter_by(category='CIENCIA Y TECNOLOGIA').order_by(NewsArticle.date_posted.desc()).limit(4).all()
    except Exception as e:
        print(f"Error al consultar la base de datos: {e}")
        # Si hay un error, muestra la página vacía para que no se caiga
        region_news, politica_news, opinion_news, ciencia_tecnologia_news = [], [], [], []
        flash('No se pudieron cargar las noticias. La base de datos puede estar inicializándose.', 'info')
    return render_template('index.html', region_news=region_news, politica_news=politica_news, opinion_news=opinion_news, ciencia_tecnologia_news=ciencia_tecnologia_news)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/news/<int:news_id>')
def news_detail(news_id):
    news_article = NewsArticle.query.get_or_404(news_id)
    return render_template('new_detail.html', news=news_article)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data) and user.is_admin:
            session.permanent = False
            login_user(user, remember=False)
            flash('¡Inicio de sesión como Administrador exitoso!', 'success')
            return redirect(request.args.get('next') or url_for('admin_dashboard'))
        else:
            flash('Credenciales incorrectas.', 'danger')
    return render_template('login.html', form=form)

# (Aquí irían las otras rutas como logout, contacto, etc. sin cambios)
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('index'))

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
                    flash('Error: Tipo de archivo de imagen no permitido.', 'danger')
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
    
# ... (Aquí irían las otras rutas de admin como edit_news, delete_news, etc. sin cambios)

# --- INICIALIZACIÓN DE LA BASE DE DATOS ---
# Este bloque de código se ejecuta una vez cuando el servidor arranca.
# Crea la base de datos y el usuario administrador si no existen.
with app.app_context():
    try:
        db.create_all()
        print("Tablas de la base de datos verificadas/creadas.")
        
        # Crear usuario admin solo si no existe NINGÚN usuario
        if not User.query.first():
            admin_username = 'eldesconocido'  # Puedes cambiar este
            admin_password = 'passwordseguro123' # ¡CAMBIA ESTA CONTRASEÑA!
            
            hashed_password = generate_password_hash(admin_password)
            admin_user = User(username=admin_username, password_hash=hashed_password, is_admin=True)
            db.session.add(admin_user)
            db.session.commit()
            print(f"Usuario administrador '{admin_username}' creado exitosamente.")
        else:
            print("El usuario administrador ya existe.")
            
    except Exception as e:
        print(f"ERROR DURANTE LA INICIALIZACIÓN DE LA BASE DE DATOS: {e}")

