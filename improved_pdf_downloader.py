#!/usr/bin/env python3
"""
Improved PDF Downloader for Ecuadorian National Assembly
Handles authentication, session management, and proper error handling
"""

import sys
import os
import time
import re
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
import logging

# Add the current directory to Python path
sys.path.append(str(Path(__file__).parent))

from utils.logger import logger

class ImprovedPDFDownloader:
    """Improved PDF downloader with authentication and session management"""
    
    def __init__(self, pdf_dir: str = "data/improved_pdfs"):
        self.pdf_dir = Path(pdf_dir)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        
        # Session for maintaining cookies and authentication
        self.session = requests.Session()
        
        # Configure session headers to mimic a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9,es;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        })
        
        # Base URLs
        self.base_url = "https://leyes.asambleanacional.gob.ec"
        self.iframe_url = "https://leyes.asambleanacional.gob.ec?vhf=1"
        self.pdf_base_url = "https://ppless.asambleanacional.gob.ec"
        
        # Download statistics
        self.stats = {
            'downloaded': 0,
            'failed': 0,
            'skipped': 0,
            'total': 0
        }
    
    def setup_session(self) -> bool:
        """Setup session by visiting the main site and establishing cookies"""
        try:
            logger.info("Setting up session and establishing cookies...")
            
            # First, visit the main site to get initial cookies
            response = self.session.get(self.base_url, timeout=30)
            response.raise_for_status()
            logger.info(f"Main site visited: {response.status_code}")
            
            # Then visit the iframe URL to get additional cookies
            response = self.session.get(self.iframe_url, timeout=30)
            response.raise_for_status()
            logger.info(f"Iframe URL visited: {response.status_code}")
            
            # Check if we have any session cookies
            cookies = self.session.cookies
            logger.info(f"Session cookies established: {len(cookies)} cookies")
            
            # Log cookie names for debugging
            for cookie in cookies:
                logger.debug(f"Cookie: {cookie.name} = {cookie.value[:50] if cookie.value else 'None'}...")
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting up session: {str(e)}")
            return False
    
    def test_pdf_access(self, pdf_url: str) -> Tuple[bool, str]:
        """Test if a PDF URL is accessible and returns actual PDF content"""
        try:
            logger.info(f"Testing PDF access: {pdf_url}")
            
            # Make a HEAD request first to check if the URL exists
            head_response = self.session.head(pdf_url, timeout=30, allow_redirects=True)
            
            if head_response.status_code == 200:
                content_type = head_response.headers.get('content-type', '').lower()
                content_length = head_response.headers.get('content-length', '0')
                
                logger.info(f"HEAD response - Status: {head_response.status_code}, "
                           f"Content-Type: {content_type}, Content-Length: {content_length}")
                
                # Check if it looks like a PDF
                if 'pdf' in content_type or pdf_url.lower().endswith('.pdf'):
                    # Make a GET request to get the first few bytes
                    get_response = self.session.get(pdf_url, timeout=30, stream=True)
                    get_response.raise_for_status()
                    
                    # Read first 1024 bytes to check if it's actually a PDF
                    content = get_response.raw.read(1024)
                    get_response.close()
                    
                    if content.startswith(b'%PDF'):
                        logger.info("✅ PDF content confirmed - starts with %PDF")
                        return True, "PDF content confirmed"
                    else:
                        logger.warning(f"❌ URL doesn't contain PDF content: {content[:50]}")
                        return False, "Not PDF content"
                else:
                    logger.warning(f"❌ Content-Type doesn't indicate PDF: {content_type}")
                    return False, f"Wrong content type: {content_type}"
            else:
                logger.warning(f"❌ HEAD request failed: {head_response.status_code}")
                return False, f"HTTP {head_response.status_code}"
                
        except requests.RequestException as e:
            logger.error(f"❌ Request error testing PDF: {str(e)}")
            return False, str(e)
        except Exception as e:
            logger.error(f"❌ Error testing PDF access: {str(e)}")
            return False, str(e)
    
    def download_pdf(self, pdf_url: str, project_info: Dict) -> Optional[str]:
        """Download a single PDF with proper error handling"""
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
            
            # Test PDF access first
            is_accessible, reason = self.test_pdf_access(pdf_url)
            if not is_accessible:
                logger.warning(f"PDF not accessible: {reason}")
                return None
            
            # Download the PDF
            response = self.session.get(pdf_url, timeout=60, stream=True)
            response.raise_for_status()
            
            # Verify content type
            content_type = response.headers.get('content-type', '').lower()
            if 'pdf' not in content_type and not pdf_url.lower().endswith('.pdf'):
                logger.warning(f"Content-Type doesn't indicate PDF: {content_type}")
                return None
            
            # Download with progress tracking
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Log progress for large files
                        if total_size > 0 and downloaded_size % (1024 * 1024) == 0:  # Every MB
                            progress = (downloaded_size / total_size) * 100
                            logger.info(f"Download progress: {progress:.1f}% ({downloaded_size}/{total_size} bytes)")
            
            # Verify the downloaded file
            file_size = filepath.stat().st_size
            if file_size == 0:
                logger.error("Downloaded file is empty")
                filepath.unlink()  # Remove empty file
                return None
            
            # Check if it's actually a PDF by reading the first few bytes
            with open(filepath, 'rb') as f:
                header = f.read(4)
                if not header.startswith(b'%PDF'):
                    logger.warning("Downloaded file doesn't start with PDF header")
                    # Don't delete it yet, it might be a valid document
            
            logger.info(f"✅ PDF downloaded successfully: {filename} ({file_size} bytes)")
            return str(filepath)
            
        except requests.RequestException as e:
            logger.error(f"❌ Request error downloading PDF: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"❌ Error downloading PDF: {str(e)}")
            return None
    
    def download_pdfs_from_data(self, projects: List[Dict]) -> Dict:
        """Download PDFs for all projects in the data"""
        logger.info(f"Starting improved PDF download for {len(projects)} projects...")
        
        # Setup session first
        if not self.setup_session():
            logger.error("Failed to setup session, aborting PDF downloads")
            return self.stats
        
        self.stats['total'] = len(projects)
        
        for i, project in enumerate(projects, 1):
            try:
                # Progress update
                if i % 5 == 0:
                    logger.info(f"PDF download progress: {i}/{len(projects)} projects processed")
                
                # Get PDF links from project
                pdf_links = project.get('pdf_links', [])
                document_url = project.get('document_url', '')
                
                if document_url:
                    pdf_links.insert(0, document_url)  # Add main document URL first
                
                if not pdf_links:
                    logger.debug(f"No PDF links for project: {project.get('title', 'Unknown')}")
                    self.stats['skipped'] += 1
                    continue
                
                # Try to download the first available PDF
                pdf_downloaded = False
                for pdf_url in pdf_links:
                    if pdf_url:
                        pdf_path = self.download_pdf(pdf_url, project)
                        if pdf_path:
                            project['pdf_file_path'] = pdf_path
                            self.stats['downloaded'] += 1
                            pdf_downloaded = True
                            break
                
                if not pdf_downloaded:
                    self.stats['failed'] += 1
                
                # Delay between downloads to be respectful
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error processing project {i}: {str(e)}")
                self.stats['failed'] += 1
        
        logger.info(f"PDF download completed: {self.stats['downloaded']} downloaded, "
                   f"{self.stats['failed']} failed, {self.stats['skipped']} skipped")
        
        return self.stats
    
    def test_specific_pdf(self, pdf_url: str) -> bool:
        """Test downloading a specific PDF URL"""
        try:
            logger.info("=" * 60)
            logger.info("Testing Specific PDF Download")
            logger.info("=" * 60)
            
            # Setup session
            if not self.setup_session():
                return False
            
            # Test PDF access
            is_accessible, reason = self.test_pdf_access(pdf_url)
            logger.info(f"PDF Access Test: {is_accessible} - {reason}")
            
            if is_accessible:
                # Try to download
                project_info = {
                    'id': 'test',
                    'title': 'Test PDF'
                }
                
                pdf_path = self.download_pdf(pdf_url, project_info)
                if pdf_path:
                    logger.info("=" * 60)
                    logger.info("✅ SPECIFIC PDF TEST SUCCESSFUL!")
                    logger.info(f"PDF saved to: {pdf_path}")
                    logger.info("=" * 60)
                    return True
                else:
                    logger.error("❌ PDF download failed")
                    return False
            else:
                logger.error(f"❌ PDF not accessible: {reason}")
                return False
                
        except Exception as e:
            logger.error(f"Error during specific PDF test: {str(e)}")
            return False

def main():
    """Main function for testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Improved PDF Downloader for Ecuadorian National Assembly")
    parser.add_argument('--test-url', help='Test a specific PDF URL')
    parser.add_argument('--pdf-dir', default='data/improved_pdfs', help='Directory to save PDFs')
    
    args = parser.parse_args()
    
    downloader = ImprovedPDFDownloader(pdf_dir=args.pdf_dir)
    
    if args.test_url:
        # Test specific URL
        success = downloader.test_specific_pdf(args.test_url)
        if success:
            logger.info("PDF test completed successfully!")
        else:
            logger.error("PDF test failed!")
    else:
        # Load existing data and download PDFs
        try:
            import json
            with open('data/law_projects.json', 'r', encoding='utf-8') as f:
                projects = json.load(f)
            
            stats = downloader.download_pdfs_from_data(projects)
            logger.info(f"Download completed with stats: {stats}")
            
        except FileNotFoundError:
            logger.error("No law_projects.json file found. Run the scraper first.")
        except Exception as e:
            logger.error(f"Error loading data: {str(e)}")

if __name__ == "__main__":
    main() 