import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import json
import io
import google.generativeai as genai
from PIL import Image

# --- CONFIG ---
st.set_page_config(page_title="Free AI Invoice Extractor", layout="wide")
st.title("🆓 Free AI Invoice Extractor (Gemini)")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Settings")
    gemini_key = st.text_input("Google Gemini API Key", type="password")
    st.info("Πάρε δωρεάν κλειδί από το Google AI Studio")

# --- FUNCTIONS ---
def pdf_to_images(pdf_bytes):
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
    images_list = []
    for page_num in range(len(pdf_document)):
        page = pdf_document.load_page(page_num)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        images_list.append(img)
    return images_list

def analyze_with_gemini(image, key):
    genai.configure(api_key=key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = """
    Analyze this invoice image and return ONLY a JSON object with:
    Date (YYYY-MM-DD), Company Name, Invoice Number, Total Amount, VAT, 
    Table Items: [Description, Quantity, Unit Price].
    If a value is missing, use null.
    """
    
    response = model.generate_content([prompt, image])
    # Καθαρισμός του κειμένου για να μείνει μόνο το JSON
    json_text = response.text.replace('```json', '').replace('```', '').strip()
    return json.loads(json_text)

# --- MAIN APP ---
uploaded_files = st.file_uploader("Ανέβασε PDF ή Φωτογραφίες", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files and gemini_key:
    if st.button("🚀 Έναρξη Επεξεργασίας (Δωρεάν)"):
        all_data = []
        for file in uploaded_files:
            st.write(f"Επεξεργασία: {file.name}")
            
            if file.type == "application/pdf":
                images = pdf_to_images(file.read())
            else:
                images = [Image.open(file)]
            
            for img in images:
                try:
                    data = analyze_with_gemini(img, gemini_key)
                    items = data.get('Table Items', []) or [None]
                    for item in items:
                        all_data.append({
                            "File": file.name,
                            "Date": data.get('Date'),
                            "Company": data.get('Company Name'),
                            "Total": data.get('Total Amount'),
                            "Description": item.get('Description') if item else "N/A",
                            "Price": item.get('Unit Price') if item else 0
                        })
                except Exception as e:
                    st.error(f"Σφάλμα: {e}")

        if all_data:
            df = pd.DataFrame(all_data)
            st.dataframe(df)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            st.download_button("📥 Λήψη Excel", output.getvalue(), "data.xlsx")