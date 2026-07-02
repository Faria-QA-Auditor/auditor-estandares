import streamlit as st
import pandas as pd
import pdfplumber
import difflib
import urllib.request
import io

# Configuración de la página
st.set_page_config(page_title="Auditor de Estándares", layout="wide")

st.title("🔍 Auditor de Actualizaciones de Estándares")
st.subheader("Detecta in-place updates emparejando el texto desactualizado con su versión nueva.")

# --- FUNCIONES DE EXTRACCIÓN ---
def extraer_texto_pdf(stream):
    texto_completo = []
    with pdfplumber.open(stream) as pdf:
        for i, pagina in enumerate(pdf.pages):
            texto_pag = pagina.extract_text()
            if texto_pag:
                for linea in texto_pag.split('\n'):
                    if linea.strip():
                        # Guardamos el texto junto con una etiqueta oculta de ubicación
                        texto_completo.append(f"[Pág {i+1}]|||{linea.strip()}")
    return texto_completo

def extraer_texto_excel(stream):
    texto_completo = []
    df = pd.read_excel(stream)
    for index, fila in df.iterrows():
        fila_str = " | ".join([f"{col}: {val}" for col, val in fila.items() if pd.notna(val)])
        texto_completo.append(f"[Fila {index+2}]|||{fila_str}")
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
    # Limpieza de líneas base
    lineas_base = [linea.strip() for linea in texto_base_raw.split('\n') if linea.strip()]

with col2:
    st.header("2. Nueva Fuente a Comparar")
    metodo_entrada = st.radio(
        "¿Cómo quieres ingresar la nueva información?",
        ["Pegar Texto Directamente", "Enlace (URL) de un PDF", "Subir Archivo Local (PDF / Excel)"]
    )
    
    lineas_nuevas = []
    procesar_fuente = False

    if metodo_entrada == "Pegar Texto Directamente":
        texto_nuevo_raw = st.text_area(
            "Pega aquí el texto de la nueva actualización:",
            height=250,
            placeholder="Copia y pega el nuevo texto detectado aquí..."
        )
        if texto_nuevo_raw.strip():
            # Para texto pegado, la ubicación es genérica u obtenida por línea
            lineas_nuevas = [f"[Línea {i+1}]|||{linea.strip()}" for i, linea in enumerate(texto_nuevo_raw.split('\n')) if linea.strip()]
            procesar_fuente = True

    elif metodo_entrada == "Enlace (URL) de un PDF":
        url_input = st.text_input("Introduce la URL directa del PDF:", placeholder="https://ejemplo.com/estandar.pdf")
        if url_input.strip():
            try:
                req = urllib.request.Request(url_input, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response:
                    pdf_memory = io.BytesIO(response.read())
                    lineas_nuevas = extraer_texto_pdf(pdf_memory)
                    procesar_fuente = True
            except Exception as e:
                st.error(f"❌ Error al acceder al PDF: {e}")

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
        
        # Separar el texto limpio de las etiquetas de ubicación para calcular la similitud matemática
        limpias_base = [l.split("|||")[-1] for l in lineas_base]
        limpias_nuevas = [l.split("|||")[-1] for l in lineas_nuevas]
        
        similitud = difflib.SequenceMatcher(None, " ".join(limpias_base), " ".join(limpias_nuevas)).ratio() * 100
        
        st.subheader("📊 Diagnóstico del Barrido")
        st.metric(label="Porcentaje de Coincidencia Global", value=f"{similitud:.2f}%")
        
        if similitud == 100:
            st.success("✅ ¡No se detectaron cambios! Toda la información coincide perfectamente.")
        else:
            st.warning("⚠️ Se detectaron discrepancias consecutivas. Revisa el contraste abajo:")
            st.write("### 🔍 Mapeo de Actualizaciones In-Place")
            
            # Usamos SequenceMatcher para encontrar bloques cambiados correlativos
            sm = difflib.SequenceMatcher(None, limpias_base, limpias_nuevas)
            html_resultado = []
            
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                # 'replace' significa que un bloque de texto antiguo fue reemplazado por uno nuevo
                if tag == 'replace':
                    # Extraer ubicaciones estimadas
                    ubicacion_vieja = lineas_base[i1].split("|||")[0] if "|||" in lineas_base[i1] else f"[Línea {i1+1}]"
                    ubicacion_nueva = lineas_nuevas[j1].split("|||")[0] if "|||" in lineas_nuevas[j1] else f"[Línea {j1+1}]"
                    ubicacion = ubicacion_nueva if ubicacion_nueva != "[Línea 1]" else ubicacion_vieja
                    
                    txt_viejo = " // ".join(limpias_base[i1:i2])
                    txt_nuevo = " // ".join(limpias_nuevas[j1:j2])
                    
                    html_resultado.append(f"""
                    <div style='background-color: #fff9e6; padding: 10px; margin: 8px 0; border-left: 6px solid #ffcc00; border-radius: 4px;'>
                        <span style='background-color: #e6f2ff; color: #0044cc; padding: 2px 6px; border-radius: 3px; font-size: 0.85em; font-weight: bold;'>📍 {ubicacion}</span>
                        <div style='margin-top: 5px; color: #cc0000;'><b>🛑 ANTES (Desactualizado):</b> <del>{txt_viejo}</del></div>
                        <div style='margin-top: 2px; color: #2e7
