import google.generativeai as genai
import os
import requests
import uuid


class EmptyObject:
    def __init__(self):
        pass


tokens = EmptyObject()
tokens.google_token = os.getenv("GOOGLE_TOKEN")

from PIL import Image

api_token = tokens.google_token

genai.configure(api_key=api_token)

# Create the model
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash-lite",
)


def get_response(prompt):
    chat_session = model.start_chat(
        history=[
            {
                "role": "user",
                "parts": [prompt],
            },
        ]
    )

    response = chat_session.send_message(prompt)
    return response.text


image_generation_model_name = "gemini-2.0-flash-exp-image-generation"
image_generation_model = genai.GenerativeModel(model_name=image_generation_model_name)

def get_image_pollinations(prompt, save_path="generated_images.png"):
    """Generates an image from a text prompt using Pollinations AI."""
    prompt += str(uuid.uuid4())  # Ensure unique prompts to bypass caching
    formatted_prompt = prompt.replace(" ", "-")
    url = f"https://image.pollinations.ai/prompt/{formatted_prompt}"
    try:
        response = requests.get(url)
        response.raise_for_status()

        # Check if it's an image
        if "image" not in response.headers["Content-Type"]:
            print(f"Error: The URL did not return an image, but a {response.headers['Content-Type']} file.")
            return None

        image_save_path = save_path
        os.makedirs(os.path.dirname(image_save_path), exist_ok=True)
        with open(image_save_path, 'wb') as f:
            f.write(response.content)

        print(f"Image saved at: {image_save_path}")  # Log image save path
        return image_save_path
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None



def crop_bottom(image_path, pixels_to_crop=60):
    """
    Crops the bottom portion of an image and saves it to the same path.

    Args:
        image_path: Path to the image file.
        pixels_to_crop: Number of pixels to crop from the bottom.

    Returns:
        A PIL Image object with the bottom cropped, or None if an error occurs.
    """
    try:
        img = Image.open(image_path)
        width, height = img.size

        if height <= pixels_to_crop:
            print("Error: Cannot crop more pixels than the image's height.")
            return None

        cropped_img = img.crop((0, 0, width, height - pixels_to_crop))

        # Extract directory and filename for saving
        directory, filename = os.path.split(image_path)
        name, ext = os.path.splitext(filename)
        cropped_filename = os.path.join(directory, f"{name}{ext}")

        cropped_img.save(cropped_filename)
        return cropped_img

    except FileNotFoundError:
        print(f"Error: Image file not found at {image_path}")
        return None
    except IOError:
        print(f"Error: Could not open or read image file at {image_path}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


crop_bottom_pixels = crop_bottom


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

Please remember The Important Rule: In Ingredients, only use commas to separate new ingredients. The user will see bullet points added for every new comma.
The same goes for Procedures: Only use commas to separate a new procedure: periods are not needed. The user, again, will see bullet points added for every new comma.

PLEASE MAKE SURE YOU FOLLOW THESE CRITERIA. THIS INFORMATION IS CRUCIAL FOR OUR APPLICATION. THANK YOU."""
    answer = get_response(prompt).split(';')

    # Handle invalid
    if answer == ["0", "0", "0", "0", "0"]:
        return answer

    # Save + crop image
    safe_title = answer[0].replace(" ", "_")
    save_folder = f"images/{safe_title}"
    os.makedirs(save_folder, exist_ok=True)
    image_path = f"{save_folder}/image.png"

    get_image_pollinations(answer[4], image_path)
    crop_bottom_pixels(image_path, 60)

    # Return full result
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
    """
    Uses Gemini Vision to analyze the image and extract possible ingredients.
    """
    try:
        model = genai.GenerativeModel(model_name="gemini-2.5-flash-lite")
        image_data = Image.open(image_path)

        # You can ask for ingredients or a description of the meal
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
        response = model.generate_content(
            [prompt, image_data],
            generation_config=generation_config,
        )
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