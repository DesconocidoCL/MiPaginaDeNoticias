import os

# Clave secreta para la sesión de Flask. ¡CAMBIA ESTO EN PRODUCCIÓN!
# Genera una clave aleatoria y larga.
SECRET_KEY = os.environ.get('SECRET_KEY') or 'una_clave_super_secreta_y_larga_que_nadie_adivinara_2025_v2'

# Configuración de la base de datos SQLite
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'site.db')
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Carpeta para subir las imágenes de las noticias
# Esto guardará las imágenes en MiPaginaDeNoticias/static/uploads/
UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}