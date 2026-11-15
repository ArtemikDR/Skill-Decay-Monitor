"""
Модуль hh_api_client.py — клиент для отправки запросов к API hh.ru.
"""
import os
import math
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

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
        self.retry_at = 0.0


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
            "only_with_salary": True
        }

        remaining = math.ceil(self.retry_at - time.monotonic())
        if remaining > 0:
            return self._rate_limit_error(remaining)

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=(5, 15))
        except requests.exceptions.Timeout:
            return {"error": "hh.ru не ответил вовремя. Попробуйте позже.", "error_code": "timeout"}
        except requests.exceptions.RequestException:
            return {"error": "Не удалось подключиться к hh.ru. Проверьте соединение и повторите поиск.",
                    "error_code": "connection"}

        if response.status_code == 429:
            delay = self._retry_delay(response.headers.get("Retry-After"))
            self.retry_at = time.monotonic() + delay
            return self._rate_limit_error(delay)
        if response.status_code == 401:
            return {"error": "hh.ru отклонил авторизацию. Проверьте токен доступа.", "error_code": "unauthorized"}
        if response.status_code == 403:
            return {"error": "hh.ru ограничил доступ к запросу. Проверьте настройки доступа; может потребоваться проверка на сайте hh.ru.",
                    "error_code": "forbidden"}
        if response.status_code >= 500:
            return {"error": "На стороне hh.ru произошёл сбой. Повторите поиск позже.", "error_code": "server"}
        if response.status_code != 200:
            return {"error": f"hh.ru отклонил запрос (код {response.status_code}). Проверьте запрос и повторите поиск.",
                    "error_code": "http_error"}

        try:
            data = response.json()
        except ValueError:
            return {"error": "hh.ru вернул нечитаемый ответ. Повторите поиск позже.", "error_code": "invalid_response"}
        if (not isinstance(data, dict) or not isinstance(data.get("items"), list)
                or not all(isinstance(item, dict) for item in data["items"])):
            return {"error": "Ответ hh.ru не содержит ожидаемого списка вакансий.", "error_code": "invalid_response"}
        return data

    @staticmethod
    def _retry_delay(value) -> int:
        if value:
            try:
                seconds = float(value)
                if math.isfinite(seconds) and seconds > 0:
                    return max(1, math.ceil(seconds))
            except (ValueError, TypeError):
                try:
                    retry_date = parsedate_to_datetime(value)
                    if retry_date.tzinfo is None:
                        retry_date = retry_date.replace(tzinfo=timezone.utc)
                    seconds = (retry_date - datetime.now(timezone.utc)).total_seconds()
                    if seconds > 0:
                        return max(1, math.ceil(seconds))
                except (ValueError, TypeError, OverflowError):
                    pass
        return 60

    @staticmethod
    def _rate_limit_error(seconds: int) -> Dict:
        return {"error": f"Слишком частые запросы к hh.ru. Повторите поиск через {seconds} сек.",
                "error_code": "rate_limit", "retry_after": seconds}
