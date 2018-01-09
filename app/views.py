from flask import render_template, request, redirect
from app import app
from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse
from time import sleep
import logging
import json
import base64

HPF_BASE_URL = base64.b64decode('d3d3LmhvdHBvcm5maWxlLm9yZw==').decode("utf-8")
USER_AGENT = 'hpf'
HPF_UPSTREAM_INDEX='http://' + HPF_BASE_URL + '/page/%d'
HPF_UPSTREAM_POST='http://' + HPF_BASE_URL + '/%s'
HPF_LINKS='http://' + HPF_BASE_URL + '/wp-admin/admin-ajax.php'
REQUEST_RATELIMIT=76.0 / 1000.0
TOKENS={}

def is_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


def fetch_links(post_id):
    if int(post_id) not in TOKENS:
        return [], ''
    response = TOKENS[int(post_id)]
    payload = 'action=get_protected_links&postId=%s&response=%s' % (post_id, response)
    headers = {
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Accept-Encoding': 'identity, deflate, compress, gzip',
        'Accept': '*/*',
        'User-Agent': USER_AGENT
    }
    r = requests.post(HPF_LINKS, payload, timeout=3, headers=headers)
    sleep(REQUEST_RATELIMIT)
    if r.status_code is not requests.codes.ok:
        logging.warning('Links page request error for: %s' % (HPF_LINKS))
        return [], ''
    jzon = json.loads(r.text)
    if jzon['type'] != 'success':
        return [], ''
    links_html = jzon['msg']
    soup = BeautifulSoup(links_html, 'html.parser')

    links = {}
    stream = ''
    for link_html in soup.findAll('a'):
        provider = urlparse(link_html['href']).hostname
        if provider in links:
            links[provider] += [link_html['href']]
        else:
            links[provider] = [link_html['href']]

    stream_html = soup.find('div', {'class': 'flex-video'})
    if stream_html is not None:
        stream = stream_html.find('iframe')['src']
    return links, stream


def fetch_links_bypass(post_id):
    if int(post_id) not in TOKENS:
        return [], ''
    challenge = TOKENS[int(post_id)]
    payload = 'action=bypass_captcha&postId=%s&challenge=%s' % (post_id, challenge)
    headers = {
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Accept-Encoding': 'identity, deflate, compress, gzip',
        'Accept': '*/*',
        'User-Agent': USER_AGENT
    }
    r = requests.post(HPF_LINKS, payload, timeout=3, headers=headers)
    sleep(REQUEST_RATELIMIT)
    if r.status_code is not requests.codes.ok:
        logging.warning('Links page request error for: %s' % (HPF_LINKS))
        return [], ''
    jzon = json.loads(r.text)
    if jzon['type'] != 'success':
        return [], ''
    links_html = jzon['msg']
    soup = BeautifulSoup(links_html, 'html.parser')

    links = {}
    stream = ''
    for link_html in soup.findAll('a'):
        provider = urlparse(link_html['href']).hostname
        if provider in links:
            links[provider] += [link_html['href']]
        else:
            links[provider] = [link_html['href']]

    stream_html = soup.find('div', {'class': 'flex-video'})
    if stream_html is not None:
        stream = stream_html.find('iframe')['src']
    return links, stream


def fetch_upstream_index(page=0, search=None):
    url = HPF_UPSTREAM_INDEX % (page)
    headers = {
        'Accept-Encoding': 'identity, deflate, compress, gzip',
        'Accept': '*/*',
        'User-Agent': USER_AGENT
    }

    if search is not None:
        url += '?s=%s&search_sortby=date' % (search)
    r = requests.get(url, timeout=3, headers=headers)
    sleep(REQUEST_RATELIMIT)
    if r.status_code is not requests.codes.ok:
        logging.warning('Index page request error for: %s' % (url))
        return None
    soup = BeautifulSoup(r.text, 'html.parser')
    posts_data = soup.findAll('div', {'class': 'box columns'})
    if len(posts_data) is 0:
        logging.warning('No results for for: %s' % (url))
        return None

    items = []
    for post_data in posts_data:
        item = {
            'id': '',
            'image': '',
            'title': '',
            'link': '',
        }
        item['id'] = post_data['id']
        post_data = post_data.find('div', {'class': 'thumbnail'})

        try:
            image_url = post_data.find('img', {'class': 'img'})['src']
            if len(image_url) is not 0:
                image = requests.get(image_url, timeout=3, headers=headers)
                sleep(REQUEST_RATELIMIT)
                item['image'] = ('data:' + image.headers['Content-Type'] + ';' + 'base64,' + str(base64.b64encode(image.content).decode("utf-8")))
        except:
            pass

        caption = post_data.find('div', {'class': 'caption text-center'})
        caption = caption.find('h2')
        item['title'] = caption.string
        item['link'] = urlparse(caption.find('a')['href']).path[1:]
        items += [item]
    return items


