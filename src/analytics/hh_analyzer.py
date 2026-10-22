# =============================================================================
# Модуль: hh_analyzer.py
# Назначение: Анализатор вакансий с hh.ru с классификацией перспективности
#             на основе Decay Index навыков из американского датасета.
# Входные данные: hh_vacancies_cleaned.csv + skill_decay_results.csv
# Выходные данные: DataFrame с классификацией и статистикой по запросу.
# Автор: Мешков Артём
# Дата: 2026
# Версия: 0.3.0
# =============================================================================


import re
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
from collections import Counter

from src.analytics.skill_extractor import SkillExtractor


class HHAnalyzer:
    """Анализатор вакансий с hh.ru с классификацией перспективности."""

    def __init__(self):
        """Инициализация: загружаем данные и создаём self.df."""
        project_root = Path(__file__).resolve().parent.parent.parent

        # Пути к файлам
        self.csv_path = project_root / 'data' / 'Initial data' / 'hh_vacancies_cleaned.csv'
        self.decay_path = project_root / 'data' / 'results' / 'skill_decay_results.csv'

        self.extractor = SkillExtractor()

        # 1. Загружаем Decay Index для навыков
        self.decay_lookup = self._load_decay_index()

        # 2. ЗАГРУЖАЕМ CSV — это ключевая строка, без неё self.df не существует
        self.df = self._load_and_prepare()

        print(f"✅ HHAnalyzer готов. Строк в датасете: {len(self.df)}")

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

    def _load_and_prepare(self) -> pd.DataFrame:
        """Загружает CSV и подготавливает данные."""
        if not self.csv_path.exists():
            print(f"⚠️ Файл не найден: {self.csv_path}")
            return pd.DataFrame()

        df = pd.read_csv(self.csv_path)
        print(f" Загружено строк: {len(df)}")

        # Нормализация опыта (на случай если там ещё текст)
        df['experience'] = df['experience'].apply(self._normalize_experience)

        # Обработка зарплаты
        if 'salary' in df.columns:
            df['salary'] = pd.to_numeric(df['salary'], errors='coerce')
        else:
            df['salary'] = None

        # Извлечение навыков из description
        df['extracted_skills'] = df['description'].apply(
            lambda x: self.extractor.extract_from_text(str(x)) if pd.notna(x) else []
        )

        return df

    def _normalize_experience(self, exp) -> str:
        """Приводит опыт к формату '3-6', '0', '6+'."""
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

    def analyze_profession_with_verdict(self, query: str) -> Dict:
        """Анализирует профессию и выдаёт вердикт о перспективности."""
        if self.df.empty:
            return {"error": "Данные hh.ru не загружены"}

        query_lower = query.lower()

        # Поиск по названию и описанию
        mask_title = self.df['job_title'].str.lower().str.contains(query_lower, na=False)
        mask_desc = self.df['description'].str.lower().str.contains(query_lower, na=False)
        mask_skills = self.df['extracted_skills'].apply(
            lambda skills: any(query_lower in str(s).lower() for s in skills)
            if isinstance(skills, list) else False
        )

        filtered = self.df[mask_title | mask_desc | mask_skills]

        if filtered.empty:
            return {"error": f"По запросу '{query}' ничего не найдено"}

        # 1. Базовая статистика
        salary_data = filtered[filtered['salary'].notna()]['salary']
        median_salary = int(salary_data.median()) if not salary_data.empty else None

        # 2. Извлекаем все навыки
        all_skills = []
        for skills in filtered['extracted_skills']:
            if isinstance(skills, list):
                all_skills.extend(skills)

        skills_counter = Counter(all_skills)
        top_skills_raw = skills_counter.most_common(10)

        # 3. Для каждого топ-навыка находим Decay Index
        top_skills_with_decay = []
        decay_values = []

        for skill, count in top_skills_raw:
            decay = self._get_skill_decay(skill)
            top_skills_with_decay.append({
                'skill': skill,
                'count': count,
                'decay_index': decay
            })
            if decay is not None:
                decay_values.append(decay)

        # 4. Считаем средний Decay Index
        avg_decay = np.mean(decay_values) if decay_values else None

        # 5. Определяем вердикт
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

        # 6. Распределение по опыту
        exp_count = filtered['experience'].value_counts().dropna()

        # 7. Список вакансий
        display_cols = ['job_title', 'company', 'experience', 'salary', 'city']
        available_cols = [c for c in display_cols if c in filtered.columns]
        vacancies = filtered[available_cols].head(20).to_dict('records')

        return {
            "query": query,
            "total_found": len(filtered),
            "median_salary": median_salary,
            "avg_decay_index": round(avg_decay, 3) if avg_decay else None,
            "classification": classification,
            "top_skills": top_skills_with_decay,
            "experience_distribution": exp_count.to_dict(),
            "vacancies": vacancies
        }

    def get_top_skills(self, n: int = 15) -> pd.Series:
        """Возвращает топ-N навыков по всему датасету."""
        all_skills = []
        for skills in self.df['extracted_skills']:
            if isinstance(skills, list):
                all_skills.extend(skills)
        return pd.Series(all_skills).value_counts().head(n)