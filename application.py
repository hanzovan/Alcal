# import module
from cs50 import SQL
from flask import Flask, flash, redirect, request, render_template, session, jsonify
from flask_session import Session
from datetime import datetime, timedelta, date
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import login_required, days_between


# config app
app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


# config SQL database
db = SQL("sqlite:///costs.db")


# Register route
@app.route("/register", methods=["GET", "POST"])
@login_required
def register():
    """ Only allow admin to create new account"""
    # if user reached route by POST (as by submiting form)
    if request.method == "POST":
        name = request.form.get("username")
        password = request.form.get("password")
        confirm = request.form.get("password2")

        # Check if user enter all required field:
        if not name:
            return render_template("error.html", message="Missing username")
        if not password:
            return render_template("error.html", message="Missing password")
        if not confirm:
            return render_template("error.html", message="You need to confirm your password")
        if password != confirm:
            return render_template("error.html", message="Passwords don't match")

        # Check if user exist in database
        check = db.execute("SELECT * FROM users WHERE username = ?", name)

        if check:
            return render_template("error.html", message="Username already exist")

        # If everything okay, add new user into database
        db.execute("INSERT INTO users(username, hash) VALUES (?, ?)", name, generate_password_hash(password))

        # Log the user in
        user = db.execute("SELECT * FROM users WHERE username = ?", name)
        session['user_id'] = user[0]['id']
        session['username'] = user[0]['username']

        # Inform that the user registered successfully
        flash("You are registered!")

        return redirect("/")

    # if user reached route via link or being redirect
    else:
        return render_template("register.html")


# Login route
@app.route("/login", methods=["GET", "POST"])
def login():

    # if user reached route via submiting form
    if request.method == "POST":
        name = request.form.get("username")
        password = request.form.get("password")

        # Check if user field the required information
        if not name:
            return render_template("error.html", message="Missing username")
        if not password:
            return render_template("error.html", message="Missing password")

        # Check if username exist in the database
        check = db.execute("SELECT * FROM users WHERE username = ?", name)
        if not check or not check_password_hash(check[0]['hash'], password):
            return render_template("error.html", message="Invalid Username or Password")

        # If everything correct, remember the user and redirect to main page
        session['user_id'] = check[0]['id']
        session['username'] = check[0]['username']

        # Inform that user logged in successfully
        flash("Logged in successfully")

        # Redirect user to homepage
        return redirect("/")

    # if user reached route via being redirect or clicking link
    else:
        return render_template("login.html")

# homepage route
@app.route("/")
def index():

    # Calculate production cost for every item in items
    items_p = db.execute("SELECT * FROM items")

    for item in items_p:
        product = item['id']

        # Find product in formula via ID
        product_formula = db.execute("SELECT * FROM formulas WHERE item_id = ?", product)

        total_cost = 0
        total_nutrition = 0

        # Calculate the production cost and total nutrition
        for material in product_formula:
            material_id = material['material_id']
            material_row = db.execute("SELECT * FROM items WHERE id = ?", material_id)
            material_price = material_row[0]['price']
            material_nutrition = material_row[0]['nutrition']
            total_cost += material_price * material['quantity']
            total_nutrition += material_nutrition * material['quantity']

            db.execute("UPDATE items SET cost = ?, nutrition = ? WHERE id = ?", total_cost, total_nutrition, product)

    # Define tax and listing fee
    tax = 0.030
    fee = 0.015

    # Shop fee per 100 nutrition consume
    shop_fee = 2000

    # Food cost was not include in island profit due to not calculated and small

    # Define return rate
    city_rate = 0.435
    island_rate = 0.371

    # Select database from items
    items = db.execute("SELECT * FROM items")

    # Update the current profit
    for item in items:
        item_id = item['id']
        cost = item['cost']
        price = item['price']
        nutrition = item['nutrition']

        # for city
        city_final_cost = cost * (1 - city_rate) + (nutrition * 2000/100)
        city_profit = round(((price/(city_final_cost + (tax * price) + (fee * price))) - 1), 2)

        # for island
        island_final_cost = round(cost * (1 - island_rate), 2)
        island_profit = round(((price/(island_final_cost + (tax * price) + (fee * price))) - 1), 2)

        # if item cost was not updated
        if cost == 0:
            city_profit = 0
            island_profit = 0

        # final profit is island or city depend on which one is greater
        if city_profit < island_profit:
            profit = island_profit

        else:
            profit = city_profit

        # Update the profit

        db.execute("UPDATE items SET city_profit = ?, island_profit = ?, profit = ? WHERE id = ?", city_profit, island_profit, profit, item_id)

    # Calculate the day between the updated date and today
    today = str(date.today())


    # Get information of items table from database
    shows = db.execute("SELECT * FROM items ORDER BY profit DESC")

    # calculate days from the last time item was updated
    for item in shows:
        updated = item['updated']
        updated_from = None
        if updated:
            if days_between(updated, today) < 7:
                updated_from = "few days ago"

            elif days_between(updated, today) < 14:
                updated_from = "a week ago"

            else:
                updated_from = "Outdated"

            db.execute("UPDATE items SET updated_from = ? WHERE id = ?", updated_from, item['id'])

    # show information of item in the web browser
    return render_template("index.html", items=shows)


