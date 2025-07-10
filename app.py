import streamlit as st
import os
import re
import shutil
import tempfile
import zipfile
import pdfplumber
import warnings
from dotenv import load_dotenv  # NUEVO: para cargar variables desde .env

# --- CARGAR VARIABLES DE ENTORNO ---
load_dotenv()
PASSWORD = os.getenv("APP_PASSWORD")

# --- FUNCIÓN DE CONTROL DE ACCESO ---
def check_password():
    password = st.text_input("🔒 Introduce la contraseña para acceder", type="password")
    if password == PASSWORD:
        return True
    elif password:
        st.error("Contraseña incorrecta.")
    return False

# --- BLOQUEO DE ACCESO ---
if not check_password():
    st.stop()



# --- CONFIGURACIÓN DE LA APLICACIÓN ---
st.set_page_config(page_title="Clasificador de Facturas por CIF", layout="wide")
st.title("🚀 Clasificador de Facturas por CIF")
st.write(
    "Sube tus archivos PDF junto con sus ficheros asociados (Excel, Word, etc.). "
    "La aplicación los clasificará en carpetas según el CIF encontrado y te ofrecerá un archivo ZIP para descargar."
)

# Ignora las advertencias de las bibliotecas para una salida más limpia
warnings.filterwarnings("ignore")

# --- LÓGICA DE CLASIFICACIÓN (DENTRO DE FUNCIONES) ---

# Lista de CIFs principales a buscar
CIFS_LIST = [
    "B85536134", "A80652928", "B84425131", "A81989360",
    "B81500043", "A79492286", "G83844316", "A81944720",
    "B60924131", "B47384649", "A31604903"
]
UNIDENTIFIED_FOLDER_NAME = "Sin identificar"

def buscar_cif_en_pdf(ruta_pdf):
    """
    Función optimizada para extraer CIFs de un PDF usando pdfplumber.
    """
    patron_cif = re.compile(r'[ABG]\d{8}', re.IGNORECASE)
    texto_completo = ""
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            for pagina in pdf.pages:
                texto_pagina = pagina.extract_text()
                if texto_pagina:
                    texto_completo += texto_pagina
    except Exception:
        # Si el PDF no se puede leer, retorna una lista vacía
        return []

    texto_limpio = re.sub(r'[\s._-]', '', texto_completo)
    matches = patron_cif.findall(texto_limpio)
    return list(set(match.upper() for match in matches))

def procesar_y_clasificar(base_dir, log_messages):
    """
    Ejecuta toda la lógica de clasificación sobre los archivos en el directorio base.
    """
    # Crear carpetas de destino
    for folder_name in CIFS_LIST + [UNIDENTIFIED_FOLDER_NAME]:
        os.makedirs(os.path.join(base_dir, folder_name), exist_ok=True)

    # Limpiar nombres de archivos con espacios
    for filename in os.listdir(base_dir):
        if os.path.isfile(os.path.join(base_dir, filename)):
            clean_filename = filename.strip()
            if filename != clean_filename:
                os.rename(os.path.join(base_dir, filename), os.path.join(base_dir, clean_filename))
                log_messages.append(f"✓ Renombrado: '{filename}' -> '{clean_filename}'")
    
    # Procesar cada PDF
    for filename in os.listdir(base_dir):
        if filename.lower().endswith('.pdf'):
            pdf_path = os.path.join(base_dir, filename)
            cifs_encontrados = buscar_cif_en_pdf(pdf_path)
            cifs_principales = [cif for cif in cifs_encontrados if cif in CIFS_LIST]
            
            destination_folder = None
            if not cifs_principales:
                destination_folder = os.path.join(base_dir, UNIDENTIFIED_FOLDER_NAME)
                log_messages.append(f"📄 '{filename}' -> Sin CIF de la lista. Moviendo a '{UNIDENTIFIED_FOLDER_NAME}'.")
            else:
                cif_principal = cifs_principales[0]
                otros_cifs = [cif for cif in cifs_encontrados if cif != cif_principal]
                if otros_cifs:
                    cif_secundario = otros_cifs[0]
                    destination_folder = os.path.join(base_dir, cif_principal, cif_secundario)
                    log_messages.append(f"⚠️ '{filename}' -> Múltiples CIFs. Principal: {cif_principal}, Secundario: {cif_secundario}.")
                else:
                    destination_folder = os.path.join(base_dir, cif_principal)
                    log_messages.append(f"📄 '{filename}' -> CIF único encontrado: {cif_principal}.")
            
            if destination_folder:
                os.makedirs(destination_folder, exist_ok=True)
                pdf_basename = os.path.splitext(filename)[0]

                # Mover el PDF y sus archivos asociados
                for file_to_move in os.listdir(base_dir):
                    if os.path.splitext(file_to_move)[0] == pdf_basename:
                        source_path = os.path.join(base_dir, file_to_move)
                        if os.path.isfile(source_path):
                            shutil.move(source_path, os.path.join(destination_folder, file_to_move))

    # Limpiar carpetas vacías
    for dirpath, _, _ in os.walk(base_dir, topdown=False):
        if dirpath != base_dir and not os.listdir(dirpath):
            os.rmdir(dirpath)
            log_messages.append(f"🗑️ Eliminada carpeta vacía: '{os.path.basename(dirpath)}'")


# --- INTERFAZ DE STREAMLIT ---

uploaded_files = st.file_uploader(
    "Sube aquí tus archivos (PDF, XLS, DOCX, etc.)",
    accept_multiple_files=True
)

if st.button("🚀 Procesar y Clasificar Archivos", disabled=not uploaded_files, type="primary"):
    # Usar un directorio temporal para manejar los archivos de forma segura
    with tempfile.TemporaryDirectory() as temp_dir:
        # 1. Guardar archivos subidos en el directorio temporal
        for uploaded_file in uploaded_files:
            with open(os.path.join(temp_dir, uploaded_file.name), "wb") as f:
                f.write(uploaded_file.getbuffer())
        
        log_messages = []
        progress_bar = st.progress(0, text="Iniciando proceso...")

        # 2. Ejecutar la lógica de clasificación
        procesar_y_clasificar(temp_dir, log_messages)
        progress_bar.progress(50, text="Archivos clasificados. Creando ZIP...")

        # 3. Crear un archivo ZIP con los resultados
        zip_path = os.path.join(temp_dir, "facturas_clasificadas.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if file != "facturas_clasificadas.zip":
                        file_path = os.path.join(root, file)
                        zipf.write(file_path, os.path.relpath(file_path, temp_dir))
        
        progress_bar.progress(100, text="¡Proceso completado!")
        st.success("✅ ¡Archivos clasificados con éxito!")

        # 4. Ofrecer el archivo ZIP para descargar
        with open(zip_path, "rb") as fp:
            st.download_button(
                label="📥 Descargar Resultados (.zip)",
                data=fp,
                file_name="facturas_clasificadas.zip",
                mime="application/zip"
            )

        # 5. Mostrar el registro de acciones
        with st.expander("Ver registro de clasificación"):
            st.code("\n".join(log_messages))

