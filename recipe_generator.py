import os
import requests
import uuid
from PIL import Image

TEXT_WORKER_URL = "https://kidslearninglab-text-only.nameless-cherry-998c.workers.dev"

# -----------------------------
# CORE TEXT CALL
# -----------------------------
def get_response(prompt):
    try:
        response = requests.post(
            TEXT_WORKER_URL,
            json={"prompt": prompt},
            timeout=30
        )
        response.raise_for_status()

        data = response.json()

        if "response" not in data:
            return ""

        return data["response"].strip()

    except Exception:
        return ""


# -----------------------------
# IMAGE GENERATION (UNCHANGED)
# -----------------------------
def get_image_pollinations(prompt, save_path="generated_images.png"):
    prompt += str(uuid.uuid4())
    formatted_prompt = prompt.replace(" ", "-")
    url = f"https://image.pollinations.ai/prompt/{formatted_prompt}"

    try:
        response = requests.get(url)
        response.raise_for_status()

        if "image" not in response.headers.get("Content-Type", ""):
            return None

        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'wb') as f:
            f.write(response.content)

        return save_path
    except Exception:
        return None


def crop_bottom(image_path, pixels_to_crop=60):
    try:
        img = Image.open(image_path)
        width, height = img.size

        if height <= pixels_to_crop:
            return None

        cropped_img = img.crop((0, 0, width, height - pixels_to_crop))
        cropped_img.save(image_path)
        return cropped_img
    except Exception:
        return None


crop_bottom_pixels = crop_bottom


# -----------------------------
# RECIPE GENERATION
# -----------------------------
def get_recipe(ingredients, budget, serves, time, meal_type):
    prompt = f"""You are a recipe generator. Generate exactly one string with five fields in this order, separated strictly by semicolons ;:

title;description;ingredients;procedures;imagedescription

Rules:

title: short clear title
description: brief summary
ingredients: comma separated only
procedures: comma separated full sentences only
imagedescription: short visual description

No extra text. No formatting. No explanation.

User data:
Ingredients available: {ingredients}
Budget: {budget}
Serves: {serves}
Time: {time}
Meal type: {meal_type}
"""

    answer_text = get_response(prompt)

    if not answer_text:
        return ["0", "0", "0", "0", "0"]

    parts = answer_text.split(";")

    if len(parts) < 5:
        return ["0", "0", "0", "0", "0"]

    title = parts[0].strip()
    desc = parts[1].strip()
    ing = parts[2].strip()
    procedures = parts[3].strip()
    image_desc = parts[4].strip()

    safe_title = title.replace(" ", "_")
    save_folder = f"images/{safe_title}"
    os.makedirs(save_folder, exist_ok=True)
    image_path = f"{save_folder}/image.png"

    get_image_pollinations(image_desc, image_path)
    crop_bottom_pixels(image_path, 60)

    return [title, desc, ing, procedures, image_desc, image_path]


# -----------------------------
# NUTRITION FACTS
# -----------------------------
def get_nutrition_facts(recipe_text):
    prompt = f"""
Analyze this recipe and estimate nutrition facts.
Return exactly:

totalfat;saturatedfat;transfat;cholesterol;sodium;totalcarbs;dietaryfiber;totalsugar;addedsugar;protein;calories

No explanation. No ranges.

Recipe:
{recipe_text}
"""
    return get_response(prompt)


# -----------------------------
# TITLE RENAMER
# -----------------------------
def newName(oldName):
    prompt = f"Generate a new different sounding recipe title. Return only the title. Old title: {oldName}"
    return get_response(prompt)


# -----------------------------
# SHOPPING LIST COST
# -----------------------------
def get_shopping_list(need_to_buy):
    prompt = "Estimate total US grocery cost of these ingredients. Return only a number.\n"
    for ing in need_to_buy:
        prompt += ing + ",\n"

    response = get_response(prompt)
    return (need_to_buy, response)


# -----------------------------
# REMOVE GEMINI IMAGE VISION
# -----------------------------
def get_ingredients_from_image(image_path):
    return None