import os
import requests
from typing import Optional


INFOAUTO_BASE_URL = "https://demo.api.infoauto.com.ar/cars"
#INFOAUTO_USER = os.getenv("INFOAUTO_USER")
#INFOAUTO_PASSWORD = os.getenv("INFOAUTO_PASSWORD")

INFOAUTO_USER = "agustintabarcache74@gmail.com"
INFOAUTO_PASSWORD = "agustin.API2025"

class InfoAutoClient:
    def __init__(self):
        self.access_token = None
        self.refresh_token = None

    def login(self):
        url = f"{INFOAUTO_BASE_URL}/auth/login"
        resp = requests.post(url, auth=(INFOAUTO_USER, INFOAUTO_PASSWORD))
        resp.raise_for_status()
        data = resp.json()
        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token")
        return self.access_token is not None

    def refresh(self):
        url = f"{INFOAUTO_BASE_URL}/auth/refresh"
        headers = {"Authorization": f"Bearer {self.refresh_token}"}
        resp = requests.post(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        self.access_token = data.get("access_token")
        return self.access_token is not None

    def get_headers(self):
        if not self.access_token:
            self.login()
        return {"Authorization": f"Bearer {self.access_token}"}

    def search(self, query: str):
        url = f"{INFOAUTO_BASE_URL}/pub/search"
        headers = self.get_headers()
        params = {"q": query}
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 401 and self.refresh_token:
            self.refresh()
            headers = self.get_headers()
            resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_brands(self):
        url = f"{INFOAUTO_BASE_URL}/pub/brands"
        headers = self.get_headers()
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def get_models_by_brand(self, brand_id):
        url = f"{INFOAUTO_BASE_URL}/pub/brands/{brand_id}/models/"
        headers = self.get_headers()
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def get_models_details(self, codia):
        url = f"{INFOAUTO_BASE_URL}/pub/models/{codia}"
        headers = self.get_headers()
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def get_all_brands(self):
        url = f"{INFOAUTO_BASE_URL}/pub/brands/download"
        headers = self.get_headers()
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()