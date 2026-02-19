import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import json
import base64
import io
from openai import OpenAI
from PIL import Image

# --- CONFIG ---
st.set_page_config(page_title="AI Vision Extractor", layout="wide", page_icon="📸")

# --- CSS ΓΙΑ ΟΜΟΡΦΟ UI ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #ff4b4b; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("📸 Smart Vision Invoice Extractor")
st.write("Ανέβασε **φωτογραφίες** ή **σκαναρισμένα PDF**. Η AI θα αναλύσει την εικόνα απευθείας.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("OpenAI API Key", type="password")
    model_name = st.selectbox("Επίλεξε Μοντέλο", ["gpt-4o", "gpt-4o-mini"], index=1)
    st.info("Το gpt-4o-mini είναι ταχύτατο και οικονομικό!")

# --- FUNCTIONS ---

def encode_image_from_bytes(image_bytes):
    """Μετατρέπει bytes εικόνας σε Base64 string"""
    return base64.b64encode(image_bytes).decode('utf-8')

def pdf_to_images(pdf_bytes):
    """Μετατρέπει κάθε σελίδα του PDF σε εικόνα (bytes) χρησιμοποιώντας το PyMuPDF"""
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
    images_list = []
    for page_num in range(len(pdf_document)):
        page = pdf_document.load_page(page_num)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) # Zoom x2 για καλύτερη ποιότητα
        img_bytes = pix.tobytes("png")
        images_list.append(img_bytes)
    return images_list

def analyze_with_vision(image_base64, key, model):
    """Στέλνει την εικόνα στο OpenAI Vision API"""
    client = OpenAI(api_key=key)
    
    prompt = """
    Λειτούργησε ως ειδικός στην εξαγωγή δεδομένων από έγγραφα. 
    Ανάλυσε την εικόνα και εξήγαγε τα εξής σε JSON:
    - Date (YYYY-MM-DD)
    - Company Name
    - Invoice Number
    - Total Amount (numeric)
    - VAT (percentage and amount)
    - Table Items: [Description, Quantity, Unit Price]
    
    Κανόνες: 
    1. Επέστρεψε ΜΟΝΟ το JSON.
    2. Αν κάτι λείπει, βάλε null.
    3. Μετέφρασε τα κλειδιά στα Αγγλικά.
    """

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                    },
                ],
            }
        ],
        response_format={ "type": "json_object" }
    )
    return json.loads(response.choices[0].message.content)

# --- MAIN APP ---
uploaded_files = st.file_uploader("Σύρε εδώ τα αρχεία σου (PDF, JPG, PNG)", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files and api_key:
    if st.button("🚀 Έναρξη Επεξεργασίας"):
        all_extracted_data = []
        
        for uploaded_file in uploaded_files:
            st.subheader(f"📄 Αρχείο: {uploaded_file.name}")
            col1, col2 = st.columns([1, 1])
            
            # Λήψη εικόνων (αν είναι PDF μπορεί να είναι πολλές σελίδες)
            if uploaded_file.type == "application/pdf":
                images_to_process = pdf_to_images(uploaded_file.read())
            else:
                images_to_process = [uploaded_file.read()]
            
            for idx, img_bytes in enumerate(images_to_process):
                # 1. Εμφάνιση Εικόνας (Preview)
                with col1:
                    st.image(img_bytes, caption=f"Σελίδα {idx+1}", use_container_width=True)
                
                # 2. Επεξεργασία AI
                with st.spinner(f"Η AI αναλύει τη σελίδα {idx+1}..."):
                    try:
                        b64_img = encode_image_from_bytes(img_bytes)
                        data = analyze_with_vision(b64_img, api_key, model_name)
                        
                        with col2:
                            st.success(f"Επιτυχής εξαγωγή (Σελίδα {idx+1})")
                            st.json(data)
                        
                        # Προσθήκη για το Excel
                        items = data.get('Table Items', []) or data.get('items', [])
                        if not items: items = [None] # Για να καταγραφεί έστω η κεφαλίδα
                        
                        for item in items:
                            row = {
                                "File": uploaded_file.name,
                                "Page": idx + 1,
                                "Date": data.get('Date'),
                                "Company": data.get('Company Name'),
                                "Invoice_No": data.get('Invoice Number'),
                                "Total": data.get('Total Amount'),
                                "VAT": data.get('VAT'),
                                "Description": item.get('Description') if item else "N/A",
                                "Qty": item.get('Quantity') if item else 0,
                                "Price": item.get('Unit Price') if item else 0
                            }
                            all_extracted_data.append(row)
                    except Exception as e:
                        st.error(f"Σφάλμα στη σελίδα {idx+1}: {e}")

        # --- ΤΕΛΙΚΟ EXCEL ---
        if all_extracted_data:
            df = pd.DataFrame(all_extracted_data)
            st.divider()
            st.write("### Συνολικά Αποτελέσματα")
            st.dataframe(df)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Data')
            
            st.download_button(
                label="📥 Λήψη όλων σε Excel",
                data=output.getvalue(),
                file_name="ai_extracted_invoices.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

elif not api_key and uploaded_files:
    st.warning("⚠️ Παρακαλώ εισήγαγε το OpenAI API Key σου στο πλάι.")
