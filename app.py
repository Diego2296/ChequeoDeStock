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

    if pdf_file and excel_file:
    # --- PROCESAR PDF ---
    data_pdf = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                for row in table:
                    # Filtramos filas vacías o encabezados
                    if row[0] and row[1] and any(char.isdigit() for char in str(row[1])):
                        try:
                            # Limpieza de código: quitamos saltos de línea internos
                            codigo_pdf = str(row[0]).strip().replace('\n', '')
                            
                            # Limpieza de cantidad: extrae solo el número
                            cant_raw = str(row[1]).split()[0]
                            cant_clean = float(cant_raw.replace('.', '').replace(',', '.'))
                            
                            data_pdf.append({
                                "Material": codigo_pdf,
                                "Descripción": str(row[2]).strip().replace('\n', ' '),
                                "Pedido": cant_clean
                            })
                        except:
                            continue
    
    df_pdf = pd.DataFrame(data_pdf)

    # --- PROCESAR EXCEL ---
    df_stock = pd.read_excel(excel_file)
    
    # LIMPIEZA CLAVE: Quitamos espacios ocultos en los nombres de las columnas del Excel
    df_stock.columns = [str(c).strip() for c in df_stock.columns]
    
    # Aseguramos que la columna 'Material' en el Excel sea texto y no tenga espacios
    if 'Material' in df_stock.columns:
        df_stock['Material'] = df_stock['Material'].astype(str).str.strip()

    # --- CRUCE DE DATOS ---
    # Ahora 'Material' existe en ambos porque lo forzamos arriba
    df_final = pd.merge(df_pdf, df_stock, on="Material", how="left")
    
    # Lógica de stock
    df_final['Diferencia'] = df_final['Libre utilización'] - df_final['Pedido']
    df_final['Estado'] = df_final['Diferencia'].apply(
        lambda x: "✅ OK" if x >= 0 else ("❌ FALTANTE" if x < 0 else "❓ NO ENCONTRADO")
    )

    # --- MOSTRAR RESULTADOS ---
    st.subheader("📋 Resultado del Chequeo")
    cols_a_mostrar = ['Material', 'Descripción', 'Pedido', 'Libre utilización', 'Estado']
    
    # Mostramos solo las columnas que existen
    st.dataframe(df_final[[c for c in cols_a_mostrar if c in df_final.columns]], use_container_width=True)