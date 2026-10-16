# =============================================================================
# Модуль: app.py
# Назначение: Интерактивный веб-дашборд платформы Skill Decay Monitor.
#             Визуализирует данные двух рынков: исторический (США, 2020-2026)
#             и актуальный (РФ, hh.ru) с классификацией вакансий.
# Функционал: Поиск навыков, графики динамики зарплат, вердикты перспективности.
# Зависимости: streamlit, plotly, pandas, HHAnalyzer, MetricsCalculator
# Автор: Мешков Артём | Дата: 2026 | Версия: 0.3.0
# =============================================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

from src.analytics.skill_extractor import SkillExtractor
from src.analytics.metrics_calculator import MetricsCalculator
from src.analytics.hh_analyzer import HHAnalyzer

st.set_page_config(
    page_title="Skill Decay Monitor",
    layout="wide",
    page_icon="📉"
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
US_DATASET = PROJECT_ROOT / 'data' / 'Initial data' / 'ai_jobs_salaries_clean.csv'

st.title("📉 Skill Decay Monitor")
st.markdown("Аналитическая платформа устаревания и роста навыков")

# Две вкладки
tab_us, tab_ru = st.tabs([
    "🇺🇸 Данные по датасету за американский рынок (2020-2026)",
    "🇺 Анализ профессий с hh.ru"
])



with tab_us:
    st.header("Американский рынок IT (2020–2026)")

    @st.cache_data
    def load_us_data():
        column_names = [
            'work_year', 'experience_level', 'employment_type', 'job_title',
            'salary', 'salary_currency', 'salary_in_usd', 'employee_residence',
            'remote_ratio', 'company_location', 'company_size',
            'experience_level_label', 'employment_type_label', 'work_mode',
            'salary_outlier_flag', 'label', 'role_family', 'isco_group_hint'
        ]
        df = pd.read_csv(US_DATASET, names=column_names)
        df['salary_in_usd'] = pd.to_numeric(df['salary_in_usd'], errors='coerce')
        df['work_year'] = pd.to_numeric(df['work_year'], errors='coerce')
        df = df.dropna(subset=['salary_in_usd'])
        df = SkillExtractor().process_dataframe(df)
        return df

    df_us = load_us_data()

    if df_us.empty:
        st.error("Не удалось загрузить американский датасет")
    else:
        calc_us = MetricsCalculator(df_us)

        # KPI
        all_skills_us = set()
        for s in df_us['extracted_skills']:
            if isinstance(s, list):
                all_skills_us.update(s)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Всего вакансий", f"{len(df_us):,}")
        col2.metric("Уникальных навыков", len(all_skills_us))
        col3.metric("Период",
                     f"{int(df_us['work_year'].min())}–{int(df_us['work_year'].max())}")
        col4.metric("Медианная ЗП",
                     f"${int(df_us['salary_in_usd'].median()):,}")

        st.markdown("---")

        # Поиск навыка
        query_us = st.text_input(
            "Введите навык или профессию:",
            placeholder="Python, Hadoop, MLOps, Data Scientist..."
        )

        if query_us:
            matches = [s for s in sorted(all_skills_us)
                       if query_us.lower() in s.lower()]
            if matches:
                query_us = st.selectbox("Выберите из найденных:", matches)

        if st.button("Проанализировать (US)", type="primary") and query_us:
            history = calc_us.get_skill_history(query_us)

            if "error" in history:
                st.error(history["error"])
            else:
                cls = history["classification"]
                labels = {
                    "RISING": "🟢 Растущий",
                    "STABLE": "🔵 Стабильный",
                    "DECLINING": "🟠 Угасающий",
                    "OBSOLETE": "🔴 Устаревший"
                }

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Статус", labels.get(cls, cls))
                c2.metric("Рост зарплаты",
                          f"{history['salary_growth_rate']:.1f}%")
                c3.metric("Рост спроса",
                          f"{history['demand_velocity']:.2f}x")
                c4.metric("Decay Index",
                          f"{history['decay_index']:.2f}")

                # График
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=history["years"],
                    y=history["median_salaries"],
                    mode="lines+markers",
                    name="Зарплата, USD",
                    line=dict(color="royalblue", width=3),
                    yaxis="y1"
                ))
                fig.add_trace(go.Bar(
                    x=history["years"],
                    y=history["vacancy_counts"],
                    name="Кол-во вакансий",
                    marker_color="rgba(255,165,0,0.6)",
                    yaxis="y2"
                ))
                fig.update_layout(
                    title=f"Динамика навыка «{query_us}» (US)",
                    xaxis=dict(title="Год", dtick=1),
                    yaxis=dict(title="Зарплата, USD", side="left"),
                    yaxis2=dict(title="Кол-во вакансий",
                                side="right", overlaying="y"),
                    template="plotly_white",
                    height=450
                )
                st.plotly_chart(fig, use_container_width=True)

        # Общий рейтинг
        with st.expander("📊 Общий рейтинг навыков (US)", expanded=False):
            results_us = calc_us.analyze_all_skills()
            st.dataframe(
                results_us[[
                    'skill', 'decay_index', 'classification',
                    'salary_growth_rate', 'demand_velocity'
                ]].sort_values('decay_index', ascending=False),
                use_container_width=True,
                hide_index=True
            )

