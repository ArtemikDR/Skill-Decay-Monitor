# =============================================================================
# Модуль: hh_analyzer.py
# Назначение: Анализатор вакансий от API hh.ru с классификацией перспективности.
#             Работает с JSON-ответом от API, а не с CSV.
# Входные данные: JSON-ответ от API hh.ru + skill_decay_results.csv
# Выходные данные: Словарь с классификацией, статистикой и списком вакансий.
# Автор: Мешков Артём
# Дата: 2026
# Версия: 3.0
# =============================================================================

import re
from html import unescape #превращает &amp; в  &
from src.analytics.skill_extractor import SkillExtractor #класс который ищет навыки по тегам йоу
import pandas as pd #для чтения csv
import numpy as np #для метрики и чиселок
from pathlib import Path #путь
from typing import Dict, List, Optional
from collections import Counter #считает сколько раз встретился навык


class HHAnalyzer: #класс который собирает статистику из ответа хх
    """Анализатор вакансий от API hh.ru с классификацией перспективности."""

    def __init__(self): #вызывается когда делаем HHAnalyzer(), self это наш объект
        """Инициализация: загружаем Decay Index из CSV."""
        project_root = Path(__file__).resolve().parent.parent.parent #берем путь этого файла и поднимаемся
        self.decay_path = project_root / 'data' / 'results' / 'skill_decay_results.csv' #собираем путь к америка фембоям

        self.decay_lookup = self._load_decay_index() #вызываем загрузку и кладем словарь навык-индекс в self
        self.skill_extractor = SkillExtractor() #создаем наш искатель навыков чтобы дальше искать в тексте

        print(f" HHAnalyzer готов. Загружено {len(self.decay_lookup)} навыков с Decay Index") #сколько навыков с индексом загрузилось

    def _load_decay_index(self) -> Dict[str, float]: #вернет словарь где ключ название навыка а значение число
        """Загружает Decay Index из skill_decay_results.csv."""
        if not self.decay_path.exists(): #если файла по этому пути нет
            print(f"⚠ Файл не найден: {self.decay_path}") #показываем какой файл не нашли
            return {} #возвращаем пустой словарь и выходим из функции

        try:
            df_decay = pd.read_csv(self.decay_path) #читаем csv
            if 'skill' in df_decay.columns and 'decay_index' in df_decay.columns:
                lookup = {} #пустой словарь под навыки и их индексы
                for _, row in df_decay.iterrows(): #перебираем строки
                    skill = str(row['skill']).strip().lower() #берем навык, делаем строкой, убираем пробелы по краям и регистр вниз
                    decay = float(row['decay_index'])
                    if np.isfinite(decay) and 0 <= decay <= 1:
                        lookup[skill] = decay
                print(f" Загружен Decay Index для {len(lookup)} навыков") #выводим сколько пар
                return lookup #возвращаем словарь
        except Exception as e:
            print(f"️ Ошибка загрузки decay results: {e}")

        return {}

    def _get_skill_decay(self, skill: str) -> Optional[float]: #на вход навык, обратно его индекс либо None если данных нет
        """Возвращает Decay Index для навыка."""
        skill_lower = skill.lower().strip() #делаем название таким же как ключи при загрузке

        if skill_lower in self.decay_lookup: #проверяем есть ли именно такой ключ в словаре
            return self.decay_lookup[skill_lower] #достаем индекс по названию

        return None

    def _extract_skills_from_json(self, vacancy: Dict) -> List[str]: #берем одну вакансию словарем, вернем список ее навыков
        """Собирает навыки из полей вакансии без повторов внутри одной записи."""
        skills = {}
        known_names = {name.casefold(): name for name in self.skill_extractor.skills_dict} # casefold убирает различия регистра

        def add_skill(name): #внутренняя функция чтобы одинаково добавлять навыки из разных полей
            if not isinstance(name, str) or not name.strip():
                return
            name = name.strip()
            name = known_names.get(name.casefold(), name) #берем написание из нашего справочника, если нет то оставляем name
            skills.setdefault(name.casefold(), name)

        for skill in vacancy.get('key_skills') or []:
            if isinstance(skill, dict):
                add_skill(skill.get('name')) #берем название

        snippet = vacancy.get('snippet') or {} #короткий текст вакансии
        if not isinstance(snippet, dict):
            snippet = {} #заменяем пустым чтобы дальше get не сломался
        parts = [vacancy.get('name'), vacancy.get('description'), #собираем название и описание
                 snippet.get('requirement'), snippet.get('responsibility')] #добавляем короткие требования и обязанности
        text = ' '.join(part for part in parts if isinstance(part, str)) #оставляем только строки и склеиваем их через пробел
        text = unescape(re.sub(r'<[^>]+>', ' ', text)) #заменяем html теги пробелом, потом расшифровываем html символы
        for skill in self.skill_extractor.extract_from_text(text): #нашим экстрактором ищем навыки
            add_skill(skill) #тоже добавляем с проверкой на повтор

        return list(skills.values()) #берем значения словаря и возвращаем обычный список навыков

    def analyze_profession_with_verdict(self, vacancies_data: Dict, query: str) -> Dict: #основной метод, на вход ответ хх и запрос, обратно вся статистика словарем
        """
        Анализирует JSON-ответ от API hh.ru и выдаёт вердикт о перспективности.

        Args:
            vacancies_data: JSON-ответ от API hh.ru
            query: Поисковый запрос

        Returns:
            Словарь с результатами анализа
        """
        if 'error' in vacancies_data: #если клиент уже вернул ошибку
            return vacancies_data.copy() #отдаем копию ошибки дальше и анализ заканчиваем

        items = vacancies_data.get('items', []) #берем вакансии
        total_found = vacancies_data.get('found', 0) #сколько всего нашел хх
        if not items: #если список пустой
            return {"error": f"По запросу '{query}' ничего не найдено"} #отдаем сообщение что по запросу ничего нет

        salaries = [] #числа зарплат чтобы потом посчитать медиану
        all_skills = [] #общий список навыков со всех вакансий
        processed_vacancies = [] #сюда соберем готовые строки для таблицы на сайте
        experience_counts = {} #словарь категория опыта: количество вакансий
        vacancies_with_skills = 0 #счетчик вакансий где нашли хотя бы один навык

        for vac in items: #перебираем вакансии по одной
            title = vac.get('name', 'Без названия') #берем название

            company = (vac.get('employer') or {}).get('name', 'Неизвестно') #берем имя работодателя

            city = (vac.get('area') or {}).get('name', 'Не указан') #город или регион

            salary_obj = vac.get('salary') #зарплаты с границами и валютой
            salary_from = None #пока нижняя граница неизвестна
            salary_to = None #верхняя тоже
            salary_display = '—'

            if salary_obj: #если объект зарплаты непустой
                salary_from = salary_obj.get('from') #нижняя граница вилки
                salary_to = salary_obj.get('to') #верхняя граница вилки
                currency = salary_obj.get('currency', 'RUR') #код валюты, если ключа нет берем RUR

                if salary_from and salary_to: #если обе границы есть
                    median = (salary_from + salary_to) / 2 #середина вилки
                    salaries.append(median) #кладем это число в список зарплат
                    salary_display = f"{int(salary_from):,} – {int(salary_to):,} {currency}" #делаем текст диапазона, int убирает дробь а :, разделяет разряды
                elif salary_from:
                    salaries.append(salary_from)
                    salary_display = f"от {int(salary_from):,} {currency}" #подпись от такой-то суммы
                elif salary_to:
                    salaries.append(salary_to)
                    salary_display = f"до {int(salary_to):,} {currency}" #подпись до такой-то суммы

            experience = (vac.get('experience') or {}).get('name', 'Не указан') #достаем название опыта
            experience_counts[experience] = experience_counts.get(experience, 0) + 1 #берем счетчик этой категории

            skills = self._extract_skills_from_json(vac) #вытаскиваем навыки нашей функцией выше
            all_skills.extend(skills) #добавляем каждый навык в общий список, extend раскрывает список
            if skills:
                vacancies_with_skills += 1

            url = vac.get('alternate_url', '') #обычная ссылка чтобы открыть вакансию на сайте хх

            metro = '—' #метро пока не указано
            address = vac.get('address') #берем объект адреса
            if address and address.get('metro'): #если есть адрес
                metro = address['metro'].get('station_name', '—') #берем название станции

            processed_vacancies.append({ #добавляем одну готовую вакансию словарем в список для таблицы
                'Должность': title,
                'Компания': company,
                'Город': city,
                'Зарплата': salary_display,
                'Опыт': experience,
                'Метро': metro,
                'Ссылка': url
            })

        median_salary = None #цикл по вакансиям закончился, медиана пока неизвестна
        if salaries:
            salaries.sort() #сортируем числа от меньшего к большему
            mid = len(salaries) // 2 #позиция середины
            if len(salaries) % 2 == 0:
                median_salary = (salaries[mid - 1] + salaries[mid]) / 2 #среднее двух центральных зарплат, индексы списка начинаются с 0
            else: #
                median_salary = salaries[mid] #берем одну центральную зарплату

        skills_counter = Counter(all_skills) #считаем сколько раз каждый навык попал в общий список
        top_skills_raw = skills_counter.most_common(10) #берем до 10 самых частых, получим пары навык и количество

        top_skills_with_decay = [] #сюда строки таблицы навыков с их индексами
        decay_values = [] #сюда только существующие индексы для расчета среднего

        for skill, count in top_skills_raw: #перебираем навык и его количество из топа
            decay = self._get_skill_decay(skill) #ищем его исторический индекс в загруженном словаре
            top_skills_with_decay.append({ #добавляем строку таблицы навыков
                'Навык': skill,
                'Упоминаний': count,
                'Доля вакансий, %': round(count / len(items) * 100, 1), #количество делим на все обработанные вакансии и в проценты
                'Decay Index': decay
            })
            if decay is not None:
                decay_values.append(decay)

        avg_decay = float(np.mean(decay_values)) if decay_values else None #обычное среднее индексов, каждый навык из топа с индексом вносит один равный вклад

        if avg_decay is None:
            classification = 'UNKNOWN'
        elif avg_decay < 0.3: #индекс меньше 0.3
            classification = 'RISING'
        elif avg_decay < 0.5: #от 0.3 включительно до 0.5
            classification = 'STABLE'
        elif avg_decay < 0.7: #от 0.5 включительно до 0.7
            classification = 'DECLINING'
        else: #остались значения от 0.7 включительно
            classification = 'OBSOLETE'

        return { #собираем весь результат одним словарем и возвращаем на сайт
            "query": query,
            "total_found": total_found,
            "median_salary": int(median_salary) if median_salary else None,
            "avg_decay_index": round(avg_decay, 3) if avg_decay is not None else None,
            "processed_count": len(items),
            "vacancies_with_skills": vacancies_with_skills,
            "skills_with_index": len(decay_values),
            "top_skills_count": len(top_skills_with_decay),
            "classification": classification,
            "top_skills": top_skills_with_decay,
            "experience_distribution": experience_counts,
            "vacancies": processed_vacancies
        }