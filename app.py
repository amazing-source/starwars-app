from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import bcrypt
import requests
import random
from functools import wraps
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)
app.secret_key = "change_me"

# ENV VARS
DATABASE_URL = os.getenv("DATABASE_URL")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

# SQLAlchemy engine (pg8000 driver auto-detected)
engine = create_engine(DATABASE_URL, echo=False)


def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                email VARCHAR(255),
                role VARCHAR(50) DEFAULT 'user'
            );
        """))

        # Create admin if not exists
        hashed = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()

        conn.execute(text("""
            INSERT INTO users (username, password, email, role)
            VALUES (:u, :p, :e, 'admin')
            ON CONFLICT (username) DO NOTHING;
        """), {"u": "admin", "p": hashed, "e": "admin@starwars.com"})


init_db()


# LOGIN REQUIRED DECORATOR
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


@app.route("/")
def home():
    return render_template("home.html")


# LOGIN
@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"].encode()

        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT * FROM users WHERE username = :u
            """), {"u": username}).fetchone()

        if result and bcrypt.checkpw(password, result.password.encode()):
            session["user_id"] = result.id
            session["username"] = result.username
            session["role"] = result.role
            return redirect(url_for("home"))

        return render_template("login.html", error="Identifiants incorrects")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/users")
@login_required
def users():
    if session.get("role") != "admin":
        return redirect(url_for("home"))

    with engine.begin() as conn:
        rows = conn.execute(text("SELECT * FROM users ORDER BY id")).fetchall()

    return render_template("users.html", users=rows)


@app.route("/users/add", methods=['POST'])
@login_required
def add_user():
    if session.get("role") != "admin":
        return "Unauthorized", 403

    username = request.form["username"]
    password = bcrypt.hashpw(request.form["password"].encode(), bcrypt.gensalt()).decode()
    email = request.form["email"]
    role = request.form.get("role", "user")

    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO users (username, password, email, role)
                VALUES (:u, :p, :e, :r)
            """), {"u": username, "p": password, "e": email, "r": role})
    except IntegrityError:
        pass

    return redirect(url_for("users"))


@app.route("/users/delete/<int:user_id>")
@login_required
def delete_user(user_id):
    if session.get("role") != "admin":
        return redirect(url_for("home"))

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})

    return redirect(url_for("users"))


@app.route("/biography")
@login_required
def biography():
    characters = [
        "Luke Skywalker", "Leia Organa", "Han Solo", "Darth Vader",
        "Obi-Wan Kenobi", "Yoda", "Rey", "Kylo Ren", "Ahsoka Tano",
        "Mace Windu", "Qui-Gon Jinn", "Padmé Amidala", "Anakin Skywalker",
        "Chewbacca", "R2-D2", "C-3PO", "Boba Fett", "Grogu"
    ]
    character = random.choice(characters)
    return render_template("biography.html", character=character)


@app.route("/api/generate_biography", methods=['POST'])
@login_required
def generate_biography():
    character = request.json.get("character")

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "model": "mistral-small-latest",
        "messages": [
            {"role": "user", "content": f"Génère une biographie détaillée de {character}."}
        ],
    }

    response = requests.post("https://api.mistral.ai/v1/chat/completions", json=data, headers=headers)
    result = response.json()

    return jsonify({"biography": result["choices"][0]["message"]["content"]})


@app.route("/story")
@login_required
def story():
    return render_template("story.html")


@app.route("/api/generate_story", methods=['POST'])
@login_required
def generate_story():
    theme = request.json["theme"]

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "model": "mistral-small-latest",
        "messages": [{"role": "user", "content": theme}],
    }

    response = requests.post("https://api.mistral.ai/v1/chat/completions", json=data, headers=headers)
    text_out = response.json()["choices"][0]["message"]["content"]

    return jsonify({"story": text_out})


if __name__ == "__main__":
    app.run()
