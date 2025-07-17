import uuid
import sqlite3

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

from recipe_generator import *

app = Flask(__name__)
CORS(app)
DB_PATH = "recipes.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Drop users table to fix schema
    c.execute('DROP TABLE IF EXISTS users')

    c.execute('''
        CREATE TABLE users (
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
    if 'image' not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    image_file = request.files['image']

    if image_file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    filename = secure_filename(image_file.filename)
    save_folder = 'images'
    os.makedirs(save_folder, exist_ok=True)
    image_path = os.path.join(save_folder, filename)
    image_file.save(image_path)

    print(f"Image saved at: {image_path}")

    try:
        gemini_response = get_ingredients_from_image(image_path)

        if gemini_response is None or gemini_response.strip() == "":
            return jsonify({"error": "Failed to generate recipe from image"}), 500

        parts = gemini_response.strip().split(";")
        if len(parts) < 4 or parts[0] == "0":
            return jsonify({"error": "Gemini could not create a recipe from this image"}), 400

        return jsonify({
            "title": parts[0].strip(),
            "description": parts[1].strip(),
            "ingredients": parts[2].split(","),
            "procedures": parts[3].split(",")
        })

    except Exception as e:
        return jsonify({"error": f"Internal error: {str(e)}"}), 500


def idfetcher():
    new_id = str(uuid.uuid4())  # generate UUID string
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO users (id) VALUES (?)', (new_id,))
    conn.commit()
    conn.close()
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

    image_url = f"/{image_path}"
    return jsonify({"image_url": image_url})


@app.route('/get_id', methods=['GET'])
def get_id():
    return jsonify({"user_id": idfetcher()})


@app.route('/create_recipe', methods=['POST'])
def create_recipe():
    data = request.json
    ingredients = data.get('ingredients', [])
    budget = data.get('budget', 0)
    time = data.get('time', 0)
    serves = data.get('serves', 0)
    meal_type = data.get('meal_type', 'dinner')
    user_id = data.get('user_id', None)

    if user_id is None:
        return jsonify({"error": "Missing user_id"}), 400

    try:
        result = get_recipe(ingredients, budget, serves, time, meal_type)
        if result == ["0", "0", "0", "0", "0"]:
            return jsonify({"error": "Could not generate recipe"}), 400

        title, desc, ing, procedures, prompt, image_path = result

        count = 711
        while count > 0:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM recipes WHERE user_id = ? AND title = ?', (user_id, title))
            count = c.fetchone()[0]
            if count > 0:
                conn.close()
                title = newName(title)

        c.execute('''
            INSERT INTO recipes (user_id, title, description, ingredients, procedures, image_prompt, image_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, title, desc, ing, procedures, prompt, image_path))
        conn.commit()
        conn.close()

        return jsonify({
            "title": title,
            "description": desc,
            "ingredients": ing,
            "procedures": procedures,
            "image_prompt": prompt,
            "image_path": image_path
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
        c.execute(
            'SELECT title, description, ingredients, procedures, image_prompt, image_path FROM recipes WHERE user_id = ?',
            (user_id,))
        recipes = c.fetchall()

        recipe_list = [
            {
                "title": r[0],
                "description": r[1],
                "ingredients": r[2],
                "procedures": r[3],
                "image_prompt": r[4],
                "image_path": r[5]
            } for r in recipes
        ]
        return jsonify({"recipes": recipe_list})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_image', methods=['GET'])
def get_image():
    user_id = request.args.get('user_id')
    title = request.args.get('title')

    if user_id == "1" and title == "Simple_Tomato_&_Cheese_Sandwich":
        return jsonify({"success": True})

    else:
        print(f"Request for image with user_id: {user_id}, title: {title}")

        if not user_id or not title:
            return jsonify({"error": "Missing user_id or title"}), 400

        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''
                SELECT image_path FROM recipes WHERE user_id = ? AND title = ?
            ''', (user_id, title.replace("_", " ")))
            result = c.fetchone()
            conn.close()

            print(f"Database result: {result}")

            if result is None:
                return jsonify({"error": f"Image not found for {title}"}), 404

            image_path = result[0]
            print(f"Image path from DB: {image_path}")

            if not os.path.exists(image_path):
                print(f"File does not exist at: {image_path}")
                return jsonify({"error": "File missing on disk"}), 404

            print(f"Sending image from path: {image_path}")
            return send_file(image_path, mimetype='image/png')

        except Exception as e:
            print(f"Error: {str(e)}")
            return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
