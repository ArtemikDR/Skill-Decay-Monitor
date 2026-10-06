import pandas as pd
import numpy as np
from typing import Dict, List


class MetricsCalculator:

    def __init__(self, df: pd.DataFrame): #принимает датасетс данными о работах семпаев(который мы сделали новый)
        self.df = df.copy() #чтобы исходняк не трогали создаем копию в селф(харм) (принцип иммутабельности)

    def calculate_salary_growth_rate(self, skill: str) -> Dict: #принимаем скилл а вернем словарь с метриками цыфрами для введнего навфка
        skill_data = self.df[self.df['extracted_skills'].apply(lambda x: skill in x)] #берем новую колонку и проверяем есть ли навык в списке и оставляем ток трушных

        if len(skill_data) == 0: #если ниче нет прям
            return {"error": "Навык не найден"}

        yearly_median = skill_data.groupby('work_year')['salary_in_usd'].median() #медиана заработка в долларах,группируем по годам работы и берем медиану из зарплаты тк среднее мб с вбросами
#индекс это год а значение это зарплата
        if len(yearly_median) < 2: #если меньше 2 лет информации наблюдения
            return {"error": "Недостаточно данных"}

        first_year = yearly_median.index[0] #первый и последний элементы списка по годам
        last_year = yearly_median.index[-1]

        first_value = yearly_median[first_year] #первый и последний зп списка по годам
        last_value = yearly_median[last_year]
#Формула Salary Growth Rate (SGR) — темп роста зарплаты в процентах
        sgr = ((last_value - first_value) / first_value) * 100 #кон - нач зарплата делить на начальную в процентах

        return {
            "skill": skill,
            "first_year": first_year,
            "last_year": last_year,
            "first_median": first_value,
            "last_median": last_value,
            "salary_growth_rate": round(sgr, 2) #округления до 2 знаков
        }

    def calculate_demand_velocity(self, skill: str) -> Dict: #на вход навык на выход слоавь спроса на навык
        skill_data = self.df[self.df['extracted_skills'].apply(lambda x: skill in x)] #оставляем только  нужное

        if len(skill_data) == 0: #тоже
            return {"error": "Навык не найден"}

        yearly_count = skill_data.groupby('work_year').size() #сортируем то что вышло по году и считаем сколько их по годам
#индекс год а значение кол-во вакансий
        if len(yearly_count) < 2: #не хватает ланных(тоже самое)
            return {"error": "Недостаточно данных"}

        first_year = yearly_count.index[0]
        last_year = yearly_count.index[-1]

        first_count = yearly_count[first_year]
        last_count = yearly_count[last_year]
#Формула Demand Velocity
        dv = last_count / first_count if first_count > 0 else 0 #защита,первое это сколько вакансий стало делить на сколько было

        return {
            "skill": skill,
            "first_year": first_year,
            "last_year": last_year,
            "first_count": first_count,
            "last_count": last_count,
            "demand_velocity": round(dv, 2) #словарь спроса
        }

    def calculate_decay_index(self, skill: str) -> Dict:
        sgr_data = self.calculate_salary_growth_rate(skill) #вызываем прошлые методы для словарей
        dv_data = self.calculate_demand_velocity(skill)

        if "error" in sgr_data or "error" in dv_data: #обр недостаточное кол-во данных
            return {"error": "Недостаточно данных для расчета"}
        sgr_norm = max(0, min(1, (sgr_data["salary_growth_rate"] + 50) / 100)) #нормализируем значние(из процентов) к 0-1 и образаем если не попадает в диапазон
        dv_norm = max(0, min(1, dv_data["demand_velocity"] / 5)) #тоже самое к 0-1
        decay_index = 1 - (sgr_norm * 0.6 + dv_norm * 0.4) #чем ниже эта переменная тем лучше  значит что навык жив

        return {
            "skill": skill,
            "salary_growth_rate": sgr_data["salary_growth_rate"],
            "demand_velocity": dv_data["demand_velocity"],
            "decay_index": round(decay_index, 2),
            "classification": self._classify_skill(decay_index, sgr_data["salary_growth_rate"]) #
        }

    def _classify_skill(self, decay_index: float, sgr: float) -> str: #принимает на вход индекс работы и темп роста зп
        if decay_index < 0.2 and sgr > 15:
            return "RISING"
        elif decay_index < 0.4:
            return "STABLE"
        elif decay_index < 0.7:
            return "DECLINING"
        else:
            return "OBSOLETE"

    def analyze_all_skills(self) -> pd.DataFrame: #анализирует все навыки и вернет датасет
        all_skills = set() #множество без дубликатов
        for skills_list in self.df['extracted_skills']:
            if isinstance(skills_list, list): #проверка на список
                all_skills.update(skills_list) #добавляем то чего нет

        results = []
        for skill in all_skills:
            metrics = self.calculate_decay_index(skill) #считем коэф для навыка
            if "error" not in metrics: #если без ошибок то добавляем
                results.append(metrics)

        return pd.DataFrame(results).sort_values('decay_index', ascending=False) #делаем из словаря таблицу и сортируем по убыванию