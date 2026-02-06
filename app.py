import streamlit as st
import google.generativeai as genai
import os
from dotenv import load_dotenv
import json
import time

# --- HIDE BRANDING ---
st.set_page_config(page_title="Sous", page_icon="🍳", layout="wide") # Switched to WIDE layout
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            /* Make checkboxes bigger for easier clicking */
            div[data-testid="stCheckbox"] label span {
                font-size: 1.1rem;
            }
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
        st.error("🔑 Google API Key missing. Please check Secrets.")
        st.stop()

genai.configure(api_key=api_key)

# --- DYNAMIC MODEL SELECTOR (Your "Universal Adapter") ---
def get_working_model():
    try:
        my_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        preferred_order = [
            "models/gemini-1.5-flash",
            "models/gemini-2.0-flash", 
            "models/gemini-1.5-pro",
            "models/gemini-pro"
        ]
        for p in preferred_order:
            if p in my_models: return genai.GenerativeModel(p)
        return genai.GenerativeModel(my_models[0]) if my_models else genai.GenerativeModel("models/gemini-1.5-flash")
    except:
        return genai.GenerativeModel("models/gemini-1.5-flash")

model = get_working_model()

# 2. Header
st.title("Sous 🍳")
st.caption("Your smart kitchen co-pilot. (Powered by Gemini)")

# 3. Input
with st.form("input_form"):
    col1, col2 = st.columns([3, 1])
    with col1:
        dish = st.text_input("What are we cooking?", placeholder="e.g. Mutton Biryani, Aglio Olio...", label_visibility="collapsed")
    with col2:
        servings = st.slider("Servings", 1, 8, 2)
    submitted = st.form_submit_button("Start Prep", use_container_width=True)

if "ingredients" not in st.session_state: st.session_state.ingredients = None
if "dish_name" not in st.session_state: st.session_state.dish_name = ""
if "generated_recipe" not in st.session_state: st.session_state.generated_recipe = False

# 4. Logic
if submitted and dish:
    st.session_state.dish_name = dish
    st.session_state.ingredients = None
    st.session_state.recipe_text = None
    st.session_state.generated_recipe = False
    
    with st.status("👨‍🍳 Sous is organizing the kitchen...", expanded=True) as status:
        
        # IMPROVED PROMPT: Handles ambiguity better and splits Pantry clearly
        prompt = f"""
        I want to cook {dish} for {servings} people. 
        If the dish name is generic (like "Biryani"), assume the most popular version (Chicken) but label the meat as "Main Protein (Chicken/Mutton)" so the user knows.
        
        Break down ingredients into JSON with these 3 keys:
        1. 'must_haves': The absolute core items (Meat, Rice, Pasta, Main Veg).
        2. 'soul': Flavor builders (Fresh Herbs, Whole Spices like Star Anise/Cardamom, Ghee, Saffron, Wine).
        3. 'foundation': The pantry basics (Onions, Tomatoes, Ginger-Garlic, Oil, Turmeric, Chili Powder, Salt).
        
        Return ONLY valid JSON.
        """
        
        try:
            time.sleep(0.5)
            response = model.generate_content(prompt)
            cleaned = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned)
            st.session_state.ingredients = data
            status.update(label="Prep List Ready!", state="complete", expanded=False)
            
        except Exception as e:
            status.update(label="Connection Error", state="error")
            st.error(f"Error: {e}")

# 5. The "ChefOS v2" Dashboard (3 Columns)
if st.session_state.ingredients:
    data = st.session_state.ingredients
    st.divider()
    st.subheader(f"Inventory: {st.session_state.dish_name}")
    st.caption("Uncheck anything you are missing. We will adapt.")
    
    # NEW LAYOUT: 3 Columns
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.info("🧱 **The Vitals** (Must Have)")
        must_haves = [st.checkbox(i, True, key=f"m_{i}") for i in data.get('must_haves', [])]
        
    with c2:
        st.warning("✨ **The Soul** (Nice to Have)")
        soul_missing = []
        soul_available = []
        for i in data.get('soul', []):
            if st.checkbox(i, True, key=f"s_{i}"):
                soul_available.append(i)
            else:
                soul_missing.append(i)
                
    with c3:
        st.success("🏗️ **The Foundation** (Pantry)")
        pantry_missing = []
        pantry_available = []
        for i in data.get('foundation', []):
            if st.checkbox(i, True, key=f"p_{i}"):
                pantry_available.append(i)
            else:
                pantry_missing.append(i)

    st.write("") 
    if all(must_haves):
        gen_btn = st.button("Generate Chef's Recipe", type="primary", use_container_width=True)
        if gen_btn: st.session_state.generated_recipe = True
            
        if st.session_state.get("generated_recipe"):
            if "recipe_text" not in st.session_state or gen_btn:
                with st.spinner("👨‍🍳 Chef is planning the strategy..."):
                    
                    # COMBINE ALL CONFIRMED ITEMS
                    confirmed_inventory = (
                        data.get('must_haves', []) + 
                        soul_available + 
                        pantry_available
                    )
                    
                    all_missing = soul_missing + pantry_missing
                    
                    final_prompt = f"""
                    Act as 'Sous', a warm, expert home chef.
                    Create a recipe for {st.session_state.dish_name} ({servings} servings).
                    
                    CRITICAL INVENTORY CONTEXT:
                    1. User CONFIRMED they have: {confirmed_inventory}. USE THESE EXACTLY.
                    2. User is MISSING: {all_missing}.
                    
                    Structure:
                    1. **The Strategy:** A quick opening note. If key flavor items (Soul/Foundation) are missing, explain the workaround (e.g., "No onions? We'll rely on the yogurt for thickness.").
                    2. **The Mise en Place:** List the exact ingredients to use.
                    3. **The Cook:** Step-by-step, descriptive instructions. Focus on sensory cues (smell, color).
                    4. **Chef's Tip:** One pro tip at the end.
                    """
                    try:
                        resp = model.generate_content(final_prompt)
                        st.session_state.recipe_text = resp.text
                    except Exception as e:
                        st.error(f"Error: {e}")

            st.markdown("---")
            if all_missing: st.info(f"💡 **Adapting for:** {', '.join(all_missing)}")
            
            if st.session_state.recipe_text:
                st.markdown(st.session_state.recipe_text)
                st.markdown("---")
                col_copy, col_reset = st.columns(2)
                with col_copy:
                    with st.expander("📋 Copy Recipe"):
                        st.code(st.session_state.recipe_text, language="markdown")
                with col_reset:
                    if st.button("🔄 Start Over", use_container_width=True):
                        st.session_state.clear()
                        st.rerun()
    else:
        st.error("🛑 You are missing a Vital Ingredient. We can't cook this dish without it.")