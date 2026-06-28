import streamlit as st
import pandas as pd
import time
from playwright.sync_api import sync_playwright

# Configuración de la interfaz de Streamlit
st.set_page_config(page_title="Bot de Estadísticas Final", layout="wide")
st.title("📊 Monitor de Estadísticas en Vivo - Flashscore (Playwright Pro)")
st.subheader("Análisis de métricas en tiempo real optimizado para bajo consumo de RAM")

def extraer_estadisticas_partido(context, url_partido):
    """Abre una pestaña nueva, extrae la info de forma ultra rápida y la cierra para liberar RAM."""
    datos_partido = {
        "Marcador": "- - -",
        "Tiempo/Estado": "-",
        "Minuto": "-",
        "Stats": {}
    }
    page = None
    try:
        page = context.new_page()
        # Optimización: Bloquear imágenes, estilos CSS y fuentes para acelerar la carga un 60%
        page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "font", "stylesheet"] else route.continue_())
        
        # Navegamos con un timeout estricto de 7 segundos para no congelar el bot
        page.goto(url_partido, timeout=7000, wait_until="domcontentloaded")
        
        # Esperar al contenedor principal del marcador
        page.wait_for_selector("div.detailScore__wrapper", timeout=4000)
        
        # Extracción directa usando selectores nativos (Sin BeautifulSoup)
        marcador_el = page.locator("div.detailScore__wrapper").first
        if marcador_el.count() > 0:
            datos_partido["Marcador"] = marcador_el.text_content(timeout=500).strip()
            
        estado_el = page.locator("span.fixedHeaderDuel__detailStatus").first
        if estado_el.count() > 0:
            datos_partido["Tiempo/Estado"] = estado_el.text_content(timeout=500).strip()
            
        minuto_el = page.locator("span.eventTime").first
        if minuto_el.count() > 0:
            datos_partido["Minuto"] = minuto_el.text_content(timeout=500).strip()
            
        # Hacer clic en la pestaña de Estadísticas si existe
        boton_stats = page.locator("//button[@role='tab' and contains(., 'Estadísticas')]").first
        if boton_stats.count() > 0:
            boton_stats.click(timeout=1000)
            page.wait_for_selector("div[data-testid='wcl-statistics']", timeout=2000)
            
            # Capturar todas las filas de estadísticas en un solo recorrido
            filas = page.locator("div[data-testid='wcl-statistics']").all()
            for fila in filas:
                cat_el = fila.locator("div[data-testid='wcl-statistics-category']").first
                if cat_el.count() > 0:
                    categoria = cat_el.text_content().strip()
                    
                    # Ubicar valores de Local y Visitante buscando las clases parciales nativas
                    home_el = fila.locator("div[class*='wcl-homeValue']").first
                    away_el = fila.locator("div[class*='wcl-awayValue']").first
                    
                    val_home = home_el.text_content().strip() if home_el.count() > 0 else "0"
                    val_away = away_el.text_content().strip() if away_el.count() > 0 else "0"
                    
                    datos_partido["Stats"][f"{categoria} (L)"] = val_home
                    datos_partido["Stats"][f"{categoria} (V)"] = val_away
    except Exception:
        pass  # Manejo de timeout o error limpio para continuar con el siguiente partido
    finally:
        if page:
            page.close()  # Cerramos la pestaña inmediatamente para liberar memoria RAM
            
    return datos_partido

# --- PROCESO PRINCIPAL EN INTERFAZ ---

if st.button("🔄 Ejecutar Escaneo Completo y Generar Tabla"):
    with st.spinner("Conectando a la sección EN DIRECTO con Playwright..."):
        
        # Iniciamos el gestor de contexto de Playwright
        with sync_playwright() as p:
            browser = None
            context = None
            try:
                # Configuración ultra-lightweight del navegador de Playwright
                browser = p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
                )
                
                # Definimos un User-Agent real para evitar bloqueos
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
                
                main_page = context.new_page()
                main_page.goto("https://www.flashscore.pe/", wait_until="domcontentloaded")
                
                # Clic en el filtro 'EN DIRECTO'
                boton_directo = main_page.locator("//div[contains(@class, 'filters__text') and text()='EN DIRECTO']")
                boton_directo.wait_for(state="visible", timeout=10000)
                boton_directo.click()
                
                # Pequeña pausa de carga dinámica de la lista
                time.sleep(2.5)
                
                # Identificar todos los bloques de partidos activos
                partidos_elementos = main_page.locator("div[id^='g_1_']").all()
                
                if not partidos_elementos:
                    st.warning("No se encontraron partidos en directo para analizar en este momento.")
                else:
                    st.success(f"Se detectaron {len(partidos_elementos)} partidos activos. Procesando métricas...")
                    
                    barra_progreso = st.progress(0)
                    lista_registros_finales = []
                    
                    for idx, fila in enumerate(partidos_elementos):
                        id_completo = fila.get_attribute("id")
                        id_partido = id_completo.split('_')[-1]
                        url_match_stats = f"https://www.flashscore.pe/partido/{id_partido}/#/resumen/estadisticas"
                        
                        # Extraer nombres de equipos directamente desde la lista general
                        local_el = fila.locator("div[class*='home'][class*='participant']").first
                        away_el = fila.locator("div[class*='away'][class*='participant']").first
                        
                        nom_local = local_el.text_content().strip() if local_el.count() > 0 else "Local"
                        nom_visitante = away_el.text_content().strip() if away_el.count() > 0 else "Visitante"
                        
                        # Extraemos estadísticas usando el mismo contexto de navegación
                        resultado_profundo = extraer_estadisticas_partido(context, url_match_stats)
                        
                        registro = {
                            "Partido en Vivo": f"{nom_local} vs {nom_visitante}",
                            "Marcador": resultado_profundo["Marcador"],
                            "Tiempo/Estado": resultado_profundo["Tiempo/Estado"],
                            "Minuto": resultado_profundo["Minuto"]
                        }
                        registro.update(resultado_profundo["Stats"])
                        lista_registros_finales.append(registro)
                        
                        barra_progreso.progress((idx + 1) / len(partidos_elementos))
                    
                    # Estructuración final de los datos en pandas
                    df_final = pd.DataFrame(lista_registros_finales).fillna("-")
                    columnas_fijas = ["Partido en Vivo", "Marcador", "Tiempo/Estado", "Minuto"]
                    columnas_stats = [col for col in df_final.columns if col not in columnas_fijas]
                    df_final = df_final[columnas_fijas + columnas_stats]
                    
                    st.write("### 📈 Cuadro de Control General (Estadísticas Principales)")
                    st.dataframe(df_final, use_container_width=True)
                    st.balloons()
                    
            except Exception as e:
                st.error(f"Fallo crítico en el sistema de análisis: {str(e)}")
            finally:
                # Playwright cierra todo automáticamente al salir del bloque 'with',
                # pero nos aseguramos por buenas prácticas.
                if context:
                    context.close()
                if browser:
                    browser.close()
