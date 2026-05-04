import streamlit as st
import requests

st.title("Fridge Recipe Finder - Edamam Version")

# Replace these with your own Edamam credentials
APP_ID = "YOUR_APP_ID"
APP_KEY = "YOUR_APP_KEY"

ingredients = st.text_input(
    "What ingredients do you have?",
    "chicken rice tomato"
)

diet = st.selectbox(
    "Diet preference",
    ["None", "balanced", "high-protein", "low-carb", "low-fat"]
)

max_calories = st.slider(
    "Maximum calories per serving",
    100,
    1500,
    800
)


def search_recipes(query, diet_choice, max_calories):
    url = "https://api.edamam.com/api/recipes/v2"

    params = {
        "type": "public",
        "q": query,
        "app_id": APP_ID,
        "app_key": APP_KEY,
        "calories": f"0-{max_calories}",
    }

    if diet_choice != "None":
        params["diet"] = diet_choice

    response = requests.get(url, params=params)

    if response.status_code != 200:
        st.error(f"API error: {response.status_code}")
        st.write(response.text)
        return []

    data = response.json()
    return data.get("hits", [])


if st.button("Find recipes"):
    results = search_recipes(ingredients, diet, max_calories)

    if not results:
        st.write("No recipes found.")
    else:
        st.session_state["results"] = results


if "results" in st.session_state:
    results = st.session_state["results"]

    recipe_names = [
        hit["recipe"]["label"]
        for hit in results
    ]

    selected_recipe = st.selectbox(
        "Choose a recipe",
        recipe_names
    )

    selected_hit = results[recipe_names.index(selected_recipe)]
    recipe = selected_hit["recipe"]

    st.header(recipe["label"])

    if recipe.get("image"):
        st.image(recipe["image"], width=350)

    st.subheader("Basic information")
    st.write("Source:", recipe.get("source"))
    st.write("Calories:", round(recipe.get("calories", 0)))
    st.write("Servings:", recipe.get("yield"))

    st.subheader("Diet labels")
    st.write(recipe.get("dietLabels", []))

    st.subheader("Health labels")
    st.write(recipe.get("healthLabels", [])[:10])

    st.subheader("Ingredients")
    for ingredient in recipe.get("ingredientLines", []):
        st.write("-", ingredient)

    st.subheader("Nutrition")
    nutrients = recipe.get("totalNutrients", {})

    for key in ["ENERC_KCAL", "PROCNT", "FAT", "CHOCDF", "FIBTG"]:
        if key in nutrients:
            nutrient = nutrients[key]
            st.write(
                f"{nutrient['label']}: "
                f"{round(nutrient['quantity'], 1)} "
                f"{nutrient['unit']}"
            )

    st.subheader("Full recipe")
    st.write(recipe.get("url"))