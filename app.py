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
st.subheader("Mapeo estricto y ordenado por numerales con resaltado preciso de cambios internos.")

# --- FUNCIONES DE EXTRACCIÓN Y MAPEO ---
def mapear_por_numerales(texto_crudo, etiqueta_origen=""):
    """
    Organiza el texto en un diccionario indexado por su numeral principal (e.g., '(4)').
    """
    diccionario_secciones = {}
    texto_filtrado = re.sub(r'\s+', ' ', texto_crudo).replace('//', ' ')
    
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
    return mapear_por_numerales(" ".join(texto_completo), "[PDF]")

def extraer_texto_excel(stream):
    diccionario_secciones = {}
    df = pd.read_excel(stream)
    for index, fila in df.iterrows():
        fila_str = " | ".join([f"{col}: {val}" for col, val in fila.items() if pd.notna(val)])
        match = re.search(r'(\(\d+\))', fila_str)
        clave = match.group(1) if match else f"[Fila {index+2}]"
        diccionario_secciones[clave] = fila_str
    return diccionario_secciones

def obtener_clave_ordenamiento(item):
    """
    Extrae el número entero dentro de los paréntesis para ordenar numéricamente (e.g., '(12)' -> 12).
    Si no tiene número, lo manda al final como texto.
    """
    match = re.search(r'\d+', item)
    if match:
        return (0, int(match.group()))
    return (1, item)

def generar_diff_palabras(texto_viejo, texto_nuevo):
    """
    Compara dos textos palabra por palabra e inyecta marcado HTML 
    para resaltar adiciones y eliminaciones de forma quirúrgica.
    """
    palabras_viejas = texto_viejo.split()
    palabras_nuevas = texto_nuevo.split()
    
    diff = difflib.ndiff(palabras_viejas, palabras_nuevas)
    
    resultado_viejo = []
    resultado_nuevo = []
    
    for token in diff:
        palabra = token[2:]
        if token.startswith('  '):  # Sin cambios
            resultado_viejo.append(palabra)
            resultado_nuevo.append(palabra)
        elif token.startswith('- '):  # Eliminado / Modificado en el origen
            resultado_viejo.append(f"<span style='background-color: #ffb3b3; color: #b30000; font-weight: bold; padding: 1px 3px; border-radius: 3px;'>{palabra}</span>")
        elif token.startswith('+ '):  # Nuevo / Adicionado
            resultado_nuevo.append(f"<span style='background-color: #cceff5; color: #007a87; font-weight: bold; padding: 1px 3px; border-radius: 3px;'>{palabra}</span>")
            
    return " ".join(resultado_viejo), " ".join(resultado_nuevo)

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

# --- PROCESAMIENTO Y COMPARACIÓN ---
if st.button("🚀 Ejecutar Barrido de Información"):
    if dicc_base and procesar_fuente and dicc_nuevo:
        
        # ORDENAMIENTO ESTRICTO: Unimos las llaves y las ordenamos numéricamente
        todos_los_numerales = sorted(list(set(dicc_base.keys()) | set(dicc_nuevo.keys())), key=obtener_clave_ordenamiento)
        
        texto_base_unido = " ".join(dicc_base.values())
        texto_nuevo_unido = " ".join(dicc_nuevo.values())
        similitud = difflib.SequenceMatcher(None, texto_base_unido, texto_nuevo_unido).ratio() * 100
        
        st.subheader("📊 Diagnóstico del Barrido")
        st.metric(label="Porcentaje de Coincidencia Global", value=f"{similitud:.2f}%")
        
        if similitud == 100:
            st.success("✅ ¡No se detectaron cambios! Toda la información coincide perfectamente.")
        else:
            st.warning("⚠️ Se detectaron discrepancias analizadas por orden numérico:")
            st.write("### 🔍 Mapeo de Actualizaciones In-Place")
            
            for numeral in todos_los_numerales:
                en_base = numeral in dicc_base
                en_nuevo = numeral in dicc_nuevo
                
                # Caso 1: El numeral existe en ambos pero tiene variaciones internas
                if en_base and en_nuevo:
                    txt_b = dicc_base[numeral]
                    txt_n = dicc_nuevo[numeral]
                    
                    if txt_b != txt_n:
                        # Generar el resaltado preciso de palabras modificadas
                        html_viejo, html_nuevo = generar_diff_palabras(txt_b, txt_n)
                        
                        with st.container():
                            st.info(f"**📍 Numeral Correspondiente: {numeral}**")
                            st.markdown(f"🔴 **ANTES (Desactualizado - Elementos modificados resaltados):**")
                            st.markdown(html_viejo, unsafe_allow_html=True)
                            st.markdown(f"🟢 **AHORA (Actualizado - Nuevas inserciones resaltadas):**")
                            st.markdown(html_nuevo, unsafe_allow_html=True)
                            st.write("---")
                
                # Caso 2: El numeral existía pero fue removido por completo
                elif en_base and not en_nuevo:
                    with st.container():
                        st.error(f"**📍 Numeral Eliminado en la Nueva Fuente: {numeral}**")
                        st.markdown(f"🗑️ **CONTENIDO REMOVIDO COMPLETAMENTE:** \n\n{dicc_base[numeral]}")
                        st.write("---")
                
                # Caso 3: Es un numeral enteramente nuevo
                elif not en_base and en_nuevo:
                    with st.container():
                        st.success(f"**📍 Numeral Nuevo Detectado: {numeral}**")
                        st.markdown(f"✨ **NUEVA SECCIÓN ADICIONADA:** \n\n{dicc_nuevo[numeral]}")
                        st.write("---")
    else:
        st.info("💡 Asegúrate de llenar el texto base y de ingresar la nueva fuente antes de ejecutar el barrido.")
