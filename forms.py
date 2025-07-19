from flask_wtf import FlaskForm
from wtforms import StringField,SubmitField
from wtforms.fields.simple import PasswordField
from wtforms.validators import DataRequired,URL
from flask_ckeditor import CKEditorField

class LoginForm(FlaskForm):
    email=StringField("Email",validators=[DataRequired()])
    password=PasswordField("Password",validators=[DataRequired()])
    submit=SubmitField("Log in")

class RegisterForm(FlaskForm):
    email=StringField("Email",validators=[DataRequired()])
    password=PasswordField("Password",validators=[DataRequired()])
    name=StringField("Name",validators=[DataRequired()])
    submit=SubmitField("Sign in")

class AddProduct(FlaskForm):
    product=StringField("Product Name",validators=[DataRequired()])
    price=StringField("Price",validators=[DataRequired()])
    img_url=StringField("Product Image URL",validators=[DataRequired()])
    description=CKEditorField("Description",validators=[DataRequired()])
    material=StringField("Material",validators=[DataRequired()])
    submit=SubmitField("Add")