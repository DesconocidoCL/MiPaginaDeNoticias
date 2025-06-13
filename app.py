from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from functools import wraps

# Importaciones de la aplicación
from extensions import db, login_manager
from config import SECRET_KEY, SQLALCHEMY_DATABASE_URI, UPLOAD_FOLDER, ALLOWED_EXTENSIONS
from forms import LoginForm, NewsForm
from models import User, NewsArticle, ContactMessage
from flask_login import login_user, logout_user, login_required, current_user

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

# --- Rutas Públicas y de Autenticación (Sin cambios) ---
@app.route('/')
def index():
    region_news = NewsArticle.query.filter_by(category='LA REGION').order_by(NewsArticle.date_posted.desc()).limit(4).all()
    politica_news = NewsArticle.query.filter_by(category='POLITICA').order_by(NewsArticle.date_posted.desc()).limit(4).all()
    opinion_news = NewsArticle.query.filter_by(category='OPINION').order_by(NewsArticle.date_posted.desc()).limit(4).all()
    ciencia_tecnologia_news = NewsArticle.query.filter_by(category='CIENCIA Y TECNOLOGIA').order_by(NewsArticle.date_posted.desc()).limit(4).all()
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
            return redirect(request.args.get('next') or url_for('admin_dashboard'))
    return render_template('login.html', form=form)

# ... (El resto de las rutas públicas y de autenticación se mantienen aquí) ...

# --- Rutas de Administración ---
@app.route('/admin/news/add', methods=['GET', 'POST'])
@admin_required
def add_news():
    form = NewsForm()
    if form.validate_on_submit():
        filename = None
        if form.image_file.data:
            file = form.image_file.data
            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        new_article = NewsArticle(
            title=form.title.data,
            category=form.category.data.upper(),
            content=form.content.data,
            author=form.author.data,
            image_filename=filename
        )
        db.session.add(new_article)
        db.session.commit()
        flash('Noticia creada exitosamente.', 'success')
        return redirect(url_for('admin_news'))
    
    # ! CORRECCIÓN DEFINITIVA: Se añade news=None para que la plantilla no falle.
    # Este era el error que causaba que la página se cayera.
    return render_template('admin_news_form.html', title='Añadir Noticia', form=form, news=None)


@app.route('/admin/news/edit/<int:news_id>', methods=['GET', 'POST'])
@admin_required
def edit_news(news_id):
    news_article = NewsArticle.query.get_or_404(news_id)
    form = NewsForm(obj=news_article)
    
    if form.validate_on_submit():
        # Lógica para guardar la noticia (sin cambios)
        if form.delete_image.data:
            if news_article.image_filename:
                old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], news_article.image_filename)
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)
                news_article.image_filename = None
        
        if form.image_file.data:
            file = form.image_file.data
            if allowed_file(file.filename):
                if news_article.image_filename:
                    old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], news_article.image_filename)
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                news_article.image_filename = filename
        
        news_article.title = form.title.data
        news_article.category = form.category.data.upper()
        news_article.author = form.author.data
        news_article.content = form.content.data
        db.session.commit()
        flash('Noticia actualizada exitosamente.', 'success')
        return redirect(url_for('admin_news'))
        
    return render_template('admin_news_form.html', title='Editar Noticia', form=form, news=news_article)

# ... (El resto del archivo, como la inicialización, se mantiene igual) ...

