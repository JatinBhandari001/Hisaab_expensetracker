from flask import Flask, flash, render_template, request, url_for, make_response, redirect, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import date, datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Try to use PostgreSQL from DATABASE_URL, fallback to SQLite for testing
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # Railway/Heroku sometimes use postgres:// instead of postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
    print("Using SQLite for testing. Set DATABASE_URL for PostgreSQL.")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'my-secret-key')
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    google_id = db.Column(db.String(255), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    expenses = db.relationship('Expense', backref='user', lazy=True, cascade='all, delete-orphan')

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(120), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) 

with app.app_context():
    db.create_all()

def format_month_label(year_month_str):
    """Convert YYYY-MM format to Month Year format (e.g., 2024-01 -> January 2024)"""
    try:
        date_obj = datetime.strptime(year_month_str, '%Y-%m').date()
        return date_obj.strftime('%B %Y')  # e.g., "January 2024"
    except (ValueError, TypeError):
        return year_month_str

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/signup", methods=['GET', 'POST'])
def signup():
    if 'user_id' in session:
        return redirect(url_for("index"))

    if request.method == 'POST':
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip()
        password = (request.form.get("password") or "").strip()
        confirm_password = (request.form.get("confirm_password") or "").strip()

        if not username or not email or not password:
            flash("Please fill all fields", "error")
            return redirect(url_for("signup"))

        if password != confirm_password:
            flash("Passwords do not match", "error")
            return redirect(url_for("signup"))

        if User.query.filter_by(username=username).first():
            flash("Username already exists", "error")
            return redirect(url_for("signup"))

        if User.query.filter_by(email=email).first():
            flash("Email already exists", "error")
            return redirect(url_for("signup"))

        user = User(username=username, email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()

        flash("Sign up successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")

@app.route("/login", methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for("index"))

    if request.method == 'POST':
        email = (request.form.get("email") or "").strip()
        password = (request.form.get("password") or "").strip()

        if not email or not password:
            flash("Please fill all fields", "error")
            return redirect(url_for("login"))

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid email or password", "error")
            return redirect(url_for("login"))

        session['user_id'] = user.id
        session['username'] = user.username
        flash(f"Welcome {user.username}!", "success")
        return redirect(url_for("index"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out", "success")
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    start_date = request.args.get('start', '').strip()
    end_date = request.args.get('end', '').strip()
    category = request.args.get('category', '').strip()

    query = Expense.query.filter_by(user_id=session['user_id'])

    if start_date:
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(Expense.date >= sd)
        except ValueError:
            flash("Invalid start date format", "error")

    if end_date:
        try:
            ed = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(Expense.date <= ed)
        except ValueError:
            flash("Invalid end date format", "error")

    if category and category.lower() != 'all':
        query = query.filter(Expense.category == category)

    expenses = query.order_by(Expense.date.desc(), Expense.id.desc()).all()
    total = sum(e.amount for e in expenses)

    category_stats = db.session.query(Expense.category, func.sum(Expense.amount)).filter(Expense.user_id==session['user_id']).group_by(Expense.category).all()
    time_stats = db.session.query(Expense.date, func.sum(Expense.amount)).filter(Expense.user_id==session['user_id']).group_by(Expense.date).order_by(Expense.date).all()

    cat_labels = [c for c, _ in category_stats]
    cat_values = [float(v) for _, v in category_stats]

    day_labels = [d.strftime("%Y-%m-%d") for d, _ in time_stats]
    day_values = [float(v) for _, v in time_stats]

    # Monthly analytics - format dates in Python for database compatibility
    all_expenses = Expense.query.filter_by(user_id=session['user_id']).order_by(Expense.date).all()
    monthly_dict = {}
    for exp in all_expenses:
        month_key = exp.date.strftime('%Y-%m')
        monthly_dict[month_key] = monthly_dict.get(month_key, 0) + exp.amount
    
    month_labels = [format_month_label(m) for m in sorted(monthly_dict.keys())]
    month_values = [float(monthly_dict[m]) for m in sorted(monthly_dict.keys())]

    # Highest spending category
    highest_category = None
    highest_amount = 0
    if category_stats:
        highest_category = max(category_stats, key=lambda x: x[1])[0]
        highest_amount = max(category_stats, key=lambda x: x[1])[1]

    return render_template(
        "index.html",
        expenses=expenses,
        total=total,
        start_date=start_date,
        end_date=end_date,
        selected_category=category,
        cat_labels=cat_labels,
        cat_values=cat_values,
        day_labels=day_labels,
        day_values=day_values,
        month_labels=month_labels,
        month_values=month_values,
        highest_category=highest_category,
        highest_amount=highest_amount,
    )

@app.route("/edit/<int:expense_id>")
@login_required
def edit(expense_id):
    exp = Expense.query.filter_by(id=expense_id, user_id=session['user_id']).first_or_404()
    start_date = request.args.get('start', '').strip()
    end_date = request.args.get('end', '').strip()
    category = request.args.get('category', '').strip()

    query = Expense.query.filter_by(user_id=session['user_id'])
    if start_date:
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(Expense.date >= sd)
        except ValueError:
            flash("Invalid start date format", "error")
    if end_date:
        try:
            ed = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(Expense.date <= ed)
        except ValueError:
            flash("Invalid end date format", "error")
    if category and category.lower() != 'all':
        query = query.filter(Expense.category == category)

    expenses = query.order_by(Expense.date.desc(), Expense.id.desc()).all()
    total = sum(e.amount for e in expenses)

    category_stats = db.session.query(Expense.category, func.sum(Expense.amount)).filter(Expense.user_id==session['user_id']).group_by(Expense.category).all()
    time_stats = db.session.query(Expense.date, func.sum(Expense.amount)).filter(Expense.user_id==session['user_id']).group_by(Expense.date).order_by(Expense.date).all()

    cat_labels = [c for c, _ in category_stats]
    cat_values = [float(v) for _, v in category_stats]
    day_labels = [d.strftime("%Y-%m-%d") for d, _ in time_stats]
    day_values = [float(v) for _, v in time_stats]

    # Monthly analytics - format dates in Python for database compatibility
    all_expenses = Expense.query.filter_by(user_id=session['user_id']).order_by(Expense.date).all()
    monthly_dict = {}
    for exp in all_expenses:
        month_key = exp.date.strftime('%Y-%m')
        monthly_dict[month_key] = monthly_dict.get(month_key, 0) + exp.amount
    
    month_labels = [format_month_label(m) for m in sorted(monthly_dict.keys())]
    month_values = [float(monthly_dict[m]) for m in sorted(monthly_dict.keys())]

    # Highest spending category
    highest_category = None
    highest_amount = 0
    if category_stats:
        highest_category = max(category_stats, key=lambda x: x[1])[0]
        highest_amount = max(category_stats, key=lambda x: x[1])[1]

    return render_template(
        "index.html",
        expenses=expenses,
        total=total,
        start_date=start_date,
        end_date=end_date,
        selected_category=category,
        cat_labels=cat_labels,
        cat_values=cat_values,
        day_labels=day_labels,
        day_values=day_values,
        month_labels=month_labels,
        month_values=month_values,
        highest_category=highest_category,
        highest_amount=highest_amount,
        edit_expense=exp,
    )

@app.route("/download")
@login_required
def download_csv():
    start_date = request.args.get('start', '').strip()
    end_date = request.args.get('end', '').strip()
    category = request.args.get('category', '').strip()

    query = Expense.query.filter_by(user_id=session['user_id'])

    if start_date:
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(Expense.date >= sd)
        except ValueError:
            pass

    if end_date:
        try:
            ed = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(Expense.date <= ed)
        except ValueError:
            pass

    if category and category.lower() != 'all':
        query = query.filter(Expense.category == category)

    expenses = query.order_by(Expense.date.desc(), Expense.id.desc()).all()

    output = "Date,Description,Category,Amount\n"
    for exp in expenses:
        date_str = exp.date.strftime('%Y-%m-%d') if exp.date else ''
        desc = exp.description.replace('"', '""')
        cat = exp.category.replace('"', '""')
        amount = f"{exp.amount:.2f}"
        output += f'"{date_str}","{desc}","{cat}","{amount}"\n'

    response = make_response(output)
    response.headers["Content-Disposition"] = "attachment; filename=expenses.csv"
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    return response

@app.route("/add",methods=['POST'])
@login_required
def add():

     description = (request.form.get("description") or "").strip()
     amount_str = (request.form.get("amount") or "").strip()
     category = (request.form.get("category") or "").strip()
     date_str = (request.form.get("date") or "").strip()

     if not description or not amount_str or not category:
        flash("please fill description, amount , and category", "error")
        return redirect(url_for("index"))

     try:
         amount = float(amount_str)
         if amount <= 0:
             raise ValueError("Amount must be greater than 0")
        
     except ValueError:
         flash("Amount must be a positive number", "error")
         return redirect(url_for("index"))

     try:
         if date_str:
             d = datetime.strptime(date_str, "%Y-%m-%d").date()
         else:
             d = date.today()
     except ValueError:
         flash("Date must be in YYYY-MM-DD format", "error")
         return redirect(url_for("index"))

     e = Expense(description=description, amount=amount, category=category, date=d, user_id=session['user_id'])
     db.session.add(e)
     db.session.commit()
     
     flash("Expense added successfully", "success")
     return redirect(url_for("index"))

@app.route("/update/<int:expense_id>", methods=['POST'])
@login_required
def update(expense_id):
    exp = Expense.query.filter_by(id=expense_id, user_id=session['user_id']).first_or_404()

    description = (request.form.get("description") or "").strip()
    amount_str = (request.form.get("amount") or "").strip()
    category = (request.form.get("category") or "").strip()
    date_str = (request.form.get("date") or "").strip()

    if not description or not amount_str or not category:
        flash("please fill description, amount , and category", "error")
        return redirect(url_for("index"))

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError("Amount must be greater than 0")
    except ValueError:
        flash("Amount must be a positive number", "error")
        return redirect(url_for("index"))

    try:
        if date_str:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            d = date.today()
    except ValueError:
        flash("Date must be in YYYY-MM-DD format", "error")
        return redirect(url_for("index"))

    exp.description = description
    exp.amount = amount
    exp.category = category
    exp.date = d

    db.session.commit()
    flash("Expense updated successfully", "success")
    return redirect(url_for("index"))

@app.route("/delete/<int:expense_id>",methods=['POST'])
@login_required
def delete(expense_id):
    e = Expense.query.filter_by(id=expense_id, user_id=session['user_id']).first_or_404()
    db.session.delete(e)
    db.session.commit()
    flash("Record deleted", "success")
    return redirect(url_for("index"))   

@app.route("/clear", methods=['POST'])
@login_required
def clear_expenses():
    num = Expense.query.filter_by(user_id=session['user_id']).delete()
    db.session.commit()
    flash(f"All expenses cleared ({num} records removed)", "success")
    return redirect(url_for("index"))   


if __name__ == "__main__":
    app.run(debug=False, port=4848)
