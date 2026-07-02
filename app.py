import streamlit as st
import pandas as pd
import pdfplumber
import difflib

# Configuración de la página
st.set_page_config(page_title="Auditor de Estándares", layout="wide")

st.title("🔍 Auditor de Actualizaciones de Estándares")
st.subtitle("Detecta cambios sutiles (in-place updates) en archivos PDF o Excel frente a tu base de datos.")

# --- FUNCIONES DE EXTRACCIÓN ---
def extraer_texto_pdf(file):
    texto_completo = []
    with pdfplumber.open(file) as pdf:
        for i, pagina in enumerate(pdf.pages):
            texto_pag = pagina.extract_text()
            if texto_pag:
                for linea in texto_pag.split('\n'):
                    if linea.strip():
                        texto_completo.append(f"[Pág {i+1}] {linea.strip()}")
    return texto_completo

def extraer_texto_excel(file):
    texto_completo = []
    df = pd.read_excel(file)
    # Convertir cada fila relevante en una cadena de texto para comparar
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
        height=300,
        placeholder="Copia y pega las líneas o párrafos que tienes registrados actualmente..."
    )
    # Dividir el texto ingresado en líneas limpias
    lineas_base = [linea.strip() for linea in texto_base_raw.split('\n') if linea.strip()]

with col2:
    st.header("2. Nueva Fuente a Comparar")
    tipo_archivo = st.radio("Selecciona el formato de la nueva actualización:", ["PDF", "Excel"])
    archivo_subido = st.file_uploader(f"Sube el archivo {tipo_archivo} descargado de la web", type=["pdf", "xlsx"])

# --- PROCESAMIENTO Y COMPARACIÓN ---
if st.button("🚀 Ejecutar Barrido de Información") and lineas_base and archivo_subido:
    
    # Extraer texto según el archivo
    if tipo_archivo == "PDF":
        lineas_nuevas = extraer_texto_pdf(archivo_subido)
    else:
        lineas_nuevas = extraer_texto_excel(archivo_subido)
        
    # Calcular similitud general
    texto_base_unido = " ".join(lineas_base)
    texto_nuevo_unido = " ".join(lineas_nuevas)
    similitud = difflib.SequenceMatcher(None, texto_base_unido, texto_nuevo_unido).ratio() * 100
    
    st.subheader("📊 Diagnóstico del Barrido")
    st.metric(label="Porcentaje de Coincidencia Global", value=f"{similitud:.2f}%")
    
    if similitud == 100:
        st.success("✅ ¡No se detectaron cambios! El archivo coincide exactamente con tu base de datos.")
    else:
        st.warning("⚠️ Se detectaron discrepancias. Revisa los cambios detallados abajo:")
        
        # Comparación línea por línea
        diferenciador = difflib.Differ()
        resultado_diff = list(diferenciador.compare(lineas_base, lineas_nuevas))
        
        st.write("### 🔍 Reporte Detallado de Cambios")
        st.caption("Leyenda: Las líneas sin cambios aparecen normal. Los textos eliminados de tu base o modificados se muestran abajo.")
        
        html_resultado = []
        
        for linea in resultado_diff:
            # Línea eliminada o cambiada en el original
            if linea.startswith("- "):
                html_resultado.append(f"<div style='background-color: #ffcccc; color: #cc0000; padding: 5px; margin: 2px 0; border-left: 5px solid #cc0000;'>❌ <b>Eliminado/Modificado en Origen:</b> <del>{linea[2:]}</del></div>")
            # Línea nueva detectada en el barrido
            elif linea.startswith("+ "):
                html_resultado.append(f"<div style='background-color: #e2f0d9; color: #385723; padding: 5px; margin: 2px 0; border-left: 5px solid #385723;'>➕ <b>Nuevo cambio detectado (In-place):</b> {linea[2:]}</div>")
            # Líneas que coinciden perfectamente (opcional mostrarlas o no, aquí las mostramos sutilmente)
            elif linea.startswith("  "):
                # Descomenta la línea de abajo si quieres ver también lo que coincide
                # html_resultado.append(f"<div style='color: #666; padding: 2px; font-size: 0.9em;'>= {linea[2:]}</div>")
                pass
                
        # Renderizar el HTML en Streamlit
        st.markdown("".join(html_resultado), unsafe_allow_html=True)
else:
    if not lineas_base or not archivo_subido:
        st.info("💡 Para empezar, asegúrate de pegar el texto base a la izquierda y subir un archivo a la derecha.")
