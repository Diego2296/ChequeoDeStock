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
    
    # Limpieza de espacios en los nombres de las columnas
    df_stock.columns = [str(c).strip() for c in df_stock.columns]
    
    # Aseguramos que la columna 'Material' sea texto
    if 'Material' in df_stock.columns:
        df_stock['Material'] = df_stock['Material'].astype(str).str.strip()

    # DETECCIÓN AUTOMÁTICA DE LA COLUMNA DE STOCK
    col_stock_real = None
    for col in df_stock.columns:
        # Buscamos variaciones (sin importar mayúsculas)
        if "libre" in col.lower() and "utilizaci" in col.lower():
            col_stock_real = col
            break
            
    # Si no la encuentra por nombre, asumimos que es la penúltima (suele ser así en estos reportes)
    if not col_stock_real:
        col_stock_real = df_stock.columns[-2]

    # Renombramos la columna a un nombre estándar y fácil para operar
    df_stock.rename(columns={col_stock_real: 'Stock_Disponible'}, inplace=True)

    # --- CRUCE DE DATOS ---
    df_final = pd.merge(df_pdf, df_stock, on="Material", how="left")
    
    # Limpiamos la columna de stock por si hay celdas vacías o con texto raro y la forzamos a número
    df_final['Stock_Disponible'] = pd.to_numeric(df_final['Stock_Disponible'], errors='coerce').fillna(0)
    
    # Lógica matemática (ahora usamos nuestro nombre estándar)
    df_final['Diferencia'] = df_final['Stock_Disponible'] - df_final['Pedido']
    df_final['Estado'] = df_final['Diferencia'].apply(
        lambda x: "✅ OK" if x >= 0 else ("❌ FALTANTE" if x < 0 else "❓ NO ENCONTRADO")
    )

    # --- MOSTRAR RESULTADOS ---
    st.subheader("📋 Resultado del Chequeo")
    
    # Lista de columnas que queremos mostrar
    cols_a_mostrar = ['Material', 'Descripción', 'Pedido', 'Stock_Disponible', 'Estado']
    
    # Mostramos el dataframe usando solo las columnas que sabemos que existen
    st.dataframe(df_final[[c for c in cols_a_mostrar if c in df_final.columns]], use_container_width=True)