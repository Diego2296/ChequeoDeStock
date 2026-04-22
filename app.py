import streamlit as st
import pandas as pd
import pdfplumber
import re

# CAMBIO 1: Nombre de pestaña fijo
st.set_page_config(page_title="Control de Stock", layout="wide")

st.title("🏗️ Validador de Stock para Construcción")
st.info("Carga el presupuesto en PDF y el stock diario (incluso exportaciones de SAP) para verificar disponibilidad.")

col1, col2 = st.columns(2)
with col1:
    pdf_file = st.file_uploader("1. Subir Presupuesto (PDF)", type="pdf")
with col2:
    excel_file = st.file_uploader("2. Subir Stock del Día (SAP/Excel/CSV)", type=["xlsx", "xls", "csv"])

def limpiar_numero(num_str):
    """Convierte números complejos a float de Python"""
    num_str = str(num_str).strip()
    if '.' in num_str and ',' in num_str:
        if num_str.rfind('.') > num_str.rfind(','):
            num_str = num_str.replace(',', '')
        else:
            num_str = num_str.replace('.', '').replace(',', '.')
    else:
        if ',' in num_str:
            if num_str.count(',') > 1 or (len(num_str) - num_str.rfind(',') == 4):
                num_str = num_str.replace(',', '')
            else:
                num_str = num_str.replace(',', '.')
        elif '.' in num_str:
            if num_str.count('.') > 1 or (len(num_str) - num_str.rfind('.') == 4):
                num_str = num_str.replace('.', '')
    try:
        return float(num_str)
    except:
        return 0.0

def leer_archivo_sap(file):
    """Función de fuerza bruta para leer exportaciones de SAP"""
    formatos = [
        lambda f: pd.read_excel(f, engine='openpyxl'),
        lambda f: pd.read_excel(f),
        lambda f: pd.read_csv(f),
        lambda f: pd.read_csv(f, sep=';'),
        lambda f: pd.read_csv(f, sep='\t', encoding='utf-16'),
        lambda f: pd.read_csv(f, sep='\t', encoding='utf-8')
    ]
    
    for intento in formatos:
        try:
            file.seek(0)
            df = intento(file)
            if not df.empty and len(df.columns) > 1: return df
        except: pass

    try:
        file.seek(0)
        dfs = pd.read_html(file.read().decode('utf-8'))
        if len(dfs) > 0 and len(dfs[0].columns) > 1: return dfs[0]
    except: pass
    
    return None

if pdf_file and excel_file:
    data_pdf = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                for line in text.split('\n'):
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        codigo = parts[0]
                        cant_raw = parts[1]
                        
                        if len(codigo) >= 4 and codigo.replace('-', '').replace('_', '').isalnum() and any(c.isdigit() for c in cant_raw):
                            if re.match(r'^[\d\.,]+$', cant_raw):
                                try:
                                    cant_clean = limpiar_numero(cant_raw)
                                    desc_start = 3 if len(parts) > 2 and parts[2].upper() in ['KG', 'UN', 'MT', 'MTS', 'LTS', 'C/U', 'M2', 'M3'] else 2
                                    desc = " ".join(parts[desc_start:])
                                    desc = re.sub(r'(\$\s*)?[\d\.,]+\s*(\$\s*)?[\d\.,]+$', '', desc).strip()
                                    
                                    data_pdf.append({
                                        "Material": codigo,
                                        "Descripción PDF": desc,
                                        "Pedido": cant_clean
                                    })
                                except: pass

    df_pdf = pd.DataFrame(data_pdf, columns=["Material", "Descripción PDF", "Pedido"])
    df_pdf = df_pdf.drop_duplicates(subset=["Material", "Pedido"])

    if df_pdf.empty:
        st.error("⚠️ No se detectaron productos legibles en el PDF.")
    else:
        df_stock = leer_archivo_sap(excel_file)
        
        if df_stock is None or df_stock.empty:
            st.error("❌ No se pudo leer el archivo de stock.")
            st.stop()
            
        df_stock.columns = [str(c).strip() for c in df_stock.columns]
        
        if 'Material' in df_stock.columns:
            df_stock['Material'] = df_stock['Material'].astype(str).str.strip()
        else:
            df_stock.rename(columns={df_stock.columns[0]: 'Material'}, inplace=True)
            df_stock['Material'] = df_stock['Material'].astype(str).str.strip()

        col_stock_real = None
        for col in df_stock.columns:
            if "libre" in col.lower() and "utilizaci" in col.lower():
                col_stock_real = col
                break
                
        if not col_stock_real:
            col_stock_real = df_stock.columns[-2] if len(df_stock.columns) >= 2 else df_stock.columns[0]

        df_stock.rename(columns={col_stock_real: 'Stock_Disponible'}, inplace=True)

        df_final = pd.merge(df_pdf, df_stock, on="Material", how="left")
        df_final['Stock_Disponible'] = pd.to_numeric(df_final['Stock_Disponible'], errors='coerce').fillna(0)
        df_final['Diferencia'] = df_final['Stock_Disponible'] - df_final['Pedido']
        
        df_final['Estado'] = df_final['Diferencia'].apply(
            lambda x: "✅ OK" if x >= 0 else ("❌ FALTANTE" if x < 0 else "❓ NO ENCONTRADO")
        )

        st.subheader("📋 Resultado del Chequeo")
        
        def color_result(val):
            color = '#28a745' if "✅ OK" in val else '#dc3545'
            if "NO ENCONTRADO" in val: color = '#6c757d'
            return f'background-color: {color}; color: white; font-weight: bold'

        # CAMBIO 2: Reordenar lista de columnas (Estado antes que Stock_Disponible)
        cols_a_mostrar = ['Material', 'Descripción PDF', 'Pedido', 'Estado', 'Stock_Disponible']
        
        st.dataframe(
            df_final[[c for c in cols_a_mostrar if c in df_final.columns]].style.map(color_result, subset=['Estado']), 
            use_container_width=True
        )

        csv = df_final.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Descargar Reporte CSV", csv, "control_stock.csv", "text/csv")
