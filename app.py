from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import requests
import os
from dotenv import load_dotenv
from flask_limiter import Limiter

# On charge le fichier secret .env (contenant ta clé API de production sur Render)
load_dotenv()

app = Flask(__name__)

# CORS configuré de manière ouverte et propre pour ton site hébergé sur GitHub Pages
CORS(app, resources={r"/api/*": {"origins": "*"}})

# 📁 CONFIGURATION DE LA BASE DE DONNÉES (Fichier local zenith.db)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///zenith.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 🗃️ STRUCTURE DU GRIMOIRE DE COACH (Modèle SQLite)
class MatchupNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    champion_id = db.Column(db.Integer, unique=True, nullable=False) # ID Riot (ex: 266 pour Aatrox)
    champion_name = db.Column(db.String(50), nullable=True)          # Nom du champion
    note = db.Column(db.Text, nullable=False)                         # Tes précieux conseils de matchup

# 🛡️ PROTECTION ANTI-SPAM COMPATIBLE AVEC LE CLOUD (RENDER / PROXY)
def get_wsgi_remote_addr():
    # Lit l'en-tête de Render pour choper la VRAIE IP du joueur, pas celle du routeur Cloud
    return request.headers.get("X-Forwarded-For", request.remote_addr)

limiter = Limiter(
    key_func=get_wsgi_remote_addr,
    app=app,
    default_limits=["60 per minute"], # Limite élargie pour le grand public
    storage_uri="memory://"
)

# Récupération de la clé API Riot cachée dans les variables d'environnement de Render
RIOT_API_KEY = os.getenv("RIOT_API_KEY")

# 🗺️ MATRICE DE ROUTAGE MONDIALE RIOT GAMES (Pour que ton site fonctionne partout sur terre)
REGION_MAPPING = {
    "euw": "europe", "eune": "europe", "tr": "europe", "ru": "europe", "euw1": "europe",
    "na": "americas", "na1": "americas", "br": "americas", "br1": "americas", "lan": "americas", "las": "americas",
    "kr": "asia", "jp": "asia", "jp1": "asia",
    "oce": "sea", "oc1": "sea", "ph": "sea", "sg": "sea", "th": "sea", "tw": "sea", "vn": "sea"
}

def determine_riot_endpoint(tag_line):
    """Analyse le Tag (ex: EUW, NA1, KR) pour renvoyer le bon serveur continental à requests"""
    clean_tag = str(tag_line).lower().strip()
    return REGION_MAPPING.get(clean_region_extractor(clean_tag), "europe")

def clean_region_extractor(tag):
    # Permet de nettoyer les tags complexes pour correspondre à la matrice (ex: EUW1 -> euw)
    for key in REGION_MAPPING.keys():
        if key in tag:
            return key
    return tag

# =========================================================
# 🛰️ ENDPOINTS OFFICIELS RIOT GAMES (Sécurisés anti-crash)
# =========================================================

@app.route('/api/coach', methods=['GET'])
@limiter.limit("30 per minute")
def get_coach_advice():
    name = request.args.get('game_name', '').strip()
    tag = request.args.get('tag_line', '').strip()

    if not name or not tag:
        return jsonify({"success": False, "error": "Paramètres manquantes (game_name et tag_line requis)"}), 400

    # 🌍 Choix dynamique du continent de communication chez Riot
    routing_continent = determine_riot_endpoint(tag)
    url = f"https://{routing_continent}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{name}/{tag}"
    headers = {"X-Riot-Token": RIOT_API_KEY}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            try:
                return jsonify({"success": True, "data": response.json()})
            except ValueError:
                return jsonify({"success": False, "error": "Riot a répondu avec un format invalide."}), 502
        else:
            return jsonify({"success": False, "error": f"Erreur Riot API: {response.status_code}"}), response.status_code
    except requests.RequestException:
        return jsonify({"success": False, "error": "Le serveur d'authentification Riot est injoignable."}), 504

