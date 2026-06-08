from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy  # 📦 Nouvelle pièce maîtresse
import requests
import os
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# On charge le fichier secret .env
load_dotenv()

app = Flask(__name__)
CORS(app)

# 📁 CONFIGURATION DE LA BASE DE DONNÉES (Fichier local zenith.db)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///zenith.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 🗃️ STRUCTURE DU GRIMOIRE DE COACH (Modèle SQLite)
class MatchupNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    champion_id = db.Column(db.Integer, unique=True, nullable=False) # ID de draft Riot (ex: 266 pour Aatrox)
    champion_name = db.Column(db.String(50), nullable=True)          # Nom du champion
    note = db.Column(db.Text, nullable=False)                         # Tes précieux conseils de matchup

# 🛡️ Activation de l'anti-spam
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["30 per minute"],
    storage_uri="memory://"
)

# Récupération de la clé API Riot cachée
RIOT_API_KEY = os.getenv("RIOT_API_KEY")

# =========================================================
# 🛰️ ENDPOINTS OFFICIELS RIOT GAMES
# =========================================================

@app.route('/api/coach', methods=['GET'])
def get_coach_advice():
    name = request.args.get('game_name', '').strip()
    tag = request.args.get('tag_line', '').strip()

    if not name or not tag:
        return jsonify({"success": False, "error": "Paramètres invalides"}), 400

    url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{name}/{tag}"
    headers = {"X-Riot-Token": RIOT_API_KEY}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return jsonify({"success": True, "data": response.json()})
        else:
            return jsonify({"success": False, "error": f"Erreur Riot: {response.status_code}"}), response.status_code
    except requests.RequestException:
        return jsonify({"success": False, "error": "Erreur de connexion"}), 502

@app.route('/api/matches', methods=['GET'])
def get_matches():
    puuid = request.args.get('puuid')
    if not puuid:
        return jsonify({"success": False, "error": "PUUID manquant"}), 400

    url = f"https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=5"
    headers = {"X-Riot-Token": RIOT_API_KEY}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return jsonify({"success": True, "matchIds": response.json()})
        else:
            return jsonify({"success": False, "error": f"Erreur Riot: {response.status_code}"}), response.status_code
    except requests.RequestException:
        return jsonify({"success": False, "error": "Erreur de connexion"}), 502

@app.route('/api/match_details', methods=['GET'])
def get_match_details():
    match_id = request.args.get('match_id')
    if not match_id:
        return jsonify({"success": False, "error": "Match ID manquant"}), 400

    url = f"https://europe.api.riotgames.com/lol/match/v5/matches/{match_id}"
    headers = {"X-Riot-Token": RIOT_API_KEY}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return jsonify({"success": True, "details": response.json()})
        else:
            return jsonify({"success": False, "error": f"Erreur Riot: {response.status_code}"}), response.status_code
    except requests.RequestException:
        return jsonify({"success": False, "error": "Erreur de connexion"}), 502


# =========================================================
# 📑 ENDPOINTS DU GRIMOIRE DE COACH (Base de données locale)
# =========================================================

@app.route('/api/notes/save', methods=['POST'])
def save_note():
    data = request.get_json()
    if not data or 'champion_id' not in data or 'note' not in data:
        return jsonify({"success": False, "error": "Données manquantes (champion_id et note requis)"}), 400
    
    champ_id = int(data['champion_id'])
    champ_name = data.get('champion_name', '')
    text_note = data['note'].strip()

    # Recherche si une note existe déjà pour ce champion
    existing_note = MatchupNote.query.filter_by(champion_id=champ_id).first()

    if existing_note:
        # On met à jour la note existante
        existing_note.note = text_note
        if champ_name: 
            existing_note.champion_name = champ_name
    else:
        # On crée une nouvelle ligne dans la table
        new_note = MatchupNote(champion_id=champ_id, champion_name=champ_name, note=text_note)
        db.session.add(new_note)

    db.session.commit()
    return jsonify({"success": True, "message": "Conseil de matchup enregistré avec succès !"})

@app.route('/api/notes/get', methods=['GET'])
def get_note():
    champ_id = request.args.get('champion_id')
    if not champ_id:
        return jsonify({"success": False, "error": "Paramètre champion_id manquant"}), 400

    note_obj = MatchupNote.query.filter_by(champion_id=int(champ_id)).first()
    
    if note_obj:
        return jsonify({"success": True, "note": note_obj.note})
    else:
        # Si on n'a pas encore écrit de note pour ce champion, on renvoie du texte vide
        return jsonify({"success": True, "note": ""})


# 🔨 CRÉATION DES TABLES AU DÉMARRAGE SI ABSENTES
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
