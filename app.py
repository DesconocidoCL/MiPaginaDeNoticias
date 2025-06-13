# app.py
# ==============================================================================
# 0. IMPORTACIONES
# ==============================================================================
import os
import sys
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, FileField, BooleanField, SelectField
from wtforms.validators import DataRequired, Length, EqualTo, Optional
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ==============================================================================
# 1. CONFIGURACIÓN DE LA APLICACIÓN
# ==============================================================================
app = Flask(__name__)
# Usar una variable de entorno para la SECRET_KEY en producción
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'clave-secreta-para-desarrollo-local')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Aumentar el tamaño máximo de archivo a 16MB
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024


# --- Configuración de Directorios para Render (CORREGIDA Y DEFINITIVA) ---
# Esta lógica asegura que los datos persistan en Render y funcionen localmente.
if os.environ.get('RENDER'):
    # En el servidor de Render, usamos el disco persistente definido en render.yaml
    data_dir = '/var/data/project_data'
else:
    # Para pruebas en tu computador, usa una carpeta local llamada 'instance'
    data_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')

upload_path = os.path.join(data_dir, 'uploads')
db_path = os.path.join(data_dir, 'site.db')

# Crear los directorios si no existen para evitar errores al iniciar
os.makedirs(upload_path, exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['UPLOAD_FOLDER'] = upload_path

# ==============================================================================
# 2. EXTENSIONES Y MODELOS DE BASE DE DATOS
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
    author = db.Column(db.String(100), default="Equipo Desconocido")
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
# 3. FORMULARIOS (WTForms)
# ==============================================================================
class LoginForm(FlaskForm):
    username = StringField('Usuario', validators=[DataRequired()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    submit = SubmitField('Iniciar Sesión')

class NewsForm(FlaskForm):
    title = StringField('Título', validators=[DataRequired(), Length(min=5, message="El título debe tener al menos 5 caracteres.")])
    category = SelectField('Categoría', choices=[('LA REGION', 'La Región'), ('POLITICA', 'Política'), ('OPINION', 'Opinión'), ('CIENCIA Y TECNOLOGIA', 'Ciencia y Tecnología')])
    author = StringField('Autor (Opcional, si se deja en blanco será "Equipo Desconocido")')
    content = TextAreaField('Contenido', validators=[DataRequired(message="El contenido no puede estar vacío.")])
    image_file = FileField('Subir o cambiar Imagen')
    submit = SubmitField('Guardar Noticia')

class UserForm(FlaskForm):
    username = StringField('Nombre de Usuario', validators=[DataRequired(), Length(min=4, max=80)])
    password = PasswordField('Contraseña', validators=[
        Optional(),
        Length(min=8, message="La contraseña debe tener al menos 8 caracteres."),
        EqualTo('confirm_password', message='Las contraseñas deben coincidir.')
    ])
    confirm_password = PasswordField('Confirmar Contraseña')
    is_admin = BooleanField('¿Es Administrador?', default=True)
    submit = SubmitField('Guardar Usuario')

# ==============================================================================
# 4. FUNCIONES AUXILIARES Y DECORADORES
# ==============================================================================
def allowed_file(filename):
    """Verifica si la extensión del archivo está permitida."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

def admin_required(f):
    """Decorador para restringir el acceso solo a administradores."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Acceso no autorizado. Se requieren permisos de administrador.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==============================================================================
# 5. RUTAS DE LA APLICACIÓN
# ==============================================================================

# --- Rutas Públicas (visibles para todos) ---

@app.route('/')
def index():
    """Página de inicio que muestra las últimas 4 noticias de cada categoría."""
    try:
        region_news = NewsArticle.query.filter_by(category='LA REGION').order_by(NewsArticle.date_posted.desc()).limit(4).all()
        politica_news = NewsArticle.query.filter_by(category='POLITICA').order_by(NewsArticle.date_posted.desc()).limit(4).all()
        opinion_news = NewsArticle.query.filter_by(category='OPINION').order_by(NewsArticle.date_posted.desc()).limit(4).all()
        ciencia_tecnologia_news = NewsArticle.query.filter_by(category='CIENCIA Y TECNOLOGIA').order_by(NewsArticle.date_posted.desc()).limit(4).all()
    except Exception as e:
        print(f"Error al cargar noticias: {e}", file=sys.stderr)
        flash("No se pudieron cargar las noticias. La base de datos podría no estar disponible.", "danger")
        region_news, politica_news, opinion_news, ciencia_tecnologia_news = [], [], [], []
    return render_template('index.html', region_news=region_news, politica_news=politica_news, opinion_news=opinion_news, ciencia_tecnologia_news=ciencia_tecnologia_news)

@app.route('/category/<category_name>')
def category_page(category_name):
    """Página genérica para mostrar todas las noticias de una categoría."""
    # Mapeo de URLs a nombres para mostrar y filtrar
    categories = {
        'region': 'LA REGION',
        'politica': 'POLITICA',
        'opinion': 'OPINION',
        'ciencia-tecnologia': 'CIENCIA Y TECNOLOGIA'
    }
    
    internal_category_name = categories.get(category_name.lower())
    if not internal_category_name:
        return "Categoría no encontrada", 404

    news_articles = NewsArticle.query.filter_by(category=internal_category_name).order_by(NewsArticle.date_posted.desc()).all()
    
    # Capitalizar para el título de la página
    display_name = internal_category_name.replace('_', ' ').title()

    return render_template('category_news.html', news_articles=news_articles, category_name=display_name)


@app.route('/news/<int:news_id>')
def news_detail(news_id):
    """Muestra el detalle completo de una noticia."""
    news_article = NewsArticle.query.get_or_404(news_id)
    return render_template('new_detail.html', news=news_article)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Sirve los archivos subidos desde la carpeta de uploads."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/contacto', methods=['GET', 'POST'])
def contact_page():
    """Página de contacto que también procesa el envío del formulario."""
    if request.method == 'POST':
        try:
            new_message = ContactMessage(
                name=request.form['name'],
                email=request.form['email'],
                subject=request.form['subject'],
                message=request.form['message']
            )
            db.session.add(new_message)
            db.session.commit()
            flash('¡Gracias por tu mensaje! Lo revisaremos pronto.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Hubo un error al enviar tu mensaje: {e}', 'danger')
        return redirect(url_for('contact_page'))
    
    return render_template('contact.html')

# --- Rutas de Autenticación y Administración ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de inicio de sesión para administradores."""
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data) and user.is_admin:
            login_user(user)
            return redirect(request.args.get('next') or url_for('admin_dashboard'))
        else:
            flash('Credenciales inválidas o no tienes permiso de administrador.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    """Cierra la sesión del usuario."""
    logout_user()
    flash('Has cerrado sesión exitosamente.', 'info')
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Panel principal de administración."""
    total_news = NewsArticle.query.count()
    total_messages = ContactMessage.query.count()
    return render_template('admin_dashboard.html', total_news=total_news, total_messages=total_messages)

# --- Gestión de Noticias (CRUD) ---

@app.route('/admin/news')
@admin_required
def admin_news():
    """Muestra la tabla para gestionar noticias."""
    news_articles = NewsArticle.query.order_by(NewsArticle.date_posted.desc()).all()
    return render_template('admin_news.html', news_articles=news_articles)

@app.route('/admin/news/add', methods=['GET', 'POST'])
@admin_required
def add_news():
    """Formulario para añadir una nueva noticia."""
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

            author_name = form.author.data if form.author.data else "Equipo Desconocido"
            new_article = NewsArticle(
                title=form.title.data, 
                category=form.category.data, 
                content=form.content.data, 
                author=author_name, 
                image_filename=filename
            )
            db.session.add(new_article)
            db.session.commit()
            flash('¡Noticia creada con éxito!', 'success')
            return redirect(url_for('admin_news'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al guardar en la base de datos: {e}', 'danger')
            print(f"Error en add_news: {e}", file=sys.stderr)

    return render_template('admin_news_form.html', title='Añadir Noticia', form=form, news=None)


@app.route('/admin/news/edit/<int:news_id>', methods=['GET', 'POST'])
@admin_required
def edit_news(news_id):
    """Formulario para editar una noticia existente."""
    news = NewsArticle.query.get_or_404(news_id)
    form = NewsForm(obj=news) # Pre-popula el formulario con los datos de la noticia

    if form.validate_on_submit():
        try:
            news.title = form.title.data
            news.category = form.category.data
            news.content = form.content.data
            news.author = form.author.data if form.author.data else "Equipo Desconocido"
            
            if form.image_file.data:
                file = form.image_file.data
                if allowed_file(file.filename):
                    # Opcional: podrías querer borrar la imagen antigua del disco
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    news.image_filename = filename
                else:
                    flash('Error: Tipo de archivo de imagen no permitido. No se actualizó la imagen.', 'danger')

            db.session.commit()
            flash('Noticia actualizada con éxito!', 'success')
            return redirect(url_for('admin_news'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar la noticia: {e}', 'danger')
            print(f"Error en edit_news: {e}", file=sys.stderr)

    return render_template('admin_news_form.html', title='Editar Noticia', form=form, news=news)


@app.route('/admin/news/delete/<int:news_id>', methods=['POST'])
@admin_required
def delete_news(news_id):
    """Ruta para eliminar una noticia."""
    news_to_delete = NewsArticle.query.get_or_404(news_id)
    try:
        # Opcional: Eliminar el archivo de imagen del disco persistente
        if news_to_delete.image_filename:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], news_to_delete.image_filename)
            if os.path.exists(image_path):
                os.remove(image_path)

        db.session.delete(news_to_delete)
        db.session.commit()
        flash('Noticia eliminada correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar la noticia: {e}', 'danger')
        print(f"Error en delete_news: {e}", file=sys.stderr)
    return redirect(url_for('admin_news'))


# --- Gestión de Mensajes ---
@app.route('/admin/contacts')
@admin_required
def admin_contacts():
    """Muestra la bandeja de entrada de mensajes de contacto."""
    messages = ContactMessage.query.order_by(ContactMessage.timestamp.desc()).all()
    return render_template('admin_contacts.html', contact_messages=messages)


@app.route('/admin/contacts/delete/<int:message_id>', methods=['POST'])
@admin_required
def delete_contact_message(message_id):
    """Elimina un mensaje de contacto."""
    message_to_delete = ContactMessage.query.get_or_404(message_id)
    try:
        db.session.delete(message_to_delete)
        db.session.commit()
        flash('Mensaje eliminado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el mensaje: {e}', 'danger')
    return redirect(url_for('admin_contacts'))

# --- Gestión de Usuarios (CRUD) ---
@app.route('/admin/users')
@admin_required
def admin_users():
    """Muestra la tabla para gestionar usuarios administradores."""
    users = User.query.all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/add', methods=['GET', 'POST'])
@admin_required
def add_user():
    """Formulario para añadir un nuevo usuario."""
    form = UserForm()
    # Para añadir, la contraseña es obligatoria
    form.password.validators = [DataRequired(), Length(min=8), EqualTo('confirm_password', message='Las contraseñas deben coincidir.')]
    
    if form.validate_on_submit():
        try:
            if User.query.filter_by(username=form.username.data).first():
                flash('El nombre de usuario ya existe.', 'danger')
            else:
                new_user = User(username=form.username.data, is_admin=form.is_admin.data)
                new_user.set_password(form.password.data)
                db.session.add(new_user)
                db.session.commit()
                flash('Usuario creado con éxito.', 'success')
                return redirect(url_for('admin_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el usuario: {e}', 'danger')
    return render_template('admin_user_form.html', form=form, title="Añadir Usuario")


@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """Formulario para editar un usuario existente."""
    user = User.query.get_or_404(user_id)
    form = UserForm(obj=user)
    
    if form.validate_on_submit():
        try:
            # Prevenir cambiar el nombre de usuario a uno que ya existe
            existing_user = User.query.filter(User.username == form.username.data, User.id != user_id).first()
            if existing_user:
                flash('Ese nombre de usuario ya está en uso por otra cuenta.', 'danger')
                return render_template('admin_user_form.html', form=form, title="Editar Usuario")

            user.username = form.username.data
            user.is_admin = form.is_admin.data
            # Solo actualizar la contraseña si se proporcionó una nueva
            if form.password.data:
                user.set_password(form.password.data)
            db.session.commit()
            flash('Usuario actualizado con éxito.', 'success')
            return redirect(url_for('admin_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al editar el usuario: {e}', 'danger')
    return render_template('admin_user_form.html', form=form, title="Editar Usuario")


@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Elimina un usuario (protegiendo contra auto-eliminación)."""
    if user_id == current_user.id:
        flash('No puedes eliminar tu propia cuenta.', 'danger')
        return redirect(url_for('admin_users'))
    
    user_to_delete = User.query.get_or_404(user_id)
    try:
        db.session.delete(user_to_delete)
        db.session.commit()
        flash('Usuario eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el usuario: {e}', 'danger')
    return redirect(url_for('admin_users'))


# ==============================================================================
# 6. INICIALIZACIÓN DE LA BASE DE DATOS Y EJECUCIÓN
# ==============================================================================
def initialize_database():
    """Crea las tablas y el primer usuario administrador si no existen."""
    with app.app_context():
        db.create_all()
        # Crear el primer usuario solo si no existe ninguno
        if not User.query.first():
            # ¡IMPORTANTE! Usa variables de entorno para las credenciales.
            admin_username = os.environ.get('ADMIN_USER', 'admin')
            admin_password = os.environ.get('ADMIN_PASS', 'defaultpassword')
            
            if admin_password == 'defaultpassword':
                 print("ADVERTENCIA: Usando contraseña por defecto. Configura ADMIN_USER y ADMIN_PASS en tus variables de entorno.", file=sys.stderr)

            admin_user = User(username=admin_username, is_admin=True)
            admin_user.set_password(admin_password)
            db.session.add(admin_user)
            db.session.commit()
            print(f"Base de datos inicializada. Usuario '{admin_username}' creado.", file=sys.stdout)

# Llama a la inicialización antes de la primera solicitud
@app.before_first_request
def setup():
    initialize_database()

if __name__ == '__main__':
    # El servidor de producción como Gunicorn llamará a la app directamente.
    # Este bloque es solo para desarrollo local.
    app.run(debug=True)

