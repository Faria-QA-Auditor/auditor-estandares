import streamlit as st
import pandas as pd
import pdfplumber
import difflib
import urllib.request
import io
import re

# Configuración de la página
st.set_page_config(page_title="Auditor de Estándares", layout="wide")

st.title("🔍 Auditor de Actualizaciones de Estándares")
st.subheader("Mapeo estricto por numerales: Compara secciones equivalentes y detecta adiciones o eliminaciones.")

# --- FUNCIONES DE EXTRACCIÓN Y MAPEO ---
def mapear_por_numerales(texto_crudo, etiqueta_origen=""):
    """
    Extrae el texto y lo organiza en un diccionario indexado por su numeral principal (e.g., '(4)', '(12)').
    Evita desalineaciones cruzadas entre numerales distintos.
    """
    diccionario_secciones = {}
    texto_filtrado = re.sub(r'\s+', ' ', texto_crudo).replace('//', ' ')
    
    # Captura numerales principales al inicio de un bloque (e.g., (4), (12))
    patron_numeral_principal = r'(\(\d+\))'
    partes = re.split(patron_numeral_principal, texto_filtrado)
    
    numeral_actual = None
    texto_acumulado = ""
    
    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue
        
        if re.match(patron_numeral_principal, parte):
            if numeral_actual and texto_acumulado:
                diccionario_secciones[numeral_actual] = texto_acumulado.strip()
            numeral_actual = parte
            texto_acumulado = parte + " "
        else:
            if numeral_actual:
                texto_acumulado += parte + " "
            else:
                # Texto introductorio antes del primer numeral
                diccionario_secciones[f"{etiqueta_origen} [Intro]"] = parte
                
    if numeral_actual and texto_acumulado:
        diccionario_secciones[numeral_actual] = texto_acumulado.strip()
        
    return diccionario_secciones

def extraer_texto_pdf(stream):
    texto_completo = []
    with pdfplumber.open(stream) as pdf:
        for pagina in pdf.pages:
            texto_pag = pagina.extract_text()
            if texto_pag:
                texto_completo.append(texto_pag)
    # Unimos todo el PDF para mapear los numerales globalmente a lo largo de las páginas
    return mapear_por_numerales(" ".join(texto_completo), "[PDF]")

def extraer_texto_excel(stream):
    diccionario_secciones = {}
    df = pd.read_excel(stream)
    for index, fila in df.iterrows():
        fila_str = " | ".join([f"{col}: {val}" for col, val in fila.items() if pd.notna(val)])
        # Intentar extraer un numeral de la fila, si no, usar el número de fila
        match = re.search(r'(\(\d+\))', fila_str)
        clave = match.group(1) if match else f"[Fila {index+2}]"
        diccionario_secciones[clave] = fila_str
    return diccionario_secciones

# --- INTERFAZ DE USUARIO ---
col1, col2 = st.columns(2)

with col1:
    st.header("1. Información Base")
    texto_base_raw = st.text_area(
        "Pega aquí el texto actual de tu Base de Datos / Estándar Original:",
        height=350,
        placeholder="Copia y pega las líneas o párrafos que tienes registrados actualmente..."
    )
    dicc_base = {}
    if texto_base_raw.strip():
        dicc_base = mapear_por_numerales(texto_base_raw, "[Base]")

