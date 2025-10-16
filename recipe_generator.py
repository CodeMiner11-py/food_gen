import os
import uuid
from PIL import Image
from io import BytesIO
import google.generativeai as genai

tokens = type("EmptyObject", (), {})()
tokens.google_token = os.getenv("GOOGLE_TOKEN")
genai.configure(api_key=tokens.google_token)

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

def get_response(prompt):
    model = genai.GenerativeModel(model_name="gemini-2.5-flash-lite")
    chat_session = model.start_chat(
        history=[{"role": "user", "parts": [prompt]}]
    )
    response = chat_session.send_message(prompt)
    return response.text

def get_image_google(prompt, save_path="generated_images.png"):
    import base64
    from io import BytesIO
    from PIL import Image
    prompt += str(uuid.uuid4())
    response = genai.images.generate(
        model="gemini-2.5-flash",
        prompt=prompt,
        size="1024x1024"
    )
    image_bytes = base64.b64decode(response[0].b64_bytes)
    img = Image.open(BytesIO(image_bytes))
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    img.save(save_path)
    return save_path


def get_recipe(ingredients, budget, serves, time, meal_type):
    prompt = f"""Create a response as follows.
You will be given ingredients the user has at home.
You will also be given the user's budget for how many extra ingredients they can buy.
Answer in five parts, separated by semicolons.
The first part is a title for the recipe. Vary this each time, even for the same dish.
The second part is a friendly description of the dish, along with the time it takes and how many it serves.
The third part is the ingredients needed, separated by commas (,) (no spaces between commas, but put spaces in the ingredient names as usual). Do not include ingredient numbers. Extra ingredients should fit within the budget. This should not include the ingredients at home. Make sure you use measurements.
The fourth part is the procedures (multiple) to make the dish, separated by periods (.) Do not include procedure numbers. Include the full procedures, and don't stop at the first one, otherwise the cook will be unhappy. 
The fifth part is a description of what the final dish looks like (including its name) that you would give to an image generator to generate an image. Make sure it's short and to the point, and it's a generator that does not know many different types of foods, so explain the food while keeping it short. For example, for a ketchup-mayonaisse dip, tell it to create an image of a cup with orange dip in it.
Format: title;description;ingredients;procedures;image.
If you cannot create a meal following these criteria, simply return: 0;0;0;0;0.
The type of meal requested is a {meal_type}.

Try to follow this Tip: Try not to include 'Quick' or 'Hearty' or 'Speedy' or any other adjective as the first word in the title.

Ingredients the user has at home are: {', '.join(ingredients)}.
User's budget: ${budget}
The user has {time} minutes to make this meal.
The user needs to serve {serves} people.

PLEASE MAKE SURE YOU FOLLOW THESE CRITERIA. THIS INFORMATION IS CRUCIAL FOR OUR APPLICATION."""
    answer = get_response(prompt).split(';')
    if answer == ["0", "0", "0", "0", "0"]:
        return answer
    safe_title = answer[0].replace(" ", "_")
    save_folder = f"images/{safe_title}"
    os.makedirs(save_folder, exist_ok=True)
    image_path = f"{save_folder}/image.png"
    get_image_google(answer[4], image_path)
    return [answer[0].strip('\n'), answer[1], answer[2], answer[3], answer[4], image_path]

def get_directories(path):
    with os.scandir(path) as entries:
        return [entry.name for entry in entries if entry.is_dir()]

def get_nutrition_facts(recipe_text):
    prompt = f"""
Your job is to analyze the recipe above and estimate the nutrition facts of it combined.
Please separate your response into the following parts. Use semicolons (;) to separate your response.
1: Total Fat
2: Saturated Fat
3: Trans Fat
4: Cholesterol
5: Sodium
6: Total Carbs
7: Dietary Fiber
8: Total Sugars
9: Added Sugars
10: Protein
11: Total Calories
Your response should be formatted as such:
totalfat;saturatedfat;transfat;cholesterol;sodium;totalcarbs;dietaryfiber;totalsugar;addedsugar;protein;calories
PLEASE TRY YOUR BEST and align these nutrition facts with the current nutrition of these ingredients in the US.
THIS INFORMATION is vital for our code.
Even if you can't give a complete answer, please try your best.
PLEASE DO NOT SPEAK ANY TEXT OTHER THAN THE FORMATTED NUTRITION RESPONSE. THIS WILL BREAK THE CODE.
DO NOT INCLUDE SOMETHING LIKE 5-10 MG. JUST SAY 7.5 MG AS AN AVERAGE. DO NOT SPEAK RANGES.
Nutritional facts should be given with their appropriate measurement units, like cal for calories or mg for sodium.
Thanks a lot for you complying.
The recipe is below, and is structured into title;description;ingredients;procedure;random. Ignore the last 'random' part:
{recipe_text}
"""
    return get_response(prompt)

def get_ingredients_from_image(image_path):
    try:
        model = genai.GenerativeModel(model_name="gemini-2.5-flash-lite")
        image_data = Image.open(image_path)
        prompt = """Create a recipe for this food item that follows the below criteria:

Answer in five parts, separated by semicolons.
The first part is a title of the recipe.
The second part is a friendly description of the dish, along with the time it takes and how many it serves.
The third part is the ingredients needed, separated by period symbols (.) (no spaces between period symbols). Do not include ingredient numbers. Make sure you use measurements. DO NOT INCLUDE the ingredients already at home.
The fourth part is the procedures to make the dish, separated by period symbols (.) (no spaces between period symbols). Do not include procedure numbers.
The fifth part is a 0. Just enter a 0.
Format: title;description;ingredients;procedures;0.
If you cannot create a meal following these criteria, simply return: 0;0;0;0;0.
The type of meal requested is a dish.

"""
        response = model.generate_content([prompt, image_data], generation_config=generation_config)
        return response.text
    except Exception as e:
        print(f"Gemini Vision error: {e}")
        return None

def newName(oldName):
    return get_response("Please generate a new, different-sounding title for this recipe. Give your response as just the title please. The old name is: "+oldName)

def get_shopping_list(need_to_buy):
    prompt = """What is the price in US dollars of the following ingredients combined? Estimate the prices for each ingredient. Measurements are given. Ingredients are separated by the comm a symbol (,). Please give your best estimate considering typical grocery prices, without a description and just a value please.
"""
    for ing in need_to_buy:
        prompt += ing + ",\n"
    prompt += "\nJust give your response as a value without a dollar sign. Just a number."
    response = get_response(prompt)
    return (need_to_buy, response)