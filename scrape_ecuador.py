#!/usr/bin/env python3
"""
Scraper Final - Asamblea Nacional Ecuador
Usa la lógica exacta que funcionó en la prueba simple
"""

import os
import time
import json
import csv
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def configurar_chrome():
    """Configurar Chrome (modo visible para ver el progreso)"""
    print("🚀 Configurando Chrome...")
    
    options = Options()
    options.add_argument("--window-size=1400,900")
    
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if os.path.exists(chrome_path):
        options.binary_location = chrome_path
    
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)
    
    print("✅ Chrome configurado")
    return driver

def navegar_y_esperar(driver):
    """Navegar al sitio"""
    print("🌐 Navegando al sitio...")
    
    url = "https://leyes.asambleanacional.gob.ec?vhf=1"
    driver.get(url)
    
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    
    print("⏳ Esperando carga completa...")
    time.sleep(10)
    
    titulo = driver.title
    print(f"✅ Página cargada: {titulo}")
    return "PROYECTOS DE LEY" in titulo

def encontrar_tabla_con_datos(driver):
    """Encontrar la tabla principal (la que tiene 10+ filas de datos)"""
    print("🔍 Buscando tabla principal...")
    
    tablas = driver.find_elements(By.CSS_SELECTOR, "table")
    print(f"📊 Encontradas {len(tablas)} tablas")
    
    for i, tabla in enumerate(tablas):
        try:
            filas = tabla.find_elements(By.CSS_SELECTOR, "tr")
            filas_con_datos = []
            
            for fila in filas:
                celdas = fila.find_elements(By.CSS_SELECTOR, "td")
                if len(celdas) >= 6:  # Al menos 6 columnas
                    texto = " ".join([c.text.strip() for c in celdas[:3]])
                    if len(texto) > 20:
                        filas_con_datos.append(fila)
            
            print(f"  Tabla {i+1}: {len(filas)} filas total, {len(filas_con_datos)} con datos")
            
            if len(filas_con_datos) >= 8:  # La tabla principal tiene ~10 filas
                print(f"✅ Tabla principal encontrada: {len(filas_con_datos)} filas de datos")
                return filas_con_datos
                
        except:
            continue
    
    print("❌ No se encontró tabla principal")
    return []

def extraer_pdf_url_de_fila(fila, driver, numero_proyecto):
    """Extraer PDF URL de una fila específica usando lógica exacta que funcionó"""
    print(f"  🔍 Buscando PDF en proyecto {numero_proyecto}...")
    
    try:
        celdas = fila.find_elements(By.CSS_SELECTOR, "td")
        
        if len(celdas) < 6:
            print(f"    ❌ Fila no tiene suficientes columnas ({len(celdas)})")
            return None
        
        # Buscar específicamente en la celda 6 (índice 5) que sabemos que funciona
        celda_docs = celdas[5]  # Celda 6 (índice 5)
        
        # Buscar elementos clickeables en esta celda específica
        elementos = celda_docs.find_elements(By.CSS_SELECTOR, "button, a, span[onclick], i[onclick], [onclick]")
        
        if not elementos:
            print(f"    ⚠️ No hay elementos clickeables en celda 'Docs'")
            return None
        
        print(f"    👆 Encontrados {len(elementos)} elementos clickeables")
        
        # Usar el primer elemento clickeable
        elemento = elementos[0]
        
        if not (elemento.is_displayed() and elemento.is_enabled()):
            print(f"    ❌ Elemento no es clickeable")
            return None
        
        # Hacer clic
        print(f"    👆 Haciendo clic en elemento 'Ver Documentos'...")
        elemento.click()
        time.sleep(3)  # Esperar que aparezca el modal
        
        # Buscar modal usando los selectores que funcionaron
        modal = buscar_modal_documentos(driver)
        if not modal:
            print(f"    ❌ No se abrió modal de documentos")
            return None
        
        print(f"    ✅ Modal abierto, buscando PDF...")
        
        # Extraer PDF del modal
        pdf_url = extraer_pdf_del_modal(modal)
        
        # Cerrar modal
        cerrar_modal(modal, driver)
        
        if pdf_url:
            print(f"    ✅ PDF encontrado: {pdf_url[:60]}...")
            return pdf_url
        else:
            print(f"    ⚠️ No se encontró PDF en modal")
            return None
            
    except Exception as e:
        print(f"    ❌ Error extrayendo PDF: {str(e)}")
        return None

def buscar_modal_documentos(driver):
    """Buscar modal usando selectores que funcionaron"""
    selectores_modal = [
        ".ui-dialog[style*='display: block']",
        ".ui-dialog[style*='display:block']", 
        ".modal[style*='display: block']",
        ".ui-dialog",
        ".modal"
    ]
    
    for selector in selectores_modal:
        try:
            modales = driver.find_elements(By.CSS_SELECTOR, selector)
            for modal in modales:
                if modal.is_displayed():
                    return modal
        except:
            continue
    
    return None

def extraer_pdf_del_modal(modal):
    """Extraer PDF del modal usando lógica que funcionó"""
    try:
        # Buscar TODOS los elementos como en el script que funcionó
        elementos = modal.find_elements(By.CSS_SELECTOR, "a, button, [onclick], span")
        
        for elemento in elementos:
            try:
                href = elemento.get_attribute("href") or ""
                onclick = elemento.get_attribute("onclick") or ""
                texto = elemento.text.strip()
                
                # Si es enlace PDF directo
                if ".pdf" in href.lower():
                    return href
                
                # Si es botón que dice PDF o tiene onclick
                if ("pdf" in texto.lower() or "PDF" in texto or 
                    "pdf" in onclick.lower()):
                    
                    # Hacer clic para activar
                    try:
                        elemento.click()
                        time.sleep(1)
                        
                        # Verificar si el href cambió
                        nuevo_href = elemento.get_attribute("href") or ""
                        if ".pdf" in nuevo_href:
                            return nuevo_href
                    except:
                        pass
                        
            except:
                continue
        
        return None
        
    except:
        return None

