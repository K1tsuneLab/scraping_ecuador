#!/usr/bin/env python3
"""
Improved pagination-aware scraper for Ecuadorian National Assembly law projects
Extracts all records by properly navigating through all pages
"""

import time
import json
import re
import os
import requests
from pathlib import Path
from urllib.parse import urljoin, urlparse
from datetime import datetime
from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from utils.data_processor import DataProcessor
from utils.logger import logger

class ImprovedPaginationEcuadorScraper:
    """Improved pagination-aware scraper using Chrome WebDriver"""
    
    def __init__(self, headless=True, delay=2, download_pdfs=True, pdf_dir="data/pdfs"):
        self.base_url = "https://proyectosdeley.asambleanacional.gob.ec"
        self.report_url = f"{self.base_url}/report"
        self.iframe_url = "https://leyes.asambleanacional.gob.ec?vhf=1"
        self.headless = headless
        self.delay = delay
        self.download_pdfs = download_pdfs
        self.pdf_dir = Path(pdf_dir)
        self.data_processor = DataProcessor()
        self.driver: Optional[webdriver.Chrome] = None
        self.all_projects = []
        self.total_records = 0
        self.current_page = 1
        self.seen_project_ids = set()  # To avoid duplicates
        
        # Create PDF directory if it doesn't exist
        if self.download_pdfs:
            self.pdf_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"PDF download directory: {self.pdf_dir}")
    
    def setup_driver(self):
        """Setup Chrome WebDriver"""
        try:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            self.driver = webdriver.Chrome(options=chrome_options)
            if self.driver:
                self.driver.set_window_size(1920, 1080)
                logger.info("Chrome WebDriver setup completed")
                return True
            return False
        except Exception as e:
            logger.error(f"WebDriver setup failed: {str(e)}")
            return False
    
    def close_driver(self):
        """Close WebDriver"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
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
            time.sleep(self.delay)
            
            # Wait for page to load
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            time.sleep(2)
            return True
        except Exception as e:
            logger.error(f"Navigation failed: {str(e)}")
            return False
    
    def get_total_records_and_pages(self) -> Dict:
        """Get the total number of records and pages from the page"""
        try:
            if not self.driver:
                return {'total_records': 0, 'total_pages': 0, 'items_per_page': 10}
                
            # Look for pagination information in the page content
            page_content = self.driver.page_source
            
            # Look for patterns like "1 of 275" or "Página 1 de 275"
            page_patterns = [
                r'(\d+)\s*of\s*(\d+)',
                r'Página\s*(\d+)\s*de\s*(\d+)',
                r'(\d+)\s*/\s*(\d+)',
                r'(\d+)\s*de\s*(\d+)'
            ]
            
            for pattern in page_patterns:
                matches = re.findall(pattern, page_content, re.IGNORECASE)
                if matches:
                    current, total = map(int, matches[0])
                    logger.info(f"Found page info: {current} of {total}")
                    
                    # Calculate total records (assuming 10 items per page)
                    total_records = total * 10
                    return {
                        'total_records': total_records,
                        'total_pages': total,
                        'items_per_page': 10,
                        'current_page': current
                    }
            
            # Look for total records information
            total_patterns = [
                r'total de registros:\s*(\d+)',
                r'total records:\s*(\d+)',
                r'registros:\s*(\d+)',
                r'records:\s*(\d+)'
            ]
            
            for pattern in total_patterns:
                matches = re.findall(pattern, page_content, re.IGNORECASE)
                if matches:
                    total_records = int(matches[0])
                    total_pages = (total_records + 9) // 10  # Round up
                    logger.info(f"Found total records: {total_records}, calculated pages: {total_pages}")
                    return {
                        'total_records': total_records,
                        'total_pages': total_pages,
                        'items_per_page': 10,
                        'current_page': 1
                    }
            
            # Default values based on known information
            logger.warning("Could not determine pagination info, using defaults")
            return {
                'total_records': 2742,
                'total_pages': 275,
                'items_per_page': 10,
                'current_page': 1
            }
            
        except Exception as e:
            logger.error(f"Error getting pagination info: {str(e)}")
            return {'total_records': 2742, 'total_pages': 275, 'items_per_page': 10, 'current_page': 1}
    
    def find_pagination_controls(self) -> Dict:
        """Find pagination controls on the page"""
        try:
            if not self.driver:
                return {}
                
            controls = {}
            
            # Look for next button
            next_selectors = [
                '//button[contains(text(), "Next")]',
                '//button[contains(text(), "Siguiente")]',
                '//button[contains(text(), ">")]',
                '//a[contains(text(), "Next")]',
                '//a[contains(text(), "Siguiente")]',
                '//a[contains(text(), ">")]',
                '.next',
                '.pagination-next',
                '[class*="next"]'
            ]
            
            for selector in next_selectors:
                try:
                    if selector.startswith('//'):
                        elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            controls['next_button'] = element
                            logger.info(f"Found next button with selector: {selector}")
                            break
                    if 'next_button' in controls:
                        break
                except Exception as e:
                    logger.debug(f"Error with next selector {selector}: {str(e)}")
                    continue
            
            # Look for page number input
            page_input_selectors = [
                'input[type="number"]',
                'input[placeholder*="page"]',
                'input[name*="page"]',
                'input[id*="page"]',
                '.page-input',
                '[class*="page-input"]'
            ]
            
            for selector in page_input_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed():
                            controls['page_input'] = element
                            logger.info(f"Found page input with selector: {selector}")
                            break
                    if 'page_input' in controls:
                        break
                except Exception as e:
                    logger.debug(f"Error with page input selector {selector}: {str(e)}")
                    continue
            
            # Look for page number links
            page_link_selectors = [
                '.pagination a',
                '[class*="pagination"] a',
                '.page-link',
                '[class*="page"] a'
            ]
            
            for selector in page_link_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        controls['page_links'] = elements
                        logger.info(f"Found {len(elements)} page links with selector: {selector}")
                        break
                except Exception as e:
                    logger.debug(f"Error with page link selector {selector}: {str(e)}")
                    continue
            
            return controls
            
        except Exception as e:
            logger.error(f"Error finding pagination controls: {str(e)}")
            return {}
    
    def navigate_to_next_page(self) -> bool:
        """Navigate to the next page using available controls"""
        try:
            if not self.driver:
                logger.error("WebDriver not initialized")
                return False
                
            logger.info(f"Attempting to navigate from page {self.current_page}")
            
            # Get current page info to verify we're actually moving
            current_page_info = self.get_current_page_number()
            
            # Find pagination controls
            controls = self.find_pagination_controls()
            
            # Method 1: Try next button
            if 'next_button' in controls:
                try:
                    next_button = controls['next_button']
                    if next_button.is_enabled():
                        next_button.click()
                        time.sleep(self.delay)
                        
                        # Verify we moved to a new page
                        new_page_info = self.get_current_page_number()
                        if new_page_info != current_page_info:
                            self.current_page = new_page_info
                            logger.info(f"Successfully navigated to page {self.current_page}")
                            return True
                        else:
                            logger.warning("Next button clicked but page didn't change")
                    else:
                        logger.warning("Next button is disabled")
                except Exception as e:
                    logger.error(f"Error clicking next button: {str(e)}")
            
            # Method 2: Try page input
            if 'page_input' in controls:
                try:
                    page_input = controls['page_input']
                    next_page = self.current_page + 1
                    page_input.clear()
                    page_input.send_keys(str(next_page))
                    page_input.send_keys('\n')  # Press Enter
                    time.sleep(self.delay)
                    
                    # Verify we moved to a new page
                    new_page_info = self.get_current_page_number()
                    if new_page_info != current_page_info:
                        self.current_page = new_page_info
                        logger.info(f"Successfully navigated to page {self.current_page}")
                        return True
                    else:
                        logger.warning("Page input used but page didn't change")
                except Exception as e:
                    logger.error(f"Error using page input: {str(e)}")
            
            # Method 3: Try page links
            if 'page_links' in controls:
                try:
                    next_page = self.current_page + 1
                    for link in controls['page_links']:
                        if link.text.strip() == str(next_page):
                            link.click()
                            time.sleep(self.delay)
                            
                            # Verify we moved to a new page
                            new_page_info = self.get_current_page_number()
                            if new_page_info != current_page_info:
                                self.current_page = new_page_info
                                logger.info(f"Successfully navigated to page {self.current_page}")
                                return True
                            break
                except Exception as e:
                    logger.error(f"Error using page links: {str(e)}")
            
            # Method 4: Try URL parameter
            try:
                current_url = self.driver.current_url
                next_page = self.current_page + 1
                
                if '?' in current_url:
                    new_url = f"{current_url}&page={next_page}"
                else:
                    new_url = f"{current_url}?page={next_page}"
                
                self.driver.get(new_url)
                time.sleep(self.delay)
                
                # Verify we moved to a new page
                new_page_info = self.get_current_page_number()
                if new_page_info != current_page_info:
                    self.current_page = new_page_info
                    logger.info(f"Successfully navigated to page {self.current_page}")
                    return True
                else:
                    logger.warning("URL navigation used but page didn't change")
            except Exception as e:
                logger.error(f"Error with URL navigation: {str(e)}")
            
            logger.error("All navigation methods failed")
            return False
            
        except Exception as e:
            logger.error(f"Error navigating to next page: {str(e)}")
            return False
    
    def get_current_page_number(self) -> int:
        """Get the current page number from the page"""
        try:
            if not self.driver:
                return 1
                
            page_content = self.driver.page_source
            
            # Look for current page patterns
            page_patterns = [
                r'(\d+)\s*of\s*(\d+)',
                r'Página\s*(\d+)\s*de\s*(\d+)',
                r'(\d+)\s*/\s*(\d+)',
                r'(\d+)\s*de\s*(\d+)'
            ]
            
            for pattern in page_patterns:
                matches = re.findall(pattern, page_content, re.IGNORECASE)
                if matches:
                    current, total = map(int, matches[0])
                    return current
            
            # If not found, return the stored current page
            return self.current_page if self.current_page is not None else 1
            
        except Exception as e:
            logger.error(f"Error getting current page number: {str(e)}")
            return self.current_page if self.current_page is not None else 1
    
    def extract_current_page_data(self) -> List[Dict]:
        """Extract data from the current page"""
        projects = []
        
        try:
            if not self.driver:
                return projects
                
            # Take a screenshot for debugging (only for first few pages)
            if self.current_page <= 3:
                self.driver.save_screenshot(f"data/improved_page_{self.current_page}_screenshot.png")
                logger.info(f"Screenshot saved: data/improved_page_{self.current_page}_screenshot.png")
            
            # Extract table data
            table_data = self.extract_table_data()
            if table_data:
                projects.extend(table_data)
                logger.info(f"Page {self.current_page}: Extracted {len(table_data)} projects from table")
            
            # Remove duplicates based on project content
            unique_projects = []
            for project in projects:
                # Create a unique identifier based on title and description
                project_id = f"{project.get('title', '')}_{project.get('description', '')}"
                if project_id not in self.seen_project_ids:
                    self.seen_project_ids.add(project_id)
                    unique_projects.append(project)
                else:
                    logger.debug(f"Page {self.current_page}: Duplicate project found and skipped")
            
            logger.info(f"Page {self.current_page}: {len(unique_projects)} unique projects after deduplication")
            return unique_projects
            
        except Exception as e:
            logger.error(f"Error extracting data from page {self.current_page}: {str(e)}")
            return projects
    
    def extract_table_data(self) -> List[Dict]:
        """Extract data from tables"""
        projects = []
        
        try:
            if not self.driver:
                return projects
                
            tables = self.driver.find_elements(By.CSS_SELECTOR, 'table, mat-table')
            
            for i, table in enumerate(tables):
                try:
                    rows = table.find_elements(By.CSS_SELECTOR, 'tr, mat-row')
                    
                    if len(rows) > 1:
                        logger.info(f"Page {self.current_page}: Found table {i+1} with {len(rows)} rows")
                        
                        for j, row in enumerate(rows[1:], 1):  # Skip header
                            try:
                                cells = row.find_elements(By.CSS_SELECTOR, 'td, th, mat-cell')
                                
                                if len(cells) >= 2:
                                    project = {
                                        'id': f"page_{self.current_page}_table_{i+1}_row_{j}",
                                        'title': '',
                                        'description': '',
                                        'status': '',
                                        'date_created': '',
                                        'author': '',
                                        'committee': '',
                                        'document_url': '',
                                        'page_number': self.current_page,
                                        'source': 'improved_pagination_table'
                                    }
                                    
                                    # Extract text from cells
                                    for k, cell in enumerate(cells):
                                        cell_text = cell.text.strip()
                                        
                                        if k == 0:
                                            project['title'] = cell_text
                                        elif k == 1:
                                            project['description'] = cell_text
                                        elif k == 2:
                                            project['status'] = cell_text
                                        elif k == 3:
                                            project['date_created'] = cell_text
                                        elif k == 4:
                                            project['author'] = cell_text
                                        elif k == 5:
                                            project['committee'] = cell_text
                                    
                                    # Look for PDF links in the entire row more thoroughly
                                    pdf_links = self.find_pdf_links_in_table(row)
                                    if pdf_links:
                                        project['pdf_links'] = pdf_links
                                        project['document_url'] = pdf_links[0]  # Use first PDF link
                                        logger.info(f"Found PDF links for project: {pdf_links}")
                                    
                                    # Also look for links in individual cells
                                    for k, cell in enumerate(cells):
                                        try:
                                            links = cell.find_elements(By.CSS_SELECTOR, 'a')
                                            for link in links:
                                                href = link.get_attribute('href')
                                                link_text = link.text.strip().lower()
                                                
                                                if href:
                                                    # Check if it's a PDF link
                                                    if any(ext in href.lower() for ext in ['.pdf', 'pdf', 'download']):
                                                        if not project.get('document_url'):
                                                            project['document_url'] = href
                                                        if 'pdf_links' not in project:
                                                            project['pdf_links'] = []
                                                        project['pdf_links'].append(href)
                                                        logger.info(f"Found PDF link in cell {k}: {href}")
                                                    
                                                    # Check link text for PDF indicators
                                                    elif any(keyword in link_text for keyword in ['pdf', 'descargar', 'download', 'ver', 'documento']):
                                                        if not project.get('document_url'):
                                                            project['document_url'] = href
                                                        if 'pdf_links' not in project:
                                                            project['pdf_links'] = []
                                                        project['pdf_links'].append(href)
                                                        logger.info(f"Found potential PDF link in cell {k}: {href} (text: {link_text})")
                                                        
                                        except Exception as e:
                                            logger.debug(f"Error checking links in cell {k}: {str(e)}")
                                            continue
                                    
                                    # Look for buttons that might trigger PDF downloads
                                    try:
                                        buttons = row.find_elements(By.CSS_SELECTOR, 'button, input[type="button"]')
                                        for button in buttons:
                                            onclick = button.get_attribute('onclick') or ''
                                            button_text = button.text.strip().lower()
                                            
                                            # Check if this is a "Ver Documentos" button
                                            if 'ver documentos' in button_text or 'projectdialog' in onclick.lower():
                                                logger.info(f"Found 'Ver Documentos' button, attempting to extract PDF links")
                                                
                                                # Click the button to open the dialog
                                                try:
                                                    button.click()
                                                    time.sleep(2)  # Wait for dialog to appear
                                                    
                                                    # Look for the dialog
                                                    dialog_selectors = [
                                                        '.ui-dialog',
                                                        '.modal',
                                                        '[id*="dialog"]',
                                                        '[id*="modal"]',
                                                        '.projectDialog',
                                                        '#projectDialog'
                                                    ]
                                                    
                                                    dialog = None
                                                    for selector in dialog_selectors:
                                                        try:
                                                            dialogs = self.driver.find_elements(By.CSS_SELECTOR, selector)
                                                            for d in dialogs:
                                                                if d.is_displayed():
                                                                    dialog = d
                                                                    break
                                                            if dialog:
                                                                break
                                                        except Exception:
                                                            continue
                                                    
                                                    if dialog:
                                                        logger.info("Dialog found, looking for PDF links")
                                                        
                                                        # Look for PDF links in the dialog
                                                        pdf_links_in_dialog = self.find_pdf_links_in_dialog(dialog)
                                                        if pdf_links_in_dialog:
                                                            project['pdf_links'] = pdf_links_in_dialog
                                                            project['document_url'] = pdf_links_in_dialog[0]
                                                            logger.info(f"Found PDF links in dialog: {pdf_links_in_dialog}")
                                                        
                                                        # Close the dialog
                                                        try:
                                                            close_buttons = dialog.find_elements(By.CSS_SELECTOR, '.ui-dialog-titlebar-close, .close, [aria-label="Close"], button[onclick*="hide"]')
                                                            for close_btn in close_buttons:
                                                                if close_btn.is_displayed():
                                                                    close_btn.click()
                                                                    time.sleep(1)
                                                                    break
                                                        except Exception as e:
                                                            logger.debug(f"Error closing dialog: {str(e)}")
                                                            # Try pressing Escape key
                                                            from selenium.webdriver.common.keys import Keys
                                                            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                                                            time.sleep(1)
                                                    else:
                                                        logger.warning("Dialog not found after clicking button")
                                                        
                                                except Exception as e:
                                                    logger.error(f"Error clicking 'Ver Documentos' button: {str(e)}")
                                            
                                            elif 'pdf' in onclick.lower() or 'download' in onclick.lower():
                                                # Try to extract URL from onclick
                                                url_match = re.search(r'["\']([^"\']*\.pdf[^"\']*)["\']', onclick)
                                                if url_match:
                                                    href = url_match.group(1)
                                                    if not project.get('document_url'):
                                                        project['document_url'] = href
                                                    if 'pdf_links' not in project:
                                                        project['pdf_links'] = []
                                                    project['pdf_links'].append(href)
                                                    logger.info(f"Found PDF link in button onclick: {href}")
                                            
                                            elif any(keyword in button_text for keyword in ['pdf', 'descargar', 'download', 'ver', 'documento']):
                                                # Try to find associated URL
                                                try:
                                                    parent = button.find_element(By.XPATH, './..')
                                                    links = parent.find_elements(By.CSS_SELECTOR, 'a')
                                                    for link in links:
                                                        href = link.get_attribute('href')
                                                        if href:
                                                            if not project.get('document_url'):
                                                                project['document_url'] = href
                                                            if 'pdf_links' not in project:
                                                                project['pdf_links'] = []
                                                            project['pdf_links'].append(href)
                                                            logger.info(f"Found PDF link near button: {href}")
                                                            break
                                                except Exception as e:
                                                    logger.debug(f"Error finding associated URL: {str(e)}")
                                    except Exception as e:
                                        logger.debug(f"Error checking buttons: {str(e)}")
                                    
                                    if project.get('title') or project.get('description'):
                                        projects.append(project)
                                        
                            except Exception as e:
                                logger.debug(f"Error processing row {j}: {str(e)}")
                                continue
                                
                except Exception as e:
                    logger.debug(f"Error processing table {i+1}: {str(e)}")
                    continue
            
            return projects
            
        except Exception as e:
            logger.error(f"Error extracting table data: {str(e)}")
            return projects
    
    def scrape_all_pages(self, max_pages: Optional[int] = None) -> List[Dict]:
        """Scrape all pages to get all records"""
        try:
            logger.info("Starting to scrape all pages...")
            
            # Get pagination information
            pagination_info = self.get_total_records_and_pages()
            self.total_records = pagination_info['total_records']
            total_pages = pagination_info['total_pages']
            self.current_page = pagination_info['current_page']
            
            if max_pages:
                total_pages = min(total_pages, max_pages)
                logger.info(f"Limited to {max_pages} pages")
            
            logger.info(f"Total records to extract: {self.total_records}")
            logger.info(f"Will scrape {total_pages} pages")
            
            # Extract data from first page
            page_projects = self.extract_current_page_data()
            if page_projects:
                self.all_projects.extend(page_projects)
                logger.info(f"Page {self.current_page}: Added {len(page_projects)} projects (Total: {len(self.all_projects)})")
            
            # Continue with remaining pages
            for page_num in range(2, total_pages + 1):
                # Navigate to next page
                if self.navigate_to_next_page():
                    # Wait for page to load
                    time.sleep(self.delay)
                    
                    # Extract data from current page
                    page_projects = self.extract_current_page_data()
                    if page_projects:
                        self.all_projects.extend(page_projects)
                        logger.info(f"Page {self.current_page}: Added {len(page_projects)} projects (Total: {len(self.all_projects)})")
                    else:
                        logger.warning(f"Page {self.current_page}: No projects found")
                else:
                    logger.error(f"Failed to navigate to page {page_num}")
                    break
                
                # Progress update every 10 pages
                if page_num % 10 == 0:
                    logger.info(f"Progress: {page_num}/{total_pages} pages completed ({len(self.all_projects)} projects so far)")
                
                # Safety check - if we haven't found any new projects in the last few pages, stop
                if page_num > 10 and len(page_projects) == 0:
                    logger.warning(f"No new projects found on page {page_num}, stopping")
                    break
            
            logger.info(f"Scraping completed. Total projects extracted: {len(self.all_projects)}")
            return self.all_projects
            
        except Exception as e:
            logger.error(f"Error during pagination scraping: {str(e)}")
            return self.all_projects
    
    def start_scraping(self, start_date: str = "2021-01-01", end_date: str = "2025-05-14", max_pages: Optional[int] = None, output_formats=None):
        """Main scraping method"""
        if output_formats is None:
            output_formats = ['csv', 'json']
        
        try:
            logger.info(f"Starting improved pagination-based Ecuadorian National Assembly scraper")
            logger.info(f"Date range: {start_date} to {end_date}")
            if max_pages:
                logger.info(f"Max pages: {max_pages}")
            
            # Setup WebDriver
            if not self.setup_driver():
                return None
            
            # Navigate to the iframe URL
            if not self.navigate_to_iframe():
                self.close_driver()
                return None
            
            # Try to fill date inputs if available
            date_filled = self.find_and_fill_date_inputs(start_date, end_date)
            if date_filled:
                logger.info("Date inputs filled successfully")
            else:
                logger.warning("Could not find or fill date inputs")
            
            # Try to click submit button if available
            submit_clicked = self.find_and_click_submit_button()
            if submit_clicked:
                logger.info("Submit button clicked successfully")
            else:
                logger.warning("Could not find or click submit button")
            
            # Scrape all pages
            all_projects = self.scrape_all_pages(max_pages)
            
            if not all_projects:
                logger.warning("No projects found")
                self.close_driver()
                return None
            
            logger.info(f"Found {len(all_projects)} total projects")
            
            # Download PDFs for all projects
            if self.download_pdfs:
                logger.info("Starting PDF downloads...")
                pdf_stats = self.download_pdfs_for_projects(all_projects)
                logger.info(f"PDF download summary: {pdf_stats}")
            
            # Process and export data
            processed_data = self.data_processor.extract_project_info(all_projects)
            
            # Validate data
            validation = self.data_processor.validate_data(processed_data)
            logger.info(f"Data validation: {validation['valid_items']}/{validation['total_items']} valid items")
            
            # Export data
            exported_files = self.data_processor.export_data(processed_data, output_formats)
            
            # Generate and save summary
            summary = self.data_processor.generate_summary(processed_data)
            self.data_processor.save_summary(summary)
            
            logger.info(f"Scraping completed. Found {len(processed_data)} projects")
            logger.info(f"Exported to: {exported_files}")
            
            # Close WebDriver
            self.close_driver()
            
            return processed_data
            
        except Exception as e:
            logger.error(f"Error during scraping: {str(e)}")
            self.close_driver()
            return None
    
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
                'input[id*="date"]',
                '.date-picker input',
                '.date-input',
                'input[type="text"][placeholder*="fecha"]',
                'input[type="text"][placeholder*="date"]'
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

    def download_pdf_for_project(self, project: Dict) -> Optional[str]:
        """Download PDF for a specific project"""
        try:
            if not self.download_pdfs:
                return None
                
            document_url = project.get('document_url', '')
            if not document_url:
                logger.debug(f"No document URL for project: {project.get('title', 'Unknown')}")
                return None
            
            # Generate a safe filename
            title = project.get('title', 'Unknown')
            safe_title = re.sub(r'[^\w\s-]', '', title).strip()
            safe_title = re.sub(r'[-\s]+', '-', safe_title)
            safe_title = safe_title[:100]  # Limit length
            
            # Add project ID for uniqueness
            project_id = project.get('id', 'unknown')
            filename = f"{project_id}_{safe_title}.pdf"
            filepath = self.pdf_dir / filename
            
            # Skip if already downloaded
            if filepath.exists():
                logger.debug(f"PDF already exists: {filename}")
                return str(filepath)
            
            logger.info(f"Downloading PDF for project: {title}")
            
            # Try to download using requests first
            try:
                response = requests.get(document_url, timeout=30, stream=True)
                response.raise_for_status()
                
                # Check if it's actually a PDF
                content_type = response.headers.get('content-type', '').lower()
                if 'pdf' not in content_type and not document_url.lower().endswith('.pdf'):
                    logger.warning(f"URL doesn't appear to be a PDF: {document_url}")
                    return None
                
                # Download the file
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                logger.info(f"PDF downloaded successfully: {filename}")
                return str(filepath)
                
            except requests.RequestException as e:
                logger.warning(f"Failed to download PDF with requests: {str(e)}")
                # Fall back to Selenium if requests fails
                return self.download_pdf_with_selenium(document_url, filepath, title)
                
        except Exception as e:
            logger.error(f"Error downloading PDF for project {project.get('title', 'Unknown')}: {str(e)}")
            return None
    
    def download_pdf_with_selenium(self, url: str, filepath: Path, title: str) -> Optional[str]:
        """Download PDF using Selenium (fallback method)"""
        try:
            if not self.driver:
                logger.error("WebDriver not available for PDF download")
                return None
            
            logger.info(f"Attempting to download PDF with Selenium: {title}")
            
            # Navigate to the PDF URL
            self.driver.get(url)
            time.sleep(3)
            
            # Check if we're on a PDF page
            current_url = self.driver.current_url
            if 'pdf' in current_url.lower() or self.driver.page_source.startswith('%PDF'):
                # Try to get the PDF content
                try:
                    # Method 1: Try to get PDF content directly
                    pdf_content = self.driver.execute_script("""
                        var xhr = new XMLHttpRequest();
                        xhr.open('GET', arguments[0], false);
                        xhr.send();
                        return xhr.responseText;
                    """, url)
                    
                    if pdf_content and pdf_content.startswith('%PDF'):
                        with open(filepath, 'wb') as f:
                            f.write(pdf_content.encode('latin-1'))
                        logger.info(f"PDF downloaded with Selenium: {filepath.name}")
                        return str(filepath)
                        
                except Exception as e:
                    logger.debug(f"Failed to get PDF content directly: {str(e)}")
            
            # Method 2: Look for download links
            download_links = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*=".pdf"], a[href*="download"]')
            for link in download_links:
                try:
                    href = link.get_attribute('href')
                    if href and ('pdf' in href.lower() or 'download' in href.lower()):
                        response = requests.get(href, timeout=30, stream=True)
                        response.raise_for_status()
                        
                        with open(filepath, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        
                        logger.info(f"PDF downloaded via download link: {filepath.name}")
                        return str(filepath)
                        
                except Exception as e:
                    logger.debug(f"Failed to download via link {href}: {str(e)}")
                    continue
            
            logger.warning(f"Could not download PDF with Selenium: {title}")
            return None
            
        except Exception as e:
            logger.error(f"Error downloading PDF with Selenium: {str(e)}")
            return None
    
    def download_pdfs_for_projects(self, projects: List[Dict]) -> Dict:
        """Download PDFs for all projects"""
        if not self.download_pdfs:
            logger.info("PDF download is disabled")
            return {'downloaded': 0, 'failed': 0, 'skipped': 0, 'total': len(projects)}
        
        logger.info(f"Starting PDF download for {len(projects)} projects...")
        
        download_stats = {
            'downloaded': 0,
            'failed': 0,
            'skipped': 0,
            'total': len(projects),
            'downloaded_files': []
        }
        
        for i, project in enumerate(projects, 1):
            try:
                # Progress update every 10 projects
                if i % 10 == 0:
                    logger.info(f"PDF download progress: {i}/{len(projects)} projects processed")
                
                # Check if project has a document URL
                if not project.get('document_url'):
                    download_stats['skipped'] += 1
                    continue
                
                # Download PDF
                pdf_path = self.download_pdf_for_project(project)
                if pdf_path:
                    download_stats['downloaded'] += 1
                    download_stats['downloaded_files'].append({
                        'project_id': project.get('id', ''),
                        'title': project.get('title', ''),
                        'pdf_path': pdf_path
                    })
                    
                    # Update project with PDF path
                    project['pdf_file_path'] = pdf_path
                else:
                    download_stats['failed'] += 1
                
                # Small delay between downloads to be respectful
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error processing project {i}: {str(e)}")
                download_stats['failed'] += 1
        
        logger.info(f"PDF download completed: {download_stats['downloaded']} downloaded, "
                   f"{download_stats['failed']} failed, {download_stats['skipped']} skipped")
        
        return download_stats
    
    def find_pdf_links_in_table(self, row_element) -> List[str]:
        """Find PDF links in a table row"""
        pdf_links = []
        try:
            # Look for links in the row
            links = row_element.find_elements(By.CSS_SELECTOR, 'a')
            for link in links:
                href = link.get_attribute('href')
                if href:
                    # Check if it's a PDF link
                    if any(ext in href.lower() for ext in ['.pdf', 'pdf', 'download']):
                        pdf_links.append(href)
                    # Also check link text for PDF indicators
                    link_text = link.text.lower()
                    if any(keyword in link_text for keyword in ['pdf', 'descargar', 'download', 'ver']):
                        pdf_links.append(href)
            
            # Also look for buttons that might trigger PDF downloads
            buttons = row_element.find_elements(By.CSS_SELECTOR, 'button, input[type="button"]')
            for button in buttons:
                onclick = button.get_attribute('onclick') or ''
                if 'pdf' in onclick.lower() or 'download' in onclick.lower():
                    # Try to extract URL from onclick
                    url_match = re.search(r'["\']([^"\']*\.pdf[^"\']*)["\']', onclick)
                    if url_match:
                        pdf_links.append(url_match.group(1))
                        
        except Exception as e:
            logger.debug(f"Error finding PDF links in row: {str(e)}")
        
        return pdf_links
    
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

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Improved pagination-aware scraper for Ecuadorian National Assembly")
    parser.add_argument('--start-date', default='2021-01-01', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', default='2025-05-14', help='End date (YYYY-MM-DD)')
    parser.add_argument('--output-format', choices=['csv', 'json', 'both'], default='both', help='Output format')
    parser.add_argument('--headless', action='store_true', default=True, help='Run browser in headless mode')
    parser.add_argument('--delay', type=float, default=2.0, help='Delay between actions')
    parser.add_argument('--max-pages', type=int, help='Maximum number of pages to scrape (for testing)')
    parser.add_argument('--download-pdfs', action='store_true', default=True, help='Download PDFs for projects')
    parser.add_argument('--no-pdfs', action='store_true', help='Disable PDF downloads')
    parser.add_argument('--pdf-dir', default='data/pdfs', help='Directory to save PDFs')
    
    args = parser.parse_args()
    
    # Convert output format
    output_formats = ['csv', 'json'] if args.output_format == 'both' else [args.output_format]
    
    # Handle PDF download settings
    download_pdfs = args.download_pdfs and not args.no_pdfs
    
    try:
        logger.info("=" * 60)
        logger.info("Improved Pagination-aware Ecuadorian National Assembly Scraper")
        logger.info("=" * 60)
        
        # Create scraper instance
        scraper = ImprovedPaginationEcuadorScraper(
            headless=args.headless, 
            delay=args.delay,
            download_pdfs=download_pdfs,
            pdf_dir=args.pdf_dir
        )
        
        # Start scraping
        results = scraper.start_scraping(
            start_date=args.start_date,
            end_date=args.end_date,
            max_pages=args.max_pages,
            output_formats=output_formats
        )
        
        if results:
            logger.info("=" * 60)
            logger.info("SCRAPING COMPLETED SUCCESSFULLY!")
            logger.info(f"Total projects scraped: {len(results)}")
            if download_pdfs:
                logger.info("PDFs have been downloaded to the specified directory")
            logger.info("Check the 'data/' directory for output files")
            logger.info("=" * 60)
        else:
            logger.error("Scraping failed or no data was found")
            
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    main() 