@app.route("/add_item", methods=["GET", "POST"])
@login_required
def add_item():
    # If user reached route via POST (as by submiting form)
    if request.method == "POST":
        name = request.form.get("name").lower()
        price = request.form.get("price")
        nutrition = request.form.get("nutrition")

        # Check the date
        updated = str(date.today())

        # change price from str to float
        price = round(float(price), 2)


        # Ensure user enter item's name
        if not name:
            return render_template("error.html", message="Missing item's name")

        # Check if user forget to enter price
        if not price:
            return render_template("error.html", message="Missing item's price")

        # if nutrition was not filled, define it as 0
        if not nutrition:
            nutrition = 0

        # check if price lower than 0 in case user change html to accept value smaller than 0
        if price < 0:
            return render_template("error.html", message="Price has to be greater than 0")

        # Check if item exist
        check = db.execute("SELECT * FROM items WHERE name = ?", name)
        if check: # or "if len(check) > 0:"" which being used in /register of item planner project

            # Update to item
            db.execute("UPDATE items SET price = ?, nutrition = ?, updated = ? WHERE name = ?", price, nutrition, updated, name)
            return redirect("/")

        # Add item into database
        db.execute("INSERT INTO items(name, price, nutrition, updated) VALUES (?, ?, ?, ?)", name, price, nutrition, updated)

        flash("Item added")

        return redirect("/")


    # If user reached route via GET (as by click link)
    return render_template("add_item.html")


@app.route("/add_formula", methods=["GET", "POST"])
@login_required
def add_formula():

    # If user reached route after submitted form
    if request.method == "POST":

        # Define variables
        name = request.form.get("name")
        material = request.form.get("material")
        quantity = request.form.get("quantity")

        # Check if user enter all required fields
        if not name:
            return render_template("error.html", message="Missing item's name")

        if not material:
            return render_template("error.html", message="Missing material")

        if not quantity:
            return render_template("error.html", message="Missing quantity")

        # Standardize the variables
        name = name.lower()
        material = material.lower()
        quantity = round(float(quantity), 2)

        # Check quantity is valid in case user change html to accept value smaller than 0
        if quantity < 0:
            return render_template("error.html", message="quantity has to be greater than 0")


        # select item and material from database
        item = db.execute("SELECT * FROM items WHERE name = ?", name)

        # Check if there is no match item
        if not item:
            return render_template("error.html", message="item is not available")

        item_id = item[0]['id']

        material = db.execute("SELECT * FROM items WHERE name = ?", material)

        # Check if there is no match material
        if not material:
            return render_template("error.html", message="material is not available")

        material_id = material[0]['id']

        # Add formula into database
        db.execute("INSERT INTO formulas(item_id, material_id, quantity) VALUES (?, ?, ?)", item_id, material_id, quantity)

        # Inform user that formula was added
        flash("Formula added")

        # Redirect user to /
        return redirect("/")

    # If user reached route by clicking link or being redirect
    else:
        items = db.execute("SELECT * FROM items")
        return render_template("add_formula.html", items=items)


@app.route("/pre_update", methods=["POST"])
@login_required
def pre_update():

    """ Let user enter new information for the item """

    id = request.form.get("id")

    if id:

        # Get item's information from database
        items = db.execute("SELECT * FROM items WHERE id = ?", id)

        return render_template("update.html", items=items)


@app.route("/update", methods=["POST"])
@login_required
def update():
    """ Modify item information in database """

    # define variables
    id = request.form.get("id")
    item = (request.form.get("item_name")).lower()
    price = request.form.get("price")
    nutrition = request.form.get("nutrition")
    updated = str(date.today())

    # Get item's information from database
    items = db.execute("SELECT * FROM items WHERE id = ?", id)

    # Get old variables
    old_item = items[0]['name']
    old_price = items[0]['price']
    old_nutrition = items[0]['nutrition']

    # Check which field the user enter
    if not item:
        item = old_item
    if not price:
        price = old_price
    if not nutrition:
        nutrition = old_nutrition


    # round up price, and nutrition
    price = round(float(price), 2)
    nutrition = round(float(nutrition), 0)

    # update new information
    db.execute("UPDATE items SET name = ?, price = ?, nutrition = ?, updated = ? WHERE id = ?", item, price, nutrition, updated, id)

    # inform successfully
    flash("Item updated")

    # Redirect user to index
    return redirect("/")


@app.route("/formula", methods=["POST"])
def formula():
    """ Allow user to check item's formula """

    # Define variable
    id = request.form.get("id")

    # If user click the formula button
    if id:
        materials = db.execute("SELECT name, quantity FROM items JOIN formulas ON items.id = formulas.material_id WHERE item_id = ?", id)

        return render_template("formula.html", materials=materials)


@app.route("/logout")
def logout():
    """ Allow user to log out """
    session.clear()
    return redirect("/")


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():

    # If user reached route by submitting form
    if request.method == "POST":
        name = request.form.get("username")
        old_password = request.form.get("old_password")
        new_password = request.form.get("new_password")
        confirm = request.form.get("new_password2")

        # Check if user enter enough information
        if not name:
            return render_template("error.html", message="Missing name")

        if not old_password:
            return render_template("error.html", message="Missing old password")

        if not new_password:
            return render_template("error.html", message="Missing new password")

        if not confirm:
            return render_template("error.html", message="You need to confirm new password")

        if new_password != confirm:
            return render_template("error.html", message="Passwords don't match")

        check = db.execute("SELECT * FROM users WHERE username = ?", name)

        if not check or not check_password_hash(check[0]['hash'], old_password):
            return render_template("error.html", message="Username or password incorrect")

        # If everything correct, update value of password hash
        db.execute("UPDATE users SET hash = ? WHERE username = ?", generate_password_hash(new_password), name)

        # Inform user
        flash("Password changed!")

        return redirect("/")

    # If user reached route via clicking link
    else:
        return render_template("change_password.html")



# Use web scrapper to pull new update information from https://albiononline.com/en/update
# Use image as link to other round such as Item, Add Item
# Use datalist (lecture 0 36:30) to allow user to choose material instead of enter material name