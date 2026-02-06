import streamlit as st
import os
from groq import Groq
from dotenv import load_dotenv
import json

# --- HIDE STREAMLIT BRANDING ---
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

try:
    api_key = st.secrets["GROQ_API_KEY"]
except:
    api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    st.error("🔑 GROQ_API_KEY missing. Please add it to Secrets.")
    st.stop()

client = Groq(api_key=api_key)

# 2. Header
st.title("Sous 🍳")
st.caption("Your smart kitchen co-pilot. (Gourmet Mode)")

# 3. Input
with st.form("input_form"):
    col1, col2 = st.columns([3, 1])
    with col1:
        dish = st.text_input("What are we cooking?", placeholder="e.g. Mutton Biryani...", label_visibility="collapsed")
    with col2:
        servings = st.slider("Servings", 1, 8, 2)
    submitted = st.form_submit_button("Let's Cook", use_container_width=True)

if "ingredients" not in st.session_state: st.session_state.ingredients = None
if "dish_name" not in st.session_state: st.session_state.dish_name = ""
if "generated_recipe" not in st.session_state: st.session_state.generated_recipe = False

# 4. Logic
if submitted and dish:
    st.session_state.dish_name = dish
    st.session_state.ingredients = None
    st.session_state.recipe_text = None
    st.session_state.generated_recipe = False
    
    with st.status("👨‍🍳 Sous is analyzing the recipe...", expanded=True) as status:
        st.write("Checking culinary requirements...")
        
        prompt = f"""
        I want to cook {dish} for {servings} people.
        Return ONLY a JSON object with these 3 keys:
        
        1. 'heroes': List 3-4 CORE ingredients that define the dish (e.g., The main meat, the specific rice, the main vegetable).
        2. 'variables': List 5-6 SECONDARY ingredients that add flavor but might be missing in a home kitchen (e.g., Fresh herbs like Mint/Coriander, specific spices like Saffron/Star Anise, specialty dairy like Ghee/Cream). DO NOT list alternative meats here.
        3. 'pantry': List basic items assumed to be in stock (Oil, Salt, Water, Onions, Ginger-Garlic paste, Chili powder, Turmeric, Cumin).
        """
        
        try:
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are an expert chef. You understand traditional recipes accurately. Output JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            data = json.loads(completion.choices[0].message.content)
            st.session_state.ingredients = data
            status.update(label="Ingredients Ready!", state="complete", expanded=False)
            
        except Exception as e:
            status.update(label="Error", state="error")
            st.error(f"Groq Error: {e}")

# 5. Output
if st.session_state.ingredients:
    data = st.session_state.ingredients
    st.divider()
    st.subheader(f"Inventory: {st.session_state.dish_name}")
    
    c1, c2 = st.columns(2)
    with c1:
        st.info("🛡️ **Heroes** (The Core)")
        heroes = [st.checkbox(i, True, key=f"h_{i}") for i in data.get('heroes', [])]
    with c2:
        st.warning("🎨 **Flavor Builders** (Check what you have)")
        # Logic: Unchecked means MISSING
        missing = []
        available_vars = []
        for i in data.get('variables', []):
            if st.checkbox(i, value=True, key=f"v_{i}"):
                available_vars.append(i)
            else:
                missing.append(i)

    st.write("") 
    if all(heroes):
        gen_btn = st.button("Generate Chef's Recipe", type="primary", use_container_width=True)
        if gen_btn: st.session_state.generated_recipe = True
            
        if st.session_state.get("generated_recipe"):
            if "recipe_text" not in st.session_state or gen_btn:
                with st.spinner("👨‍🍳 Chef is writing detailed instructions..."):
                    
                    # --- THE FIX: Pass the CONFIRMED list ---
                    confirmed_list = data.get('heroes', []) + data.get('pantry', []) + available_vars
                    
                    system_persona = """
                    You are 'Sous', a warm, encouraging, expert home chef.
                    Your recipes are authentic and mouth-watering.
                    Do NOT be robotic. Use bolding for ingredients and steps.
                    """
                    
                    user_request = f"""
                    Create a recipe for {st.session_state.dish_name} ({servings} servings).
                    
                    CRITICAL INVENTORY CONTEXT:
                    1. The User HAS these ingredients: {confirmed_list}. USE THEM EXACTLY (e.g., if 'Ginger-Garlic Paste' is listed, do not ask for chopped ginger).
                    2. The User is MISSING: {missing}.
                    
                    Structure:
                    1. **The Fix:** Briefly explain how we adapt to the missing items.
                    2. **The Ingredients:** List the full shopping list (Heroes + Pantry + Available Variables).
                    3. **The Recipe:** Step-by-step, engaging instructions.
                    """
                    
                    try:
                        resp = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=[
                                {"role": "system", "content": system_persona},
                                {"role": "user", "content": user_request}
                            ],
                            temperature=0.7 
                        )
                        st.session_state.recipe_text = resp.choices[0].message.content
                    except Exception as e:
                        st.error(f"Error: {e}")

            st.markdown("---")
            if missing: st.success(f"💡 **Kitchen Adaptation:** {', '.join(missing)}")
            if st.session_state.recipe_text:
                st.markdown(st.session_state.recipe_text)
                st.markdown("---")
                c_copy, c_reset = st.columns(2)
                with c_copy:
                    with st.expander("📋 Copy Recipe"):
                        st.code(st.session_state.recipe_text, language="markdown")
                with c_reset:
                    if st.button("🔄 Start Over", use_container_width=True):
                        st.session_state.clear()
                        st.rerun()
    else:
        st.error("🛑 Need Heroes!")