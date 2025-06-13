import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

# Importaciones locales
from extensions import db, login_manager
from config import SECRET_KEY, SQLALCHEMY_DATABASE_URI as LOCAL_DB_URI
from forms import LoginForm, NewsForm
from models import User, NewsArticle, ContactMessage
from flask_login import login_user, logout_user, login_required, current_user

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY

# --- Configuración de Directorios para Render ---
# Render usa un directorio persistente en /var/data para guardar archivos
# Esto asegura que tu base de datos y tus imágenes no se borren.
data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
if os.environ.get('RENDER'):
    data_dir = '/var/data'

db_path = os.path.join(data_dir, 'site.db')
upload_path = os.path.join(data_dir, 'uploads')

# Crear directorios si no existen
os.makedirs(data_dir, exist_ok=True)
os.makedirs(upload_path, exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['UPLOAD_FOLDER'] = upload_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

# --- RUTAS PÚBLICAS Y DE AUTENTICACIÓN ---
@app.route('/')
def index():
    try:
        region_news = NewsArticle.query.filter_by(category='LA REGION').order_by(NewsArticle.date_posted.desc()).limit(4).all()
        politica_news = NewsArticle.query.filter_by(category='POLITICA').order_by(NewsArticle.date_posted.desc()).limit(4).all()
        opinion_news = NewsArticle.query.filter_by(category='OPINION').order_by(NewsArticle.date_posted.desc()).limit(4).all()
        ciencia_tecnologia_news = NewsArticle.query.filter_by(category='CIENCIA Y TECNOLOGIA').order_by(NewsArticle.date_posted.desc()).limit(4).all()
        return render_template('index.html', region_news=region_news, politica_news=politica_news, opinion_news=opinion_news, ciencia_tecnologia_news=ciencia_tecnologia_news)
    except Exception as e:
        print(f"Error en la ruta principal: {e}")
        return "Error al cargar la página principal. Por favor, revise los logs del servidor.", 500

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

# ... (otras rutas públicas como /logout, /contacto, etc. van aquí)

# --- RUTAS DE ADMINISTRACIÓN ---
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
                    flash('Error: Tipo de archivo no permitido.', 'danger')
                    return render_template('admin_news_form.html', title='Añadir Noticia', form=form)

            new_article = NewsArticle(title=form.title.data, category=form.category.data, content=form.content.data, author=form.author.data, image_filename=filename)
            db.session.add(new_article)
            db.session.commit()
            flash('¡Noticia creada con éxito!', 'success')
            return redirect(url_for('admin_news'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al guardar en la base de datos: {e}', 'danger')
            print(f"ERROR DB (add): {e}")
    elif request.method == 'POST':
        flash('El formulario tiene errores. Revisa los campos.', 'danger')
        print(f"ERRORES DE FORMULARIO (add): {form.errors}")
    return render_template('admin_news_form.html', title='Añadir Noticia', form=form)

@app.route('/admin/news/edit/<int:news_id>', methods=['GET', 'POST'])
@admin_required
def edit_news(news_id):
    news_article = NewsArticle.query.get_or_404(news_id)
    form = NewsForm(obj=news_article)
    if form.validate_on_submit():
        # Lógica de edición
        try:
            if form.image_file.data:
                # ... (lógica de subida de imagen) ...
                pass
            news_article.title = form.title.data
            # ... (actualizar otros campos) ...
            db.session.commit()
            flash('Noticia actualizada con éxito.', 'success')
            return redirect(url_for('admin_news'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar la noticia: {e}', 'danger')
    return render_template('admin_news_form.html', title='Editar Noticia', form=form, news=news_article)
    
# --- INICIALIZACIÓN DE LA APP ---
with app.app_context():
    db.create_all()
    if not User.query.first():
        hashed_password = generate_password_hash('password123')
        admin_user = User(username='admin', password_hash=hashed_password, is_admin=True)
        db.session.add(admin_user)
        db.session.commit()
        print("Usuario admin creado.")