def cerrar_modal(modal, driver):
    """Cerrar modal"""
    try:
        # Buscar botón cerrar
        botones = modal.find_elements(By.CSS_SELECTOR, ".ui-dialog-titlebar-close, .close, [aria-label='Close']")
        for boton in botones:
            if boton.is_displayed():
                boton.click()
                time.sleep(1)
                return
        
        # Escape como fallback
        from selenium.webdriver.common.keys import Keys
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(1)
        
    except:
        pass

def extraer_datos_de_fila(fila, numero_proyecto):
    """Extraer datos básicos de una fila"""
    try:
        celdas = fila.find_elements(By.CSS_SELECTOR, "td")
        datos = [celda.text.strip() for celda in celdas]
        
        proyecto = {
            'id': f'proyecto_{numero_proyecto}',
            'fecha': datos[0] if len(datos) > 0 else '',
            'titulo': datos[1] if len(datos) > 1 else '',
            'estado': datos[2] if len(datos) > 2 else '',
            'autor': datos[3] if len(datos) > 3 else '',
            'tramite': datos[4] if len(datos) > 4 else '',
            'docs_columna': datos[5] if len(datos) > 5 else '',
            'datos_completos': datos,
            'extraido_en': datetime.now().isoformat()
        }
        
        return proyecto
        
    except Exception as e:
        return None

def guardar_resultados(proyectos):
    """Guardar resultados"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # JSON completo
    archivo_json = f"proyectos_final_{timestamp}.json"
    with open(archivo_json, 'w', encoding='utf-8') as f:
        json.dump(proyectos, f, ensure_ascii=False, indent=2)
    
    # CSV
    archivo_csv = f"proyectos_final_{timestamp}.csv"
    if proyectos:
        campos = set()
        for p in proyectos:
            campos.update(p.keys())
        
        with open(archivo_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=sorted(campos))
            writer.writeheader()
            writer.writerows(proyectos)
    
    # URLs de PDFs encontradas
    pdfs_encontrados = [p for p in proyectos if p.get('pdf_url')]
    if pdfs_encontrados:
        archivo_pdfs = f"urls_pdfs_exitosas_{timestamp}.txt"
        with open(archivo_pdfs, 'w', encoding='utf-8') as f:
            f.write("URLs de PDFs encontradas exitosamente:\n")
            f.write("=" * 50 + "\n\n")
            for i, proyecto in enumerate(pdfs_encontrados, 1):
                f.write(f"{i}. {proyecto['titulo'][:60]}...\n")
                f.write(f"   📄 PDF: {proyecto['pdf_url']}\n")
                f.write(f"   📅 Fecha: {proyecto['fecha']}\n\n")
        
        print(f"📄 URLs de PDFs guardadas: {archivo_pdfs}")
    
    print(f"💾 Datos: {archivo_json}")
    print(f"💾 CSV: {archivo_csv}")
    
    return len(pdfs_encontrados)

def main():
    """Función principal - scraper final exitoso"""
    print("=" * 60)
    print("🇪🇨 SCRAPER FINAL - ASAMBLEA NACIONAL")
    print("Usando lógica exacta que funcionó en prueba simple")
    print("=" * 60)
    
    driver = None
    
    try:
        # Configurar Chrome
        driver = configurar_chrome()
        
        # Navegar
        if not navegar_y_esperar(driver):
            print("❌ Falló la navegación")
            return
        
        # Encontrar filas con datos
        filas_datos = encontrar_tabla_con_datos(driver)
        if not filas_datos:
            print("❌ No se encontraron filas con datos")
            return
        
        print(f"\n📊 Procesando {len(filas_datos)} proyectos...")
        
        proyectos = []
        pdfs_exitosos = 0
        
        for i, fila in enumerate(filas_datos, 1):
            print(f"\n📄 Proyecto {i}/{len(filas_datos)}:")
            
            # Extraer datos básicos
            proyecto = extraer_datos_de_fila(fila, i)
            if not proyecto:
                print(f"  ❌ Error extrayendo datos básicos")
                continue
            
            print(f"  📋 {proyecto['titulo'][:50]}...")
            
            # Intentar extraer PDF
            pdf_url = extraer_pdf_url_de_fila(fila, driver, i)
            if pdf_url:
                proyecto['pdf_url'] = pdf_url
                proyecto['pdf_disponible'] = True
                pdfs_exitosos += 1
            else:
                proyecto['pdf_disponible'] = False
            
            proyectos.append(proyecto)
            
            # Pausa entre proyectos
            time.sleep(2)
        
        # Guardar resultados
        pdfs_guardados = guardar_resultados(proyectos)
        
        print("\n" + "=" * 60)
        print("🎉 SCRAPER FINAL COMPLETADO")
        print(f"📊 Proyectos procesados: {len(proyectos)}")
        print(f"📄 PDFs encontrados: {pdfs_exitosos}")
        print(f"✅ Tasa de éxito: {(pdfs_exitosos/len(proyectos)*100):.1f}%")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        
    finally:
        if driver:
            try:
                driver.quit()
                print("🔒 Chrome cerrado")
            except:
                pass

if __name__ == "__main__":
    main() 