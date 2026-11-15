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
from html import unescape
from src.analytics.skill_extractor import SkillExtractor
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

        self.decay_lookup = self._load_decay_index()
        self.skill_extractor = SkillExtractor()

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
                    if np.isfinite(decay) and 0 <= decay <= 1:
                        lookup[skill] = decay
                print(f"✅ Загружен Decay Index для {len(lookup)} навыков")
                return lookup
        except Exception as e:
            print(f"⚠️ Ошибка загрузки decay results: {e}")

        return {}

    def _get_skill_decay(self, skill: str) -> Optional[float]:
        """Возвращает Decay Index для навыка."""
        skill_lower = skill.lower().strip()

        if skill_lower in self.decay_lookup:
            return self.decay_lookup[skill_lower]

        return None

    def _extract_skills_from_json(self, vacancy: Dict) -> List[str]:
        """Собирает навыки из полей вакансии без повторов внутри одной записи."""
        skills = {}
        known_names = {name.casefold(): name for name in self.skill_extractor.skills_dict}

        def add_skill(name):
            if not isinstance(name, str) or not name.strip():
                return
            name = name.strip()
            name = known_names.get(name.casefold(), name)
            skills.setdefault(name.casefold(), name)

        for skill in vacancy.get('key_skills') or []:
            if isinstance(skill, dict):
                add_skill(skill.get('name'))

        snippet = vacancy.get('snippet') or {}
        if not isinstance(snippet, dict):
            snippet = {}
        parts = [vacancy.get('name'), vacancy.get('description'),
                 snippet.get('requirement'), snippet.get('responsibility')]
        text = ' '.join(part for part in parts if isinstance(part, str))
        text = unescape(re.sub(r'<[^>]+>', ' ', text))
        for skill in self.skill_extractor.extract_from_text(text):
            add_skill(skill)

        return list(skills.values())

    def analyze_profession_with_verdict(self, vacancies_data: Dict, query: str) -> Dict:
        """
        Анализирует JSON-ответ от API hh.ru и выдаёт вердикт о перспективности.

        Args:
            vacancies_data: JSON-ответ от API hh.ru
            query: Поисковый запрос

        Returns:
            Словарь с результатами анализа
        """
        if 'error' in vacancies_data:
            return vacancies_data.copy()

        items = vacancies_data.get('items', [])
        total_found = vacancies_data.get('found', 0)

        if not items:
            return {"error": f"По запросу '{query}' ничего не найдено"}

        salaries = []
        all_skills = []
        processed_vacancies = []
        experience_counts = {}
        vacancies_with_skills = 0

        for vac in items:
            title = vac.get('name', 'Без названия')

            company = (vac.get('employer') or {}).get('name', 'Неизвестно')

            city = (vac.get('area') or {}).get('name', 'Не указан')

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

            experience = (vac.get('experience') or {}).get('name', 'Не указан')
            experience_counts[experience] = experience_counts.get(experience, 0) + 1

            skills = self._extract_skills_from_json(vac)
            all_skills.extend(skills)
            if skills:
                vacancies_with_skills += 1

            url = vac.get('alternate_url', '')

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

        median_salary = None
        if salaries:
            salaries.sort()
            mid = len(salaries) // 2
            if len(salaries) % 2 == 0:
                median_salary = (salaries[mid - 1] + salaries[mid]) / 2
            else:
                median_salary = salaries[mid]

        skills_counter = Counter(all_skills)
        top_skills_raw = skills_counter.most_common(10)

        top_skills_with_decay = []
        decay_values = []

        for skill, count in top_skills_raw:
            decay = self._get_skill_decay(skill)
            top_skills_with_decay.append({
                'Навык': skill,
                'Упоминаний': count,
                'Доля вакансий, %': round(count / len(items) * 100, 1),
                'Decay Index': decay
            })
            if decay is not None:
                decay_values.append(decay)

        avg_decay = float(np.mean(decay_values)) if decay_values else None

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