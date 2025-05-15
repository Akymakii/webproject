from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import os
from werkzeug.utils import secure_filename
import mimetypes
from PIL import Image

# конфигурация приложения
app = Flask(__name__)
app.config['SECRET_KEY'] = 'mY$eCrEtK3y!178'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shop.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # функция для перенаправления при необходимости авторизации


class User(UserMixin, db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)  # добавил email
    # связь с товарами (пользователь, добавивший товар)
    products: Mapped[list["Product"]] = relationship(back_populates="user")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    # связь с товарами (одна категория может содержать много товаров)
    products: Mapped[list["Product"]] = relationship(back_populates="category")

    def __repr__(self):
        return f'<Category {self.name}>'


class Product(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("category.id"))
    category: Mapped["Category"] = relationship(back_populates="products")
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    user: Mapped["User"] = relationship(back_populates="products")  # Пользователь, добавивший товар
    image_path: Mapped[str] = mapped_column(String(255), nullable=True)

    def __repr__(self):
        return f'<Product {self.name}>'


class Order(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    user: Mapped["User"] = relationship()
    order_date: Mapped[DateTime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20),
                                        default='pending')  # Статусы: pending, processing, shipped, completed

    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="order")

    def __repr__(self):
        return f'<Order {self.id}>'


class OrderItem(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("order.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped["Order"] = relationship(back_populates="order_items")
    product: Mapped["Product"] = relationship()

    def __repr__(self):
        return f'<OrderItem {self.id}>'


@login_manager.user_loader
def load_user(user_id):
    # загружает пользователя по ID.
    return User.query.get(int(user_id))


@app.route('/', methods=['GET', 'POST'])
def index():
    # главная страница. отображает список товаров.
    search_query = request.form.get('search')  # Получаем поисковый запрос из формы
    if search_query:
        # ищем товары, соответствующие поисковому запросу
        products = Product.query.filter(
            (Product.name.contains(search_query)) | (Product.description.contains(search_query))
        ).all()
    else:
        products = Product.query.all()  # если поисковый запрос пустой, отображаем все товары
    return render_template('index.html', products=products, search_query=search_query)


@app.route('/register', methods=['GET', 'POST'])
def register():
    # cтраница регистрации пользователя.
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
            return render_template('register.html')

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('register.html')

        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    # страница авторизации пользователя.
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
            return render_template('login.html')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    # выход из системы.
    logout_user()
    flash('Logged out successfully!', 'info')
    return redirect(url_for('index'))


@app.route('/profile')
@login_required
def profile():
    # страница профиля пользователя. доступна только авторизованным пользователям.
    return render_template('profile.html', user=current_user)


@app.route('/products/add', methods=['GET', 'POST'])
@login_required
def add_product():
    # страница добавления товара. доступна только авторизованным пользователям.
    categories = Category.query.all()
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        stock = int(request.form['stock'])
        category_id = int(request.form['category'])

        image = request.files['image']
        image_path = None

        try:
            if image:
                filename = secure_filename(image.filename)
                if filename == '':
                    flash('Invalid file name.', 'danger')
                    return render_template('add_product.html', categories=categories)

                upload_folder = 'uploads'
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)
                image_path = os.path.join(upload_folder, filename)
                image.save(image_path)
        except Exception as e:
            flash(f'Error uploading image: {str(e)}', 'danger')
            return render_template('add_product.html', categories=categories)

        new_product = Product(name=name, description=description, price=price,
                              stock=stock, category_id=category_id, user_id=current_user.id, image_path=image_path)
        db.session.add(new_product)
        db.session.commit()
        flash('Product added successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('add_product.html', categories=categories)


@app.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if product.user_id != current_user.id:
        flash('You are not authorized to edit this product.', 'danger')
        return redirect(url_for('index'))

    categories = Category.query.all()
    if request.method == 'POST':
        product.name = request.form['name']
        product.description = request.form['description']
        product.price = float(request.form['price'])
        product.stock = int(request.form['stock'])
        product.category_id = int(request.form['category'])

        # обработка загрузки изображения (аналогично add_product)
        image = request.files['image']
        if image:
            filename = image.filename
            #  сохраняем изображение в uploads folder
            upload_folder = 'uploads'
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            image_path = os.path.join(upload_folder, filename)
            image.save(image_path)
            product.image_path = image_path

        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('edit_product.html', product=product, categories=categories)


@app.route('/products/delete/<int:product_id>')
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    if product.user_id != current_user.id:
        flash('You are not authorized to delete this product.', 'danger')
        return redirect(url_for('index'))

    db.session.delete(product)
    db.session.commit()
    flash('Product deleted successfully!', 'success')
    return redirect(url_for('index'))


@app.route('/api/products')
def api_products():
    products = Product.query.all()
    product_list = []
    for product in products:
        product_list.append({
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'price': product.price,
            'stock': product.stock,
            'category': product.category.name,
            'user': product.user.username
        })
    return jsonify(product_list)


@app.route('/category/add', methods=['GET', 'POST'])
@login_required
def add_category():
    if request.method == 'POST':
        name = request.form['name']
        if Category.query.filter_by(name=name).first():
            flash('Category already exists.', 'danger')
            return render_template('add_category.html')

        new_category = Category(name=name)
        db.session.add(new_category)
        db.session.commit()
        flash('Category added successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('add_category.html')


@app.route('/products/<int:product_id>')
def view_product(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('view_product.html', product=product)


@app.route('/cart/add/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    quantity = int(request.form['quantity'])

    if quantity <= 0:
        flash('Quantity must be greater than 0.', 'danger')
        return redirect(url_for('view_product', product_id=product_id))

    if quantity > product.stock:
        flash('Not enough stock available.', 'danger')
        return redirect(url_for('view_product', product_id=product_id))

    # попробуем найти незавершенный заказ пользователя
    order = Order.query.filter_by(user_id=current_user.id, status='pending').first()

    if not order:
        # если нет, создаем новый заказ
        order = Order(user_id=current_user.id)
        db.session.add(order)
        db.session.commit()  # нужно зафиксировать, чтобы получить order.id

    # ищем этот товар в текущем заказе
    order_item = OrderItem.query.filter_by(order_id=order.id, product_id=product.id).first()

    if order_item:
        # если товар уже есть в заказе, увеличиваем количество
        order_item.quantity += quantity
    else:
        # иначе, создаем новую запись OrderItem
        order_item = OrderItem(order_id=order.id, product_id=product.id, quantity=quantity)
        db.session.add(order_item)

    # уменьшаем количество товара на складе
    product.stock -= quantity
    db.session.commit()

    flash('Product added to cart!', 'success')
    return redirect(url_for('view_product', product_id=product_id))


@app.route('/cart')
@login_required
def view_cart():
    order = Order.query.filter_by(user_id=current_user.id, status='pending').first()
    if order:
        order_items = OrderItem.query.filter_by(order_id=order.id).all()

        # вычисляем общую стоимость для каждого товара и общую стоимость корзины
        total_cost = 0
        for item in order_items:
            item.total_item_cost = item.quantity * item.product.price
            total_cost += item.total_item_cost
    else:
        order_items = []
        total_cost = 0

    return render_template('cart.html', order_items=order_items, order=order, total_cost=total_cost)


@app.route('/cart/remove/<int:order_item_id>')
@login_required
def remove_from_cart(order_item_id):
    order_item = OrderItem.query.get_or_404(order_item_id)

    # проверка, что пользователь имеет право удалять этот товар из корзины
    order = Order.query.get(order_item.order_id)
    if order.user_id != current_user.id:
        flash('You are not authorized to remove this item from the cart.', 'danger')
        return redirect(url_for('view_cart'))

    product = Product.query.get(order_item.product_id)
    product.stock += order_item.quantity  # возвращаем количество на склад

    db.session.delete(order_item)
    db.session.commit()
    flash('Item removed from cart.', 'success')
    return redirect(url_for('view_cart'))


@app.route('/checkout')
@login_required
def checkout():
    order = Order.query.filter_by(user_id=current_user.id, status='pending').first()
    if not order:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('index'))

    order.status = 'processing'  # меняем статус заказа
    db.session.commit()
    flash('Order placed successfully!', 'success')
    return redirect(url_for('index'))


@app.route('/orders')
@login_required
def view_orders():
    orders = Order.query.filter_by(user_id=current_user.id).all()
    return render_template('orders.html', orders=orders)


@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query')  # получаем поисковый запрос из адресной строки
    if query:
        # ищем товары, в названии или описании которых есть поисковый запрос
        products = Product.query.filter(
            (Product.name.contains(query)) | (Product.description.contains(query))
        ).all()
    else:
        products = []  # если поисковый запрос пустой, возвращаем пустой список

    return render_template('search_results.html', products=products, query=query)


if __name__ == '__main__':
    app.run(debug=True)
