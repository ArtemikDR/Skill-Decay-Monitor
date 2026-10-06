import re
import pandas as pd
from typing import List, Dict, Set


class SkillExtractor:

    def __init__(self):
        # словарь с работами, \b это границы слова чтобы код не искал одно внутри другого, \ это обработка спец символов а r значит чтобы питон их игнорил а как ровного пацана обработал
        self.skills_dict = {
            # Языки программирования
            "Python": r"\bpython\b",
            "R": r"\br\b|\blanguage r\b",
            "Java": r"\bjava\b",
            "C++": r"\bc\+\+\b",
            "SQL": r"\bsql\b",
            "Scala": r"\bscala\b",

            # ML / AI фреймворки
            "TensorFlow": r"\btensorflow\b",
            "PyTorch": r"\bpytorch\b|\btorch\b",
            "Scikit-learn": r"\bscikit-learn\b|\bsklearn\b",
            "Keras": r"\bkeras\b",
            "Hugging Face": r"\bhugging\s*face\b|\btransformers\b",
            "LangChain": r"\blangchain\b",
            "OpenAI": r"\bopenai\b|\bgpt\b",

            # Data Engineering & Big Data
            "Spark": r"\bspark\b|\bapache\s*spark\b",
            "Hadoop": r"\bhadoop\b",
            "Kafka": r"\bkafka\b",
            "Airflow": r"\bairflow\b",
            "Snowflake": r"\bsnowflake\b",

            # Cloud & DevOps
            "AWS": r"\baws\b|\bamazon\s*web\s*services\b",
            "GCP": r"\bgcp\b|\bgoogle\s*cloud\b",
            "Azure": r"\bazure\b",
            "Docker": r"\bdocker\b",
            "Kubernetes": r"\bkubernetes\b|\bk8s\b",

            # BI & Визуализация
            "Tableau": r"\btableau\b",
            "Power BI": r"\bpower\s*bi\b",
            "Excel": r"\bexcel\b",

            # Специализированные области
            "NLP": r"\bnlp\b|\bnatural\s*language\s*processing\b",
            "Computer Vision": r"\bcomputer\s*vision\b|\bcv\b",
            "MLOps": r"\bmlops\b",
            "Deep Learning": r"\bdeep\s*learning\b",
        }

        # компилируем выражения с высокой скоростью
        self.compiled_patterns = {
            skill: re.compile(pattern, re.IGNORECASE) #компилируем,игнорируя регистр
            for skill, pattern in self.skills_dict.items() #перебираем ключи и значения словаря выше
        }

    def extract_from_text(self, text: str) -> List[str]: #принимает строку и вернет навыки уже
        if not isinstance(text, str): #если поступит не текст и не строка обработаем ошибку
            return []

        found_skills = [] #создания списка с найденными навыками
        for skill, pattern in self.compiled_patterns.items(): #берем ттже самое
            if pattern.search(text): #ищем совпадение паттерна
                found_skills.append(skill) #добавляем в список
        return found_skills

    def process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame: #на вход идет датасет и вернет новый с проффесиями
        df = df.copy() #копируем во избежания неурядиц
        df['search_text'] = df['job_title'].fillna('') + ' ' + df['label'].fillna('') #объеденяем название и метку чепез пробел дабы создать  временную новую колоночку
        df['extracted_skills'] = df['search_text'].apply(self.extract_from_text) #делаем новую колонку с окончательными рабоатми из временной новой колонки и применяем к ним нашу функцию обработки
        df.drop(columns=['search_text'], inplace=True) #удаляем временную колнку,а изменения применим к изначальрой inplace=True
        return df #возвращаем дятясет фембойчик