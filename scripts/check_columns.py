import pandas as pd
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
csv_path = project_root / 'data' / 'Initial data' / 'hh_vacancies_cleaned.csv'

print(f"Читаем файл: {csv_path}")
df = pd.read_csv(csv_path, nrows=3)

print(f"\nНайдено колонок: {len(df.columns)}")
print("\nСписок колонок:")
for i, col in enumerate(df.columns):
    print(f"  {i+1}. '{col}'  (тип: {df[col].dtype})")

print(f"\nПервые 2 строки:")
print(df.head(2).to_string())