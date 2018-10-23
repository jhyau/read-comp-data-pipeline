import requests
from bs4 import BeautifulSoup
import logging

previews = []

def scrape(request):
    """Main request."""
    if request.method == 'POST':
        # Allows POST requests from any origin with the Content-Type
        # header and caches preflight response for an 3600s
        global previews
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        links = []
        request_json = request.get_json()
        ghost_url = request_json['url']
        r = requests.get(ghost_url)
        raw_html = r.text
        print('raw_html = ', raw_html)
        html = BeautifulSoup(raw_html, 'html.parser')
        links = html.find_all('.post-content a')
        for link in links:
            url = link.get('href')
            r2 = requests.get(url)
            link_html = r2.text
            link_preview = BeautifulSoup(link_html, 'html.parser')
            preview_dict = {
                'title': link_preview.title.string,
                'description': link_preview.find("meta",  property="og:description"),
                'image': link_preview.find("meta",  property="og:image"),
                'url': url
            }
            logging.warn(preview_dict)
            previews.append(preview_dict)
        return (previews, 200, headers)
