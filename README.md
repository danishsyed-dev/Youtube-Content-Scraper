# YouTube Content Scraper

A web application built using Python and the **Flask** framework that automates the collection of YouTube video data for any specified company or brand. It utilizes **Selenium** for browser automation and page scrolling, parses the dynamic content with **BeautifulSoup**, and generates a downloadable CSV file using **Pandas**.

---

## 🚀 Features
* **Automated Search:** Dynamically searches Google to find the correct YouTube channel page for a company.
* **Infinite Scroll Support:** Automatically scrolls through the channel's videos tab to load all available videos.
* **Scraped Fields:** Captures video link, title, views count, and upload date.
* **CSV Generation:** Converts scraped video data into a structured CSV file.
* **Web UI:** Simple input form and one-click CSV file download.

---

## 🛠️ Prerequisites
Before running the application, make sure you have:
1. **Python 3.8+** installed.
2. **Google Chrome** browser installed.
3. **ChromeDriver** installed and added to your system's PATH (or matching your Chrome version).

---

## 💻 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone <your-repository-url>
   cd YouTube-Content-Scraper
   ```

2. **Create and activate a virtual environment (recommended):**
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

---

## 🏃 Running the Application

1. Start the Flask development server:
   ```bash
   python app.py
   ```
2. Open your web browser and navigate to:
   ```
   http://127.0.0.1:5000
   ```
3. Enter a company name and click **Scrape YouTube Data**.
4. Once completed, download the generated `data.csv`.

---

## 📁 Repository Structure
* `app.py` - Core web application and scraper logic.
* `templates/` - HTML layout for the frontend.
* `requirements.txt` - Python project dependencies.
* `data.csv` - Scraped data output (excluded from Git tracking).
* `Youtube infinite scraping.ipynb` - Prototype Jupyter notebook.

---

## ⚠️ Disclaimer
This project is for educational purposes. Scraping websites must comply with their respective terms of service and robots.txt policies. Use responsibly and avoid overloading target servers.
