from datetime import datetime
from extensions import db # Importamos 'db' desde extensions.py
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False) # Para asegurar que solo admin puede acceder a ciertas rutas

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"User('{self.username}', 'Admin: {self.is_admin}')"

class NewsArticle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False) # Aumentado a 200 caracteres
    category = db.Column(db.String(50), nullable=False) # Ej: 'LA REGION', 'POLITICA', 'OPINION', 'CIENCIA Y TECNOLOGIA'
    content = db.Column(db.Text, nullable=False)
    image_filename = db.Column(db.String(100), nullable=True) # Nombre del archivo de imagen subida
    author = db.Column(db.String(50), nullable=True, default="Equipo Desconocido")
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"NewsArticle('{self.title}', '{self.category}', '{self.date_posted}')"

class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(100), nullable=True)
    message = db.Column(db.Text, nullable=False) # db.Text permite mensajes muy largos
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"ContactMessage('{self.name}', '{self.subject}', '{self.timestamp}')"