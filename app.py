from flask import Flask, render_template, request, send_file, redirect, url_for
import time
import pandas as pd
from tqdm import tqdm
from bs4 import BeautifulSoup
from selenium import webdriver
import os
from urllib.parse import quote_plus

app = Flask(__name__)

def scrape_youtube_data(company_name):
    browser = webdriver.Chrome()
    try:
        search_url = 'https://www.google.com/search?q=' + quote_plus(company_name + ' youtube')
        browser.get(search_url)

        soup = BeautifulSoup(browser.page_source, 'html.parser')
        result = next(
            (item.find('a', href=True) for item in soup.find_all('div', class_='MjjYud')),
            None,
        )
        if result is None:
            raise ValueError('No search result found for that company.')

        channel_url = result['href'].rstrip('/')
        browser.get(channel_url + '/videos')

        for i in tqdm(range(0, 2500000, 1000)):
            browser.execute_script('window.scrollTo(0,' + str(i) + ')')
            time.sleep(0.1)

        soup = BeautifulSoup(browser.page_source, 'html.parser')

        data = []
        for item in soup.find_all('ytd-rich-item-renderer', class_='style-scope ytd-rich-grid-row'):
            video = item.find(
                'a', class_='yt-simple-endpoint focus-on-expand style-scope ytd-rich-grid-media'
            )
            metadata = item.find_all('span', class_='inline-metadata-item style-scope ytd-video-meta-block')
            if video is None or len(metadata) < 2:
                continue
            data.append([
                'https://www.youtube.com/' + video['href'].lstrip('/'),
                video.get('title', ''),
                metadata[0].text.split(' ')[0],
                metadata[1].text,
            ])

        df = pd.DataFrame(data, columns=['Link', 'Title', 'Views', 'Upload Time'])
        df.to_csv('data.csv', index=False)
    finally:
        browser.quit()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        input_company = request.form['company']
        try:
            scrape_youtube_data(input_company)
        except ValueError as error:
            return render_template('index.html', error=str(error)), 400
        return redirect(url_for('download'))

    return render_template('index.html')

@app.route('/download')
def download():
    path = os.path.join(os.getcwd(), 'data.csv')
    return send_file(path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)