import io
import os
from datetime import datetime
import pandas as pd
import pypdf
from PIL import Image
import streamlit as st
from streamlit_gsheets import GSheetsConnection

# Page Configuration
st.set_page_config(
    page_title="Tertiary Data Entry", page_icon="📊", layout="wide"
)

st.title("📦 Tertiary Data Entry Portal")
st.markdown("Enter outlet-wise tertiary stock data, quantities, and upload verification files.")

# -------------------------------------------------------------------------
# 1. CONNECTION & DATA LOADING FROM GOOGLE SHEETS
# -------------------------------------------------------------------------
# Initialize Google Sheets Connection
# Ensure you have configured your [connections.gsheets] in .streamlit/secrets.toml
@st.cache_data(ttl=60)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Read Outlet Master and Tertiary Data sheets
    outlet_master = conn.read(worksheet="Outlet Master", usecols=list(range(4)))  # Adjust columns as needed (ASM, TSE, Outlet Code, Outlet Name)
    tertiary_data = conn.read(worksheet="Tertiary Data")
    return conn, outlet_master, tertiary_data

try:
    conn, outlet_master_df, tertiary_df = load_data()
except Exception as e:
    st.error(f"Failed to connect to Google Sheets: {e}")
    st.stop()

# -------------------------------------------------------------------------
# 2. FILTERS SETUP (ASM, TSE, Outlet Code, Outlet Name)
# -------------------------------------------------------------------------
st.sidebar.header("🔍 Filters & Selection")

# Filter ASM
asm_list = outlet_master_df["ASM"].dropna().unique().tolist()
selected_asm = st.sidebar.selectbox("Select ASM", ["--Select--"] + asm_list)

if selected_asm != "--Select--":
    filtered_tse = outlet_master_df[outlet_master_df["ASM"] == selected_asm]
    tse_list = filtered_tse["TSE"].dropna().unique().tolist()
    selected_tse = st.sidebar.selectbox("Select TSE", ["--Select--"] + tse_list)
else:
    selected_tse = st.sidebar.selectbox("Select TSE", ["--Select--"])

# Filter Outlet Code & Name
if selected_tse != "--Select--":
    filtered_outlets = outlet_master_df[
        (outlet_master_df["ASM"] == selected_asm) & (outlet_master_df["TSE"] == selected_tse)
    ]
else:
    filtered_outlets = outlet_master_df

# Create a combined label for selection
filtered_outlets["Outlet_Display"] = filtered_outlets["Outlet Code"].astype(str) + " - " + filtered_outlets["Outlet Name"].astype(str)
outlet_options = ["--Select--"] + filtered_outlets["Outlet_Display"].tolist()

selected_outlet_display = st.sidebar.selectbox("Select Outlet (Code & Name)", outlet_options)

# Select Month
months_list = ["January", "February", "March", "April", "May", "June", 
               "July", "August", "September", "October", "November", "December"]
current_month_name = datetime.now().strftime("%B")
selected_month = st.sidebar.selectbox("Select Month", months_list, index=months_list.index(current_month_name))

# -------------------------------------------------------------------------
# 3. STOCK ENTRY GRID (Bottles Entry)
# -------------------------------------------------------------------------
st.subheader("📋 Stock Entry (In Bottles)")
st.info("Enter quantities in bottles for each brand configuration.")

brands = [
    "IBDC", "MHW", "MHFB", "BLGOR", "BLGLM", 
    "SMG", "SMGP", "SIW", "SITARA", "Monarch"
]

# We will use a form to collect inputs cleanly
with st.form("tertiary_entry_form"):
    stock_data = {}
    
    # Header layout for sizes
    cols = st.columns([2, 1.5, 1.5, 1.5, 1.5, 2])
    cols[0].markdown("**Brand Name**")
    cols[1].markdown("**750 (12)**")
    cols[2].markdown("**500 (18)**")
    cols[3].markdown("**375 (24)**")
    cols[4].markdown("**180 (48)**")
    cols[5].markdown("**Total Bottles**")
    
    for brand in brands:
        c = st.columns([2, 1.5, 1.5, 1.5, 1.5, 2])
        c[0].markdown(f"**{brand}**")
        
        b_750 = c[1].number_input(f"{brand}_750", min_value=0, value=0, step=1, label_visibility="collapsed")
        b_500 = c[2].number_input(f"{brand}_500", min_value=0, value=0, step=1, label_visibility="collapsed")
        b_375 = c[3].number_input(f"{brand}_375", min_value=0, value=0, step=1, label_visibility="collapsed")
        b_180 = c[4].number_input(f"{brand}_180", min_value=0, value=0, step=1, label_visibility="collapsed")
        
        row_total = b_750 + b_500 + b_375 + b_180
        c[5].markdown(f"**{row_total}**")
        
        stock_data[brand] = {
            "750": b_750,
            "500": b_500,
            "375": b_375,
            "180": b_180,
            "Total_Bottles": row_total
        }

    st.markdown("---")
    st.subheader("📎 Upload Documents")
    
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        upload_1 = st.file_uploader("Upload 1 (Mandatory)", type=["pdf", "png", "jpg", "jpeg"])
        upload_2 = st.file_uploader("Upload 2 (Optional)", type=["pdf", "png", "jpg", "jpeg"])
    with col_up2:
        upload_3 = st.file_uploader("Upload 3 (Optional)", type=["pdf", "png", "jpg", "jpeg"])
        upload_4 = st.file_uploader("Upload 4 (Optional)", type=["pdf", "png", "jpg", "jpeg"])

    submitted = st.form_submit_button("🚀 Submit Tertiary Entry")

