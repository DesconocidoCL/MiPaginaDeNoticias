from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, PasswordField, SubmitField, FileField, BooleanField, SelectField
from wtforms.validators import DataRequired, Length
from flask_wtf.file import FileAllowed

# Ya no necesitamos importar User aquí

class LoginForm(FlaskForm):
    username = StringField('Nombre de Usuario', validators=[DataRequired()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    submit = SubmitField('Iniciar Sesión')

class NewsForm(FlaskForm):
    title = StringField('Título de la Noticia', validators=[DataRequired(), Length(min=5, max=200)])
    category = SelectField('Categoría', 
        choices=[
            ('LA REGION', 'La Región'),
            ('POLITICA', 'Política'),
            ('OPINION', 'Opinión'),
            ('CIENCIA Y TECNOLOGIA', 'Ciencia y Tecnología')
        ],
        validators=[DataRequired()]
    )
    author = StringField('Autor (Opcional)', validators=[Length(max=50)])
    content = TextAreaField('Contenido de la Noticia', validators=[DataRequired()])
    image_file = FileField('Cambiar/Subir Imagen (Opcional)', validators=[
        FileAllowed(['jpg', 'png', 'jpeg', 'gif'], '¡Solo se permiten imágenes!')
    ])
    delete_image = BooleanField('Eliminar imagen actual')
    submit = SubmitField('Guardar Noticia')

# ! ELIMINADO: La clase UserForm se ha quitado porque ya no es necesaria.