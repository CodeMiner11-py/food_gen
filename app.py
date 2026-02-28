from io import BytesIO

from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import sqlite3, base64

import requests
from flask import current_app

from flask import Flask, request, jsonify, send_file, make_response
from flask_cors import CORS

from recipe_generator import *

app = Flask(__name__)

app.config['SPOTIFY_CLIENT_ID'] = os.getenv('SPOTIFY_CLIENT_ID')
app.config['SPOTIFY_CLIENT_SECRET'] = os.getenv('SPOTIFY_CLIENT_SECRET')
app.config['SPOTIFY_SHOW_ID'] = "7C7zL1MoVdOjUgxQyhO6rQ"
CORS(app)
DB_PATH = "recipes.db"

@app.route("/")
def home():
    return """
    <html>
        <head>
            <meta http-equiv="refresh" content="3;url=https://kidslearninglab.com">
            <title>Loading...</title>
            <style>
                body {
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    font-family: Arial, sans-serif;
                    background-color: #f0f0f0;
                }
                h1 {
                    font-size: 5em;
                    color: #333;
                }
            </style>
        </head>
        <body>
            <h1>Loading...</h1>
        </body>
    </html>
    """

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"message": "Pong!"})

@app.route("/example/get", methods=['GET'])
def example_get():
    return jsonify({"message": "Hello there!", "status": "API working"})

@app.route("/verify_guest", methods=['GET'])
def verifyguest():
    username = request.args.get("username", "")
    password = request.args.get("password", "")
    users_dict = {"MsLevonius": ("Merryhill", "1")}
    if username in users_dict:
        if users_dict[username][0] == password:
            return jsonify({"status": users_dict[username][0]})
    return jsonify({"status": "0"})

@app.route('/api/spotify-episodes', methods=['GET'])
def spotify_episodes():
    show_id = current_app.config.get('SPOTIFY_SHOW_ID', '7C7zL1MoVdOjUgxQyhO6rQ')
    try:
        access_token = get_spotify_access_token()
    except Exception as e:
        return jsonify({"error": f"Failed to get Spotify access token: {str(e)}"}), 500

    episodes = []
    url = f'https://api.spotify.com/v1/shows/{show_id}/episodes?limit=50'
    headers = {'Authorization': f'Bearer {access_token}'}

    try:
        while url:
            res = requests.get(url, headers=headers)
            res.raise_for_status()
            data = res.json()
            episodes.extend(data['items'])
            url = data.get('next')

        mapped = [{'title': ep['name'], 'spotifyId': ep['id']} for ep in episodes]
        return jsonify(mapped)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch episodes from Spotify API: {str(e)}"}), 500

@app.route("/get_response", methods=["GET"])
def get_response_from_ai():
    prompt = request.args.get("prompt", "")
    return get_response(prompt)

