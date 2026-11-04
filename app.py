"""AI Fridge Chef: Streamlit UI + Gemini Flash.

Enter the ingredients you have, your diet and the time you can spend, and get
recipe ideas, step-by-step instructions and a shopping list for what is missing.
Talks to Gemini through its REST API using only the standard library.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import streamlit as st

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Free-tier Flash models. The "-latest" aliases always point to Google's newest
# stable Flash / Flash-Lite, so the app keeps working when models are retired.
# (gemini-2.5-flash and gemini-2.5-flash-lite were shut down on 16 Oct 2026.)
MODELS = [
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
]

DIETS = ["No restriction", "Halal", "Vegetarian", "Vegan", "Low carb", "High protein"]
CUISINES = ["Any", "Pakistani / Desi", "Chinese", "Italian", "Middle Eastern", "Continental", "Fast food style"]
LEVELS = ["Beginner", "Intermediate", "Advanced"]


# ----------------------------------------------------------------- helpers
def get_api_key() -> str:
    """Read the key from Streamlit secrets, env var, or the sidebar box."""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "")


def build_prompt(ingredients, diet, cuisine, minutes, servings, level, allergies, count):
    return f"""You are a friendly professional chef. Suggest {count} different recipes.

Ingredients the user has: {ingredients}
Diet: {diet}
Cuisine preference: {cuisine}
Maximum cooking time: {minutes} minutes
Servings: {servings}
Cooking skill: {level}
Allergies / foods to avoid: {allergies or "none"}

Rules:
- Use mostly the listed ingredients. Assume basic pantry items (salt, oil, water, common spices) are available.
- Never use anything that breaks the diet or the allergies.
- Keep each recipe within the time limit.
- Keep steps short, clear and suited to the skill level.

Return ONLY valid JSON in exactly this shape:
{{
  "recipes": [
    {{
      "name": "string",
      "time_minutes": 20,
      "difficulty": "Easy | Medium | Hard",
      "calories_per_serving": 450,
      "why_it_fits": "one short sentence",
      "ingredients_used": ["string"],
      "missing_ingredients": ["string"],
      "steps": ["string"],
      "chef_tip": "string"
    }}
  ],
  "shopping_list": ["combined missing ingredients across all recipes, no duplicates"]
}}"""


def call_gemini(api_key: str, prompt: str) -> dict:
    """Try each model in turn; return parsed JSON or raise RuntimeError."""
    body = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
    ).encode("utf-8")

    last_error = "Unknown error"
    for model in MODELS:
        req = urllib.request.Request(
            API_URL.format(model=model),
            data=body,
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
            if text.startswith("```"):
                text = text.strip("`")
                if text.lower().startswith("json"):
                    text = text[4:]
            return json.loads(text)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="ignore")[:200]
            last_error = f"{model}: HTTP {e.code} {detail}"
            if e.code in (401, 403) or (e.code == 400 and "API key" in detail):
                break  # bad key: trying other models will not help
        except (KeyError, IndexError, json.JSONDecodeError):
            last_error = f"{model}: could not read the model's answer"
        except Exception as e:  # network errors, timeouts
            last_error = f"{model}: {e}"
    raise RuntimeError(last_error)


# --------------------------------------------------------------------- UI
st.set_page_config(page_title="AI Fridge Chef", page_icon="🍳", layout="centered")

with st.sidebar:
    st.header("Settings")
    key_input = st.text_input("Gemini API key", type="password", value=get_api_key())
    st.caption("Get a free key at aistudio.google.com/apikey")
    st.caption("Models tried in order: " + " → ".join(MODELS))

st.title("🍳 AI Fridge Chef")
st.write("Tell me what is in your fridge and I will tell you what to cook.")

ingredients = st.text_area(
    "What ingredients do you have?",
    placeholder="e.g. eggs, potatoes, onion, tomato, rice, yogurt, chicken",
    height=100,
)

c1, c2 = st.columns(2)
diet = c1.selectbox("Diet", DIETS)
cuisine = c2.selectbox("Cuisine", CUISINES)

c3, c4, c5 = st.columns(3)
minutes = c3.slider("Max time (min)", 10, 120, 30, step=5)
servings = c4.number_input("Servings", 1, 12, 2)
count = c5.slider("Recipes", 1, 5, 3)

level = st.radio("Cooking skill", LEVELS, horizontal=True)
allergies = st.text_input("Allergies / avoid (optional)", placeholder="e.g. peanuts, dairy")

if st.button("Find recipes", type="primary", use_container_width=True):
    if not key_input:
        st.error("Please add your Gemini API key in the sidebar.")
    elif not ingredients.strip():
        st.warning("Please enter at least one ingredient.")
    else:
        with st.spinner("The chef is thinking..."):
            try:
                st.session_state["result"] = call_gemini(
                    key_input,
                    build_prompt(ingredients.strip(), diet, cuisine, minutes, servings, level, allergies.strip(), count),
                )
            except RuntimeError as err:
                st.session_state.pop("result", None)
                st.error(f"Could not get recipes. {err}")

result = st.session_state.get("result")
if result:
    recipes = result.get("recipes", [])
    st.subheader(f"{len(recipes)} recipe ideas for you")

    for i, r in enumerate(recipes):
        with st.expander(f"🍽️ {r.get('name', 'Recipe')}  ·  {r.get('time_minutes', '?')} min", expanded=(i == 0)):
            m1, m2, m3 = st.columns(3)
            m1.metric("Time", f"{r.get('time_minutes', '?')} min")
            m2.metric("Difficulty", r.get("difficulty", "-"))
            m3.metric("Calories", f"{r.get('calories_per_serving', '?')} kcal")
            st.info(r.get("why_it_fits", ""))

            left, right = st.columns(2)
            with left:
                st.markdown("**✅ You have**")
                for item in r.get("ingredients_used", []):
                    st.markdown(f"- {item}")
            with right:
                st.markdown("**🛒 You need**")
                missing = r.get("missing_ingredients", [])
                if missing:
                    for item in missing:
                        st.markdown(f"- {item}")
                else:
                    st.markdown("Nothing, you have it all!")

            st.markdown("**👩‍🍳 Steps**")
            for n, step in enumerate(r.get("steps", []), 1):
                st.markdown(f"{n}. {step}")
            if r.get("chef_tip"):
                st.success(f"Chef's tip: {r['chef_tip']}")

    shopping = result.get("shopping_list", [])
    if shopping:
        st.subheader("🛒 Shopping list")
        for item in shopping:
            st.checkbox(item, key=f"shop_{item}")
        st.download_button(
            "Download shopping list",
            "\n".join(f"- {s}" for s in shopping),
            file_name="shopping_list.txt",
        )

st.caption("AI-generated suggestions. Check allergens and cooking safety yourself.")
