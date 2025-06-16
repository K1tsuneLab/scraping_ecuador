# Ecuadorian National Assembly Law Projects Scraper

This project scrapes law project data from the Ecuadorian National Assembly's official website: https://proyectosdeley.asambleanacional.gob.ec/report

## Features

- Scrapes law project data from the Ecuadorian National Assembly
- Handles dynamic JavaScript content using Playwright
- Extracts comprehensive project information including:
  - Project titles and descriptions
  - Legislative status
  - Dates and timestamps
  - Related documents and links
- Exports data to CSV and JSON formats
- Includes error handling and retry mechanisms

## Setup

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Playwright browsers:**
   ```bash
   playwright install
   ```

3. **Set up environment variables (optional):**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

## Usage

### Basic Usage
```bash
python main.py
```

### Advanced Usage
```bash
python scraper.py --output-format csv --max-pages 10
```

### Using the API Scraper
```bash
python api_scraper.py --endpoint projects --limit 100
```

## Project Structure

```
scraping_ecuador/
├── main.py                 # Main entry point
├── scraper.py             # Core scraping logic
├── api_scraper.py         # API-based scraping
├── utils/
│   ├── __init__.py
│   ├── browser.py         # Browser management
│   ├── data_processor.py  # Data processing utilities
│   └── logger.py          # Logging configuration
├── data/                  # Output directory
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## Configuration

The scraper can be configured through environment variables or command-line arguments:

- `MAX_PAGES`: Maximum number of pages to scrape
- `OUTPUT_FORMAT`: Output format (csv, json, both)
- `HEADLESS`: Run browser in headless mode (true/false)
- `DELAY`: Delay between requests in seconds

## Output

The scraper generates the following output files in the `data/` directory:

- `law_projects.csv`: CSV file with all scraped data
- `law_projects.json`: JSON file with structured data
- `scraping_log.txt`: Detailed logging information

## Legal Notice

This scraper is for educational and research purposes. Please respect the website's robots.txt and terms of service. Consider implementing appropriate delays between requests to avoid overwhelming the server.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details 