import json
from flask import Flask, jsonify, request
from bs4 import BeautifulSoup
import requests
import re
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor
from ch import CHANNELS  
from fake_useragent import UserAgent

app = Flask(__name__)

def generate_user_agent():
    ua = UserAgent()
    return ua.random

def extract_playback_info(url):
    try:
        headers = {
            'User-Agent': generate_user_agent()
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()
        html = response.text

        pattern = r'<script type="text/javascript">var player_aaaa=\{(.*?)\}</script>'
        match = re.findall(pattern, html)
        if match:
            json_data = match[0]  # Remove the extra curly brace
            data = json.loads("{" + json_data + "}")  # Parse JSON data
            url = data.get("url")
            url_next = data.get("url_next")
            # Creating dictionary to store data
            playback_info = {
                "url": url,
                "next_url": url_next,
            }
            return playback_info
        else:
            return None

    except requests.RequestException as e:
        return None

@app.route('/player', methods=['GET'])
def get_playback_info():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'Missing URL parameter'}), 400

    playback_info = extract_playback_info(url)
    if playback_info:
        return jsonify(playback_info)
    else:
        return jsonify({'error': 'Failed to extract playback information.'}), 500

def extract_movie_info(html: str) -> Dict:
    movie_info = {}

    # Extract film title
    title_pattern = re.compile(r'<h3 class="slide-info-title hide">(.*?)</h3>')
    title_match = title_pattern.search(html)
    movie_info['title'] = title_match.group(1).strip() if title_match else ""

    # Extract film year, region, and genre
    year_pattern = re.compile(r'<span class="slide-info-remarks"><a.*?>(.*?)</a></span>')
    year_matches = year_pattern.findall(html)
    movie_info['year'] = year_matches[0].strip() if year_matches else ""
    movie_info['area'] = year_matches[1].strip() if len(year_matches) > 1 else ""
    movie_info['genres'] = [match.strip() for match in year_matches[2:]]

    # Extract film remark
    remark_pattern = re.compile(r'<div class="slide-info hide"><strong class="r6">备注 :</strong>(.*?)</div>')
    remark_match = remark_pattern.search(html)
    movie_info['remark'] = remark_match.group(1).strip() if remark_match else ""

    # Extract update date
    update_pattern = re.compile(r'<div class="slide-info hide"><strong class="r6">更新 :</strong>(.*?)</div>')
    update_match = update_pattern.search(html)
    movie_info['update_date'] = update_match.group(1).strip() if update_match else ""

    return movie_info

def fetch_film_info(film_link: str) -> Dict:
    try:
        if not film_link.startswith('http'):
            film_link = 'https://www.huale.tv' + film_link
        response = requests.get(film_link,headers={'User-Agent': generate_user_agent()}, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        info = extract_movie_info(response.text)
        cover_url = soup.find('img', class_='lazy1')['data-src']
        last_div = soup.find_all("div", class_="anthology-list-box")[-1]
        ul = last_div.find("ul")
        lis = ul.find_all("li")
        dt = []

        for li in lis:
            a = li.find("a")
            href = a["href"]
            title = a.text
            dt.append({
                'title': title,
                'href': 'https://www.huale.tv' + href
            })

        other = {
            'cover_url': cover_url,
            'player_link': dt
        }

        info.update(other)
        return info

    except Exception as e:
        print(f"获取电影信息失败：{e}")
        return None

def fetch_film_info_threaded(film_links: List[str]) -> List[Dict]:
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = executor.map(fetch_film_info, film_links)
    return [result for result in results if result]

def get_channel_url(channel: str, category: str, page_num: int) -> str:
    channel_info = CHANNELS.get(channel)
    if not channel_info:
        return f'https://www.huale.tv/vodshow/1/by/hits/page/{page_num}.html'  # 默认返回全部电影

    category_url = channel_info.get(category)
    if not category_url:
        return f'https://www.huale.tv/vodshow/1/by/hits/page/{page_num}.html'  # 默认返回全部电影

    return f'https://www.huale.tv{category_url}{page_num}.html'

@app.route('/movies', methods=['GET'])
def get_movies():
    category = request.args.get('category')
    channel = request.args.get('channel')
    page_num = request.args.get('page_num')  
    if not page_num or not channel:
        return jsonify({'error': 'Missing page_num or channel parameter'}), 400

    url = get_channel_url(channel, category, int(page_num))

    try:
        response = requests.get(url,headers={'User-Agent': generate_user_agent()}, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        film_links = [a['href'] for a in soup.find_all('a', class_='public-list-exp')]
        film_set = set(film_links)  # Remove duplicate links

        films_data = fetch_film_info_threaded(film_set)

        return jsonify(films_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False,host='0.0.0.0',port=5000)
