import streamlit as st
import google.generativeai as genai
import os
from dotenv import load_dotenv
import json
import time

# --- HIDE BRANDING ---
st.set_page_config(page_title="Sous", page_icon="🍳", layout="centered")
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# 1. Configuration
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    try:
        api_key = st.secrets["GOOGLE_API_KEY"]
    except:
        st.error("🔑 API Key missing. Please add it to Secrets.")
        st.stop()

genai.configure(api_key=api_key)

# --- THE SELF-HEALING MODEL SELECTOR ---
def get_working_model():
    """Finds the first available model that actually works."""
    # Preferred order of models to try
    preferred_models = [
        "models/gemini-1.5-flash",
        "models/gemini-1.5-flash-001",
        "models/gemini-1.5-flash-002",
        "models/gemini-1.5-flash-8b",
        "models/gemini-pro",
        "models/gemini-1.0-pro"
    ]
    
    # Check what is actually available in your account
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    except:
        # Fallback if listing fails
        return genai.GenerativeModel("models/gemini-1.5-flash")

    # Try to find a match
    for preferred in preferred_models:
        if preferred in available:
            return genai.GenerativeModel(preferred)
    
    # If none of our preferred ones are there, take the first valid one (avoiding 2.0 experimental if possible)
    # But if 2.0 is all you have, we take it.
    if available:
        return genai.GenerativeModel(available[0])
        
    return genai.GenerativeModel("models/gemini-1.5-flash") # Hail Mary

model = get_working_model()

# 2. The Header
st.title("Sous 🍳")
st.caption("Your smart kitchen co-pilot. I adapt recipes to what you actually have.")

# 3. The Input
with st.form("input_form"):
    col1, col2 = st.columns([3, 1])
    with col1:
        dish = st.text_input("What are we cooking?", placeholder="e.g. Butter Chicken...", label_visibility="collapsed")
    with col2:
        servings = st.slider("Servings", 1, 8, 2)
    submitted = st.form_submit_button("Let's Cook", use_container_width=True)

# Session State
if "ingredients" not in st.session_state: st.session_state.ingredients = None
if "dish_name" not in st.session_state: st.session_state.dish_name = ""
if "generated_recipe" not in st.session_state: st.session_state.generated_recipe = False

# 4. Logic
if submitted and dish:
    st.session_state.dish_name = dish
    st.session_state.ingredients = None
    st.session_state.recipe_text = None
    st.session_state.generated_recipe = False
    
    with st.status("👨‍🍳 Sous is analyzing...", expanded=True) as status:
        st.write("Searching culinary database...")
        prompt = f"""
        I want to cook {dish} for {servings} people. 
        Break down the ingredients. 
        Return ONLY a JSON object with these 3 keys: 
        'heroes' (list of 3-4 absolute dealbreaker main ingredients), 
        'variables' (list of 4-6 ingredients that affect flavor/texture but can be substituted), 
        'pantry' (list of basic items like oil, salt, water, basic spices).
        """
        try:
            time.sleep(1) # Safety pause
            response = model.generate_content(prompt)
            cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned_text)
            st.session_state.ingredients = data
            status.update(label="Ingredients Found!", state="complete", expanded=False)
        except Exception as e:
            status.update(label="Connection Error", state="error")
            st.error(f"Oops: {e}")
            st.info("Tip: If you see a 404/429 error, just wait 30 seconds and try again.")

# 5. Triage & Output
if st.session_state.ingredients:
    data = st.session_state.ingredients
    st.divider()
    st.subheader(f"Inventory Check: {st.session_state.dish_name}")
    
    col_heroes, col_vars = st.columns(2)
    with col_heroes:
        st.info("🛡️ **The Heroes**")
        heroes_checks = [st.checkbox(i, value=True, key=f"h_{i}") for i in data['heroes']]
    with col_vars:
        st.warning("🎨 **The Variables**")
        missing_vars = [i for i in data['variables'] if not st.checkbox(i, value=True, key=f"v_{i}")]

    st.write("") 
    if all(heroes_checks):
        generate_btn = st.button("Generate My Recipe", type="primary", use_container_width=True)
        if generate_btn: st.session_state.generated_recipe = True
            
        if st.session_state.get("generated_recipe"):
            if "recipe_text" not in st.session_state or generate_btn:
                with st.spinner("Writing recipe..."):
                    time.sleep(2)
                    final_prompt = f"""
                    Act as 'Sous'. Create a recipe for {st.session_state.dish_name} ({servings} servings).
                    User is MISSING: {missing_vars}.
                    1. List "Chef's Fixes" for missing items first.
                    2. Full recipe. Concise.
                    """
                    try:
                        resp = model.generate_content(final_prompt)
                        st.session_state.recipe_text = resp.text
                    except:
                        st.error("Traffic limit hit. Wait 30s.")
                        
            st.markdown("---")
            if missing_vars: st.success(f"💡 **Substitutes found for:** {', '.join(missing_vars)}")
            if st.session_state.recipe_text:
                st.markdown(st.session_state.recipe_text)
                st.markdown("---")
                c1, c2 = st.columns(2)
                with c1:
                    with st.expander("📋 Copy Recipe"):
                        st.code(st.session_state.recipe_text, language="markdown")
                with c2:
                    if st.button("🔄 Start Over", use_container_width=True):
                        st.session_state.ingredients = None
                        st.session_state.recipe_text = None
                        st.session_state.generated_recipe = False
                        st.rerun()
    else:
        st.error("🛑 Missing a Hero ingredient! Cannot proceed.")