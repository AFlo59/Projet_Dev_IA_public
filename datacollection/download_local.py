#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_local.py

Scrape and download D&D JSON and images from 5etools GitHub repo
to LOCAL storage only (no cloud upload).
Supports smart updates (only download if changed).
"""
import os
import argparse
import logging
import requests
import json
from urllib.parse import quote
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from datetime import datetime
import hashlib

# Load environment variables
load_dotenv()

# GitHub repo configuration from environment variables
github_owner = os.getenv('GITHUB_OWNER', '5etools-mirror-3')
github_repo  = os.getenv('GITHUB_REPO', '5etools-src')
branch       = os.getenv('GITHUB_BRANCH', 'main')
tree_api_url = f'https://api.github.com/repos/{github_owner}/{github_repo}/git/trees/{branch}?recursive=1'
raw_base_url = f'https://raw.githubusercontent.com/{github_owner}/{github_repo}/{branch}/'

# Site image URLs from environment variables
SITE_IMG_BASE = os.getenv('SITE_IMG_BASE', 'https://5e.tools/img')

# Default folders from environment variables
logs_dir    = os.getenv('LOGS_DIR', 'Logs')
output_dir  = os.getenv('OUTPUT_DIR', 'Output')
json_exts   = {'.json'}

# Create a session with retries for transient or SSL errors
session = requests.Session()
adapter = HTTPAdapter(
    max_retries=Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=['GET'],
        raise_on_status=False
    )
)
session.mount('https://', adapter)


def slugify_url(name: str) -> str:
    """Prepare slug for URL, percent-encoding spaces."""
    s = name.strip().replace("'", '')
    return quote(s.replace(' ', '%20'), safe='%20')


def slugify_fname(name: str) -> str:
    """Prepare slug for filename, replacing spaces with underscores."""
    return name.strip().replace("'", '').replace(' ', '_')


def setup_logger(name):
    # Reset log file
    os.makedirs(logs_dir, exist_ok=True)
    log_path = os.path.join(logs_dir, f'{name}.log')
    open(log_path, 'w').close()
    # Ensure output dir exists
    os.makedirs(output_dir, exist_ok=True)
    # Configure logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fh = logging.FileHandler(log_path, mode='w', encoding='utf-8')
    fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.info(f'Logger started (reset): {name}')
    return logger


def fetch_tree(logger):
    logger.info(f'GET {tree_api_url}')
    r = session.get(tree_api_url)
    r.raise_for_status()
    items = r.json().get('tree', [])
    logger.info(f'Tree items: {len(items)}')
    return items


def file_needs_update(local_path, remote_content):
    """Check if file needs update by comparing content hash"""
    if not os.path.exists(local_path):
        return True
    
    # Calculate hash of remote content
    remote_hash = hashlib.md5(remote_content).hexdigest()
    
    # Calculate hash of local file
    with open(local_path, 'rb') as f:
        local_hash = hashlib.md5(f.read()).hexdigest()
    
    return remote_hash != local_hash


class JsonScraper:
    def __init__(self):
        self.logger = setup_logger('JsonScraper')
        self.out_base = os.path.join(output_dir, 'data')
        os.makedirs(self.out_base, exist_ok=True)

    def scrape(self):
        items = fetch_tree(self.logger)
        files = [i['path'] for i in items
                 if i['type']=='blob'
                 and i['path'].startswith('data/')
                 and os.path.splitext(i['path'])[1] in json_exts]
        self.logger.info(f'JSON files: {len(files)}')
        for p in files:
            self.download(p)

    def download(self, path):
        url = raw_base_url + path
        rel = os.path.relpath(path, 'data')
        local = os.path.join(self.out_base, rel)
        os.makedirs(os.path.dirname(local), exist_ok=True)
        
        # Vérifier si mise à jour nécessaire
        r = session.get(url)
        r.raise_for_status()
        content = r.content
        
        if not file_needs_update(local, content):
            self.logger.info(f'SKIP JSON (up to date): {local}')
            return
            
        self.logger.info(f'DOWNLOAD JSON {url} -> {local}')
        with open(local, 'wb') as f:
            f.write(content)
        self.logger.info(f'SAVED JSON: {local}')


class ImageScraper:
    def __init__(self):
        self.logger = setup_logger('ImageScraper')
        self.out_base = os.path.join(output_dir, 'images')
        os.makedirs(self.out_base, exist_ok=True)

    def scrape(self):
        items = fetch_tree(self.logger)
        jsons = [i['path'] for i in items
                 if i['type']=='blob'
                 and i['path'].startswith('data/')
                 and os.path.splitext(i['path'])[1] in json_exts]
        self.logger.info(f'Analyze {len(jsons)} JSONs for images')
        for p in jsons:
            if p.startswith('data/bestiary/'):
                self.process_bestiary(p)
            elif p.startswith('data/races'):
                self.process_races(p)
            elif p.startswith('data/classes'):
                self.process_classes(p)
            elif p.startswith('data/feats'):
                self.process_feats(p)
            elif p.startswith('data/objects'):
                self.process_objects(p)
            else:
                self.process_generic(p)
        self.logger.info('Image scraping complete.')

    def process_bestiary(self, path):
        r = session.get(raw_base_url + path); r.raise_for_status(); data = r.json()
        for m in data.get('monster', []):
            name, src = m.get('name'), m.get('source')
            slug_url = slugify_url(name)
            slug_fn  = slugify_fname(name)
            # token
            if m.get('hasToken'):
                url_tok = f'{SITE_IMG_BASE}/bestiary/tokens/{src}/{slug_url}.webp'
                self.download_url(url_tok, f'bestiary/{src}/{slug_fn}_token.webp')
            # full image
            if m.get('hasFluffImages'):
                url_full = f'{SITE_IMG_BASE}/bestiary/{src}/{slug_url}.webp'
                self.download_url(url_full, f'bestiary/{src}/{slug_fn}.webp')

    def process_races(self, path):
        r = session.get(raw_base_url + path); r.raise_for_status(); data = r.json()
        for rc in data.get('race', []):
            name, src = rc.get('name'), rc.get('source')
            slug_url = slugify_url(name)
            slug_fn  = slugify_fname(name)
            url_img = f'{SITE_IMG_BASE}/races/{src}/{slug_url}.webp'
            self.download_url(url_img, f'races/{src}/{slug_fn}.webp')

    def process_classes(self, path):
        r = session.get(raw_base_url + path); r.raise_for_status(); data = r.json()
        for c in data.get('class', []):
            name, src = c.get('name'), c.get('source')
            slug_url = slugify_url(name)
            slug_fn  = slugify_fname(name)
            url_img = f'{SITE_IMG_BASE}/classes/{src}/{slug_url}.webp'
            self.download_url(url_img, f'classes/{src}/{slug_fn}.webp')

    def process_feats(self, path):
        r = session.get(raw_base_url + path); r.raise_for_status(); data = r.json()
        for f in data.get('feat', []) or data.get('feats', []):
            name, src = f.get('name'), f.get('source')
            slug_url = slugify_url(name)
            slug_fn  = slugify_fname(name)
            url_img = f'{SITE_IMG_BASE}/feats/{src}/{slug_url}.webp'
            self.download_url(url_img, f'feats/{src}/{slug_fn}.webp')

    def process_objects(self, path):
        r = session.get(raw_base_url + path); r.raise_for_status(); data = r.json()
        for o in data.get('object', []) or data.get('objects', []):
            name, src = o.get('name'), o.get('source')
            slug_url = slugify_url(name)
            slug_fn  = slugify_fname(name)
            # token
            url_tok = f'{SITE_IMG_BASE}/objects/tokens/{src}/{slug_url}.webp'
            self.download_url(url_tok, f'objects/tokens/{src}/{slug_fn}.webp')
            # full
            url_full = f'{SITE_IMG_BASE}/objects/{src}/{slug_url}.webp'
            self.download_url(url_full, f'objects/{src}/{slug_fn}.webp')

    def process_generic(self, path):
        r = session.get(raw_base_url + path); r.raise_for_status(); data = r.json()
        def walk(o):
            if isinstance(o, str) and o.startswith('/img/'):
                url = f'https://5e.tools{o}'
                rel = o.lstrip('/')
                self.download_url(url, rel)
            elif isinstance(o, dict):
                for v in o.values(): walk(v)
            elif isinstance(o, list):
                for v in o: walk(v)
        walk(data)

    def download_url(self, url, rel_output):
        local = os.path.join(self.out_base, rel_output)
        os.makedirs(os.path.dirname(local), exist_ok=True)
        
        # Vérifier si l'image existe déjà (skip si présente)
        if os.path.exists(local):
            self.logger.info(f'SKIP IMAGE (exists): {local}')
            return
            
        self.logger.info(f'DOWNLOAD IMG {url} -> {local}')
        try:
            r = session.get(url, stream=True)
            r.raise_for_status()
            with open(local, 'wb') as f:
                for c in r.iter_content(8192): f.write(c)
            self.logger.info(f'SAVED IMG: {local}')
        except Exception as e:
            self.logger.error(f'Failed to download {url}: {e}')


def main():
    p = argparse.ArgumentParser(description='Download D&D JSON and images to local storage')
    p.add_argument('--json',   action='store_true', help='Download JSON files only')
    p.add_argument('--images', action='store_true', help='Download images only')
    a = p.parse_args()
    
    # Par défaut : faire les deux si aucune option spécifiée
    if not a.json and not a.images:
        a.json = True
        a.images = True
        print('No specific option provided, downloading both JSON and images by default')
    
    if a.json:
        print('Starting JSON scraping...')
        JsonScraper().scrape()
    if a.images:
        print('Starting image scraping...')
        ImageScraper().scrape()
    print('Done')

if __name__=='__main__': main()