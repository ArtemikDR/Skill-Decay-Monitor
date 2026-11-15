"""
Модуль hh_api_client.py — клиент для отправки запросов к API hh.ru.
"""
import os
import math #для округления
import time #отсчет паузы после запрпоса
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime #преобразует дату из HTTP-заголовка в объект Python.

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
        self.base_url = "https://api.hh.ru"#сновной адрес апи
        self.retry_at = 0.0 #позже содержит время после повторной отпр запроса


        self.token = os.environ.get("HH_ACCESS_TOKEN", getattr(local_config, "HH_ACCESS_TOKEN", "")).strip()#получает токен из окружения,если нет то из файла конфига,иначе ниче пусто,
        email = os.environ.get(
            "USER_AGENT_EMAIL", getattr(local_config, "USER_AGENT_EMAIL", "")
        ).strip()#тоже самое но с почтой
        user_agent = "SkillDecayMonitor/0.4.0" #версия для заголовка
        if email:
            user_agent += f" ({email})" #+почта
        self.headers = {"User-Agent": user_agent}
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}" #добавляет заголовок авторизации. Слово Bearer обозначает способ передачи токена.

    def search_vacancies(self, query: str, area: str = "113", per_page: int = 20) -> Dict: #
        """
        Ищет вакансии по запросу.
        :param query: Текст поиска (например, "Python разработчик")
        :param area: ID региона (113 = Россия)
        :param per_page: Количество вакансий на странице (макс. 100)
        """
        url = f"{self.base_url}/vacancies" #формирует адрес
        params = {
            "text": query,
            "area": area,
            "per_page": per_page,
            "page": 0,
            "only_with_salary": True
        }

        remaining = math.ceil(self.retry_at - time.monotonic()) #вычисление оконч паузы,первая функ округляет вверх
        if remaining > 0: #проверяет скок сек осталось
            return self._rate_limit_error(remaining)

        try: #ошибки сетевые сервера
            response = requests.get(url, headers=self.headers, params=params, timeout=(5, 15))#отправка гет запроса оп адресу с заголовком и параметром ,тайм аут в 5 сек и ожид в 15
        except requests.exceptions.Timeout:#прев времени
            return {"error": "hh.ru не ответил вовремя. Попробуйте позже.", "error_code": "timeout"}
        except requests.exceptions.RequestException:#ошибки бибилиотеки
            return {"error": "Не удалось подключиться к hh.ru. Проверьте соединение и повторите поиск.",
                    "error_code": "connection"}

        if response.status_code == 429: #если слишком частые запросы
            delay = self._retry_delay(response.headers.get("Retry-After")) #передает методу вычмслиения задержки
            self.retry_at = time.monotonic() + delay
            return self._rate_limit_error(delay) #возвр огр
        if response.status_code == 401:#авт не удалась
            return {"error": "hh.ru отклонил авторизацию. Проверьте токен доступа.", "error_code": "unauthorized"}
        if response.status_code == 403: #огр доступа
            return {"error": "hh.ru ограничил доступ к запросу. Проверьте настройки доступа; может потребоваться проверка на сайте hh.ru.",
                    "error_code": "forbidden"}
        if response.status_code >= 500: #всо не наши ошибки
            return {"error": "На стороне hh.ru произошёл сбой. Повторите поиск позже.", "error_code": "server"}
        if response.status_code != 200: #все ост ошибки
            return {"error": f"hh.ru отклонил запрос (код {response.status_code}). Проверьте запрос и повторите поиск.",
                    "error_code": "http_error"}

        try:
            data = response.json() #здесь получается словарь со списком вакансий.
        except ValueError:
            return {"error": "hh.ru вернул нечитаемый ответ. Повторите поиск позже.", "error_code": "invalid_response"}
        if (not isinstance(data, dict) or not isinstance(data.get("items"), list)
                or not all(isinstance(item, dict) for item in data["items"])):
            return {"error": "Ответ hh.ru не содержит ожидаемого списка вакансий.", "error_code": "invalid_response"}
        return data
#объявляет следующий метод статическим. Ему доступны переданные аргументы, а объект self ему не требуется.
    @staticmethod
    def _retry_delay(value) -> int: #метод, принимающий содержимое Retry-After и возвращающий целое число секунд.
        if value:
            try:
                seconds = float(value)#чтения ответа
                if math.isfinite(seconds) and seconds > 0:
                    return max(1, math.ceil(seconds)) #округляет и возвр мин 1 сек
            except (ValueError, TypeError):
                try:
                    retry_date = parsedate_to_datetime(value) #пытается прочитать заголовок как дату. Retry-After может задавать конкретное время следующего запроса.
                    if retry_date.tzinfo is None:
                        retry_date = retry_date.replace(tzinfo=timezone.utc) #в таком случае присваивает ей пояс UTC. Здесь replace() задаёт пояс для существующего времени.
                    seconds = (retry_date - datetime.now(timezone.utc)).total_seconds()
                    if seconds > 0:
                        return max(1, math.ceil(seconds))
                except (ValueError, TypeError, OverflowError): #перехватывает ошибки чтения даты, неподходящего типа и выхода значения за допустимый диапазон.
                    pass
        return 60 #возвращает запасную паузу в 60 секунд, если подходящее значение получить не удалось

    @staticmethod
    def _rate_limit_error(seconds: int) -> Dict:
        return {"error": f"Слишком частые запросы к hh.ru. Повторите поиск через {seconds} сек.",
                "error_code": "rate_limit", "retry_after": seconds}
