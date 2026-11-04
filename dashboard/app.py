import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

from src.analytics.skill_extractor import SkillExtractor
from src.analytics.metrics_calculator import MetricsCalculator
from src.parsers.hh_api_client import HHApiClient
from src.analytics.hh_analyzer import HHAnalyzer

# =============================================================================
# ПАЛИТРА ТЁМНОЙ ТЕМЫ "Cyber Green"
# =============================================================================
BG_COLOR_DARK = "#16251c"  # RGB(22, 37, 28) - тёмно-зелёный
CARD_COLOR_DARK = "#1a2f24"  # чуть светлее для карточек
TEXT_COLOR_DARK = "#e0f2f1"  # яркий белый для тёмной темы
ACCENT_CYAN = "#2dd4bf"  # неоново-бирюзовый (мягкий)
RISING_COLOR = "#34d399"  # зелёный
STABLE_COLOR = "#60a5fa"  # синий
DECLINING_COLOR = "#fbbf24"  # оранжевый
OBSOLETE_COLOR = "#f87171"  # красный

# =============================================================================
# ПАЛИТРА СВЕТЛОЙ ТЕМЫ
# =============================================================================
BG_COLOR_LIGHT = "#ffffff"
CARD_COLOR_LIGHT = "#f8f9fa"
TEXT_COLOR_LIGHT = "#212529"
ACCENT_BLUE_LIGHT = "#0d6efd"

# Инициализация состояния темы
if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'

# Определяем текущую тему
if st.session_state.theme == 'dark':
    BG_COLOR = BG_COLOR_DARK
    CARD_COLOR = CARD_COLOR_DARK
    TEXT_COLOR = TEXT_COLOR_DARK
    ACCENT_COLOR = ACCENT_CYAN
else:
    BG_COLOR = BG_COLOR_LIGHT
    CARD_COLOR = CARD_COLOR_LIGHT
    TEXT_COLOR = TEXT_COLOR_LIGHT
    ACCENT_COLOR = ACCENT_BLUE_LIGHT

st.set_page_config(
    page_title="Skill Decay Monitor",
    layout="wide",
    page_icon="📉"
)

