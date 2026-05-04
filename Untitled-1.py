import streamlit as st
import requests

st.title("Fridge Recipe Finder")

ingredient = st.text_input("What ingredient do you have?", "chicken")

if st.button("Find recipes"):
    url = f"https://www.themealdb.com/api/json/v1/1/filter.php?i={ingredient}"
    response = requests.get(url)
    data = response.json()

    meals = data.get("meals")

    if meals is None:
        st.write("No recipes found.")
    else:
        for meal in meals[:5]:
            st.subheader(meal["strMeal"])
            st.image(meal["strMealThumb"], width=250)
            st.write("Meal ID:", meal["idMeal"])