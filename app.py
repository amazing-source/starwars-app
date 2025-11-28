# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import os
from functools import wraps
import requests

app = Flask(__name__)
app.secret_key = 'votre_cle_secrete_changez_moi'

# Configuration Mistral AI
MISTRAL_API_KEY = 'lUGD0HL6OAc0Gwk5zVJovjkGDu60nzDc'
MISTRAL_API_URL = 'https://api.mistral.ai/v1/chat/completions'

# Initialisation de la base de données
def init_db():
    conn = sqlite3.connect('starwars.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  email TEXT,
                  role TEXT DEFAULT 'user')''')
    
    # Créer un utilisateur admin par défaut
    try:
        c.execute("INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)",
                  ('admin', 'admin123', 'admin@starwars.com', 'admin'))
    except sqlite3.IntegrityError:
        pass
    
    conn.commit()
    conn.close()

init_db()

# Décorateur pour vérifier la connexion
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Route d'accueil
@app.route('/')
def home():
    return render_template('home.html')

# Route de connexion
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('starwars.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[4]
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="Identifiants incorrects")
    
    return render_template('login.html')

# Route de déconnexion
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# Route de gestion des utilisateurs
@app.route('/users')
@login_required
def users():
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('starwars.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users")
    users_list = c.fetchall()
    conn.close()
    
    return render_template('users.html', users=users_list)

# Ajouter un utilisateur
@app.route('/users/add', methods=['POST'])
@login_required
def add_user():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Non autorisé'}), 403
    
    username = request.form['username']
    password = request.form['password']
    email = request.form['email']
    role = request.form.get('role', 'user')
    
    conn = sqlite3.connect('starwars.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)",
                  (username, password, email, role))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()
    
    return redirect(url_for('users'))

# Supprimer un utilisateur
@app.route('/users/delete/<int:user_id>')
@login_required
def delete_user(user_id):
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('starwars.db')
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('users'))

# Route pour générer une biographie de personnage aléatoire
@app.route('/biography')
@login_required
def biography():
    characters = [
        "Luke Skywalker", "Leia Organa", "Han Solo", "Darth Vader", 
        "Obi-Wan Kenobi", "Yoda", "Rey", "Kylo Ren", "Ahsoka Tano",
        "Mace Windu", "Qui-Gon Jinn", "Padmé Amidala", "Anakin Skywalker",
        "Chewbacca", "R2-D2", "C-3PO", "Boba Fett", "Grogu"
    ]
    import random
    character = random.choice(characters)
    return render_template('biography.html', character=character)

# API pour générer la biographie avec Mistral
@app.route('/api/generate_biography', methods=['POST'])
@login_required
def generate_biography():
    character = request.json.get('character')
    
    headers = {
        'Authorization': f'Bearer {MISTRAL_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    data = {
        'model': 'mistral-small-latest',
        'messages': [
            {
                'role': 'user',
                'content': f'Génère une biographie détaillée et captivante de {character} de Star Wars en français. Inclus son histoire, ses compétences, et son importance dans la saga. Fais environ 200-300 mots.'
            }
        ],
        'temperature': 0.7,
        'max_tokens': 800
    }
    
    try:
        response = requests.post(MISTRAL_API_URL, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        biography_text = result['choices'][0]['message']['content']
        return jsonify({'biography': biography_text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Route pour générer une histoire
@app.route('/story')
@login_required
def story():
    return render_template('story.html')

# API pour générer une histoire avec Mistral
@app.route('/api/generate_story', methods=['POST'])
@login_required
def generate_story():
    theme = request.json.get('theme', '')
    
    headers = {
        'Authorization': f'Bearer {MISTRAL_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    prompt = f'Écris une histoire courte et captivante dans l\'univers Star Wars en français'
    if theme:
        prompt += f' sur le thème suivant : {theme}'
    prompt += '. L\'histoire doit être originale, immersive et faire environ 300-400 mots.'
    
    data = {
        'model': 'mistral-small-latest',
        'messages': [
            {
                'role': 'user',
                'content': prompt
            }
        ],
        'temperature': 0.8,
        'max_tokens': 1200
    }
    
    try:
        response = requests.post(MISTRAL_API_URL, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        story_text = result['choices'][0]['message']['content']
        return jsonify({'story': story_text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run()
