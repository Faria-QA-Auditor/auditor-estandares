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
st.subheader("Detecta in-place updates respetando la estructura jerárquica de los estándares.")

# --- FUNCIONES DE EXTRACCIÓN Y LIMPIEZA ---
def segmentar_texto_estructurado(texto_crudo, etiqueta_origen=""):
    """
    Divide el texto usando los numerales (e.g., (12), (A), (B)) como guías 
    para mantener la estructura jerárquica y evitar bloques masivos.
    """
    lineas_limpias = []
    # Reemplazar múltiples espacios o barras raras que introduce el PDF
    texto_filtrado = re.sub(r'\s+', ' ', texto_crudo).replace('//', ' ')
    
    # Expresión regular para detectar numerales como (12) o (A)
    patron_seccion = r'(\(\d+\)|\([A-Za-z]\))'
    
    # Dividir el texto manteniendo el separador
    partes = re.split(patron_seccion, texto_filtrado)
    
    ubicacion_actual = etiqueta_origen if etiqueta_origen else "[General]"
    texto_acumulado = ""
    
    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue
        
        # Si la parte es un numeral o letra entre paréntesis, actualizamos el contexto
        if re.match(patron_seccion, parte):
            if texto_acumulado:
                lineas_limpias.append(f"{ubicacion_actual}|||{texto_acumulado.strip()}")
            ubicacion_actual = f"{etiqueta_origen} {parte}".strip()
            texto_acumulado = parte + " "
        else:
            texto_acumulado += parte + " "
            
    if texto_acumulado:
        lineas_limpias.append(f"{ubicacion_actual}|||{texto_acumulado.strip()}")
        
    return lineas_limpias

def extraer_texto_pdf(stream):
    lineas_totales = []
    with pdfplumber.open(stream) as pdf:
        for i, pagina in enumerate(pdf.pages):
            texto_pag = pagina.extract_text()
            if texto_pag:
                # Segmentamos el texto de la página de forma estructurada
                lineas_totales.extend(segmentar_texto_estructurado(texto_pag, f"[Pág {i+1}]"))
    return lineas_totales

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
    # Procesamos también el texto pegado para estructurarlo bajo la misma lógica
    lineas_base = []
    if texto_base_raw.strip():
        lineas_base = segmentar_texto_estructurado(texto_base_raw, "[Base de Datos]")

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
            lineas_nuevas = segmentar_texto_estructurado(texto_nuevo_raw, "[Texto Pegado]")
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
        
        limpias_base = [l.split("|||")[-1] for l in lineas_base]
        limpias_nuevas = [l.split("|||")[-1] for l in lineas_nuevas]
        
        similitud = difflib.SequenceMatcher(None, " ".join(limpias_base), " ".join(limpias_nuevas)).ratio() * 100
        
        st.subheader("📊 Diagnóstico del Barrido")
        st.metric(label="Porcentaje de Coincidencia Global", value=f"{similitud:.2f}%")
        
        if similitud == 100:
            st.success("✅ ¡No se detectaron cambios! Toda la información coincide perfectamente.")
        else:
            st.warning("⚠️ Se detectaron discrepancias estructuradas. Revisa el contraste abajo:")
            st.write("### 🔍 Mapeo de Actualizaciones In-Place")
            
            sm = difflib.SequenceMatcher(None, limpias_base, limpias_nuevas)
            html_resultado = []
            
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == 'replace':
                    ubicacion_vieja = lineas_base[i1].split("|||")[0]
                    ubicacion_nueva = lineas_nuevas[j1].split("|||")[0]
                    # Priorizar la ubicación que tenga más detalle (como el numeral o literal)
                    ubicacion = ubicacion_nueva if "(" in ubicacion_nueva else ubicacion_vieja
                    
                    txt_viejo = " <br> ".join(limpias_base[i1:i2])
                    txt_nuevo = " <br> ".join(limpias_nuevas[j1:j2])
                    
                    html_resultado.append(f"""
                    <div style='background-color: #fff9e6; padding: 12px; margin: 10px 0; border-left: 6px solid #ffcc00; border-radius: 4px; font-family: monospace;'>
                        <span style='background-color: #e6f2ff; color: #0044cc; padding: 3px 8px; border-radius: 3px; font-size: 0.9em; font-weight: bold;'>📍 {ubicacion}</span>
                        <div style='margin-top: 8px; color: #cc0000;'><b>🛑 ANTES (Desactualizado):</b><br>{txt_viejo}</div>
                        <div style='margin-top: 6px; color: #2e7d32;'><b>🟢 AHORA (Actualizado):</b><br>{txt_nuevo}</div>
                    </div>
                    """)
                
                elif tag == 'delete':
                    ubicacion = lineas_base[i1].split("|||")[0]
                    txt_del = " <br> ".join(limpias_base[i1:i2])
                    html_resultado.append(f"""
                    <div style='background-color: #ffeeef; padding: 12px; margin: 10px 0; border-left: 6px solid #d32f2f; border-radius: 4px; font-family: monospace;'>
                        <span style='background-color: #e6f2ff; color: #0044cc; padding: 3px 8px; border-radius: 3px; font-size: 0.9em; font-weight: bold;'>📍 {ubicacion}</span>
                        <div style='margin-top: 8px; color: #d32f2f;'><b>🗑️ ELIMINADO:</b><br><del>{txt_del}</del></div>
                    </div>
                    """)
                
                elif tag == 'insert':
                    ubicacion = lineas_nuevas[j1].split("|||")[0]
                    txt_ins = " <br> ".join(limpias_nuevas[j1:j2])
                    html_resultado.append(f"""
                    <div style='background-color: #edf7ed; padding: 12px; margin: 10px 0; border-left: 6px solid #388e3c; border-radius: 4px; font-family: monospace;'>
                        <span style='background-color: #e6f2ff; color: #0044cc; padding: 3px 8px; border-radius: 3px; font-size: 0.9em; font-weight: bold;'>📍 {ubicacion}</span>
                        <div style='margin-top: 8px; color: #388e3c;'><b>✨ NUEVA ADICIÓN:</b><br>{txt_ins}</div>
                    </div>
                    """)
            
            st.markdown("".join(html_resultado), unsafe_allow_html=True)
else:
    if not lineas_base or not l_nuevas if 'l_nuevas' in locals() else True:
        st.info("💡 Asegúrate de llenar el texto base y proveer la nueva fuente antes de ejecutar el barrido.")
