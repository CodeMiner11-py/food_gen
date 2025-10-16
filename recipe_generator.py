import google.generativeai as genai
import os
import uuid
import base64
from PIL import Image

genai.configure(api_key=os.getenv("GOOGLE_TOKEN"))

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

def get_response(prompt):
    chat_session = genai.chat.start(
        model="gemini-2.5-flash-lite",
        messages=[{"author": "user", "content": prompt}]
    )
    return chat_session.message

def get_image_google(prompt, save_path="generated_images.png", size="1024x1024"):
    prompt += str(uuid.uuid4())
    response = genai.images.generate(
        model="gemini-2.5-flash",
        prompt=prompt,
        size=size
    )
    image_bytes = base64.b64decode(response[0].b64_bytes)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "wb") as f:
        f.write(image_bytes)
    return save_path

def get_recipe(ingredients, budget, serves, time, meal_type):
    prompt = f"""Create a response as follows.
You will be given ingredients the user has at home.
You also have the user's budget for extra ingredients.
Answer in five parts separated by semicolons: title; description; ingredients; procedures; image prompt.
Type of meal: {meal_type}.
Ingredients: {', '.join(ingredients)}. Budget: ${budget}. Time: {time} minutes. Serves: {serves}."""
    answer = get_response(prompt).split(';')
    if answer == ["0","0","0","0","0"]:
        return answer
    safe_title = answer[0].replace(" ", "_")
    save_folder = f"images/{safe_title}"
    os.makedirs(save_folder, exist_ok=True)
    image_path = f"{save_folder}/image.png"
    get_image_google(answer[4], image_path)
    return [answer[0], answer[1], answer[2], answer[3], answer[4], image_path]

def get_directories(path):
    with os.scandir(path) as entries:
        return [entry.name for entry in entries if entry.is_dir()]

def get_nutrition_facts(recipe_text):
    prompt = f"""
Analyze the recipe and provide nutrition facts separated by semicolons: totalfat;saturatedfat;transfat;cholesterol;sodium;totalcarbs;dietaryfiber;totalsugar;addedsugar;protein;calories
Recipe: {recipe_text}
"""
    return get_response(prompt)

def get_ingredients_from_image(image_path):
    try:
        image_data = Image.open(image_path)
        prompt = """Create a recipe in five parts separated by semicolons: title; description; ingredients; procedures; 0. Type: dish."""
        response = genai.chat.start(
            model="gemini-2.5-flash-lite",
            messages=[{"author": "user", "content": prompt}],
            image=image_data
        )
        return response.message
    except Exception as e:
        return None

def newName(oldName):
    return get_response("Generate a new, different-sounding title for this recipe. Old name: "+oldName)

def get_shopping_list(need_to_buy):
    prompt = "Estimate the total price in USD of these ingredients:\n"
    for ing in need_to_buy:
        prompt += ing + ",\n"
    prompt += "Just give a number."
    response = get_response(prompt)
    return (need_to_buy, response)
