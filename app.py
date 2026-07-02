import streamlit as st
import pandas as pd
import pdfplumber
import difflib
import urllib.request
import io

# Configuración de la página
st.set_page_config(page_title="Auditor de Estándares", layout="wide")

st.title("🔍 Auditor de Actualizaciones de Estándares")
st.subheader("Detecta cambios sutiles (in-place updates) pegando texto, usando enlaces web o subiendo archivos.")

# --- FUNCIONES DE EXTRACCIÓN ---
def extraer_texto_pdf(stream):
    texto_completo = []
    with pdfplumber.open(stream) as pdf:
        for i, pagina in enumerate(pdf.pages):
            texto_pag = pagina.extract_text()
            if texto_pag:
                for linea in texto_pag.split('\n'):
                    if linea.strip():
                        texto_completo.append(f"[Pág {i+1}] {linea.strip()}")
    return texto_completo

def extraer_texto_excel(stream):
    texto_completo = []
    df = pd.read_excel(stream)
    for index, fila in df.iterrows():
        fila_str = " | ".join([f"{col}: {val}" for col, val in fila.items() if pd.notna(val)])
        texto_completo.append(f"[Fila {index+2}] {fila_str}")
    return texto_completo

# --- INTERFAZ DE USUARIO ---
col1, col2 = st.columns(2)

with col1:
    st.header("1. Información Base")
    texto_base_raw = st.text_area(
        "Pega aquí el texto actual de tu Base de Datos / Estándar Original:",
        height=350,
        placeholder="Copia y pega las líneas o párrafos que tienes registrados actualmente..."
    )
    lineas_base = [linea.strip() for linea in texto_base_raw.split('\n') if linea.strip()]

with col2:
    st.header("2. Nueva Fuente a Comparar")
    
    # Opción para elegir el método de entrada
    metodo_entrada = st.radio(
        "¿Cómo quieres ingresar la nueva información?",
        ["Pegar Texto Directamente", "Enlace (URL) de un PDF", "Subir Archivo Local (PDF / Excel)"]
    )
    
    lineas_nuevas = []
    procesar_fuente = False

    if metodo_entrada == "Pegar Texto Directamente":
        texto_nuevo_raw = st.text_area(
            "Pega aquí el texto de la nueva actualización / sweep:",
            height=250,
            placeholder="Copia y pega el nuevo texto detectado aquí..."
        )
        if texto_nuevo_raw.strip():
            lineas_nuevas = [linea.strip() for linea in texto_nuevo_raw.split('\n') if linea.strip()]
            procesar_fuente = True

    elif metodo_entrada == "Enlace (URL) de un PDF":
        url_input = st.text_input("Introduce la URL directa del PDF:", placeholder="https://ejemplo.com/estandar-actualizado.pdf")
        if url_input.strip():
            try:
                # Descargar el PDF en memoria de forma segura
                req = urllib.request.Request(url_input, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response:
                    pdf_memory = io.BytesIO(response.read())
                    lineas_nuevas = extraer_texto_pdf(pdf_memory)
                    procesar_fuente = True
            except Exception as e:
                st.error(f"❌ No se pudo acceder o leer el PDF desde esa URL. Verifica el enlace. Error: {e}")

    elif metodo_entrada == "Subir Archivo Local (PDF / Excel)":
        tipo_archivo = st.radio("Selecciona el formato del archivo:", ["PDF", "Excel"])
        archivo_subido = st.file_uploader(f"Sube el archivo {tipo_archivo}", type=["pdf", "xlsx"])
        if archivo_subido:
            if tipo_archivo == "PDF":
                lineas_nuevas = extraer_texto_pdf(archivo_subido)
            else:
                lineas_nuevas = extraer_texto_excel(archivo_subido)
            procesar_fuente = True

# --- PROCESAMIENTO Y COMPARACIÓN ---
if st.button("🚀 Ejecutar Barrido de Información"):
    if lineas_base and procesar_fuente and lineas_nuevas:
        
        # Calcular similitud general
        texto_base_unido = " ".join(lineas_base)
        texto_nuevo_unido = " ".join(lineas_nuevas)
        similitud = difflib.SequenceMatcher(None, texto_base_unido, texto_nuevo_unido).ratio() * 100
        
        st.subheader("📊 Diagnóstico del Barrido")
        st.metric(label="Porcentaje de Coincidencia Global", value=f"{similitud:.2f}%")
        
        if similitud == 100:
            st.success("✅ ¡No se detectaron cambios! Toda la información coincide exactamente.")
        else:
            st.warning("⚠️ Se detectaron discrepancias. Revisa los cambios detallados abajo:")
            
            # Comparación línea por línea
            diferenciador = difflib.Differ()
            resultado_diff = list(diferenciador.compare(lineas_base, lineas_nuevas))
            
            st.write("### 🔍 Reporte Detallado de Cambios")
            st.caption("Leyenda: El texto eliminado de tu base se resalta en rojo. Las nuevas actualizaciones (In-place) se muestran en verde.")
            
            html_resultado = []
            
            for linea in resultado_diff:
                if linea.startswith("- "):
                    html_resultado.append(f"<div style='background-color: #ffcccc; color: #cc0000; padding: 5px; margin: 2px 0; border-left: 5px solid #cc0000;'>❌ <b>Eliminado o Modificado en tu Base:</b> <del>{linea[2:]}</del></div>")
                elif linea.startswith("+ "):
                    html_resultado.append(f"<div style='background-color: #e2f0d9; color: #385723; padding: 5px; margin: 2px 0; border-left: 5px solid #385723;'>➕ <b>Nuevo cambio detectado (In-place):</b> {linea[2:]}</div>")
                elif linea.startswith("  "):
                    pass
                    
            st.markdown("".join(html_resultado), unsafe_allow_html=True)
    else:
        st.info("💡 Por favor, asegúrate de ingresar la información base (izquierda) y configurar correctamente la nueva fuente (derecha) antes de ejecutar.")
