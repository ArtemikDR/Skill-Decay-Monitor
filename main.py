import pandas as pd
from src.analytics.skill_extractor import SkillExtractor #импорт класса манипуляций с колонками
from src.analytics.metrics_calculator import MetricsCalculator #рассчитывание метрик импорт тоже


def main():
    print("~" * 60) #визуал
    print("SKILL DECAY MONITOR")
    print("~" * 60)
    print("\n Загрузка данных")
    column_names = [
        'work_year', 'experience_level', 'employment_type', 'job_title',
        'salary', 'salary_currency', 'salary_in_usd', 'employee_residence',
        'remote_ratio', 'company_location', 'company_size', 'experience_level_label',
        'employment_type_label', 'work_mode', 'salary_outlier_flag', 'label',
        'role_family', 'isco_group_hint'
    ]
    df = pd.read_csv('data/Initial data/ai_jobs_salaries_clean.csv', names=column_names)

    # Конвертация в числовые типы
    df['salary_in_usd'] = pd.to_numeric(df['salary_in_usd'], errors='coerce')
    df['work_year'] = pd.to_numeric(df['work_year'], errors='coerce')

    # Удаляем строки, где зарплата не конвертировалась (битые данные)
    df = df.dropna(subset=['salary_in_usd'])

    print(f"Загружено {len(df)} записей")
    print("\n Извлечение навыков")
    extractor = SkillExtractor() #компилирует выражения(теги) для поиска навыков в будущем
    df = extractor.process_dataframe(df) #меняем датасет и добавл колонку
    total_with_skills = df['extracted_skills'].apply(len).sum() #считаем сколько таких навыков
    print(f"Найдено {total_with_skills} упоминаний навыков")
    print("\n Расчет метрик устаревания")
    calculator = MetricsCalculator(df) #делаем копию по факту
    results = calculator.analyze_all_skills() #фильтрация расчет метрик и тд
    print(f"\nПроанализировано навыков: {len(results)}")
    print("\n Результаты анализа:")
    print("\nТоп-10 навыков по индексу устаревания (чем выше — тем хуже):")
    print(results.head(10).to_string(index=False)) #берем первые 10 самых плохих и убираем мишуру
    print("\n\nТоп-10 растущих навыков:")
    rising = results[results['classification'] == 'RISING'].head(10) #первые 10 с статусом растущие
    if len(rising) > 0:
        print(rising.to_string(index=False))
    else:
        print("Нет растущих навыков в данных")
    results.to_csv('data/skill_decay_results.csv', index=False) #сохраняем в виде csv и убираем мишуру также(номера строк)
    print(f"\nРезультаты сохранены в data/skill_decay_results.csv")


if __name__ == "__main__":
    main()