with tab_ru:
    st.header("Российский рынок IT (hh.ru, актуальные данные)")


    @st.cache_data
    def load_ru_analyzer():
        # Загружаем данные об устаревании навыков из американского датасета
        us_results_path = PROJECT_ROOT / 'data' / 'results' / 'skill_decay_results.csv'
        us_decay_data = None
        if us_results_path.exists():
            us_decay_data = pd.read_csv(us_results_path)
        return HHAnalyzer(us_decay_data=us_decay_data)


    hh = load_ru_analyzer()

    if hh.df.empty:
        st.error("Файл hh_vacancies_cleaned.csv не найден")
        st.info("Положите файл в data/Initial data/")
    else:
        # KPI
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Всего вакансий", len(hh.df))
        c2.metric("С указанием ЗП", hh.df['salary'].notna().sum())
        c3.metric("Медианная ЗП",
                  f"{int(hh.df['salary'].median()):,} ₽"
                  if hh.df['salary'].notna().any() else "—")
        c4.metric("Уникальных навыков", len(hh.get_top_skills(n=1000)))

        st.markdown("---")

        # Поиск
        query_ru = st.text_input(
            "Введите профессию или навык:",
            placeholder="Data Scientist, Python, DevOps, 1C, Flutter..."
        )

        if st.button("Найти (hh.ru)", type="primary") and query_ru:
            result = hh.search(query_ru)

            if "error" in result:
                st.error(result["error"])
            else:
                st.subheader(f"Результаты по запросу «{query_ru}»")

                sc1, sc2, sc3 = st.columns(3)
                sc1.metric("Найдено вакансий", result["total_found"])
                sc2.metric("Медианная зарплата",
                           f"{result['median_salary_rub']:,} ₽"
                           if result['median_salary_rub']
                           else "не указана")
                sc3.metric("Уникальных навыков", len(result["top_skills"]))

                # Распределение по классификации
                if result.get("classification_distribution"):
                    st.subheader("Перспективность найденных вакансий")
                    cls_labels = {
                        'RISING': '🟢 Растущие',
                        'STABLE': '🔵 Стабильные',
                        'DECLINING': '🟠 Угасающие',
                        'OBSOLETE': '🔴 Устаревшие',
                        'UNKNOWN': '⚪ Не определено'
                    }
                    cls_colors = {
                        'RISING': '#2ecc71',
                        'STABLE': '#3498db',
                        'DECLINING': '#e67e22',
                        'OBSOLETE': '#e74c3c',
                        'UNKNOWN': '#95a5a6'
                    }
                    fig_cls = go.Figure(data=[go.Pie(
                        labels=[cls_labels.get(k, k) for k in result["classification_distribution"].keys()],
                        values=list(result["classification_distribution"].values()),
                        marker_colors=[cls_colors.get(k, '#95a5a6')
                                       for k in result["classification_distribution"].keys()]
                    )])
                    fig_cls.update_layout(title="Распределение по перспективности", height=350)
                    st.plotly_chart(fig_cls, use_container_width=True)

                col_exp, col_sal = st.columns(2)
                with col_exp:
                    if result["experience_distribution"]:
                        fig_exp = go.Figure(data=[go.Pie(
                            labels=list(result["experience_distribution"].keys()),
                            values=list(result["experience_distribution"].values())
                        )])
                        fig_exp.update_layout(title="Распределение по опыту", height=350)
                        st.plotly_chart(fig_exp, use_container_width=True)

                with col_sal:
                    if result["top_skills"]:
                        fig_skills = go.Figure(data=[go.Bar(
                            x=list(result["top_skills"].values()),
                            y=list(result["top_skills"].keys()),
                            orientation='h',
                            marker_color='royalblue'
                        )])
                        fig_skills.update_layout(
                            title="Топ навыков в найденных вакансиях",
                            xaxis_title="Количество упоминаний",
                            height=350
                        )
                        st.plotly_chart(fig_skills, use_container_width=True)

                # Таблица вакансий с классификацией
                st.subheader("Список вакансий")
                if result["vacancies"]:
                    df_vac = pd.DataFrame(result["vacancies"])

                    # Добавляем эмодзи для классификации
                    cls_emoji = {
                        'RISING': '🟢 Растущая',
                        'STABLE': '🔵 Стабильная',
                        'DECLINING': '🟠 Угасающая',
                        'OBSOLETE': '🔴 Устаревшая',
                        'UNKNOWN': '⚪ Не определено'
                    }
                    if 'classification' in df_vac.columns:
                        df_vac['classification'] = df_vac['classification'].map(
                            lambda x: cls_emoji.get(x, x)
                        )

                    st.dataframe(
                        df_vac.head(50),
                        use_container_width=True,
                        hide_index=True
                    )

        # Общий топ навыков
        with st.expander("📊 Топ навыков по всему датасету hh.ru", expanded=False):
            top_skills = hh.get_top_skills(n=20)
            fig_top = go.Figure(data=[go.Bar(
                x=top_skills.values,
                y=top_skills.index,
                orientation='h',
                marker_color='orange'
            )])
            fig_top.update_layout(
                title="Топ-20 навыков на российском рынке",
                xaxis_title="Количество вакансий",
                height=500
            )
            st.plotly_chart(fig_top, use_container_width=True)