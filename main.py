import os
from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_login import UserMixin,login_user,logout_user,login_required,LoginManager,current_user
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship,DeclarativeBase,Mapped,mapped_column
from sqlalchemy import Integer,String,Text,ForeignKey
from werkzeug.security import generate_password_hash,check_password_hash
from dotenv import load_dotenv
from forms import LoginForm,RegisterForm,AddProduct

from flask_ckeditor import CKEditor
from functools import wraps
import stripe


load_dotenv()

app=Flask(__name__)
app.config["SECRET_KEY"]=os.getenv("FLASK_KEY")
ckeditor=CKEditor(app)
Bootstrap5(app)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


login_manager=LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User,int(user_id))

class Base(DeclarativeBase):
    pass

app.config["SQLALCHEMY_DATABASE_URI"]=os.getenv("DB_URI")
db=SQLAlchemy()
db.init_app(app)

class Products(db.Model):
    __tablename__="products"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    product_name:Mapped[str]=mapped_column(String(250),nullable=False)
    image_url:Mapped[str]=mapped_column(String(250),nullable=False)
    description:Mapped[str]=mapped_column(String(250),nullable=False)
    material:Mapped[str]=mapped_column(String(250),nullable=False)
    price:Mapped[int]=mapped_column(Integer,nullable=False)

    cart_items=relationship("CartItem",back_populates='product')

class User(db.Model,UserMixin):
    __tablename__="user"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    email:Mapped[str]=mapped_column(String,nullable=False,unique=True)
    password:Mapped[str]=mapped_column(String,nullable=False)
    name:Mapped[str]=mapped_column(String,nullable=False)
    cart_items=relationship("CartItem",back_populates='user')


class CartItem(db.Model):
    __tablename__="cart_items"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(Integer,ForeignKey("user.id"))
    product_id:Mapped[int]=mapped_column(Integer,ForeignKey("products.id"))
    user=relationship("User",back_populates="cart_items")
    product=relationship("Products",back_populates="cart_items")

def admin_only(f):
    @wraps(f)
    def wrapper(*args,**kwargs):
        if current_user.id!=1:
            return abort (403)
        return f(*args,**kwargs)
    return wrapper



with app.app_context():
    db.create_all()
   

@app.route("/",methods=["GET","POST"])
def home_page():
    all_products=db.session.execute(db.select(Products)).scalars().all()

    alert = request.args.get('alert')
    return render_template("home.html",products=all_products,alert=alert)

@app.route("/login",methods=["GET","POST"])
def login_page():
    login_form=LoginForm()
    if login_form.validate_on_submit():
        email=login_form.email.data
        password=login_form.password.data
        user=db.session.execute(db.select(User).where(User.email==email)).scalar()
        if not user:
            flash("That email doesn't exist,please try again.")
        elif not check_password_hash(user.password,password):
            flash("Incorrect Password,try again.")
        elif user and check_password_hash(user.password,password):
            login_user(user)
            return redirect(url_for("home_page"))
        
    return render_template("login.html",form=login_form)

@app.route("/signin",methods=["GET","POST"])
def signin_page():
    register_form=RegisterForm()
    if register_form.validate_on_submit():
        hash_and_salted_password=generate_password_hash(
            register_form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        email=register_form.email.data
        password=hash_and_salted_password
        name=register_form.name.data
        user=User(email=email,
                  password=password,
                  name=name)
        

        already_their=db.session.execute(db.select(User).where(User.email==email)).scalar()
        if already_their:
            flash("You've already signed up with that email,log in instead.")
            return redirect(url_for("login_page"))
        else:
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("signin_page"))
    return render_template("signin.html",form=register_form)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home_page"))

@app.route("/addproduct",methods=["GET","POST"])
@admin_only
def addproduct_page():
    add_form=AddProduct()
    if add_form.validate_on_submit():
        new_product=Products(
            product_name=add_form.product.data,
            price=add_form.price.data,
            image_url=add_form.img_url.data,
            description=add_form.description.data,
            material=add_form.material.data,
        )
        db.session.add(new_product)
        db.session.commit()
        return redirect(url_for("home_page"))
    return render_template("addproduct.html",form=add_form)


@app.route("/cart",methods=["GET","POST"])
@login_required
def cart_preview_page():
    cart_items=db.session.execute(db.select(CartItem).where(CartItem.user_id==current_user.id)).scalars().all()
    total=sum(item.product.price for item in cart_items)
    return render_template("cart.html",items=cart_items,total=total)

@app.route("/addcart/<int:product_id>",methods=["GET","POST"])
@login_required
def add_to_cart(product_id):
    new_cart_item=CartItem(
        user_id=current_user.id,
        product_id=product_id
    )
    db.session.add(new_cart_item)
    db.session.commit()
    return redirect(url_for("home_page"))


@app.route("/create-checkout-session")
@login_required
def create_checkout_session():
    line_items=[]
    cart_items=db.session.execute(db.select(CartItem).where(CartItem.user_id==current_user.id)).scalars().all()
    
    for item in cart_items:
        line_items.append({
            "price_data":{
                "currency":"inr",
                "product_data":{
                    "name":item.product.product_name,
                    "images":[item.product.image_url],
                },
                "unit_amount":int(item.product.price*100),
            },
            "quantity":1,
        })
    session=stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=line_items,
        mode="payment",
        success_url=url_for("payment_success",_external=True),
        cancel_url=url_for("cart_preview_page",_external=True)

    )
    return redirect(session.url,code=303)

@app.route("/alert",methods=["POST"])
def show_alert():
    msg="Please log in to add items to your cart."
    
    return redirect(url_for('home_page',alert=msg))

@app.route("/success",methods=["GET","POST"])
@login_required
def payment_success():
    return render_template("success.html")


@app.route("/product/<int:product_id>/user/<int:user_id>",methods=["POST","GET"])
def remove_cart_item(product_id,user_id):
    item_to_delete=db.session.execute(db.select(CartItem).where(CartItem.user_id==user_id).where(CartItem.product_id==product_id)).scalar()

    if item_to_delete:
        db.session.delete(item_to_delete)
        db.session.commit()
    return redirect(url_for("cart_preview_page"))


if __name__=="__main__":
    app.run(debug=False)