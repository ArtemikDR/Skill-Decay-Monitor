"""
Модуль hh_api_client.py — клиент для отправки запросов к API hh.ru.
"""
import os

import requests

try:
    import config as local_config
except ModuleNotFoundError as exc:
    if exc.name != "config":
        raise
    local_config = None
from typing import Dict


class HHApiClient:
    def __init__(self):
        self.base_url = "https://api.hh.ru"


        self.token = os.environ.get("HH_ACCESS_TOKEN", getattr(local_config, "HH_ACCESS_TOKEN", "")).strip()
        email = os.environ.get(
            "USER_AGENT_EMAIL", getattr(local_config, "USER_AGENT_EMAIL", "")
        ).strip()
        user_agent = "SkillDecayMonitor/0.4.0"
        if email:
            user_agent += f" ({email})"
        self.headers = {"User-Agent": user_agent}
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    def search_vacancies(self, query: str, area: str = "113", per_page: int = 20) -> Dict:
        """
        Ищет вакансии по запросу.
        :param query: Текст поиска (например, "Python разработчик")
        :param area: ID региона (113 = Россия)
        :param per_page: Количество вакансий на странице (макс. 100)
        """
        url = f"{self.base_url}/vacancies"
        params = {
            "text": query,
            "area": area,
            "per_page": per_page,
            "page": 0,
            "only_with_salary": True  # Показываем только вакансии с зарплатой
        }

        response = requests.get(url, headers=self.headers, params=params)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 403:
            print("❌ Ошибка 403: Проверьте User-Agent (должна быть реальная почта в скобках) или срок действия токена.")
            return {"items": [], "found": 0}
        else:
            print(f"❌ Ошибка API hh.ru: {response.status_code} - {response.text}")
            return {"items": [], "found": 0}