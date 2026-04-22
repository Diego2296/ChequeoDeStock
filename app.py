import streamlit as st
import pandas as pd
import pdfplumber

st.set_page_config(page_title="Control de Stock - DYCSA", layout="wide")

st.title("🏗️ Validador de Stock para Construcción")
st.info("Carga el presupuesto en PDF y el stock diario en Excel para verificar disponibilidad.")

col1, col2 = st.columns(2)
with col1:
    pdf_file = st.file_uploader("1. Subir Presupuesto (PDF)", type="pdf")
with col2:
    excel_file = st.file_uploader("2. Subir Stock del Día (Excel)", type=["xlsx", "xls", "csv"])

if pdf_file and excel_file:
    # --- PROCESAR PDF ---
    data_pdf = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                for row in table:
                    try:
                        # PREVENCIÓN DE ERRORES: Nos aseguramos de que la fila tenga al menos 3 columnas
                        if len(row) >= 3 and row[0] and row[1]:
                            if any(char.isdigit() for char in str(row[1])):
                                codigo_pdf = str(row[0]).strip().replace('\n', '')
                                
                                # Limpieza de cantidad (ej: "1000.00 KG" -> 1000.0)
                                cant_raw = str(row[1]).split()[0]
                                cant_clean = float(cant_raw.replace('.', '').replace(',', '.'))
                                
                                data_pdf.append({
                                    "Material": codigo_pdf,
                                    "Descripción PDF": str(row[2]).strip().replace('\n', ' '),
                                    "Pedido": cant_clean
                                })
                    except Exception:
                        continue
    
    # LA MAGIA QUE SOLUCIONA EL ERROR: Forzamos la creación de columnas aunque no haya datos
    df_pdf = pd.DataFrame(data_pdf, columns=["Material", "Descripción PDF", "Pedido"])

    # Si la extracción falló y está vacío, le avisamos al usuario en vez de crashear
    if df_pdf.empty:
        st.error("⚠️ No se detectaron productos legibles en el PDF. Revisa el formato del archivo subido.")
    else:
        # --- PROCESAR EXCEL ---
        # Detectamos automáticamente el tipo de archivo para usar el motor correcto
        nombre_archivo = excel_file.name.lower()
        
        if nombre_archivo.endswith('.csv'):
            # Si el sistema contable le tiró un CSV, lo leemos separado por comas o punto y coma
            try:
                df_stock = pd.read_csv(excel_file)
            except:
                excel_file.seek(0) # Reiniciamos el puntero de lectura
                df_stock = pd.read_csv(excel_file, sep=';')
        elif nombre_archivo.endswith('.xls'):
            # Formato viejo de Excel
            df_stock = pd.read_excel(excel_file)
        else:
            # Formato nuevo de Excel (.xlsx) - Forzamos openpyxl
            df_stock = pd.read_excel(excel_file, engine='openpyxl')
        
        # Limpieza inicial de encabezados
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
            col_stock_real = df_stock.columns[-2]

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