def get_spotify_access_token():
    client_id = current_app.config.get('SPOTIFY_CLIENT_ID')
    client_secret = current_app.config.get('SPOTIFY_CLIENT_SECRET')
    if not client_id or not client_secret:
        raise Exception("Spotify client ID or secret not configured")

    auth_str = f"{client_id}:{client_secret}"
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()

    headers = {
        'Authorization': f'Basic {b64_auth_str}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {'grant_type': 'client_credentials'}
    response = requests.post('https://accounts.spotify.com/api/token', headers=headers, data=data)
    response.raise_for_status()
    return response.json()['access_token']

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Create users table only if it doesn't exist
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS recipes (
            user_id TEXT,
            title TEXT,
            description TEXT,
            ingredients TEXT,
            procedures TEXT,
            image_prompt TEXT,
            image_path TEXT
        )
    ''')

    conn.commit()
    conn.close()


init_db()


def get_next_user_id():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT MAX(id) FROM users')
    result = c.fetchone()
    max_id = result[0] if result[0] is not None else 0
    next_id = max_id + 1
    conn.close()
    return next_id


from flask import request, jsonify
from werkzeug.utils import secure_filename
import os

WORKER_URL = "https://foodgenimage.kidslearninglab099.workers.dev/"
WORKER_API_KEY = "bob"  # placeholder

@app.route("/generate_image", methods=["POST"])
def generate_image():
    data = request.get_json(force=True)
    if not data or "prompt" not in data:
        return {"error": "Missing 'prompt' in JSON"}, 400

    prompt = data["prompt"]

    try:
        # Call your Cloudflare Worker
        response = requests.post(
            WORKER_URL,
            headers={
                "Authorization": f"Bearer {WORKER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={"prompt": prompt},
            timeout=30
        )

        if response.status_code != 200:
            return {"error": f"Worker failed: {response.text}"}, response.status_code

        # response.content is raw JPEG bytes
        return send_file(
            BytesIO(response.content),
            mimetype="image/jpeg",
            as_attachment=False,
            download_name="generated.jpg"
        )

    except Exception as e:
        return {"error": str(e)}, 500

@app.route("/example/post", methods=['POST'])
def example_post():
    data = request.get_json(force=True)
    name = data['name']
    return jsonify({"response": f"Hello there {name}! Thanks for buying this book!"})

@app.route('/get_facts', methods=['POST'])
def get_facts():
    data = request.get_json(force=True)
    if not data or 'recipe_text' not in data:
        return jsonify({"error": "Invalid input"}), 400

    recipe = data['recipe_text']
    facts_string = get_nutrition_facts(recipe)

    keys = [
        "totalfat", "saturatedfat", "transfat", "cholesterol", "sodium",
        "totalcarbs", "dietaryfiber", "totalsugar", "addedsugar", "protein", "calories"
    ]

    if not facts_string:
        return jsonify({"error": "No facts returned"}), 500

    values = facts_string.split(";")
    if len(values) != len(keys):
        return jsonify({"error": "Unexpected facts format"}), 500

    facts_dict = dict(zip(keys, values))
    facts_dict["calories"] = facts_dict["calories"].strip()
    facts_dict["totalfat"] = facts_dict["totalfat"].strip()

    return jsonify({"facts": facts_dict})

@app.route('/scan_recipe', methods=['POST'])
def scan_recipe():
    user_id = request.form.get('user_id')  # Optional user_id

    if 'image' not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    image_file = request.files['image']

    if image_file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Save with unique filename to avoid collisions
    filename = secure_filename(image_file.filename)
    unique_filename = f"{uuid.uuid4()}_{filename}"
    save_folder = 'images'
    os.makedirs(save_folder, exist_ok=True)
    image_path = os.path.join(save_folder, unique_filename)
    image_file.save(image_path)

    try:
        gemini_response = get_ingredients_from_image(image_path)

        if not gemini_response or gemini_response.strip() == "":
            return jsonify({"error": "Maximum image scanning quota reached daily! You can create free ingredient-based recipes."}), 500

        parts = gemini_response.strip().split(";")
        if len(parts) < 4 or parts[0] == "0":
            return jsonify({"error": "Gemini could not create a recipe from this image"}), 400

        title = parts[0].strip()
        description = parts[1].strip()
        ingredients = [i.strip() for i in parts[2].split(",")]
        procedures = [p.strip() for p in parts[3].split(",")]

        # Save recipe in DB if user_id provided
        if user_id:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()

            # Make title unique per user
            original_title = title
            suffix = 1
            while True:
                c.execute('SELECT COUNT(*) FROM recipes WHERE user_id = ? AND title = ?', (user_id, title))
                count = c.fetchone()[0]
                if count == 0:
                    break
                title = f"{original_title} ({suffix})"
                suffix += 1

            image_prompt = ""  # You can add prompt logic if available

            c.execute('''
                INSERT INTO recipes (user_id, title, description, ingredients, procedures, image_prompt, image_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, title, description, ",".join(ingredients), ",".join(procedures), image_prompt, image_path))
            conn.commit()
            conn.close()

        return jsonify({
            "title": title,
            "description": description,
            "ingredients": ingredients,
            "procedures": procedures
        })

    except Exception as e:
        return jsonify({"error": f"Internal error: {str(e)}"}), 500


def idfetcher():
    new_id = str(uuid.uuid4())  # generate UUID string
    return new_id


@app.route('/pollinate', methods=['POST'])
def pollinate():
    data = request.get_json(force=True)
    if not data or 'prompt' not in data:
        return jsonify({"error": "Missing prompt"}), 400

    prompt = data['prompt']
    image_filename = f"images/{uuid.uuid4()}.png"
    os.makedirs(os.path.dirname(image_filename), exist_ok=True)

    image_path = get_image_pollinations(prompt, image_filename)
    if not image_path:
        return jsonify({"error": "Image generation failed"}), 500

    crop_result = crop_bottom(image_path, 60)
    if crop_result is None:
        return jsonify({"error": "Image cropping failed"}), 500

# Instead of returning the image directly, return the filename
    return jsonify({"filename": os.path.basename(image_path)})

from flask import send_from_directory


@app.route('/image_return', methods=['GET'])
def image_return():
    filename = request.args.get('filename')
    if not filename:
        return jsonify({"error": "Missing filename parameter"}), 400

    images_dir = os.path.join(os.getcwd(), 'images')
    file_path = os.path.join(images_dir, filename)

    if not os.path.isfile(file_path):
        return jsonify({"error": "File not found"}), 404

    return send_from_directory(images_dir, filename)


@app.route('/get_id', methods=['GET'])
def get_id():
    return jsonify({"user_id": idfetcher()})