with col2:
    st.header("2. Nueva Fuente a Comparar")
    metodo_entrada = st.radio(
        "¿Cómo quieres ingresar la nueva información?",
        ["Pegar Texto Directamente", "Enlace (URL) de un PDF", "Subir Archivo Local (PDF / Excel)"]
    )
    
    dicc_nuevo = {}
    procesar_fuente = False

    if metodo_entrada == "Pegar Texto Directamente":
        texto_nuevo_raw = st.text_area(
            "Pega aquí el texto de la nueva actualización:",
            height=250,
            placeholder="Copia y pega el nuevo texto detectado aquí..."
        )
        if texto_nuevo_raw.strip():
            dicc_nuevo = mapear_por_numerales(texto_nuevo_raw, "[Texto Pegado]")
            procesar_fuente = True

    elif metodo_entrada == "Enlace (URL) de un PDF":
        url_input = st.text_input("Introduce la URL directa del PDF:", placeholder="https://ejemplo.com/estandar.pdf")
        if url_input.strip():
            try:
                req = urllib.request.Request(url_input, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response:
                    pdf_memory = io.BytesIO(response.read())
                    dicc_nuevo = extraer_texto_pdf(pdf_memory)
                    procesar_fuente = True
            except Exception as e:
                st.error(f"❌ Error al acceder al PDF: {e}")

    elif metodo_entrada == "Subir Archivo Local (PDF / Excel)":
        tipo_archivo = st.radio("Selecciona el formato del archivo:", ["PDF", "Excel"])
        archivo_subido = st.file_uploader(f"Sube el archivo {tipo_archivo}", type=["pdf", "xlsx"])
        if archivo_subido:
            if tipo_archivo == "PDF":
                dicc_nuevo = extraer_texto_pdf(archivo_subido)
            else:
                dicc_nuevo = extraer_texto_excel(archivo_subido)
            procesar_fuente = True

# --- PROCESAMIENTO Y COMPARACIÓN EN PARALELO ---
if st.button("🚀 Ejecutar Barrido de Información"):
    if dicc_base and procesar_fuente and dicc_nuevo:
        
        # Consolidar todas las claves/numerales únicos identificados en ambas fuentes
        todos_los_numerales = sorted(list(set(dicc_base.keys()) | set(dicc_nuevo.keys())), key=lambda x: len(x))
        
        # Calcular similitud global de los contenidos
        texto_base_unido = " ".join(dicc_base.values())
        texto_nuevo_unido = " ".join(dicc_nuevo.values())
        similitud = difflib.SequenceMatcher(None, texto_base_unido, texto_nuevo_unido).ratio() * 100
        
        st.subheader("📊 Diagnóstico del Barrido")
        st.metric(label="Porcentaje de Coincidencia Global", value=f"{similitud:.2f}%")
        
        if similitud == 100:
            st.success("✅ ¡No se detectaron cambios! Toda la información coincide perfectamente por secciones.")
        else:
            st.warning("⚠️ Se detectaron discrepancias localizadas. Analizando cambios específicos:")
            
            html_resultado = []
            
            for numeral in todos_los_numerales:
                en_base = numeral in dicc_base
                en_nuevo = numeral in dicc_nuevo
                
                # Caso 1: El numeral existe en ambos (Comparación Directa e Inteligente)
                if en_base and en_nuevo:
                    txt_b = dicc_base[numeral]
                    txt_n = dicc_nuevo[numeral]
                    
                    if txt_b != txt_n:
                        # Resaltar sub-cambios internos (como literales A, B, C) de forma limpia
                        html_resultado.append(f"""
                        <div style='background-color: #fff9e6; padding: 12px; margin: 10px 0; border-left: 6px solid #ffcc00; border-radius: 4px; font-family: sans-serif;'>
                            <span style='background-color: #e6f2ff; color: #0044cc; padding: 3px 8px; border-radius: 3px; font-size: 0.9em; font-weight: bold;'>📍 Numeral Correspondiente: {numeral}</span>
                            <div style='margin-top: 8px; color: #cc0000;'><b>🛑 ANTES (Desactualizado):</b><br>{txt_b}</div>
                            <div style='margin-top: 6px; color: #2e7d32;'><b>🟢 AHORA (Actualizado):</b><br>{txt_n}</div>
                        </div>
                        """)
                
                # Caso 2: El numeral estaba en tu base pero desapareció por completo en el nuevo
                elif en_base and not en_nuevo:
                    html_resultado.append(f"""
                    <div style='background-color: #ffeeef; padding: 12px; margin: 10px 0; border-left: 6px solid #d32f2f; border-radius: 4px; font-family: sans-serif;'>
                        <span style='background-color: #e6f2ff; color: #0044cc; padding: 3px 8px; border-radius: 3px; font-size: 0.9em; font-weight: bold;'>📍 Numeral Eliminado: {numeral}</span>
                        <div style='margin-top: 8px; color: #d32f2f;'><b>🗑️ REMOVIDO COMPLETAMENTE DE LA FUENTE NUEVA:</b><br>{dicc_base[numeral]}</div>
                    </div>
                    """)
                
                # Caso 3: Es un numeral completamente nuevo (Inyección in-place) que antes no tenías
                elif not en_base and en_nuevo:
                    html_resultado.append(f"""
                    <div style='background-color: #edf7ed; padding: 12px; margin: 10px 0; border-left: 6px solid #388e3c; border-radius: 4px; font-family: sans-serif;'>
                        <span style='background-color: #e6f2ff; color: #0044cc; padding: 3px 8px; border-radius: 3px; font-size: 0.9em; font-weight: bold;'>📍 Numeral Nuevo Detectado: {numeral}</span>
                        <div style='margin-top: 8px; color: #388e3c;'><b>✨ NUEVA SECCIÓN ADICIONADA:</b><br>{dicc_nuevo[numeral]}</div>
                    </div>
                    """)
            
            if html_resultado:
                st.markdown("".join(html_resultado), unsafe_allow_html=True)
            else:
                st.info("No hay cambios estructurales que mostrar en los numerales principales.")
    else:
        st.info("💡 Asegúrate de llenar el texto base y proveer la nueva fuente antes de ejecutar el barrido.")
