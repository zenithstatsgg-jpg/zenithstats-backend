from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# On charge le fichier secret .env
load_dotenv()

app = Flask(__name__)
CORS(app)

# 🛡️ Activation de l'anti-spam (Enregistre les abus dans la mémoire du serveur)
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["30 per minute"],  # Limite globale : max 30 requêtes par minute par personne
    storage_uri="memory://"
)

# On récupère la clé de manière cachée
RIOT_API_KEY = os.getenv("RIOT_API_KEY")

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
    from flask import Flask, jsonify, request
from flask_cors import CORS  # Prépare l'accès public

app = Flask(__name__)
CORS(app)  # Permet à n'importe quel navigateur sur le web de lire ton API de statistiques