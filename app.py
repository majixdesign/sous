import streamlit as st
import google.generativeai as genai
import os
from dotenv import load_dotenv
import json

# 1. Configuration
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

# Configure page settings - "Sous" branding
st.set_page_config(page_title="Sous", page_icon="🍳", layout="centered")

if not api_key:
    st.error("🔑 API Key missing. Please check your .env file or Streamlit Secrets.")
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel("models/gemini-flash-latest") # The "Toyota Corolla" model (Reliable)

# 2. The Header (Clean & Modern)
st.title("Sous 🍳")
st.caption("Your smart kitchen co-pilot. I adapt recipes to what you actually have.")

# 3. The "Intelligent Input" Section
# We use st.form so the user can hit "Enter" on their keyboard!
with st.form("input_form"):
    col1, col2 = st.columns([3, 1])
    
    with col1:
        dish = st.text_input(
            "What are we cooking?", 
            placeholder="e.g. Butter Chicken, Aglio Olio...",
            label_visibility="collapsed"
        )
    
    with col2:
        servings = st.slider("Servings", min_value=1, max_value=8, value=2)
        
    # This button submits the form
    submitted = st.form_submit_button("Let's Cook", use_container_width=True)

# Initialize session state to keep data alive after clicking buttons
if "ingredients" not in st.session_state:
    st.session_state.ingredients = None
if "dish_name" not in st.session_state:
    st.session_state.dish_name = ""

# 4. The Logic (Triggered by the Form)
if submitted and dish:
    st.session_state.dish_name = dish
    
    # The "Status" Log - Shows transparency
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
            response = model.generate_content(prompt)
            # Clean up JSON formatting if the AI adds backticks
            cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned_text)
            st.session_state.ingredients = data
            status.update(label="Ingredients Found!", state="complete", expanded=False)
            
        except Exception as e:
            status.update(label="Connection Error", state="error")
            st.error(f"Oops: {e}")

# 5. The "Triage" Dashboard (Only shows if we have data)
if st.session_state.ingredients:
    data = st.session_state.ingredients
    
    st.divider()
    st.subheader(f"Inventory Check: {st.session_state.dish_name}")
    
    # Layout: Two columns for cleaner UI
    col_heroes, col_vars = st.columns(2)
    
    with col_heroes:
        st.info("🛡️ **The Heroes** (Must Haves)")
        # We assume heroes are present, but if unchecked, we block.
        heroes_checks = []
        for item in data['heroes']:
            # Checked by default
            is_checked = st.checkbox(item, value=True, key=f"h_{item}")
            heroes_checks.append(is_checked)
            
    with col_vars:
        st.warning("🎨 **The Variables** (Swappable)")
        # We track what is UNCHECKED here
        missing_vars = []
        for item in data['variables']:
            is_checked = st.checkbox(item, value=True, key=f"v_{item}")
            if not is_checked:
                missing_vars.append(item)

    # 6. The "Action" Section
    st.write("") # Spacer
    
    # Logic Gate: Are all heroes present?
    if all(heroes_checks):
        generate_btn = st.button("Generate My Recipe", type="primary", use_container_width=True)
        
        # We use session state to "remember" the recipe so it doesn't vanish if you click other buttons
        if generate_btn:
            st.session_state.generated_recipe = True
            
        if st.session_state.get("generated_recipe"):
            
            # Only run the AI if we haven't already (or if user requested a redo)
            if "recipe_text" not in st.session_state or generate_btn:
                with st.spinner("👨‍🍳 Sous is writing your custom recipe..."):
                    final_prompt = f"""
                    Act as a professional chef named 'Sous'.
                    Create a recipe for {st.session_state.dish_name} (Servings: {servings}).
                    
                    CONSTRAINT: The user is MISSING these ingredients: {missing_vars}.
                    
                    1. If there are missing ingredients, you MUST explicitly list how you are fixing it in a "Chef's Note" at the top.
                    2. Then provide the full step-by-step recipe. 
                    3. Be concise and encouraging.
                    """
                    recipe_response = model.generate_content(final_prompt)
                    st.session_state.recipe_text = recipe_response.text

            # --- DISPLAY THE RESULT ---
            st.markdown("---")
            
            # 1. The "Fix" Box
            if missing_vars:
                st.success(f"💡 **Adaptive Mode Active:** Substitutes found for {', '.join(missing_vars)}.")
            
            # 2. The Recipe
            st.markdown(st.session_state.recipe_text)
            
            st.markdown("---")
            
            # 3. Action Buttons (Copy & Remix)
            col_copy, col_reset = st.columns(2)
            
            with col_copy:
                # The "Copy" Hack: We use a code block because it has a built-in copy button!
                # We hide it in an expander so it doesn't look ugly.
                with st.expander("📋 Click to Copy Recipe"):
                    st.code(st.session_state.recipe_text, language="markdown")
            
            with col_reset:
                if st.button("🔄 Start Over", use_container_width=True):
                    # Clear everything to restart
                    st.session_state.ingredients = None
                    st.session_state.recipe_text = None
                    st.session_state.generated_recipe = False
                    st.rerun()

    else:
        st.error("🛑 Hold up! You are missing a 'Hero' ingredient. We can't make this dish without it.")