def fetch_upstream_post(post):
    headers = {
        'Accept-Encoding': 'identity, deflate, compress, gzip',
        'Accept': '*/*',
        'User-Agent': USER_AGENT
    }
    url = HPF_UPSTREAM_POST % (post)
    r = requests.get(url, timeout=3, headers=headers)
    sleep(REQUEST_RATELIMIT)

    if r.status_code is not requests.codes.ok:
        logging.warning('Post page request error for: %s' % (url))
        return None
    soup = BeautifulSoup(r.text, 'html.parser')
    post_id = post[post.rfind('/') + 1:]
    if len(post_id) is 0 or not is_int(post_id):
        logging.warning('Invalid post ID: %s' % (url))
        return None

    item = {
        'title': '',
        'cover': '',
        'screencap_thumb': '',
        'screencap': '',
        'download': [
            # 'provider': {}
        ],
        'stream': ''
    }

    post_data = soup.find('article', {'id': 'post-%s' % (post_id)})
    if post_data is None:
        return None

    post_data = post_data.find('div', {'class': 'entry-content'})
    post_data = post_data.findChildren('p')
    if len(post_data) < 2:
        return None
    cover_data = post_data[0]

    try:
        image_url = cover_data.find('img')['src']
        if len(image_url) is not 0:
            image = requests.get(image_url, timeout=3, headers=headers)
            sleep(REQUEST_RATELIMIT)
            item['cover'] = ('data:' + image.headers['Content-Type'] + ';' + 'base64,' + str(base64.b64encode(image.content).decode("utf-8")))
    except:
        pass

    screencap_data = post_data[1]
    item['title'] = screencap_data.find('strong').string
    item['screencap'] = screencap_data.find('a')['href']
    # item['screencap_thumb'] = screencap_data.find('a').find('img')['src']
    # image = requests.get(screencap_data.find('a').find('img')['src'], headers=headers)
    # sleep(REQUEST_RATELIMIT)
    # item['screencap_thumb'] = ('data:' + image.headers['Content-Type'] + ';' + 'base64,' + str(base64.b64encode(image.content).decode("utf-8")))

    item['download'], item['stream'] = fetch_links(post_id)
    return item


@app.route('/', methods=['GET'])
@app.route('/index/<int:page>', methods=['GET'])
@app.route('/search', methods=['POST'])
@app.route('/search/<string:search>', methods=['GET'])
@app.route('/search/<string:search>/<int:page>', methods=['GET'])
def index(page=0, search=None):
    if request.form is not None and len(request.form) is not 0:
        return redirect('%s/search/%s' % (app.config['APPLICATION_ROOT'], request.form['search']))
    if request.path.startswith('/search') and page == 0:
        page = 1
    current_page = fetch_upstream_index(page, search)

    path = ''
    if request.path == '/' or request.path.startswith('/index'):
        path = 'index'
    if request.path.startswith('/search'):
        if not is_int(request.path[request.path.rfind('/') + 1:]):
            path = request.path[1:]
        else:
            path = request.path[1:request.path.rfind('/')]

    previous_page = '' if page == 0 else '%s/%d' % (path, page - 1)
    next_page = '' if fetch_upstream_index(page + 1, search) is None else '%s/%d' % (path, page + 1)
    return render_template('index.html', title='All Results - Page %s' % (page), root=app.config['APPLICATION_ROOT'], posts=current_page, previous_page=previous_page, next_page=next_page)


@app.route('/post/<string:name>/<int:id>', methods=['GET', 'POST'])
def post(name, id):
    global TOKENS
    if request.form is not None and len(request.form) is not 0:
        TOKENS[id] = request.form['g-recaptcha-response']
    if id not in TOKENS:
        captcha = True
    else:
        captcha = False
    info = fetch_upstream_post('%s/%d' % (name, id))
    captcha = len(info['download']) == 0 or captcha
    return render_template('post.html', root=app.config['APPLICATION_ROOT'], info=info, display_captcha=captcha)