@app.route('/api/matches', methods=['GET'])
@limiter.limit("30 per minute")
def get_matches():
    puuid = request.args.get('puuid', '').strip()
    region = request.args.get('tag_line', 'euw').strip() # Récupère le tag pour adapter l'historique
    
    if not puuid:
        return jsonify({"success": False, "error": "Identifiant PUUID manquant"}), 400

    routing_continent = determine_riot_endpoint(region)
    url = f"https://{routing_continent}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=5"
    headers = {"X-Riot-Token": RIOT_API_KEY}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            try:
                return jsonify({"success": True, "matchIds": response.json()})
            except ValueError:
                return jsonify({"success": False, "error": "Impossible de décoder l'historique."}), 502
        else:
            return jsonify({"success": False, "error": f"Riot HTTP {response.status_code}"}), response.status_code
    except requests.RequestException:
        return jsonify({"success": False, "error": "Délai d'attente dépassé avec l'API Riot."}), 504

@app.route('/api/match_details', methods=['GET'])
@limiter.limit("40 per minute")
def get_match_details():
    match_id = request.args.get('match_id', '').strip()
    
    if not match_id:
        return jsonify({"success": False, "error": "Match ID manquant"}), 400

    # Les IDs de matchs contiennent le serveur au début (ex: EUW1_6546545). On s'en sert pour router !
    server_prefix = match_id.split('_')[0] if '_' in match_id else "euw"
    routing_continent = determine_riot_endpoint(server_prefix)
    
    url = f"https://{routing_continent}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    headers = {"X-Riot-Token": RIOT_API_KEY}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            try:
                return jsonify({"success": True, "details": response.json()})
            except ValueError:
                return jsonify({"success": False, "error": "Structure de match illisible."}), 502
        else:
            return jsonify({"success": False, "error": f"Riot HTTP {response.status_code}"}), response.status_code
    except requests.RequestException:
        return jsonify({"success": False, "error": "Le serveur de télémétrie Riot est saturé."}), 504


# =========================================================
# 📑 ENDPOINTS DU GRIMOIRE DE COACH (Transactions Sécurisées)
# =========================================================

@app.route('/api/notes/save', methods=['POST'])
def save_note():
    try:
        data = request.get_json()
        if not data or 'champion_id' not in data or 'note' not in data:
            return jsonify({"success": False, "error": "Données manquantes (champion_id et note requis)"}), 400
        
        champ_id = int(data['champion_id'])
        champ_name = str(data.get('champion_name', '')).strip()
        text_note = str(data['note']).strip()

        existing_note = MatchupNote.query.filter_by(champion_id=champ_id).first()

        if existing_note:
            existing_note.note = text_note
            if champ_name: 
                existing_note.champion_name = champ_name
        else:
            new_note = MatchupNote(champion_id=champ_id, champion_name=champ_name, note=text_note)
            db.session.add(new_note)

        # 🛡️ TRANSACTION PROTEGÉE : Si la base est occupée, on évite le crash fatal
        db.session.commit()
        return jsonify({"success": True, "message": "Conseil de matchup enregistré avec succès !"})
        
    except Exception as err:
        db.session.rollback() # On annule la transaction proprement pour débloquer SQLite
        return jsonify({"success": False, "error": f"Erreur critique BDD : {str(err)}"}), 500

@app.route('/api/notes/get', methods=['GET'])
def get_note():
    champ_id = request.args.get('champion_id')
    if not champ_id:
        return jsonify({"success": False, "error": "Paramètre champion_id manquant"}), 400

    try:
        note_obj = MatchupNote.query.filter_by(champion_id=int(champ_id)).first()
        if note_obj:
            return jsonify({"success": True, "note": note_obj.note})
        return jsonify({"success": True, "note": ""})
    except Exception as err:
        return jsonify({"success": False, "error": f"Erreur de lecture BDD : {str(err)}"}), 500


# 🔨 CRÉATION DES TABLES AU DÉMARRAGE SI ABSENTES
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    # Configuration parée pour l'écoute des requêtes distantes sur le cloud de Render
    app.run(host='0.0.0.0', port=5000, debug=True)
