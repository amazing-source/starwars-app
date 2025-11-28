from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import psycopg2
import psycopg2.extras
import bcrypt
import requests
from functools import wraps
import random

app = Flask(__name__)
app.secret_key = 'votre_cle_secrete_changez_moi'

# Configuration Mistral
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_API_URL = 'https://api.mistral.ai/v1/chat/completions'

# Connexion PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL")


def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # Create USERS table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            email VARCHAR(255),
            role VARCHAR(50) DEFAULT 'user'
        )
    """)

    # Insert admin user if not exists
    hashed = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()

    cur.execute("""
        INSERT INTO users (username, password, email, role)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (username) DO NOTHING
    """, ("admin", hashed, "admin@starwars.com", "admin"))

    conn.commit()
    conn.close()


init_db()


# LOGIN REQUIRED DECORATOR
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


@app.route('/')
def home():
    return render_template("home.html")


# LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password'].encode()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cur.fetchone()
        conn.close()

        if user and bcrypt.checkpw(password, user["password"].encode()):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("home"))

        return render_template("login.html", error="Identifiants incorrects")

    return render_template("login.html")


# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("home"))


# USERS PAGE
@app.route('/users')
@login_required
def users():
    if session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users ORDER BY id")
    users_list = cur.fetchall()
    conn.close()

    return render_template("users.html", users=users_list)


# ADD USER
@app.route('/users/add', methods=['POST'])
@login_required
def add_user():
    if session.get("role") != "admin":
        return jsonify({"error": "Non autorisé"}), 403

    username = request.form['username']
    password = request.form['password'].encode()
    email = request.form['email']
    role = request.form.get("role", "user")

    hashed = bcrypt.hashpw(password, bcrypt.gensalt()).decode()

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO users (username, password, email, role)
            VALUES (%s, %s, %s, %s)
        """, (username, hashed, email, role))
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        pass

    conn.close()
    return redirect(url_for("users"))


# DELETE USER
@app.route('/users/delete/<int:user_id>')
@login_required
def delete_user(user_id):
    if session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("users"))


# RANDOM CHARACTER PAGE
@app.route('/biography')
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


# GENERATE BIOGRAPHY (API)
@app.route('/api/generate_biography', methods=['POST'])
@login_required
def generate_biography():
    character = request.json.get("character")

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "mistral-small-latest",
        "messages": [
            {"role": "user", "content": f"Génère une biographie détaillée de {character}."}
        ]
    }

    response = requests.post(MISTRAL_API_URL, json=data, headers=headers)
    result = response.json()
    return jsonify({"biography": result["choices"][0]["message"]["content"]})


# STORY PAGE
@app.route('/story')
@login_required
def story():
    return render_template("story.html")


@app.route('/api/generate_story', methods=['POST'])
@login_required
def generate_story():
    theme = request.json.get("theme", "")

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"Histoire Star Wars sur le thème : {theme}"

    data = {
        "model": "mistral-small-latest",
        "messages": [{"role": "user", "content": prompt}]
    }

    response = requests.post(MISTRAL_API_URL, json=data, headers=headers)
    result = response.json()

    return jsonify({"story": result["choices"][0]["message"]["content"]})


if __name__ == "__main__":
    app.run()
