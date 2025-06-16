#!/usr/bin/env python3
"""
Comprehensive PDF Scraper for Ecuadorian National Assembly
Integrates data extraction and PDF downloading with proper session management
"""

import sys
import os
import time
import re
import json
import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
import logging
from datetime import datetime

# Add the current directory to Python path
sys.path.append(str(Path(__file__).parent))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from utils.logger import logger

class ComprehensivePDFScraper:
    """Comprehensive scraper that extracts data and downloads PDFs in one session"""
    
    def __init__(self, pdf_dir: str = "data/comprehensive_pdfs", headless: bool = True, delay: float = 2.0):
        self.pdf_dir = Path(pdf_dir)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.delay = delay
        self.driver = None
        
        # Base URLs
        self.base_url = "https://leyes.asambleanacional.gob.ec"
        self.iframe_url = "https://leyes.asambleanacional.gob.ec?vhf=1"
        
        # Data storage
        self.projects = []
        self.stats = {
            'projects_extracted': 0,
            'pdfs_downloaded': 0,
            'pdfs_failed': 0,
            'pdfs_skipped': 0
        }
    
    def setup_driver(self):
        """Setup Chrome WebDriver with proper options"""
        try:
            chrome_options = Options()
            
            if self.headless:
                chrome_options.add_argument("--headless")
            
            # PDF download settings
            chrome_options.add_experimental_option(
                "prefs", {
                    "download.default_directory": str(self.pdf_dir),
                    "download.prompt_for_download": False,
                    "download.directory_upgrade": True,
                    "plugins.always_open_pdf_externally": True,
                    "safebrowsing.enabled": True
                }
            )
            
            # Additional options for stability
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(10)
            
            logger.info("Chrome WebDriver setup completed")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up WebDriver: {str(e)}")
            return False
    
    def close_driver(self):
        """Close the WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver closed")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {str(e)}")
    
    def navigate_to_iframe(self) -> bool:
        """Navigate directly to the iframe URL"""
        try:
            if not self.driver:
                logger.error("WebDriver not initialized")
                return False
            
            logger.info(f"Navigating directly to iframe URL: {self.iframe_url}")
            self.driver.get(self.iframe_url)
            time.sleep(5)
            
            # Wait for page to load
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                logger.info("Iframe navigation completed successfully")
                return True
            except TimeoutException:
                logger.warning("Timeout waiting for page to load, but continuing...")
                return True
                
        except Exception as e:
            logger.error(f"Error navigating to iframe: {str(e)}")
            return False
    
    def find_and_fill_date_inputs(self, start_date: str, end_date: str) -> bool:
        """Find and fill date input fields"""
        try:
            if not self.driver:
                logger.error("WebDriver not initialized")
                return False
            
            logger.info("Looking for date input fields...")
            
            # Common date input selectors
            date_selectors = [
                'input[type="date"]',
                'input[placeholder*="fecha"]',
                'input[placeholder*="date"]',
                'input[name*="fecha"]',
                'input[name*="date"]',
                'input[id*="fecha"]',
                'input[id*="date"]'
            ]
            
            start_date_filled = False
            end_date_filled = False
            
            for selector in date_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for i, element in enumerate(elements):
                        try:
                            # Get element attributes to understand its purpose
                            placeholder = element.get_attribute('placeholder') or ''
                            name = element.get_attribute('name') or ''
                            id_attr = element.get_attribute('id') or ''
                            
                            logger.info(f"Found date input: placeholder='{placeholder}', name='{name}', id='{id_attr}'")
                            
                            # Determine if this is start or end date field
                            is_start = any(keyword in (placeholder + name + id_attr).lower() 
                                         for keyword in ['inicio', 'start', 'desde', 'from', 'begin'])
                            is_end = any(keyword in (placeholder + name + id_attr).lower() 
                                       for keyword in ['fin', 'end', 'hasta', 'to', 'until'])
                            
                            if is_start and not start_date_filled:
                                element.clear()
                                element.send_keys(start_date)
                                logger.info(f"Filled start date: {start_date}")
                                start_date_filled = True
                                time.sleep(1)
                            elif is_end and not end_date_filled:
                                element.clear()
                                element.send_keys(end_date)
                                logger.info(f"Filled end date: {end_date}")
                                end_date_filled = True
                                time.sleep(1)
                            elif not start_date_filled and not end_date_filled:
                                # If we can't determine, fill the first one as start date
                                element.clear()
                                element.send_keys(start_date)
                                logger.info(f"Filled first date input as start date: {start_date}")
                                start_date_filled = True
                                time.sleep(1)
                            elif not end_date_filled:
                                # Fill the second one as end date
                                element.clear()
                                element.send_keys(end_date)
                                logger.info(f"Filled second date input as end date: {end_date}")
                                end_date_filled = True
                                time.sleep(1)
                                
                        except Exception as e:
                            logger.debug(f"Error filling date input {i}: {str(e)}")
                            continue
                            
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {str(e)}")
                    continue
            
            return start_date_filled or end_date_filled
            
        except Exception as e:
            logger.error(f"Error finding and filling date inputs: {str(e)}")
            return False
    
    def find_and_click_submit_button(self) -> bool:
        """Find and click submit/search button"""
        try:
            if not self.driver:
                logger.error("WebDriver not initialized")
                return False
                
            logger.info("Looking for submit/search button...")
            
            # Common button selectors
            button_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                '.btn-primary',
                '.btn-search',
                '.search-button',
                '[class*="search"]',
                '[class*="submit"]',
                '[class*="buscar"]',
                '[class*="consultar"]',
                'button[onclick*="search"]',
                'button[onclick*="buscar"]'
            ]
            
            # Also try to find buttons by text
            button_texts = ['Buscar', 'Search', 'Consultar', 'Submit', 'Generar', 'Reporte', 'Filtrar']
            
            for selector in button_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            logger.info(f"Found and clicking button with selector: {selector}")
                            element.click()
                            time.sleep(self.delay)
                            return True
                except Exception as e:
                    logger.debug(f"Error with button selector {selector}: {str(e)}")
                    continue
            
            # Try finding by text
            for text in button_texts:
                try:
                    elements = self.driver.find_elements(By.XPATH, f"//button[contains(text(), '{text}')]")
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            logger.info(f"Found and clicking button with text: {text}")
                            element.click()
                            time.sleep(self.delay)
                            return True
                except Exception as e:
                    logger.debug(f"Error with button text {text}: {str(e)}")
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Error finding and clicking submit button: {str(e)}")
            return False
    
    def get_total_records_and_pages(self) -> Dict:
        """Get total records and pages information"""
        try:
            if not self.driver:
                logger.error("WebDriver not initialized")
                return {'total_records': 0, 'total_pages': 0}
            
            # Look for pagination information
            page_info_selectors = [
                '.pagination-info',
                '.page-info',
                '[class*="pagination"]',
                '[class*="page"]',
                '.ui-paginator-current',
                '.ui-paginator-page-count'
            ]
            
            total_records = 0
            total_pages = 0
            
            for selector in page_info_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        logger.info(f"Found pagination info: {text}")
                        
                        # Look for patterns like "1 of 275" or "Page 1 of 275"
                        page_match = re.search(r'(\d+)\s*(?:of|de)\s*(\d+)', text, re.IGNORECASE)
                        if page_match:
                            current_page = int(page_match.group(1))
                            total_pages = int(page_match.group(2))
                            logger.info(f"Found page info: {current_page} of {total_pages}")
                            break
                        
                        # Look for total records
                        records_match = re.search(r'(\d+)\s*(?:records?|registros?)', text, re.IGNORECASE)
                        if records_match:
                            total_records = int(records_match.group(1))
                            logger.info(f"Found total records: {total_records}")
                        
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {str(e)}")
                    continue
            
            # If we found total pages but not records, estimate records
            if total_pages > 0 and total_records == 0:
                # Try to count records on current page
                try:
                    table_rows = self.driver.find_elements(By.CSS_SELECTOR, 'table tr')
                    records_per_page = len([row for row in table_rows if row.find_elements(By.CSS_SELECTOR, 'td')])
                    total_records = total_pages * records_per_page
                    logger.info(f"Estimated total records: {total_records} ({total_pages} pages × {records_per_page} records/page)")
                except Exception as e:
                    logger.debug(f"Error estimating records: {str(e)}")
            
            return {
                'total_records': total_records,
                'total_pages': total_pages
            }
            
        except Exception as e:
            logger.error(f"Error getting total records and pages: {str(e)}")
            return {'total_records': 0, 'total_pages': 0}
    
    def extract_table_data(self) -> List[Dict]:
        """Extract data from the current page table"""
        projects = []
        try:
            if not self.driver:
                logger.error("WebDriver not initialized")
                return projects
            
            # Find all tables
            tables = self.driver.find_elements(By.CSS_SELECTOR, 'table')
            logger.info(f"Found {len(tables)} tables on the page")
            
            for table_index, table in enumerate(tables, 1):
                try:
                    # Get table rows
                    rows = table.find_elements(By.CSS_SELECTOR, 'tr')
                    logger.info(f"Table {table_index}: Found {len(rows)} rows")
                    
                    for row_index, row in enumerate(rows, 1):
                        try:
                            # Get cells in the row
                            cells = row.find_elements(By.CSS_SELECTOR, 'td')
                            
                            if len(cells) >= 4:  # Minimum expected columns
                                project = self.extract_project_from_row(cells, table_index, row_index)
                                if project:
                                    projects.append(project)
                                    
                        except Exception as e:
                            logger.debug(f"Error processing row {row_index} in table {table_index}: {str(e)}")
                            continue
                            
                except Exception as e:
                    logger.debug(f"Error processing table {table_index}: {str(e)}")
                    continue
            
            logger.info(f"Extracted {len(projects)} projects from current page")
            return projects
            
        except Exception as e:
            logger.error(f"Error extracting table data: {str(e)}")
            return projects
    
    def extract_project_from_row(self, cells: List, table_index: int, row_index: int) -> Optional[Dict]:
        """Extract project information from a table row"""
        try:
            # Generate unique ID
            project_id = f"page_{self.current_page}_table_{table_index}_row_{row_index}"
            
            # Extract data from cells (adjust indices based on actual table structure)
            title = cells[0].text.strip() if len(cells) > 0 else ""
            description = cells[1].text.strip() if len(cells) > 1 else ""
            status = cells[2].text.strip() if len(cells) > 2 else ""
            author = cells[3].text.strip() if len(cells) > 3 else ""
            committee = cells[4].text.strip() if len(cells) > 4 else ""
            
            # Look for "Ver Documentos" button and extract PDF links
            pdf_links = []
            document_url = ""
            
            try:
                # Find "Ver Documentos" button in the row
                ver_documentos_buttons = []
                for cell in cells:
                    buttons = cell.find_elements(By.XPATH, './/button[contains(text(), "Ver Documentos")] | .//a[contains(text(), "Ver Documentos")]')
                    ver_documentos_buttons.extend(buttons)
                
                if ver_documentos_buttons:
                    logger.info(f"Found 'Ver Documentos' button, attempting to extract PDF links")
                    
                    for button in ver_documentos_buttons:
                        try:
                            # Click the button to open dialog
                            button.click()
                            time.sleep(2)
                            
                            # Look for modal dialog
                            if self.driver:
                                dialog = self.driver.find_element(By.CSS_SELECTOR, '.ui-dialog, .modal, [role="dialog"]')
                                if dialog:
                                    logger.info("Dialog found, looking for PDF links")
                                    pdf_links = self.find_pdf_links_in_dialog(dialog)
                                    
                                    # Close dialog
                                    try:
                                        close_button = dialog.find_element(By.CSS_SELECTOR, '.ui-dialog-titlebar-close, .close, [aria-label="Close"]')
                                        close_button.click()
                                        time.sleep(1)
                                    except:
                                        # Try pressing Escape key
                                        from selenium.webdriver.common.keys import Keys
                                        if self.driver:
                                            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                                            time.sleep(1)
                                    
                                    if pdf_links:
                                        document_url = pdf_links[0]  # Use first PDF as main document
                                        break
                                    
                        except Exception as e:
                            logger.error(f"Error clicking 'Ver Documentos' button: {str(e)}")
                            continue
                            
            except Exception as e:
                logger.debug(f"Error extracting PDF links: {str(e)}")
            
            # Create project object
            project = {
                'id': project_id,
                'title': title,
                'description': description,
                'status': status,
                'date_created': '',
                'date_modified': '',
                'author': author,
                'committee': committee,
                'document_url': document_url,
                'pdf_links': pdf_links,
                'scraped_at': datetime.now().isoformat()
            }
            
            return project
            
        except Exception as e:
            logger.error(f"Error extracting project from row: {str(e)}")
            return None
    
    def find_pdf_links_in_dialog(self, dialog_element) -> List[str]:
        """Find PDF links in a modal dialog"""
        pdf_links = []
        try:
            # Look for links in the dialog
            links = dialog_element.find_elements(By.CSS_SELECTOR, 'a')
            for link in links:
                href = link.get_attribute('href')
                link_text = link.text.strip().lower()
                
                if href:
                    # Check if it's a PDF link
                    if any(ext in href.lower() for ext in ['.pdf', 'pdf', 'download']):
                        pdf_links.append(href)
                        logger.info(f"Found PDF link in dialog: {href}")
                    # Check link text for PDF indicators
                    elif any(keyword in link_text for keyword in ['pdf', 'descargar', 'download', 'ver', 'documento']):
                        pdf_links.append(href)
                        logger.info(f"Found potential PDF link in dialog: {href} (text: {link_text})")
            
            # Look for buttons in the dialog
            buttons = dialog_element.find_elements(By.CSS_SELECTOR, 'button, input[type="button"]')
            for button in buttons:
                onclick = button.get_attribute('onclick') or ''
                button_text = button.text.strip().lower()
                
                if 'pdf' in onclick.lower() or 'download' in onclick.lower():
                    # Try to extract URL from onclick
                    url_match = re.search(r'["\']([^"\']*\.pdf[^"\']*)["\']', onclick)
                    if url_match:
                        pdf_links.append(url_match.group(1))
                        logger.info(f"Found PDF link in dialog button onclick: {url_match.group(1)}")
                
                elif any(keyword in button_text for keyword in ['pdf', 'descargar', 'download', 'ver', 'documento']):
                    # Try to find associated URL
                    try:
                        parent = button.find_element(By.XPATH, './..')
                        links = parent.find_elements(By.CSS_SELECTOR, 'a')
                        for link in links:
                            href = link.get_attribute('href')
                            if href:
                                pdf_links.append(href)
                                logger.info(f"Found PDF link near dialog button: {href}")
                                break
                    except Exception as e:
                        logger.debug(f"Error finding associated URL in dialog: {str(e)}")
            
            # Look for any clickable elements with PDF indicators
            clickables = dialog_element.find_elements(By.CSS_SELECTOR, '[onclick*="pdf"], [onclick*="download"], [href*="pdf"], [href*="download"]')
            for clickable in clickables:
                href = clickable.get_attribute('href') or ''
                onclick = clickable.get_attribute('onclick') or ''
                
                if href and any(ext in href.lower() for ext in ['.pdf', 'pdf', 'download']):
                    pdf_links.append(href)
                    logger.info(f"Found PDF link in dialog clickable: {href}")
                elif onclick and ('pdf' in onclick.lower() or 'download' in onclick.lower()):
                    url_match = re.search(r'["\']([^"\']*\.pdf[^"\']*)["\']', onclick)
                    if url_match:
                        pdf_links.append(url_match.group(1))
                        logger.info(f"Found PDF link in dialog clickable onclick: {url_match.group(1)}")
                        
        except Exception as e:
            logger.error(f"Error finding PDF links in dialog: {str(e)}")
        
        return list(set(pdf_links))  # Remove duplicates
    
    def download_pdf(self, pdf_url: str, project_info: Dict) -> Optional[str]:
        """Download a single PDF using the current session"""
        try:
            # Generate filename
            project_id = project_info.get('id', 'unknown')
            title = project_info.get('title', 'Unknown')
            safe_title = re.sub(r'[^\w\s-]', '', title).strip()
            safe_title = re.sub(r'[-\s]+', '-', safe_title)
            safe_title = safe_title[:50]  # Limit length
            
            # Extract filename from URL
            url_filename = os.path.basename(urlparse(pdf_url).path)
            if url_filename and '.' in url_filename:
                filename = f"{project_id}_{url_filename}"
            else:
                filename = f"{project_id}_{safe_title}.pdf"
            
            filepath = self.pdf_dir / filename
            
            # Skip if already downloaded and has content
            if filepath.exists() and filepath.stat().st_size > 0:
                logger.info(f"PDF already exists: {filename}")
                return str(filepath)
            
            logger.info(f"Downloading PDF: {filename}")
            logger.info(f"URL: {pdf_url}")
            
            if not self.driver:
                logger.error("WebDriver not initialized")
                return None
            
            # Navigate to the PDF URL using the current session
            self.driver.get(pdf_url)
            time.sleep(5)
            
            # Check if we need to handle authentication
            current_url = self.driver.current_url
            page_source = self.driver.page_source
            
            if "login" in current_url.lower() or "autenticacion" in page_source.lower():
                logger.warning("Authentication required - cannot download PDF")
                return None
            
            # Try to find and click download buttons
            download_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                'button[onclick*="download"], a[href*="download"]')
            
            if download_buttons:
                logger.info(f"Found {len(download_buttons)} download buttons")
                for button in download_buttons:
                    try:
                        button.click()
                        time.sleep(3)
                        logger.info("Clicked download button")
                        break
                    except Exception as e:
                        logger.debug(f"Error clicking download button: {str(e)}")
                        continue
            
            # Check if file was downloaded
            time.sleep(5)  # Wait for download to complete
            
            # Look for downloaded files in the download directory
            downloaded_files = list(self.pdf_dir.glob(f"{project_id}_*"))
            if downloaded_files:
                # Find the most recent file
                latest_file = max(downloaded_files, key=lambda f: f.stat().st_mtime)
                file_size = latest_file.stat().st_size
                
                if file_size > 0:
                    logger.info(f"✅ PDF downloaded successfully: {latest_file.name} ({file_size} bytes)")
                    return str(latest_file)
                else:
                    logger.warning("Downloaded file is empty")
                    latest_file.unlink()  # Remove empty file
            
            # If no download button found, try to get the PDF content directly
            logger.info("Attempting to extract PDF content directly...")
            
            # Check if we can get the PDF content via JavaScript
            try:
                pdf_content = self.driver.execute_script("""
                    var xhr = new XMLHttpRequest();
                    xhr.open('GET', arguments[0], false);
                    xhr.send();
                    return xhr.responseText;
                """, pdf_url)
                
                if pdf_content and pdf_content.startswith('%PDF'):
                    with open(filepath, 'wb') as f:
                        f.write(pdf_content.encode('utf-8'))
                    
                    file_size = filepath.stat().st_size
                    if file_size > 0:
                        logger.info(f"✅ PDF content extracted successfully: {filename} ({file_size} bytes)")
                        return str(filepath)
                
            except Exception as e:
                logger.debug(f"Error extracting PDF content via JavaScript: {str(e)}")
            
            logger.warning("Could not download PDF")
            return None
            
        except Exception as e:
            logger.error(f"Error downloading PDF: {str(e)}")
            return None
    
    def navigate_to_next_page(self) -> bool:
        """Navigate to the next page"""
        try:
            if not self.driver:
                logger.error("WebDriver not initialized")
                return False
            
            # Look for next page button
            next_selectors = [
                'button[aria-label="Next"]',
                'a[aria-label="Next"]',
                '.ui-paginator-next',
                '.pagination-next',
                '[class*="next"]',
                'button:contains("Next")',
                'a:contains("Next")',
                'button:contains("Siguiente")',
                'a:contains("Siguiente")'
            ]
            
            for selector in next_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            # Check if it's not disabled
                            class_attr = element.get_attribute('class') or ''
                            if 'disabled' not in class_attr:
                                logger.info(f"Found and clicking next page button: {selector}")
                                element.click()
                                time.sleep(self.delay)
                                return True
                except Exception as e:
                    logger.debug(f"Error with next selector {selector}: {str(e)}")
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Error navigating to next page: {str(e)}")
            return False
    
    def get_current_page_number(self) -> int:
        """Get the current page number"""
        try:
            if not self.driver:
                return 1
            
            # Look for current page indicator
            page_selectors = [
                '.ui-paginator-page.ui-state-active',
                '.pagination-current',
                '[class*="current"]',
                '[class*="active"]'
            ]
            
            for selector in page_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text.isdigit():
                            return int(text)
                except Exception as e:
                    logger.debug(f"Error with page selector {selector}: {str(e)}")
                    continue
            
            return 1
            
        except Exception as e:
            logger.error(f"Error getting current page number: {str(e)}")
            return 1
    
    def scrape_all_pages(self, max_pages: Optional[int] = None) -> List[Dict]:
        """Scrape all pages and download PDFs"""
        try:
            logger.info("Starting to scrape all pages...")
            
            # Get total pages info
            page_info = self.get_total_records_and_pages()
            total_pages = page_info['total_pages']
            total_records = page_info['total_records']
            
            logger.info(f"Found page info: {self.get_current_page_number()} of {total_pages}")
            
            if max_pages:
                logger.info(f"Limited to {max_pages} pages")
                total_pages = min(total_pages, max_pages)
            
            logger.info(f"Total records to extract: {total_records}")
            logger.info(f"Will scrape {total_pages} pages")
            
            all_projects = []
            self.current_page = 1
            
            for page_num in range(1, total_pages + 1):
                try:
                    logger.info(f"Scraping page {page_num}...")
                    
                    # Take screenshot for debugging
                    screenshot_path = f"data/comprehensive_page_{page_num}_screenshot.png"
                    if self.driver:
                        self.driver.save_screenshot(screenshot_path)
                        logger.info(f"Screenshot saved: {screenshot_path}")
                    
                    # Extract data from current page
                    page_projects = self.extract_table_data()
                    
                    # Download PDFs for projects on this page
                    for project in page_projects:
                        if project.get('pdf_links'):
                            # Try to download the first PDF
                            pdf_url = project['pdf_links'][0]
                            pdf_path = self.download_pdf(pdf_url, project)
                            if pdf_path:
                                project['pdf_file_path'] = pdf_path
                                self.stats['pdfs_downloaded'] += 1
                            else:
                                self.stats['pdfs_failed'] += 1
                        else:
                            self.stats['pdfs_skipped'] += 1
                    
                    # Add projects to main list
                    all_projects.extend(page_projects)
                    self.stats['projects_extracted'] = len(all_projects)
                    
                    logger.info(f"Page {page_num}: Extracted {len(page_projects)} projects from table")
                    logger.info(f"Page {page_num}: {len(page_projects)} unique projects after deduplication")
                    logger.info(f"Page {page_num}: Added {len(page_projects)} projects (Total: {len(all_projects)})")
                    
                    # Navigate to next page (except for last page)
                    if page_num < total_pages:
                        if not self.navigate_to_next_page():
                            logger.warning(f"Could not navigate to next page from page {page_num}")
                            break
                        
                        self.current_page = page_num + 1
                        time.sleep(self.delay)
                    
                except Exception as e:
                    logger.error(f"Error scraping page {page_num}: {str(e)}")
                    continue
            
            logger.info(f"Scraping completed. Total projects extracted: {len(all_projects)}")
            logger.info(f"Found {len(all_projects)} total projects")
            
            return all_projects
            
        except Exception as e:
            logger.error(f"Error scraping all pages: {str(e)}")
            return []
    
    def save_results(self, projects: List[Dict], output_formats: List[str] = None):
        """Save results to files"""
        if output_formats is None:
            output_formats = ['csv', 'json']
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if 'csv' in output_formats:
            csv_file = f"data/comprehensive_law_projects_{timestamp}.csv"
            try:
                with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                    if projects:
                        fieldnames = projects[0].keys()
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(projects)
                logger.info(f"Results saved to CSV: {csv_file}")
            except Exception as e:
                logger.error(f"Error saving CSV: {str(e)}")
        
        if 'json' in output_formats:
            json_file = f"data/comprehensive_law_projects_{timestamp}.json"
            try:
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(projects, f, ensure_ascii=False, indent=2)
                logger.info(f"Results saved to JSON: {json_file}")
            except Exception as e:
                logger.error(f"Error saving JSON: {str(e)}")
        
        # Save summary
        summary = {
            'total_projects': len(projects),
            'pdfs_downloaded': self.stats['pdfs_downloaded'],
            'pdfs_failed': self.stats['pdfs_failed'],
            'pdfs_skipped': self.stats['pdfs_skipped'],
            'scraped_at': datetime.now().isoformat(),
            'pdf_directory': str(self.pdf_dir)
        }
        
        summary_file = f"data/comprehensive_scraping_summary_{timestamp}.json"
        try:
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            logger.info(f"Summary saved: {summary_file}")
        except Exception as e:
            logger.error(f"Error saving summary: {str(e)}")
    
    def start_scraping(self, start_date: str = "2021-01-01", end_date: str = "2025-05-14", 
                      max_pages: Optional[int] = None, output_formats: Optional[List[str]] = None) -> List[Dict]:
        """Start the comprehensive scraping process"""
        try:
            logger.info("=" * 60)
            logger.info("Comprehensive PDF Scraper for Ecuadorian National Assembly")
            logger.info("=" * 60)
            logger.info(f"PDF download directory: {self.pdf_dir}")
            
            # Setup WebDriver
            if not self.setup_driver():
                logger.error("Failed to setup WebDriver")
                return []
            
            # Navigate to iframe
            if not self.navigate_to_iframe():
                logger.error("Failed to navigate to iframe")
                self.close_driver()
                return []
            
            # Fill date inputs
            self.find_and_fill_date_inputs(start_date, end_date)
            
            # Click submit button
            self.find_and_click_submit_button()
            
            # Scrape all pages
            projects = self.scrape_all_pages(max_pages)
            
            # Save results
            if output_formats is None:
                output_formats = ['csv', 'json']
            self.save_results(projects, output_formats)
            
            # Close WebDriver
            self.close_driver()
            
            logger.info("=" * 60)
            logger.info("COMPREHENSIVE SCRAPING COMPLETED SUCCESSFULLY!")
            logger.info(f"Total projects: {len(projects)}")
            logger.info(f"PDFs downloaded: {self.stats['pdfs_downloaded']}")
            logger.info(f"PDFs failed: {self.stats['pdfs_failed']}")
            logger.info(f"PDFs skipped: {self.stats['pdfs_skipped']}")
            logger.info("=" * 60)
            
            return projects
            
        except Exception as e:
            logger.error(f"Error in comprehensive scraping: {str(e)}")
            self.close_driver()
            return []

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Comprehensive PDF Scraper for Ecuadorian National Assembly")
    parser.add_argument('--start-date', default='2021-01-01', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', default='2025-05-14', help='End date (YYYY-MM-DD)')
    parser.add_argument('--output-format', choices=['csv', 'json', 'both'], default='both', help='Output format')
    parser.add_argument('--headless', action='store_true', default=True, help='Run browser in headless mode')
    parser.add_argument('--no-headless', action='store_true', help='Run browser in visible mode')
    parser.add_argument('--delay', type=float, default=2.0, help='Delay between actions')
    parser.add_argument('--max-pages', type=int, help='Maximum number of pages to scrape (for testing)')
    parser.add_argument('--pdf-dir', default='data/comprehensive_pdfs', help='Directory to save PDFs')
    
    args = parser.parse_args()
    
    # Convert output format
    output_formats = ['csv', 'json'] if args.output_format == 'both' else [args.output_format]
    
    # Handle headless mode
    headless = args.headless and not args.no_headless
    
    try:
        # Create scraper instance
        scraper = ComprehensivePDFScraper(
            pdf_dir=args.pdf_dir,
            headless=headless,
            delay=args.delay
        )
        
        # Start scraping
        results = scraper.start_scraping(
            start_date=args.start_date,
            end_date=args.end_date,
            max_pages=args.max_pages,
            output_formats=output_formats
        )
        
        if results:
            logger.info("Comprehensive scraping completed successfully!")
        else:
            logger.error("Comprehensive scraping failed!")
            
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main() 