# -------------------------------------------------------------------------
# 4. SUBMISSION HANDLING & CONVERSION LOGIC
# -------------------------------------------------------------------------
if submitted:
    # Validation checks
    if selected_asm == "--Select--" or selected_tse == "--Select--" or selected_outlet_display == "--Select--":
        st.error("⚠️ Please select valid ASM, TSE, and Outlet filters before submitting.")
    elif upload_1 is None:
        st.error("⚠️ Upload 1 is mandatory. Please attach the required document.")
    else:
        # Extract Outlet Code and Name
        outlet_code = selected_outlet_display.split(" - ")[0]
        outlet_name = " - ".join(selected_outlet_display.split(" - ")[1:])
        
        # Conversion to cases calculations:
        # 750ml -> pack of 12, 500ml -> pack of 18, 375ml -> pack of 24, 180ml -> pack of 48
        cases_records = []
        bottles_records = []
        
        for brand, vals in stock_data.items():
            # Cases computation (float representation for partial cases or standard rounding)
            c_750 = vals["750"] / 12 if vals["750"] > 0 else 0
            c_500 = vals["500"] / 18 if vals["500"] > 0 else 0
            c_375 = vals["375"] / 24 if vals["375"] > 0 else 0
            c_180 = vals["180"] / 48 if vals["180"] > 0 else 0
            
            cases_records.append({
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Month": selected_month,
                "ASM": selected_asm,
                "TSE": selected_tse,
                "Outlet Code": outlet_code,
                "Outlet Name": outlet_name,
                "Brand": brand,
                "Type": "Cases",
                "750ml (12)':": round(c_750, 2),
                "500ml (18)": round(c_500, 2),
                "375ml (24)": round(c_375, 2),
                "180ml (48)": round(c_180, 2),
                "Total Cases": round(c_750 + c_500 + c_375 + c_180, 2)
            })

        # Process and combine uploaded documents into a single PDF
        pdf_writer = pypdf.PdfWriter()
        uploaded_files = [f for f in [upload_1, upload_2, upload_3, upload_4] if f is not None]
        
        for uploaded_file in uploaded_files:
            file_bytes = uploaded_file.read()
            file_extension = uploaded_file.name.split('.')[-1].lower()
            
            if file_extension == 'pdf':
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                for page in reader.pages:
                    pdf_writer.add_page(page)
            elif file_extension in ['png', 'jpg', 'jpeg']:
                image = Image.open(io.BytesIO(file_bytes))
                # Convert image to RGB PDF page
                rgb_image = image.convert('RGB')
                img_byte_arr = io.BytesIO()
                rgb_image.save(img_byte_arr, format='PDF')
                img_byte_arr.seek(0)
                
                img_reader = pypdf.PdfReader(img_byte_arr)
                for page in img_reader.pages:
                    pdf_writer.add_page(page)

        # Rename combined PDF file format: Outlet Code, Name and Month[cite: 1]
        safe_outlet_name = "".join(c for c in outlet_name if c.isalnum() or c.isspace()).strip()
        combined_pdf_filename = f"{outlet_code}_{safe_outlet_name}_{selected_month}.pdf"
        
        final_pdf_bytes = io.BytesIO()
        pdf_writer.write(final_pdf_bytes)
        final_pdf_bytes.seek(0)
        
        # Save to Google Sheets
        try:
            new_entry_df = pd.DataFrame(cases_records)
            updated_df = pd.concat([tertiary_df, new_entry_df], ignore_index=True)
            conn.update(worksheet="Tertiary Data", data=updated_df)
            
            st.success("✅ Data successfully converted to cases and saved to Google Sheets[cite: 1]!")
            
            # Optional: Provide download link for the combined PDF locally or upload storage integration
            st.download_button(
                label="📥 Download Combined Renamed PDF",
                data=final_pdf_bytes,
                file_name=combined_pdf_filename,
                mime="application/pdf"
            )
            
        except Exception as e:
            st.error(f"Error saving data to Google Sheets: {e}")
