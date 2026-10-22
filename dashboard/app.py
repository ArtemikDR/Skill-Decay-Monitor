# =============================================================================
# Модуль: app.py
# Назначение: Интерактивный веб-дашборд Skill Decay Monitor.
#             Две вкладки: американский рынок (2020-2026) и российский (hh.ru).
# Вкладки:
#     1. Данные по датасету за американский рынок (2020-2026)
#        — поиск навыка, график динамики, вердикт.
#     2. Анализ профессий с hh.ru
#        — поиск профессии, статистика, топ навыков, список вакансий.
# Зависимости:
#     streamlit, pandas, plotly,
#     src.analytics.skill_extractor,
#     src.analytics.metrics_calculator,
#     src.analytics.hh_analyzer.
# Автор: Оуджи буда
# Дата: 2026
# Версия: 2.0
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
    "🇷 Анализ профессий с hh.ru"
])

# ============================================================
# ВКЛАДКА 1: АМЕРИКАНСКИЙ РЫНОК
# ============================================================
with tab_us:
    st.header("Американский рынок IT (2020–2026)")


    @st.cache_data
    def load_us_data():
        """Загружает и обрабатывает американский датасет."""
        if not US_DATASET.exists():
            st.error(f"Файл не найден: {US_DATASET}")
            return pd.DataFrame()

        column_names = [
            'work_year', 'experience_level', 'employment_type', 'job_title',
            'salary', 'salary_currency', 'salary_in_usd', 'employee_residence',
            'remote_ratio', 'company_location', 'company_size',
            'experience_level_label', 'employment_type_label', 'work_mode',
            'salary_outlier_flag', 'label', 'role_family', 'isco_group_hint'
        ]
        df = pd.read_csv(US_DATASET, names=column_names, low_memory=False)
        df['salary_in_usd'] = pd.to_numeric(df['salary_in_usd'], errors='coerce')
        df['work_year'] = pd.to_numeric(df['work_year'], errors='coerce')
        df = df.dropna(subset=['salary_in_usd'])

        # Извлекаем навыки
        extractor = SkillExtractor()
        df = extractor.process_dataframe(df)

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

# ============================================================
# ВКЛАДКА 2: РОССИЙСКИЙ РЫНОК (hh.ru)
# ============================================================
with tab_ru:
    st.header("🇷 Российский рынок IT (hh.ru, актуальные данные)")


    @st.cache_resource
    def load_ru_analyzer():
        """Загружает анализатор hh.ru."""
        return HHAnalyzer()


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

        # Поиск профессии
        query_ru = st.text_input(
            "Введите профессию или навык:",
            placeholder="Python разработчик, Data Scientist, DevOps, 1C, Flutter..."
        )

        if st.button(" Анализировать профессию", type="primary") and query_ru:
            with st.spinner(f"Анализируем '{query_ru}' на hh.ru..."):
                result = hh.analyze_profession_with_verdict(query_ru)

            if "error" in result:
                st.error(result["error"])
            else:
                # === ВЕРДИКТ ===
                st.subheader(f"Результаты анализа: «{result['query']}»")

                cls = result['classification']
                labels = {
                    'RISING': '🟢 Перспективная (RISING)',
                    'STABLE': '🔵 Стабильная (STABLE)',
                    'DECLINING': '🟠 Угасающая (DECLINING)',
                    'OBSOLETE': '🔴 Устаревшая (OBSOLETE)',
                    'UNKNOWN': '⚪ Не определено (недостаточно данных)'
                }

                # Большая карточка с вердиктом
                st.markdown(f"### {labels.get(cls, cls)}")
                if result['avg_decay_index'] is not None:
                    st.metric("Средний Decay Index", f"{result['avg_decay_index']:.3f}")
                st.metric("Найдено вакансий", result['total_found'])
                st.metric("Медианная зарплата",
                          f"{result['median_salary']:,} ₽"
                          if result['median_salary'] else "не указана")

                st.markdown("---")

                # === ТОП НАВЫКОВ С DECAY INDEX ===
                if result['top_skills']:
                    st.subheader("📊 Топ навыков в профессии")

                    # Создаём DataFrame для таблицы
                    skills_df = pd.DataFrame(result['top_skills'])
                    skills_df.columns = ['Навык', 'Упоминаний', 'Decay Index']


                    # Форматируем Decay Index
                    def format_decay(val):
                        if val is None:
                            return 'N/A'
                        if val < 0.3:
                            return f"🟢 {val:.3f}"
                        elif val < 0.5:
                            return f"🔵 {val:.3f}"
                        elif val < 0.7:
                            return f"🟠 {val:.3f}"
                        else:
                            return f" {val:.3f}"


                    skills_df['Decay Index'] = skills_df['Decay Index'].apply(format_decay)

                    st.dataframe(skills_df, use_container_width=True, hide_index=True)

                    # График топ навыков
                    fig_skills = go.Figure(data=[go.Bar(
                        x=skills_df['Упоминаний'].values,
                        y=skills_df['Навык'].values,
                        orientation='h',
                        marker_color='royalblue'
                    )])
                    fig_skills.update_layout(
                        title="Частота упоминания навыков в вакансиях",
                        xaxis_title="Количество упоминаний",
                        height=400
                    )
                    st.plotly_chart(fig_skills, use_container_width=True)

                # === РАСПРЕДЕЛЕНИЕ ПО ОПЫТУ ===
                if result['experience_distribution']:
                    st.subheader("📈 Требуемый опыт работы")
                    fig_exp = go.Figure(data=[go.Pie(
                        labels=list(result['experience_distribution'].keys()),
                        values=list(result['experience_distribution'].values())
                    )])
                    fig_exp.update_layout(
                        title="Распределение вакансий по опыту",
                        height=350
                    )
                    st.plotly_chart(fig_exp, use_container_width=True)

                # === СПИСОК ВАКАНСИЙ ===
                st.subheader("💼 Актуальные вакансии")
                if result['vacancies']:
                    df_vac = pd.DataFrame(result['vacancies'])
                    # Форматируем зарплату
                    if 'salary' in df_vac.columns:
                        df_vac['salary'] = df_vac['salary'].apply(
                            lambda x: f"{int(x):,} ₽" if pd.notna(x) else "—"
                        )
                    st.dataframe(df_vac, use_container_width=True, hide_index=True)

        # === ОБЩИЙ ТОП НАВЫКОВ ПО ВСЕМУ ДАТАСЕТУ ===
        with st.expander("📊 Топ навыков по всему рынку hh.ru", expanded=False):
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