# =============================================================================
# CSS СТИЛИ С ТЕМБЛЕРОМ И УЛУЧШЕНИЯМИ
# =============================================================================
st.markdown(f"""
<style>
    /* Основной фон */
    .stApp {{
        background-color: {BG_COLOR} !important;
        color: {TEXT_COLOR} !important;
        transition: all 0.3s ease;
    }}

    /* Скрываем header */
    header[data-testid="stHeader"] {{
        background-color: {BG_COLOR} !important;
    }}

    /* Тумблер темы */
    .theme-toggle {{
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        background: {CARD_COLOR};
        padding: 10px 20px;
        border-radius: 25px;
        border: 2px solid {ACCENT_COLOR};
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }}

    /* Кнопки */
    .stButton>button {{
        background-color: {ACCENT_COLOR};
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        font-size: 16px;
        transition: all 0.3s ease;
    }}
    .stButton>button:hover {{
        transform: scale(1.05);
        box-shadow: 0 0 20px {ACCENT_COLOR};
    }}

    /* Поисковая строка с RGB-анимацией */
    .stTextInput>div>div>input {{
        background-color: {CARD_COLOR};
        color: {TEXT_COLOR};
        border: 2px solid {ACCENT_COLOR};
        border-radius: 10px;
        padding: 12px;
        font-size: 16px;
        animation: rgb-border 3s infinite;
    }}

    @keyframes rgb-border {{
        0% {{ border-color: #34d399; box-shadow: 0 0 10px rgba(52, 211, 153, 0.5); }}
        33% {{ border-color: #2dd4bf; box-shadow: 0 0 10px rgba(45, 212, 191, 0.5); }}
        66% {{ border-color: #60a5fa; box-shadow: 0 0 10px rgba(96, 165, 250, 0.5); }}
        100% {{ border-color: #34d399; box-shadow: 0 0 10px rgba(52, 211, 153, 0.5); }}
    }}

    /* Метрики */
    .stMetric {{
        background-color: {CARD_COLOR};
        padding: 1.5rem;
        border-radius: 12px;
        border-left: 5px solid {ACCENT_COLOR};
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }}
    .stMetric label {{
        color: {TEXT_COLOR} !important;
        font-weight: 600;
    }}
    .stMetric div[data-testid="stMetricValue"] {{
        color: {ACCENT_COLOR} !important;
    }}

    /* Заголовки */
    h1, h2, h3, h4, h5, h6 {{
        color: {TEXT_COLOR} !important;
        font-weight: 700;
    }}

    /* Вкладки */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 10px;
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: {CARD_COLOR};
        color: {TEXT_COLOR};
        border-radius: 8px;
        padding: 12px 24px;
        font-weight: 600;
        border: 2px solid transparent;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {ACCENT_COLOR};
        color: white;
        border-color: {ACCENT_COLOR};
    }}

    /* Таблицы - НЕОНОВО-БИРЮЗОВЫЕ */
    .dataframe {{
        color: {TEXT_COLOR} !important;
        background-color: {CARD_COLOR} !important;
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 4px 15px rgba(45, 212, 191, 0.2);
    }}
    .dataframe th {{
        background-color: {ACCENT_COLOR} !important;
        color: white !important;
        font-weight: 700;
        padding: 12px;
        border: none;
    }}
    .dataframe td {{
        background-color: {CARD_COLOR} !important;
        color: {TEXT_COLOR} !important;
        padding: 10px;
        border-bottom: 1px solid rgba(45, 212, 191, 0.2);
    }}
    .dataframe tr:hover td {{
        background-color: rgba(45, 212, 191, 0.1) !important;
    }}

    /* Pie chart legend - делаем ярче */
    .legend text {{
        fill: {TEXT_COLOR} !important;
        font-size: 14px !important;
        font-weight: 600 !important;
    }}

    /* Expander */
    .streamlit-expanderHeader {{
        background-color: {CARD_COLOR};
        color: {TEXT_COLOR};
        border-radius: 8px;
        border: 1px solid {ACCENT_COLOR};
    }}

    /* Spinner */
    .stSpinner {{
        color: {ACCENT_COLOR};
    }}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# ТЕМБЛЕР ПЕРЕКЛЮЧЕНИЯ ТЕМ
# =============================================================================
col_toggle1, col_toggle2 = st.columns([10, 1])
with col_toggle2:
    theme_icon = "🌙" if st.session_state.theme == 'dark' else "☀️"
    if st.button(f"{theme_icon}", key="theme_toggle", help="Переключить тему"):
        st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'
        st.rerun()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
US_DATASET = PROJECT_ROOT / 'data' / 'Initial data' / 'ai_jobs_salaries_clean.csv'

st.title(" Skill Decay Monitor")
st.markdown("### Аналитическая платформа устаревания и роста навыков")

tab_us, tab_ru = st.tabs([
    "🇺🇸 Американский рынок (2020-2026)",
    "🇷🇺 Российский рынок (hh.ru API)"
])

# =============================================================================
# ВКЛАДКА 1: АМЕРИКАНСКИЙ РЫНОК
# =============================================================================
with tab_us:
    st.header("Американский рынок IT (2020–2026)")


    @st.cache_data
    def load_us_data():
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

        extractor = SkillExtractor()
        df = extractor.process_dataframe(df)

        return df


    df_us = load_us_data()

    if df_us.empty:
        st.error("Не удалось загрузить американский датасет")
    else:
        calc_us = MetricsCalculator(df_us)

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

        query_us = st.text_input(
            "Введите навык или профессию:",
            placeholder="Python, Hadoop, MLOps, Data Scientist..."
        )

        if query_us:
            matches = [s for s in sorted(all_skills_us)
                       if query_us.lower() in s.lower()]
            if matches:
                query_us = st.selectbox("Выберите из найденных:", matches)

        if st.button("🔍 Проанализировать (US)", type="primary") and query_us:
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

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=history["years"],
                    y=history["median_salaries"],
                    mode="lines+markers",
                    name="Зарплата, USD",
                    line=dict(color=ACCENT_COLOR, width=3),
                    marker=dict(size=10, color=ACCENT_COLOR),
                    yaxis="y1"
                ))
                fig.add_trace(go.Bar(
                    x=history["years"],
                    y=history["vacancy_counts"],
                    name="Кол-во вакансий",
                    marker_color="rgba(251, 191, 36, 0.6)",
                    yaxis="y2"
                ))
                fig.update_layout(
                    title=f"Динамика навыка «{query_us}» (US)",
                    xaxis=dict(title="Год", dtick=1, color=TEXT_COLOR),
                    yaxis=dict(title="Зарплата, USD", side="left", color=TEXT_COLOR),
                    yaxis2=dict(title="Кол-во вакансий",
                                side="right", overlaying="y", color=TEXT_COLOR),
                    template="plotly_dark" if st.session_state.theme == 'dark' else "plotly_white",
                    height=450,
                    paper_bgcolor=BG_COLOR,
                    plot_bgcolor=CARD_COLOR,
                    font=dict(color=TEXT_COLOR, size=12)
                )
                st.plotly_chart(fig, use_container_width=True)

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

# =============================================================================
# ВКЛАДКА 2: РОССИЙСКИЙ РЫНОК (hh.ru API)
# =============================================================================
with tab_ru:
    st.header("🇷🇺 Российский рынок IT (hh.ru API)")


    @st.cache_resource
    def load_ru_analyzer():
        return HHAnalyzer()


    @st.cache_resource
    def load_api_client():
        return HHApiClient()


    hh_analyzer = load_ru_analyzer()
    api_client = load_api_client()

    query_ru = st.text_input(
        "Введите профессию или навык:",
        placeholder="Python разработчик, Data Scientist, DevOps..."
    )

    if st.button("🔍 Анализировать профессию", type="primary") and query_ru:
        with st.spinner(f"Запрашиваем данные от hh.ru..."):
            vacancies_data = api_client.search_vacancies(query_ru, per_page=30)
            result = hh_analyzer.analyze_profession_with_verdict(vacancies_data, query_ru)

        if "error" in result:
            st.error(result["error"])
        else:
            st.subheader(f"Результаты анализа: «{result['query']}»")

            cls = result['classification']
            labels = {
                'RISING': '🟢 Перспективная (RISING)',
                'STABLE': '🔵 Стабильная (STABLE)',
                'DECLINING': '🟠 Угасающая (DECLINING)',
                'OBSOLETE': ' Устаревшая (OBSOLETE)',
                'UNKNOWN': '⚪ Не определено'
            }

            st.markdown(f"### {labels.get(cls, cls)}")

            if result['avg_decay_index'] is not None:
                st.metric("Средний Decay Index", f"{result['avg_decay_index']:.3f}")
            st.metric("Найдено вакансий", result['total_found'])
            st.metric("Медианная зарплата",
                      f"{result['median_salary']:,} ₽"
                      if result['median_salary'] else "не указана")

            st.markdown("---")

            if result['top_skills']:
                st.subheader("📊 Топ навыков в профессии")

                skills_df = pd.DataFrame(result['top_skills'])


                def format_decay(val):
                    if val is None:
                        return 'N/A'
                    if val < 0.3:
                        return f" {val:.3f}"
                    elif val < 0.5:
                        return f"🔵 {val:.3f}"
                    elif val < 0.7:
                        return f"🟠 {val:.3f}"
                    else:
                        return f"🔴 {val:.3f}"


                skills_df['Decay Index'] = skills_df['Decay Index'].apply(format_decay)

                st.dataframe(skills_df, use_container_width=True, hide_index=True)

                fig_skills = go.Figure(data=[go.Bar(
                    x=skills_df['Упоминаний'].values,
                    y=skills_df['Навык'].values,
                    orientation='h',
                    marker_color=ACCENT_COLOR
                )])
                fig_skills.update_layout(
                    title="Частота упоминания навыков в вакансиях",
                    xaxis_title="Количество упоминаний",
                    template="plotly_dark" if st.session_state.theme == 'dark' else "plotly_white",
                    height=400,
                    paper_bgcolor=BG_COLOR,
                    plot_bgcolor=CARD_COLOR,
                    font=dict(color=TEXT_COLOR, size=12)
                )
                st.plotly_chart(fig_skills, use_container_width=True)

            if result['experience_distribution']:
                st.subheader("📈 Требуемый опыт работы")
                fig_exp = go.Figure(data=[go.Pie(
                    labels=list(result['experience_distribution'].keys()),
                    values=list(result['experience_distribution'].values()),
                    marker=dict(colors=[RISING_COLOR, STABLE_COLOR, DECLINING_COLOR, OBSOLETE_COLOR]),
                    textfont=dict(color=TEXT_COLOR, size=14, weight='bold')
                )])
                fig_exp.update_layout(
                    title="Распределение вакансий по опыту",
                    template="plotly_dark" if st.session_state.theme == 'dark' else "plotly_white",
                    height=400,
                    paper_bgcolor=BG_COLOR,
                    plot_bgcolor=CARD_COLOR,
                    font=dict(color=TEXT_COLOR, size=14),
                    legend=dict(font=dict(color=TEXT_COLOR, size=12))
                )
                st.plotly_chart(fig_exp, use_container_width=True)

            st.subheader("💼 Актуальные вакансии")
            if result['vacancies']:
                df_vac = pd.DataFrame(result['vacancies'])
                df_vac['Ссылка'] = df_vac['Ссылка'].apply(
                    lambda x: f"[Открыть]({x})" if x else '—'
                )
                st.dataframe(df_vac, use_container_width=True, hide_index=True)