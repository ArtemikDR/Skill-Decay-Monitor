# =============================================================================
# Модуль: hh_analyzer.py
# Назначение: Анализатор свежего среза вакансий российского рынка (hh.ru).
#             Загружает CSV, нормализует опыт и зарплаты, извлекает навыки
#             и классифицирует вакансии по перспективности на основе
#             среднего Decay Index их навыков (из американского датасета).
# Входные данные: data/Initial data/hh_vacancies_cleaned.csv
# Выходные данные: DataFrame с классификацией и статистикой по запросу.
# Автор: Мешков Артём | Дата: 2026 | Версия: 0.3.0
# =============================================================================

import re
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional

from src.analytics.skill_extractor import SkillExtractor


class HHAnalyzer:
    """Анализатор вакансий с hh.ru с классификацией по перспективности."""

    def __init__(self, csv_path: Optional[str] = None,
                 us_decay_data: Optional[pd.DataFrame] = None):
        if csv_path is None:
            csv_path = Path(__file__).resolve().parent.parent.parent / \
                       'data' / 'Initial data' / 'hh_vacancies_cleaned.csv'
        self.csv_path = Path(csv_path)
        self.extractor = SkillExtractor()

        # Данные об устаревании навыков из американского датасета
        # Ожидаем DataFrame с колонками: skill, decay_index, classification
        self.us_decay_data = us_decay_data
        self._decay_lookup = self._build_decay_lookup()

        self.df = self._load_and_prepare()

    def _build_decay_lookup(self) -> Dict[str, Dict]:
        """Строит словарь {навык: {decay_index, classification}}."""
        if self.us_decay_data is None or self.us_decay_data.empty:
            return {}

        lookup = {}
        for _, row in self.us_decay_data.iterrows():
            skill = str(row.get('skill', '')).strip()
            if skill:
                lookup[skill.lower()] = {
                    'decay_index': float(row.get('decay_index', 0.5)),
                    'classification': str(row.get('classification', 'STABLE'))
                }
        return lookup

    def classify_vacancy(self, skills: List[str]) -> Dict:
        """
        Классифицирует вакансию по среднему Decay Index её навыков.
        Возвращает словарь с classification и avg_decay_index.
        """
        if not skills or not self._decay_lookup:
            return {
                'classification': 'UNKNOWN',
                'avg_decay_index': None,
                'matched_skills': []
            }

        decay_values = []
        matched = []
        for skill in skills:
            key = skill.lower()
            if key in self._decay_lookup:
                info = self._decay_lookup[key]
                decay_values.append(info['decay_index'])
                matched.append(skill)

        if not decay_values:
            return {
                'classification': 'UNKNOWN',
                'avg_decay_index': None,
                'matched_skills': []
            }

        avg_di = sum(decay_values) / len(decay_values)

        # Классификация по среднему Decay Index
        if avg_di < 0.3:
            cls = 'RISING'
        elif avg_di < 0.5:
            cls = 'STABLE'
        elif avg_di < 0.7:
            cls = 'DECLINING'
        else:
            cls = 'OBSOLETE'

        return {
            'classification': cls,
            'avg_decay_index': round(avg_di, 2),
            'matched_skills': matched
        }

    def _load_and_prepare(self) -> pd.DataFrame:
        """Загружает CSV, извлекает навыки и классифицирует вакансии."""
        if not self.csv_path.exists():
            print(f"⚠️ Файл не найден: {self.csv_path}")
            return pd.DataFrame()

        df = pd.read_csv(self.csv_path)
        print(f" Загружено строк: {len(df)}")

        # Нормализация опыта
        df['experience'] = df['experience'].apply(self._normalize_experience)

        # Обработка зарплаты
        df['salary'] = pd.to_numeric(df['salary'], errors='coerce')
        if 'salary_min' in df.columns and 'salary_max' in df.columns:
            df['salary_min'] = pd.to_numeric(df['salary_min'], errors='coerce')
            df['salary_max'] = pd.to_numeric(df['salary_max'], errors='coerce')
            mask = df['salary'].isna() & df['salary_min'].notna() & df['salary_max'].notna()
            df.loc[mask, 'salary'] = (df.loc[mask, 'salary_min'] + df.loc[mask, 'salary_max']) / 2

        # Извлечение навыков
        if 'skills' not in df.columns or df['skills'].isna().all():
            df['skills'] = ''

        df['extracted_skills'] = df.apply(
            lambda row: self._get_skills(row), axis=1
        )

        # Классификация вакансий по перспективности
        df['classification'] = df['extracted_skills'].apply(
            lambda skills: self.classify_vacancy(skills)['classification']
            if isinstance(skills, list) else 'UNKNOWN'
        )
        df['avg_decay_index'] = df['extracted_skills'].apply(
            lambda skills: self.classify_vacancy(skills)['avg_decay_index']
            if isinstance(skills, list) else None
        )

        return df

    def _normalize_experience(self, exp) -> str:
        if pd.isna(exp):
            return None
        exp = str(exp).strip()
        if 'Без опыта' in exp or exp == '0':
            return '0'
        m = re.search(r'(\d+)\s*-\s*(\d+)', exp)
        if m:
            return f"{m.group(1)}-{m.group(2)}"
        if 'более 6' in exp or exp == '6+':
            return '6+'
        m = re.search(r'от\s+(\d+)', exp)
        if m:
            return f"{m.group(1)}+"
        if re.match(r'^\d+[-+]?\d*$', exp):
            return exp
        return None

    def _get_skills(self, row) -> List[str]:
        if pd.notna(row.get('skills')) and str(row['skills']).strip():
            skills_str = str(row['skills']).lower()
            found = []
            for skill in self.extractor.skills_dict.keys():
                if skill.lower() in skills_str:
                    found.append(skill)
            if found:
                return found
        desc = str(row.get('description', ''))
        return self.extractor.extract_from_text(desc)

    def search(self, query: str) -> Dict:
        if self.df.empty:
            return {"error": "Данные hh.ru не загружены"}

        query_lower = query.lower()

        mask_title = self.df['job_title'].str.lower().str.contains(query_lower, na=False)
        mask_desc = self.df['description'].str.lower().str.contains(query_lower, na=False)
        mask_skills = self.df['extracted_skills'].apply(
            lambda skills: any(query_lower in str(s).lower() for s in skills)
            if isinstance(skills, list) else False
        )

        filtered = self.df[mask_title | mask_desc | mask_skills]

        if filtered.empty:
            return {"error": f"По запросу '{query}' ничего не найдено"}

        salary_data = filtered[filtered['salary'].notna()]['salary']
        median_salary = int(salary_data.median()) if not salary_data.empty else None

        all_skills = []
        for skills in filtered['extracted_skills']:
            if isinstance(skills, list):
                all_skills.extend(skills)
        skills_count = pd.Series(all_skills).value_counts().head(10)

        exp_count = filtered['experience'].value_counts().dropna()

        # Распределение по классификации
        cls_count = filtered['classification'].value_counts().dropna()

        return {
            "query": query,
            "total_found": len(filtered),
            "median_salary_rub": median_salary,
            "top_skills": skills_count.to_dict(),
            "experience_distribution": exp_count.to_dict(),
            "classification_distribution": cls_count.to_dict(),
            "vacancies": filtered[[
                'job_title', 'company', 'experience', 'salary',
                'schedule', 'city', 'classification', 'avg_decay_index'
            ]].to_dict('records')
        }

    def get_top_skills(self, n: int = 15) -> pd.Series:
        all_skills = []
        for skills in self.df['extracted_skills']:
            if isinstance(skills, list):
                all_skills.extend(skills)
        return pd.Series(all_skills).value_counts().head(n)