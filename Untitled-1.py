import streamlit as st
import requests

st.title("Fridge Recipe Finder")

ingredient = st.text_input("What ingredient do you have?", "chicken")


def get_recipes_by_ingredient(ingredient):
    url = f"https://www.themealdb.com/api/json/v1/1/filter.php?i={ingredient}"
    response = requests.get(url)
    return response.json().get("meals")


def get_recipe_details(meal_id):
    url = f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={meal_id}"
    response = requests.get(url)
    data = response.json()
    return data["meals"][0]


if st.button("Find recipes"):
    meals = get_recipes_by_ingredient(ingredient)

    if meals is None:
        st.write("No recipes found.")
    else:
        st.session_state["meals"] = meals


if "meals" in st.session_state:
    meals = st.session_state["meals"]

    meal_options = {
        meal["strMeal"]: meal["idMeal"]
        for meal in meals
    }

    selected_meal = st.selectbox("Choose a recipe:", meal_options.keys())

    if selected_meal:
        meal_id = meal_options[selected_meal]
        details = get_recipe_details(meal_id)

        st.header(details["strMeal"])
        st.image(details["strMealThumb"], width=350)

        st.subheader("Ingredients")

        for i in range(1, 21):
            ingredient_name = details.get(f"strIngredient{i}")
            measure = details.get(f"strMeasure{i}")

            if ingredient_name and ingredient_name.strip():
                st.write(f"- {measure} {ingredient_name}")

        st.subheader("Instructions")
        st.write(details["strInstructions"])

        if details.get("strYoutube"):
            st.subheader("Video")
            st.write(details["strYoutube"])
x=5000