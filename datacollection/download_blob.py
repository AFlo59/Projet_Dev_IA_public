#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_blob.py

Scrape and download D&D JSON and images from 5etools GitHub repo,
save locally AND upload to Azure Blob Storage.
Supports smart updates (only download/upload if changed).
"""
import json
import os
import argparse
import logging
import requests
from urllib.parse import quote
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
import hashlib

# 👇 importer les clients Blob configurés
from azure_blob_setup import json_container_client, image_container_client
from azure.core.exceptions import AzureError

# GitHub repo configuration from environment variables (via azure_blob_setup.py load_dotenv)
github_owner = os.getenv('GITHUB_OWNER', '5etools-mirror-3')
github_repo  = os.getenv('GITHUB_REPO', '5etools-src')
branch       = os.getenv('GITHUB_BRANCH', 'main')
tree_api_url = f'https://api.github.com/repos/{github_owner}/{github_repo}/git/trees/{branch}?recursive=1'
raw_base_url = f'https://raw.githubusercontent.com/{github_owner}/{github_repo}/{branch}/'

# Site image base URL from environment variables
SITE_IMG_BASE = os.getenv('SITE_IMG_BASE', 'https://5e.tools/img')

# Default folders from environment variables
logs_dir   = os.getenv('LOGS_DIR', 'Logs')
output_dir = os.getenv('OUTPUT_DIR', 'Output')
json_exts  = {'.json'}

# HTTP session with retry
session = requests.Session()
adapter = HTTPAdapter(
    max_retries=Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500,502,503,504],
        allowed_methods=['GET'],
        raise_on_status=False
    )
)
session.mount('https://', adapter)


def slugify_url(name: str) -> str:
    s = name.strip().replace("'", '')
    return quote(s.replace(' ', '%20'), safe='%20')


def slugify_fname(name: str) -> str:
    return name.strip().replace("'", '').replace(' ', '_')


def setup_logger(name):
    os.makedirs(logs_dir, exist_ok=True)
    log_path = os.path.join(logs_dir, f'{name}.log')
    open(log_path, 'w').close()
    os.makedirs(output_dir, exist_ok=True)
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
    tree = r.json().get('tree', [])
    logger.info(f'Tree items: {len(tree)}')
    return tree


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
        tree = fetch_tree(self.logger)
        json_files = [e['path'] for e in tree
                      if e['type']=='blob'
                      and e['path'].startswith('data/')
                      and os.path.splitext(e['path'])[1].lower() in json_exts]
        self.logger.info(f'{len(json_files)} JSON files detected')
        for path in json_files:
            self._download(path)

    def _download(self, path):
        url    = raw_base_url + path
        rel    = os.path.relpath(path, 'data')
        out    = os.path.join(self.out_base, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)

        try:
            # 1) Télécharger en mémoire pour vérifier si mise à jour nécessaire
            r = session.get(url)
            r.raise_for_status()
            data_bytes = r.content

            # 2) Vérifier si mise à jour nécessaire
            if not file_needs_update(out, data_bytes):
                self.logger.info(f'SKIP JSON (up to date): {out}')
                return

            self.logger.info(f'DOWNLOAD JSON {url} -> {out}')

            # 3) Sauvegarder localement
            try:
                with open(out, 'wb') as f:
                    f.write(data_bytes)
                self.logger.info(f'SAVED JSON: {out}')
            except OSError as e:
                self.logger.error(f'Impossible de sauvegarder localement {out}: {e}')

            # 4) Uploader sur Azure (overwrite=True pour mettre à jour)
            blob_name = f"data/{rel.replace(os.sep, '/')}"
            json_container_client.upload_blob(
                name=blob_name,
                data=data_bytes,
                overwrite=True
            )
            self.logger.info(f'UPLOADED JSON to blob://{json_container_client.container_name}/{blob_name}')

        except (requests.HTTPError, AzureError) as e:
            self.logger.error(f'Échec download/upload {url}: {e}')


class ImageScraper:
    def __init__(self):
        self.logger = setup_logger('ImageScraper')
        self.out_base = os.path.join(output_dir, 'images')
        os.makedirs(self.out_base, exist_ok=True)

    def scrape(self):
        tree = fetch_tree(self.logger)
        jsons = [e['path'] for e in tree
                 if e['type']=='blob'
                 and e['path'].startswith('data/')
                 and os.path.splitext(e['path'])[1].lower() in json_exts]
        self.logger.info(f'Analyze {len(jsons)} JSONs for images')
        for path in jsons:
            if path.startswith('data/bestiary/'):
                self._bestiary(path)
            elif path.startswith('data/races'):
                self._races(path)
            elif path.startswith('data/class/'):
                self._classes(path)
            elif path.startswith('data/feats'):
                self._feats(path)
            elif path.startswith('data/objects'):
                self._objects(path)
            else:
                self._generic(path)
        self.logger.info('Image scraping complete.')

    def _bestiary(self, path):
        data = session.get(raw_base_url + path).json()
        for m in data.get('monster', []):
            name, src = m.get('name'), m.get('source')
            slug_u, slug_f = slugify_url(name), slugify_fname(name)
            if m.get('hasToken'):
                tok = f'{SITE_IMG_BASE}/bestiary/tokens/{src}/{slug_u}.webp'
                self._download(tok, f'bestiary/{src}/{slug_f}_token.webp')
            if m.get('hasFluffImages'):
                full = f'{SITE_IMG_BASE}/bestiary/{src}/{slug_u}.webp'
                self._download(full, f'bestiary/{src}/{slug_f}.webp')

    def _races(self, path):
        data = session.get(raw_base_url + path).json()
        for rc in data.get('race', []):
            name, src = rc.get('name'), rc.get('source')
            slug_u, slug_f = slugify_url(name), slugify_fname(name)
            img = f'{SITE_IMG_BASE}/races/{src}/{slug_u}.webp'
            self._download(img, f'races/{src}/{slug_f}.webp')

    def _classes(self, path):
        prefix = os.path.basename(path).split('-',1)[0]
        data = session.get(raw_base_url + path).json()
        # entries
        for entry in data.get('class', []):
            name, main_src = entry.get('name'), entry.get('source')
            others = [o.get('source') for o in entry.get('otherSources', [])]
            for src in {main_src}|set(others):
                slug_u, slug_f = slugify_url(name), slugify_fname(name)
                url = f'{SITE_IMG_BASE}/classes/{src}/{slug_u}.webp'
                rel = os.path.join('classes', prefix, src, f'{slug_f}.webp')
                self._download(url, rel)
        # fluff class data
        for entry in data.get('classFluff', []):
            name, src = entry.get('name'), entry.get('source')
            slug_u, slug_f = slugify_url(name), slugify_fname(name)
            url = f'{SITE_IMG_BASE}/classes/{src}/{slug_u}.webp'
            rel = os.path.join('classes', prefix, src, f'{slug_f}.webp')
            self._download(url, rel)

    def _feats(self, path):
        data = session.get(raw_base_url + path).json()
        feats = data.get('feat', []) + data.get('feats', [])
        for f in feats:
            name, src = f.get('name'), f.get('source')
            slug_u, slug_f = slugify_url(name), slugify_fname(name)
            url = f'{SITE_IMG_BASE}/feats/{src}/{slug_u}.webp'
            self._download(url, f'feats/{src}/{slug_f}.webp')

    def _objects(self, path):
        data = session.get(raw_base_url + path).json()
        objs = data.get('object', []) + data.get('objects', [])
        for o in objs:
            name, src = o.get('name'), o.get('source')
            slug_u, slug_f = slugify_url(name), slugify_fname(name)
            tok = f'{SITE_IMG_BASE}/objects/tokens/{src}/{slug_u}.webp'
            self._download(tok, f'objects/tokens/{src}/{slug_f}.webp')
            full = f'{SITE_IMG_BASE}/objects/{src}/{slug_u}.webp'
            self._download(full, f'objects/{src}/{slug_f}.webp')

    def _generic(self, path):
        data = session.get(raw_base_url + path).json()
        def walk(o):
            if isinstance(o, str) and o.startswith('/img/'):
                url = f'https://5e.tools{o}'
                rel = o.lstrip('/')
                self._download(url, rel)
            elif isinstance(o, dict):
                for v in o.values(): walk(v)
            elif isinstance(o, list):
                for v in o: walk(v)
        walk(data)

    def _download(self, url, rel_path):
        out = os.path.join(self.out_base, rel_path)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        
        # Vérifier si l'image existe déjà (skip si présente)
        if os.path.exists(out):
            self.logger.info(f'SKIP IMAGE (exists): {out}')
            return
            
        self.logger.info(f'DOWNLOAD IMG {url} -> {out}')
        try:
            # 1) Download
            r = session.get(url, stream=True)
            r.raise_for_status()
            with open(out, 'wb') as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            self.logger.info(f'SAVED IMG: {out}')

            # 2) Upload vers blob (overwrite=True pour mettre à jour si besoin)
            blob_name = f"images/{rel_path.replace(os.sep, '/')}"
            with open(out, 'rb') as data:
                image_container_client.upload_blob(
                    name=blob_name,
                    data=data,
                    overwrite=True
                )
            self.logger.info(f'UPLOADED IMG to blob://{image_container_client.container_name}/{blob_name}')

        except Exception as e:
            self.logger.error(f'Failed to download or upload {url}: {e}')


def main():
    p = argparse.ArgumentParser(description='Download D&D JSON and images to local + Azure Blob Storage')
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

if __name__=='__main__':
    main()