@app.route('/reset_db')
def reset_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('DROP TABLE IF EXISTS users')
        c.execute('DROP TABLE IF EXISTS recipes')
        conn.commit()
        conn.close()
        init_db()
        return "Tables dropped, DB reset"
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/create_recipe', methods=['POST'])
def create_recipe():
    data = request.json
    user_id = data.get('user_id')
    ingredients = data.get('ingredients', [])
    budget = data.get('budget', 0)
    time_val = data.get('time', 0)
    serves = data.get('serves', 0)
    meal_type = data.get('meal_type', 'dinner')

    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    try:
        # Generate the recipe using your Gemini logic
        title, desc, ing, procedures, prompt, _ = get_recipe(ingredients, budget, serves, time_val, meal_type)

        if result := [title, desc, ing, procedures, prompt]:
            if all(x == "0" for x in result):
                return jsonify({"error": "Could not generate recipe"}), 400

        if not prompt:
            return jsonify({"error": "Recipe returned no prompt for image"}), 500

        # Generate unique filename for AI image
        image_filename = f"images/{uuid.uuid4()}.jpg"
        os.makedirs(os.path.dirname(image_filename), exist_ok=True)

        # Call Cloudflare Worker to generate image
        response = requests.post(
            WORKER_URL,
            headers={
                "Authorization": f"Bearer {WORKER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={"prompt": prompt},
            timeout=30
        )

        if response.status_code != 200:
            return jsonify({"error": f"Worker failed: {response.text}"}), response.status_code

        with open(image_filename, "wb") as f:
            f.write(response.content)

        # Make title unique per user
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        original_title = title
        suffix = 1
        while True:
            c.execute('SELECT COUNT(*) FROM recipes WHERE user_id = ? AND title = ?', (user_id, title))
            count = c.fetchone()[0]
            if count == 0:
                break
            title = f"{original_title} ({suffix})"
            suffix += 1

        # Insert recipe with image into DB
        c.execute('''
            INSERT INTO recipes (user_id, title, description, ingredients, procedures, image_prompt, image_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, title, desc, ing, procedures, prompt, image_filename))
        conn.commit()
        conn.close()

        return jsonify({
            "title": title,
            "description": desc,
            "ingredients": ing,
            "procedures": procedures,
            "image_prompt": prompt,
            "image_path": image_filename
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route('/get_recipes', methods=['GET'])
def get_recipes():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            SELECT title, description, ingredients, procedures, image_prompt, image_path
            FROM recipes
            WHERE user_id = ?
        ''', (user_id,))
        recipes = c.fetchall()
        conn.close()

        recipe_list = [
            {
                "title": r[0],
                "description": r[1],
                "ingredients": r[2] if isinstance(r[2], str) else "",
                "procedures": r[3] if isinstance(r[3], str) else "",
                "image_prompt": r[4],
                "image_path": r[5]
            } for r in recipes
        ]

        return jsonify({"recipes": recipe_list})

    except Exception as e:
        print(f"Error in get_recipes: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/get_image', methods=['GET'])
def get_image():
    user_id = request.args.get('user_id')
    title = request.args.get('title')
    title = title.replace("_", " ").strip()

    if not user_id or not title:
        return jsonify({"error": "Missing user_id or title"}), 400

    print(f"Request for image with user_id: {user_id}, title: {title}")

    try:
        # Main lookup: by user_id and title
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT image_path FROM recipes WHERE user_id = ? AND title = ?', (user_id, title))
        result = c.fetchone()
        conn.close()

        if result:
            image_path = result[0]
            print(f"Image path from DB: {image_path}")

            if os.path.exists(image_path):
                print(f"Sending image from path: {image_path}")
                if os.path.exists(image_path):
                    mimetype = 'image/jpeg' if image_path.lower().endswith(('.jpg', '.jpeg')) else 'image/png'
                    response = make_response(send_file(image_path, mimetype=mimetype))
                    response.headers['Access-Control-Allow-Origin'] = "*"
                    return response
            else:
                print(f"File does not exist at: {image_path}")
                return jsonify({"error": "File missing on disk"}), 404

        # Fallback: check by title only (ignore user_id)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT title FROM recipes')
        available_titles = [row[0].strip() for row in c.fetchall()]
        conn.close()

        if title in available_titles:
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute('SELECT image_path FROM recipes WHERE title = ?', (title,))
                sql_return = c.fetchone()
                conn.close()

                if sql_return:
                    fallback_path = sql_return[0]
                    if os.path.exists(fallback_path):
                        print(f"Fallback image found: {fallback_path}")
                        response = make_response(send_file(fallback_path, mimetype='image/png'))
                        response.headers['Access-Control-Allow-Origin'] = "*"
                        return response
                    else:
                        print(f"Fallback file does not exist: {fallback_path}")
                        return jsonify({"error": "Fallback image missing"}), 404

                return jsonify({"error": "Title matched, but no image_path"}), 404

            except Exception as e:
                print(f"Error in fallback block: {str(e)}")
                return jsonify({"error": str(e)}), 500

        # No match at all
        return jsonify({
            "error": f"Image not found for {title}",
            "available_titles": available_titles
        }), 404

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

