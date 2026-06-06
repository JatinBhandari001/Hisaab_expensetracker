from flask import Flask, flash, render_template, request, url_for, make_response, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import date, datetime 

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'my-secret-key'
db = SQLAlchemy(app)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(120), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today) 

with app.app_context():
    db.create_all()

@app.route("/")
def index():
    start_date = request.args.get('start', '').strip()
    end_date = request.args.get('end', '').strip()
    category = request.args.get('category', '').strip()

    query = Expense.query

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

    category_stats = db.session.query(Expense.category, func.sum(Expense.amount)).group_by(Expense.category).all()
    time_stats = db.session.query(Expense.date, func.sum(Expense.amount)).group_by(Expense.date).order_by(Expense.date).all()

    cat_labels = [c for c, _ in category_stats]
    cat_values = [float(v) for _, v in category_stats]

    day_labels = [d.strftime("%Y-%m-%d") for d, _ in time_stats]
    day_values = [float(v) for _, v in time_stats]

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
    )

@app.route("/edit/<int:expense_id>")
def edit(expense_id):
    exp = Expense.query.get_or_404(expense_id)
    start_date = request.args.get('start', '').strip()
    end_date = request.args.get('end', '').strip()
    category = request.args.get('category', '').strip()

    query = Expense.query
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

    category_stats = db.session.query(Expense.category, func.sum(Expense.amount)).group_by(Expense.category).all()
    time_stats = db.session.query(Expense.date, func.sum(Expense.amount)).group_by(Expense.date).order_by(Expense.date).all()

    cat_labels = [c for c, _ in category_stats]
    cat_values = [float(v) for _, v in category_stats]
    day_labels = [d.strftime("%Y-%m-%d") for d, _ in time_stats]
    day_values = [float(v) for _, v in time_stats]

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
        edit_expense=exp,
    )

@app.route("/download")
def download_csv():
    start_date = request.args.get('start', '').strip()
    end_date = request.args.get('end', '').strip()
    category = request.args.get('category', '').strip()

    query = Expense.query

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

     e = Expense(description=description, amount=amount, category=category, date=d)
     db.session.add(e)
     db.session.commit()
     
     flash("Expense added successfully")
     return redirect(url_for("index"))

@app.route("/update/<int:expense_id>", methods=['POST'])
def update(expense_id):
    exp = Expense.query.get_or_404(expense_id)

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
def delete(expense_id):
    e = Expense.query.get_or_404(expense_id)
    db.session.delete(e)
    db.session.commit()
    flash("Record deleted")
    return redirect(url_for("index"))   

@app.route("/clear", methods=['POST'])
def clear_expenses():
    num = Expense.query.delete()
    db.session.commit()
    flash(f"All expenses cleared ({num} records removed)", "success")
    return redirect(url_for("index"))   


if __name__ == "__main__":
    app.run(debug=True, port=4848)
