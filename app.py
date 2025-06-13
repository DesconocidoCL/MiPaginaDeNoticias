from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime

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

# Asegurarse de que la carpeta de subidas exista
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Por favor, inicia sesión para acceder a esta página."
login_manager.login_message_category = 'info'

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Decorador de Admin ---
from functools import wraps
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Debes ser administrador para acceder a esta página.', 'danger')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# --- Rutas Públicas ---
@app.route('/')
def index():
    # El código para la página de inicio se mantiene igual
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

@app.route('/la-region')
def category_region():
    news_articles = NewsArticle.query.filter_by(category='LA REGION').order_by(NewsArticle.date_posted.desc()).all()
    return render_template('category_news.html', title='Noticias de La Región', news_articles=news_articles)

@app.route('/politica')
def category_politica():
    news_articles = NewsArticle.query.filter_by(category='POLITICA').order_by(NewsArticle.date_posted.desc()).all()
    return render_template('category_news.html', title='Noticias de Política', news_articles=news_articles)

@app.route('/opinion')
def category_opinion():
    news_articles = NewsArticle.query.filter_by(category='OPINION').order_by(NewsArticle.date_posted.desc()).all()
    return render_template('category_news.html', title='Artículos de Opinión', news_articles=news_articles)

@app.route('/ciencia-tecnologia')
def category_ciencia_tecnologia():
    news_articles = NewsArticle.query.filter_by(category='CIENCIA Y TECNOLOGIA').order_by(NewsArticle.date_posted.desc()).all()
    return render_template('category_news.html', title='Noticias de Ciencia y Tecnología', news_articles=news_articles)

@app.route('/contacto', methods=['GET', 'POST'])
def contact_page():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')
        if name and email and message:
            new_message = ContactMessage(name=name, email=email, subject=subject, message=message)
            db.session.add(new_message)
            db.session.commit()
            flash('¡Tu mensaje ha sido recibido con éxito!', 'success')
        else:
            flash('Por favor completa todos los campos requeridos.', 'danger')
        return redirect(url_for('contact_page'))
    return render_template('contact.html')

# --- Autenticación ---
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
            next_page = request.args.get('next')
            return redirect(next_page or url_for('admin_dashboard'))
        else:
            flash('Credenciales incorrectas. Por favor, verifica tu usuario y contraseña.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('index'))

# --- Rutas de Administración ---
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    total_news = NewsArticle.query.count()
    total_messages = ContactMessage.query.count()
    return render_template('admin_dashboard.html', total_news=total_news, total_messages=total_messages)

@app.route('/admin/news')
@admin_required
def admin_news():
    news_articles = NewsArticle.query.order_by(NewsArticle.date_posted.desc()).all()
    return render_template('admin_news.html', news_articles=news_articles)

# ! CORREGIDO: Lógica para Añadir Noticia
@app.route('/admin/news/add', methods=['GET', 'POST'])
@admin_required
def add_news():
    form = NewsForm()
    if form.validate_on_submit():
        filename = None
        # Procesa la subida de imagen
        if form.image_file.data:
            file = form.image_file.data
            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                try:
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                except Exception as e:
                    flash(f'Error al guardar la imagen: {e}', 'danger')
                    return render_template('admin_news_form.html', title='Añadir Noticia', form=form)
            else:
                flash('Tipo de archivo de imagen no permitido.', 'danger')
                return render_template('admin_news_form.html', title='Añadir Noticia', form=form)
        
        # Crea el nuevo artículo en la base de datos
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
        
    return render_template('admin_news_form.html', title='Añadir Noticia', form=form, news=None)

# ! CORREGIDO: Lógica para Editar Noticia
@app.route('/admin/news/edit/<int:news_id>', methods=['GET', 'POST'])
@admin_required
def edit_news(news_id):
    news_article = NewsArticle.query.get_or_404(news_id)
    form = NewsForm(obj=news_article)
    
    if form.validate_on_submit():
        # Lógica para borrar la imagen
        if form.delete_image.data:
            if news_article.image_filename:
                old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], news_article.image_filename)
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)
                news_article.image_filename = None
        
        # Lógica para subir una nueva imagen
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
            else:
                flash('Tipo de archivo de imagen no permitido.', 'danger')
                return render_template('admin_news_form.html', title='Editar Noticia', form=form, news=news_article)

        # Actualiza los otros campos
        news_article.title = form.title.data
        news_article.category = form.category.data.upper()
        news_article.author = form.author.data
        news_article.content = form.content.data
        
        db.session.commit()
        flash('Noticia actualizada exitosamente.', 'success')
        return redirect(url_for('admin_news'))
        
    return render_template('admin_news_form.html', title='Editar Noticia', form=form, news=news_article)


@app.route('/admin/news/delete/<int:news_id>', methods=['POST'])
@admin_required
def delete_news(news_id):
    news_article = NewsArticle.query.get_or_404(news_id)
    if news_article.image_filename:
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], news_article.image_filename)
        if os.path.exists(image_path):
            os.remove(image_path)
    db.session.delete(news_article)
    db.session.commit()
    flash('Noticia eliminada exitosamente.', 'success')
    return redirect(url_for('admin_news'))

@app.route('/admin/contacts')
@admin_required
def admin_contacts():
    contact_messages = ContactMessage.query.order_by(ContactMessage.timestamp.desc()).all()
    return render_template('admin_contacts.html', contact_messages=contact_messages)

@app.route('/admin/contacts/delete/<int:message_id>', methods=['POST'])
@admin_required
def delete_contact_message(message_id):
    message = ContactMessage.query.get_or_404(message_id)
    db.session.delete(message)
    db.session.commit()
    flash('Mensaje eliminado.', 'danger')
    return redirect(url_for('admin_contacts'))

# --- Lógica de Inicialización ---
def create_initial_admin(app):
    with app.app_context():
        db.create_all() 
        ADMIN_USERNAME = 'editor'
        ADMIN_PASSWORD = 'password123' 
        if not User.query.first():
            hashed_password = generate_password_hash(ADMIN_PASSWORD)
            admin_user = User(username=ADMIN_USERNAME, password_hash=hashed_password, is_admin=True)
            db.session.add(admin_user)
            db.session.commit()
            print(f"--- Usuario administrador '{ADMIN_USERNAME}' creado. ---")

if __name__ == '__main__':
    create_initial_admin(app) 
    app.run(debug=True)
