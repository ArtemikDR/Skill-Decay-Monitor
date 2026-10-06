# dashboard/app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Настройка страницы
st.set_page_config(page_title="Skill Decay Monitor", layout="wide")

st.title("📉 Skill Decay Monitor")
st.markdown("Аналитическая панель устаревания и роста навыков на рынке AI/Data")


# 1. Загрузка данных
@st.cache_data
def load_data():
    return pd.read_csv('data/skill_decay_results.csv')

df = load_data()

# Боковая панель с фильтрами
st.sidebar.header("Фильтры")
classification_filter = st.sidebar.multiselect(
    "Выберите категорию навыков:",
    options=df['classification'].unique(),
    default=df['classification'].unique()
)

# Фильтрация DataFrame
df_filtered = df[df['classification'].isin(classification_filter)]

# 2. Основные метрики (KPI)
col1, col2, col3, col4 = st.columns(4)
col1.metric("Всего навыков", len(df))
col2.metric("Растущих (RISING)", len(df[df['classification'] == 'RISING']))
col3.metric("Устаревающих (OBSOLETE)", len(df[df['classification'] == 'OBSOLETE']))
col4.metric("Средний Decay Index", f"{df['decay_index'].mean():.2f}")

st.markdown("---")

# 3. Графики
tab1, tab2 = st.tabs(["📊 Рейтинг навыков", "📈 Корреляция метрик"])

with tab1:
    st.subheader("Топ-15 навыков по индексу устаревания (Decay Index)")
    # Сортируем и берем топ-15
    top_n = df_filtered.nlargest(15, 'decay_index')

    fig_bar = px.bar(
        top_n,
        x='decay_index',
        y='skill',
        orientation='h',
        color='classification',
        color_discrete_map={'OBSOLETE': 'red', 'DECLINING': 'orange', 'STABLE': 'blue', 'RISING': 'green'},
        title="Чем выше бар, тем быстрее навык устаревает"
    )
    fig_bar.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig_bar, use_container_width=True)

with tab2:
    st.subheader("Рост зарплаты (SGR) vs Изменение спроса (DV)")
    # Scatter plot: по осям SGR и DV, размер точки - Decay Index
    fig_scatter = px.scatter(
        df_filtered,
        x='salary_growth_rate',
        y='demand_velocity',
        size='decay_index',
        color='classification',
        hover_name='skill',
        title="Каждый круг — это навык. Чем правее и выше — тем лучше.",
        labels={'salary_growth_rate': 'Рост зарплаты (%)', 'demand_velocity': 'Рост спроса (x раз)'}
    )
    # Добавляем линию "нулевого роста"
    fig_scatter.add_hline(y=1.0, line_dash="dash", line_color="gray")
    fig_scatter.add_vline(x=0.0, line_dash="dash", line_color="gray")
    st.plotly_chart(fig_scatter, use_container_width=True)

# 4. Таблица с деталями
st.subheader("Детальные данные")
st.dataframe(
    df_filtered.sort_values('decay_index', ascending=False),
    use_container_width=True,
    hide_index=True
)