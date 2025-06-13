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
app.config['SECRET_KEY'] = 'esta-es-una-clave-secreta-muy-larga-y-dificil-de-adivinar'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Configuración de Directorios para Render (MUY IMPORTANTE) ---
# Si el código se está ejecutando en Render, usamos su disco persistente.
if os.environ.get('RENDER'):
    data_dir = '/var/data/eldesconocido_data'
else:
    # Si lo ejecutas en tu computador, usa una carpeta local llamada 'instance'.
    data_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')

# Rutas para la base de datos y las imágenes
upload_path = os.path.join(data_dir, 'uploads')
db_path = os.path.join(data_dir, 'site.db')

# Crear los directorios si no existen
os.makedirs(upload_path, exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['UPLOAD_FOLDER'] = upload_path

# ==============================================================================
# 2. EXTENSIONES Y MODELOS DE BASE DE DATOS
# ==============================================================================
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Debes iniciar sesión para acceder."
login_manager.login_message_category = "info"

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=True)

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
# 3. FORMULARIOS
# ==============================================================================
class LoginForm(FlaskForm):
    username = StringField('Usuario', validators=[DataRequired()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    submit = SubmitField('Iniciar Sesión')

class NewsForm(FlaskForm):
    title = StringField('Título de la Noticia', validators=[DataRequired(), Length(min=5)])
    category = SelectField('Categoría', choices=[('LA REGION', 'La Región'), ('POLITICA', 'Política'), ('OPINION', 'Opinión'), ('CIENCIA Y TECNOLOGIA', 'Ciencia y Tecnología')])
    author = StringField('Autor (Opcional)')
    content = TextAreaField('Contenido de la Noticia', validators=[DataRequired()])
    image_file = FileField('Cambiar/Subir Imagen')
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
        print(f"Error al consultar noticias: {e}")
        region_news, politica_news, opinion_news, ciencia_tecnologia_news = [], [], [], []
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
            flash('¡Inicio de sesión exitoso!', 'success')
            return redirect(request.args.get('next') or url_for('admin_dashboard'))
        else:
            flash('Credenciales incorrectas.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('index'))

@app.route('/contacto', methods=['GET', 'POST'])
def contact_page():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        if name and email and message:
            new_message = ContactMessage(name=name, email=email, subject=request.form.get('subject'), message=message)
            db.session.add(new_message)
            db.session.commit()
            flash('Mensaje enviado con éxito.', 'success')
        else:
            flash('Por favor, completa todos los campos.', 'danger')
        return redirect(url_for('contact_page'))
    return render_template('contact.html')

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
    elif request.method == 'POST':
        flash('El formulario tiene errores. Revisa los campos.', 'danger')
    return render_template('admin_news_form.html', title='Añadir Noticia', form=form)

@app.route('/admin/news/edit/<int:news_id>', methods=['GET', 'POST'])
@admin_required
def edit_news(news_id):
    news_article = NewsArticle.query.get_or_404(news_id)
    form = NewsForm(obj=news_article)
    if form.validate_on_submit():
        try:
            if form.delete_image.data and news_article.image_filename:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], news_article.image_filename)
                if os.path.exists(old_path):
                    os.remove(old_path)
                news_article.image_filename = None
            if form.image_file.data:
                file = form.image_file.data
                if allowed_file(file.filename):
                    if news_article.image_filename:
                        old_path = os.path.join(app.config['UPLOAD_FOLDER'], news_article.image_filename)
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    news_article.image_filename = filename
            news_article.title = form.title.data
            news_article.category = form.category.data
            news_article.author = form.author.data
            news_article.content = form.content.data
            db.session.commit()
            flash('Noticia actualizada con éxito.', 'success')
            return redirect(url_for('admin_news'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar la noticia: {e}', 'danger')
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
    flash('Noticia eliminada.', 'success')
    return redirect(url_for('admin_news'))

# ==============================================================================
# 5. INICIALIZACIÓN DE LA BASE DE DATOS
# ==============================================================================
with app.app_context():
    db.create_all()
    if not User.query.first():
        admin_username = 'eldesconocido'
        admin_password = 'PasswordSeguro2025' # ¡CAMBIA ESTA CONTRASEÑA!
        hashed_password = generate_password_hash(admin_password)
        admin_user = User(username=admin_username, password_hash=hashed_password, is_admin=True)
        db.session.add(admin_user)
        db.session.commit()
        print(f"Usuario administrador '{admin_username}' creado con éxito.")

# Esta parte es solo para ejecutar en tu propio computador
if __name__ == '__main__':
    app.run(debug=True)
