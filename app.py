import streamlit as st
import pandas as pd
import pdfplumber

st.set_page_config(page_title="Control de Stock - DYCSA", layout="wide")

st.title("🏗️ Validador de Stock para Construcción")
st.info("Carga el presupuesto en PDF y el stock diario (incluso exportaciones de SAP) para verificar disponibilidad.")

col1, col2 = st.columns(2)
with col1:
    pdf_file = st.file_uploader("1. Subir Presupuesto (PDF)", type="pdf")
with col2:
    excel_file = st.file_uploader("2. Subir Stock del Día (SAP/Excel/CSV)", type=["xlsx", "xls", "csv"])

def leer_archivo_sap(file):
    """
    Función de fuerza bruta para leer exportaciones de SAP.
    Prueba todos los formatos posibles hasta que uno devuelva más de 1 columna.
    """
    # 1. Intento: Excel Moderno
    try:
        file.seek(0)
        df = pd.read_excel(file, engine='openpyxl')
        if not df.empty and len(df.columns) > 1: return df
    except: pass
    
    # 2. Intento: Excel Antiguo
    try:
        file.seek(0)
        df = pd.read_excel(file)
        if not df.empty and len(df.columns) > 1: return df
    except: pass

    # 3. Intento: CSV estándar
    try:
        file.seek(0)
        df = pd.read_csv(file)
        if len(df.columns) > 1: return df
    except: pass

    # 4. Intento: CSV europeo (Punto y coma)
    try:
        file.seek(0)
        df = pd.read_csv(file, sep=';')
        if len(df.columns) > 1: return df
    except: pass

    # 5. Intento: Formato SAP TSV (Tab-Separated Values) con UTF-16
    try:
        file.seek(0)
        df = pd.read_csv(file, sep='\t', encoding='utf-16')
        if len(df.columns) > 1: return df
    except: pass
    
    # 6. Intento: Formato SAP TSV con UTF-8
    try:
        file.seek(0)
        df = pd.read_csv(file, sep='\t', encoding='utf-8')
        if len(df.columns) > 1: return df
    except: pass

    # 7. Intento: HTML disfrazado de Excel (Muy común en SAP ALV)
    try:
        file.seek(0)
        # Leemos el contenido como HTML
        dfs = pd.read_html(file.read().decode('utf-8'))
        if len(dfs) > 0 and len(dfs[0].columns) > 1: return dfs[0]
    except: pass
    
    # Si todo lo anterior falla
    return None

if pdf_file and excel_file:
    # --- PROCESAR PDF ---
    data_pdf = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                for row in table:
                    try:
                        if len(row) >= 3 and row[0] and row[1]:
                            if any(char.isdigit() for char in str(row[1])):
                                codigo_pdf = str(row[0]).strip().replace('\n', '')
                                cant_raw = str(row[1]).split()[0]
                                cant_clean = float(cant_raw.replace('.', '').replace(',', '.'))
                                
                                data_pdf.append({
                                    "Material": codigo_pdf,
                                    "Descripción PDF": str(row[2]).strip().replace('\n', ' '),
                                    "Pedido": cant_clean
                                })
                    except Exception:
                        continue
    
    df_pdf = pd.DataFrame(data_pdf, columns=["Material", "Descripción PDF", "Pedido"])

    if df_pdf.empty:
        st.error("⚠️ No se detectaron productos legibles en el PDF. Revisa el formato del archivo subido.")
    else:
        # --- PROCESAR EXCEL / SAP ---
        df_stock = leer_archivo_sap(excel_file)
        
        if df_stock is None or df_stock.empty or len(df_stock.columns) < 2:
            st.error("❌ Formato de SAP no reconocido. Por favor, abre el archivo en Excel, ve a 'Guardar como...' y guárdalo explícitamente como 'Libro de Excel (*.xlsx)' antes de subirlo.")
            st.stop()
            
        # Limpieza de columnas
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
            if len(df_stock.columns) >= 2:
                col_stock_real = df_stock.columns[-2]
            else:
                col_stock_real = df_stock.columns[0]

        df_stock.rename(columns={col_stock_real: 'Stock_Disponible'}, inplace=True)

        # --- CRUCE DE DATOS ---
        df_final = pd.merge(df_pdf, df_stock, on="Material", how="left")
        
        df_final['Stock_Disponible'] = pd.to_numeric(df_final['Stock_Disponible'], errors='coerce').fillna(0)
        df_final['Diferencia'] = df_final['Stock_Disponible'] - df_final['Pedido']
        
        df_final['Estado'] = df_final['Diferencia'].apply(
            lambda x: "✅ OK" if x >= 0 else ("❌ FALTANTE" if x < 0 else "❓ NO ENCONTRADO")
        )

        # --- RESULTADOS ---
        st.subheader("📋 Resultado del Chequeo")
        
        def color_result(val):
            color = '#28a745' if "✅ OK" in val else '#dc3545'
            if "NO ENCONTRADO" in val: color = '#6c757d'
            return f'background-color: {color}; color: white; font-weight: bold'

        cols_a_mostrar = ['Material', 'Descripción PDF', 'Pedido', 'Stock_Disponible', 'Estado']
        
        st.dataframe(
            df_final[[c for c in cols_a_mostrar if c in df_final.columns]].style.applymap(color_result, subset=['Estado']), 
            use_container_width=True
        )

        csv = df_final.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Descargar Reporte CSV", csv, "control_stock.csv", "text/csv")
