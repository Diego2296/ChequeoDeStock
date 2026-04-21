import streamlit as st
import pandas as pd
import pdfplumber
import re

st.set_page_config(page_title="Control de Stock Constructora", layout="wide")

st.title("🏗️ Validador de Presupuestos")

# Carga de archivos
col1, col2 = st.columns(2)
with col1:
    pdf_file = st.file_uploader("Subir Presupuesto (PDF)", type="pdf")
with col2:
    excel_file = st.file_uploader("Subir Stock (Excel)", type=["xlsx", "xls"])

if pdf_file and excel_file:
    data_pdf = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                for row in table:
                    # Detectamos filas que tengan formato de producto (Código suele ser alfanumérico largo)
                    if row[0] and row[1] and any(char.isdigit() for char in row[1]):
                        try:
                            # Limpieza de cantidad: extrae el número sin importar la unidad (KG, UN, etc.)
                            # "1.000,00 KG" -> 1000.0
                            cant_raw = row[1].split()[0]
                            cant_clean = float(cant_raw.replace('.', '').replace(',', '.'))
                            
                            data_pdf.append({
                                "Material": row[0].strip(),
                                "Descripción": row[2].strip(),
                                "Pedido": cant_clean
                            })
                        except:
                            continue
    
    df_presupuesto = pd.DataFrame(data_pdf)

    # Procesar Excel
    df_stock = pd.read_excel(excel_file)
    
    # Cruce de datos (Join)
    df_final = pd.merge(df_presupuesto, df_stock, on="Material", how="left")
    
    # Cálculo de disponibilidad
    df_final['Diferencia'] = df_final['Libre utilización'] - df_final['Pedido']
    df_final['Estado'] = df_final['Diferencia'].apply(
        lambda x: "✅ Disponible" if x >= 0 else ("⚠️ FALTANTE" if x < 0 else "❓ No encontrado")
    )

    st.subheader("📊 Resultados de la Comparación")
    
    # Estilado simple
    def highlight_status(val):
        color = '#ff4b4b' if "FALTANTE" in val else ('#28a745' if "Disponible" in val else '#6c757d')
        return f'background-color: {color}; color: white; font-weight: bold'

    st.dataframe(df_final[['Material', 'Descripción', 'Pedido', 'Libre utilización', 'Estado']].style.applymap(highlight_status, subset=['Estado']), use_container_width=True)