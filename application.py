import os
import requests
import json

from flask import Flask, session, render_template, request, redirect, url_for, abort
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine("DATABASE_URL")
db = scoped_session(sessionmaker(bind=engine))


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        # Check if user already logged in
        if session.get("user_name") is None:
            return render_template("login.html")
        else:
            return redirect(url_for("welcome"))

    if request.method == "POST":
        # Try to login user
        name = request.form.get("user_name")
        pwd = request.form.get("user_pwd")
        user = db.execute("SELECT * FROM users WHERE name = :name AND password = :password",
                          {"name": name, "password": pwd}).fetchone()

        if user is None:
            return render_template("login.html", error_message="Invalid username or password")
        else:
            session["user_name"] = user.name
            return redirect(url_for("welcome"))


@app.route("/registration", methods=["GET", "POST"])
def registration():
    if request.method == "GET":
        return render_template("register.html")

    elif request.method == "POST":
        # Try to register user
        name = request.form.get("user_name")
        pwd = request.form.get("user_pwd")

        if db.execute("SELECT * FROM users WHERE name = :name", {"name": name}).rowcount == 1:
            return render_template("register.html", error_message="Username is already exists")
        else:
            db.execute("INSERT INTO users (name, password) VALUES (:name, :pwd)", {
                       "name": name, "pwd": pwd})
            db.commit()
            return render_template("login.html", message="Registration successful")


@app.route("/welcome", methods=["GET", "POST"])
def welcome():
    if session.get("user_name") is None:
        return redirect("index")
    elif request.method == "POST":
        # Search the books
        text = request.form.get("text")
        results = db.execute("SELECT isbn, title, author, year FROM books WHERE isbn ILIKE :text OR title ILIKE :text OR author ILIKE :text",
                            {"text": text}).fetchall()
        return render_template("welcome.html", user_name=session["user_name"], results=results, alert_message="Sorry! did not find any book")
    else:
        return render_template("welcome.html", user_name=session["user_name"])


@app.route("/logout")
def logout():
    session["user_name"] = None
    return redirect(url_for("index"))



@app.route("/books/<string:isbn>", methods=["GET", "POST"])
def book(isbn):
    reviews = db.execute(
         "SELECT * FROM reviews WHERE isbn = :isbn", {"isbn": isbn}).fetchall()
    book_info = db.execute(
        "SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
    if request.method == "GET":
        # Show the page
        if session.get("user_name") is None:
            return redirect("index")
        else:
            return render_template("book.html", book=book_info, user_name=session["user_name"], reviews=reviews)

    elif request.method == "POST":
        # Add a review
        # Check if user already did a review for this book
        if db.execute("SELECT * FROM reviews WHERE username = :username AND isbn = :isbn", {"username": session["user_name"], "isbn": isbn}).rowcount > 0:
            return render_template("book.html", book=book_info, user_name=session["user_name"], alert_message="You've already done review", reviews=reviews)
        else:
            rating = request.form.get("rating")
            text = request.form.get("text")
            db.execute("INSERT INTO reviews(rating, text, isbn, username) VALUES (:rating, :text, :isbn, :username)", {
                       "rating": rating, "text": text, "isbn": isbn, "username": session["user_name"]})
            db.commit()
            reviews = db.execute(
                "SELECT * FROM reviews WHERE isbn = :isbn", {"isbn": isbn}).fetchall()

            return render_template("book.html", book=book_info, user_name=session["user_name"], reviews=reviews)

@app.route("/shelf", methods=["GET","POST"])
def shelf():
    if request.method == "GET":
        # Show the page
        if session.get("user_name") is None:
            return redirect("index")
        else:
            reviews = db.execute(
                "SELECT * FROM cart WHERE username = :username", {"username": session["user_name"]}).fetchall()

            return render_template("cart.html", reviews=reviews, user_name=session["user_name"])


@app.route("/cart/<string:isbn>,<string:title>,<string:author>,<int:year>", methods=["GET","POST"])
def cart(isbn, title, author, year):
    if request.method == "GET":
        # Show the page
        if session.get("user_name") is None:
            return redirect("index")
        else:
            db.execute("INSERT INTO cart(isbn, title, author, year, username) VALUES (:isbn, :title, :author, :year, :username)", {
                       "isbn": isbn, "title": title, "author": author, "year": year,"username": session["user_name"] })
            db.commit()
            reviews = db.execute(
                "SELECT * FROM cart WHERE username = :username", {"username": session["user_name"]}).fetchall()

            return render_template("cart.html", reviews=reviews, user_name=session["user_name"])


@app.route("/remove/<string:isbn>", methods=["GET","POST"])
def remove(isbn):
    if request.method == "GET":
        # Show the page
        if session.get("user_name") is None:
            return redirect("index")
        else:
            db.execute("DELETE from cart WHERE isbn = :isbn", {"isbn": isbn})
            db.commit()
            reviews = db.execute(
                "SELECT * FROM cart WHERE username = :username", {"username": session["user_name"]}).fetchall()

            return render_template("cart.html", reviews=reviews, user_name=session["user_name"])


@app.route('/api/<string:isbn>', methods=["GET","POST"])
def api(isbn):
    book_info = db.execute(
        "SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
    if book_info is None:
        return "404 Error - Not Found"
    else:
        result = {
            "title": book_info.title,
            "author": book_info.author,
            "year": book_info.year,
            "isbn": book_info.isbn,
        }
        return json.dumps(result)


@app.route('/api/reviews/<string:isbn>', methods=["GET","POST"])
def apireview(isbn):
    book_info = db.execute(
        "SELECT * FROM reviews WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
    if book_info is None:
        return "404 Error - Not Found"
    else:
        result = {
            "id": book_info.id,
            "rating": book_info.rating,
            "text": book_info.text,
            "isbn": book_info.isbn,
            "username": book_info.username
        }
        return json.dumps(result)
