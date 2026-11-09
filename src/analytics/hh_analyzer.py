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
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
from collections import Counter


class HHAnalyzer:
    """Анализатор вакансий от API hh.ru с классификацией перспективности."""

    def __init__(self):
        """Инициализация: загружаем Decay Index из CSV."""
        project_root = Path(__file__).resolve().parent.parent.parent
        self.decay_path = project_root / 'data' / 'results' / 'skill_decay_results.csv'

        # Загружаем Decay Index для навыков
        self.decay_lookup = self._load_decay_index()

        print(f"✅ HHAnalyzer готов. Загружено {len(self.decay_lookup)} навыков с Decay Index")

    def _load_decay_index(self) -> Dict[str, float]:
        """Загружает Decay Index из skill_decay_results.csv."""
        if not self.decay_path.exists():
            print(f"⚠️ Файл не найден: {self.decay_path}")
            return {}

        try:
            df_decay = pd.read_csv(self.decay_path)
            if 'skill' in df_decay.columns and 'decay_index' in df_decay.columns:
                lookup = {}
                for _, row in df_decay.iterrows():
                    skill = str(row['skill']).strip().lower()
                    decay = float(row['decay_index'])
                    lookup[skill] = decay
                print(f"✅ Загружен Decay Index для {len(lookup)} навыков")
                return lookup
        except Exception as e:
            print(f"⚠️ Ошибка загрузки decay results: {e}")

        return {}

    def _get_skill_decay(self, skill: str) -> Optional[float]:
        """Возвращает Decay Index для навыка."""
        skill_lower = skill.lower().strip()

        # Прямое совпадение
        if skill_lower in self.decay_lookup:
            return self.decay_lookup[skill_lower]

        # Частичное совпадение
        for key, value in self.decay_lookup.items():
            if skill_lower in key or key in skill_lower:
                return value

        return None

    def _extract_skills_from_json(self, vacancy: Dict) -> List[str]:
        """Извлекает навыки из JSON вакансии."""
        skills = []

        # Из поля key_skills (если есть)
        key_skills = vacancy.get('key_skills') or []
        for skill in key_skills:
            skill_name = skill.get('name', '') if skill else ''
            if skill_name:
                skills.append(skill_name)

        # Из описания (snippet) — с полной проверкой на None
        snippet = vacancy.get('snippet')
        if snippet and isinstance(snippet, dict):
            requirement = snippet.get('requirement') or ''
            responsibility = snippet.get('responsibility') or ''
            # Можно использовать для будущего NLP-анализа
            # description_text = requirement + " " + responsibility

        return skills

    def analyze_profession_with_verdict(self, vacancies_data: Dict, query: str) -> Dict:
        """
        Анализирует JSON-ответ от API hh.ru и выдаёт вердикт о перспективности.

        Args:
            vacancies_data: JSON-ответ от API hh.ru
            query: Поисковый запрос

        Returns:
            Словарь с результатами анализа
        """
        items = vacancies_data.get('items', [])
        total_found = vacancies_data.get('found', 0)

        if not items:
            return {"error": f"По запросу '{query}' ничего не найдено"}

        # 1. Базовая статистика
        salaries = []
        all_skills = []
        processed_vacancies = []
        experience_counts = {}

        for vac in items:
            # Название
            title = vac.get('name', 'Без названия')

            # Компания
            company = vac.get('employer', {}).get('name', 'Неизвестно')

            # Город
            city = vac.get('area', {}).get('name', 'Не указан')

            # Зарплата
            salary_obj = vac.get('salary')
            salary_from = None
            salary_to = None
            salary_display = '—'

            if salary_obj:
                salary_from = salary_obj.get('from')
                salary_to = salary_obj.get('to')
                currency = salary_obj.get('currency', 'RUR')

                if salary_from and salary_to:
                    median = (salary_from + salary_to) / 2
                    salaries.append(median)
                    salary_display = f"{int(salary_from):,} – {int(salary_to):,} {currency}"
                elif salary_from:
                    salaries.append(salary_from)
                    salary_display = f"от {int(salary_from):,} {currency}"
                elif salary_to:
                    salaries.append(salary_to)
                    salary_display = f"до {int(salary_to):,} {currency}"

            # Опыт
            experience = vac.get('experience', {}).get('name', 'Не указан')
            experience_counts[experience] = experience_counts.get(experience, 0) + 1

            # Навыки
            skills = self._extract_skills_from_json(vac)
            all_skills.extend(skills)

            # Ссылка
            url = vac.get('alternate_url', '')

            # Метро
            metro = '—'
            address = vac.get('address')
            if address and address.get('metro'):
                metro = address['metro'].get('station_name', '—')

            processed_vacancies.append({
                'Должность': title,
                'Компания': company,
                'Город': city,
                'Зарплата': salary_display,
                'Опыт': experience,
                'Метро': metro,
                'Ссылка': url
            })

        # 2. Медианная зарплата
        median_salary = None
        if salaries:
            salaries.sort()
            mid = len(salaries) // 2
            if len(salaries) % 2 == 0:
                median_salary = (salaries[mid - 1] + salaries[mid]) / 2
            else:
                median_salary = salaries[mid]

        # 3. Топ навыков с Decay Index
        skills_counter = Counter(all_skills)
        top_skills_raw = skills_counter.most_common(10)

        top_skills_with_decay = []
        decay_values = []

        for skill, count in top_skills_raw:
            decay = self._get_skill_decay(skill)
            top_skills_with_decay.append({
                'Навык': skill,
                'Упоминаний': count,
                'Decay Index': decay
            })
            if decay is not None:
                decay_values.append(decay)

        # 4. Средний Decay Index
        avg_decay = np.mean(decay_values) if decay_values else None

        # 5. Вердикт
        if avg_decay is None:
            classification = 'UNKNOWN'
        elif avg_decay < 0.3:
            classification = 'RISING'
        elif avg_decay < 0.5:
            classification = 'STABLE'
        elif avg_decay < 0.7:
            classification = 'DECLINING'
        else:
            classification = 'OBSOLETE'

        return {
            "query": query,
            "total_found": total_found,
            "median_salary": int(median_salary) if median_salary else None,
            "avg_decay_index": round(avg_decay, 3) if avg_decay else None,
            "classification": classification,
            "top_skills": top_skills_with_decay,
            "experience_distribution": experience_counts,
            "vacancies": processed_vacancies
        }