from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Inicializamos db y login_manager aquí, pero sin conectarlos aún a la aplicación
# Eso se hará en app.py, para evitar dependencias circulares.
db = SQLAlchemy()
login_manager = LoginManager()