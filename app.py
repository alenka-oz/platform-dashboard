import streamlit as st
import pandas as pd
import plotly.express as px
import io
from datetime import timedelta

# ============================================================
# НАСТРОЙКА СТРАНИЦЫ
# ============================================================
st.set_page_config(
    page_title="Дашборд площадок",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Дашборд по площадкам и сотрудникам")
st.markdown("---")


# ============================================================
# ФУНКЦИЯ ЗАГРУЗКИ И ОЧИСТКИ ДАННЫХ
# ============================================================
@st.cache_data(ttl=300)
def load_and_clean_data(source_type, source_value):
    """Загружает и очищает данные из Excel или CSV."""
    try:
        if source_type == "Google Sheets (CSV-ссылка)":
            df = pd.read_csv(source_value)
        elif source_type == "Excel файл":
            df = pd.read_excel(io.BytesIO(source_value), engine='openpyxl')
        else:
            st.error("Неизвестный источник")
            return None, None

        # --- 1. Убираем строки-дубли шапок ---
        header_keywords = ["Операционный день", "login", "Сумма", "Производ", "площадка"]
        mask = df.iloc[:, 0].astype(str).str.contains(
            "|".join(header_keywords), case=False, na=False
        )
        df = df[~mask].copy()

        # --- 2. Нормализуем названия колонок ---
        df.columns = ["date", "login", "sum", "production", "platform"]

        # --- 3. Приводим даты к единому формату ---
        def parse_date(val):
            val = str(val).strip()
            if val in ["nan", "NaT", "", "None"]:
                return pd.NaT
            # Пробуем разные форматы
            for fmt in ["%d/%m/%y", "%m/%d/%y", "%Y-%m-%d", "%d.%m.%Y"]:
                try:
                    return pd.to_datetime(val, format=fmt)
                except:
                    continue
            try:
                return pd.to_datetime(val, dayfirst=True)
            except:
                return pd.NaT

        df["date"] = df["date"].apply(parse_date)
        df = df.dropna(subset=["date"])

        # --- 4. Приводим числа ---
        df["sum"] = pd.to_numeric(df["sum"], errors="coerce").fillna(0)
        df["production"] = pd.to_numeric(df["production"], errors="coerce")

        # --- 5. Нормализуем названия площадок ---
        df["platform"] = df["platform"].astype(str).str.strip()

        # --- 6. Агрегация: один сотрудник + одна дата + одна площадка = одна строка ---
        # Сумма суммируется, производ берётся первый (он одинаковый для всех строк сотрудника в день)
        df_agg = df.groupby(["date", "login", "platform"], as_index=False).agg(
            sum=("sum", "sum"),
            production=("production", "first")
        ).copy()

        return df, df_agg

    except Exception as e:
        st.error(f"Ошибка загрузки данных: {e}")
        return None, None


# ============================================================
# БОКОВАЯ ПАНЕЛЬ: ВЫБОР ИСТОЧНИКА ДАННЫХ
# ============================================================
st.sidebar.header("📥 Источник данных")

source_type = st.sidebar.radio(
    "Выберите источник:",
    ["Google Sheets (CSV-ссылка)", "Excel файл"],
    index=1
)

df_raw = None
df_agg = None

if source_type == "Google Sheets (CSV-ссылка)":
    st.sidebar.markdown("""
    **Как получить ссылку:**
    1. Откройте Google Таблицу
    2. Файл → Поделиться → Опубликовать в интернете
    3. Выберите формат **CSV**
    4. Скопируйте ссылку
    """)
    sheet_url = st.sidebar.text_input("Вставьте CSV-ссылку:")
    if sheet_url:
        df_raw, df_agg = load_and_clean_data(source_type, sheet_url)

elif source_type == "Excel файл":
    uploaded_file = st.sidebar.file_uploader(
        "Загрузите Excel файл",
        type=["xlsx", "xls"]
    )
    if uploaded_file:
        df_raw, df_agg = load_and_clean_data(source_type, uploaded_file)


# ============================================================
# ЕСЛИ ДАННЫЕ НЕ ЗАГРУЖЕНЫ
# ============================================================
if df_raw is None or df_agg is None:
    st.info("👈 Загрузите данные через боковую панель, чтобы увидеть дашборд.")
    st.stop()


# ============================================================
# БОКОВАЯ ПАНЕЛЬ: ФИЛЬТРЫ
# ============================================================
st.sidebar.markdown("---")
st.sidebar.header("📅 Фильтры")

min_date = df_agg["date"].min()
max_date = df_agg["date"].max()

# Кнопки быстрого выбора
st.sidebar.markdown("**Быстрый выбор:**")
col_b1, col_b2, col_b3 = st.sidebar.columns(3)

with col_b1:
    if st.button("День", use_container_width=True):
        st.session_state.period = "day"
with col_b2:
    if st.button("Неделя", use_container_width=True):
        st.session_state.period = "week"
with col_b3:
    if st.button("Всё время", use_container_width=True):
        st.session_state.period = "all"

if "period" not in st.session_state:
    st.session_state.period = "all"

# Вычисление дат
if st.session_state.period == "day":
    default_start, default_end = max_date, max_date
elif st.session_state.period == "week":
    default_start = max_date - timedelta(days=6)
    default_end = max_date
else:
    default_start, default_end = min_date, max_date

# Календарь
selected_dates = st.sidebar.date_input(
    "Диапазон дат:",
    value=(default_start, default_end),
    min_value=min_date,
    max_value=max_date,
    format="DD.MM.YYYY"
)

if len(selected_dates) == 2:
    start_date, end_date = selected_dates
else:
    start_date, end_date = min_date, max_date

# Фильтр по площадке
all_platforms = sorted(df_agg["platform"].unique())
selected_platforms = st.sidebar.multiselect(
    "🏢 Площадка:",
    options=all_platforms,
    default=all_platforms
)

# Фильтр по сотруднику
all_logins = sorted(df_agg["login"].unique())
search_login = st.sidebar.text_input("🔎 Поиск сотрудника:", "")
if search_login:
    filtered_logins = [l for l in all_logins if search_login.lower() in l.lower()]
else:
    filtered_logins = all_logins

selected_logins = st.sidebar.multiselect(
    "👤 Сотрудник:",
    options=filtered_logins,
    default=filtered_logins[:50]
)

# Применяем фильтры
df_filtered = df_agg[
    (df_agg["date"] >= pd.to_datetime(start_date)) &
    (df_agg["date"] <= pd.to_datetime(end_date)) &
    (df_agg["platform"].isin(selected_platforms)) &
    (df_agg["login"].isin(selected_logins))
].copy()

st.sidebar.success(f"✅ Записей: {len(df_filtered)}")


# ============================================================
# БЛОК 1: KPI КАРТОЧКИ
# ============================================================
st.subheader(" Общие показатели")

col1, col2, col3, col4 = st.columns(4)

total_sum = df_filtered["sum"].sum()
avg_production = df_filtered["production"].mean()
total_employees = df_filtered["login"].nunique()
total_records = len(df_filtered)

col1.metric("💰 Общая сумма", f"{total_sum:,.2f} ₽")
col2.metric("📈 Средний производ", f"{avg_production:.3f}")
col3.metric("👥 Сотрудников", total_employees)
col4.metric("📋 Записей", total_records)

st.markdown("---")


# ============================================================
# БЛОК 2: СРЕДНИЙ ПРОИЗВОД ПО ПЛОЩАДКАМ
# ============================================================
st.subheader("🏢 Средний производ по площадкам")

platform_stats = df_filtered.groupby("platform").agg(
    avg_production=("production", "mean"),
    total_sum=("sum", "sum"),
    employees=("login", "nunique")
).reset_index().sort_values("avg_production", ascending=True)

fig_platform = px.bar(
    platform_stats,
    x="avg_production",
    y="platform",
    orientation="h",
    color="platform",
    text="avg_production",
    title="Средний производ по площадкам",
    color_discrete_sequence=px.colors.qualitative.Set2
)
fig_platform.update_traces(texttemplate="%{text:.3f}", textposition="outside")
fig_platform.update_layout(showlegend=False, height=400)
st.plotly_chart(fig_platform, use_container_width=True)


# ============================================================
# БЛОК 3: ДИНАМИКА ПО ДНЯМ
# ============================================================
st.subheader(" Динамика среднего производства по дням")

daily_platform = df_filtered.groupby(["date", "platform"])["production"].mean().reset_index()

fig_daily = px.line(
    daily_platform,
    x="date",
    y="production",
    color="platform",
    markers=True,
    title="Средний производ по площадкам в разрезе дней",
    color_discrete_sequence=px.colors.qualitative.Bold
)
fig_daily.update_layout(height=450)
st.plotly_chart(fig_daily, use_container_width=True)


# ============================================================
# БЛОК 4: РАСПРЕДЕЛЕНИЕ СУММЫ И СОТРУДНИКОВ
# ============================================================
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("💵 Доля площадок в общей сумме")
    fig_pie = px.pie(
        platform_stats,
        values="total_sum",
        names="platform",
        title="Распределение суммы по площадкам",
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    fig_pie.update_traces(textinfo="percent+label")
    st.plotly_chart(fig_pie, use_container_width=True)

with col_right:
    st.subheader("👥 Количество сотрудников по площадкам")
    fig_bar_emp = px.bar(
        platform_stats,
        x="platform",
        y="employees",
        color="platform",
        text="employees",
        title="Сотрудников на площадке",
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    fig_bar_emp.update_traces(texttemplate="%{text}", textposition="outside")
    fig_bar_emp.update_layout(showlegend=False)
    st.plotly_chart(fig_bar_emp, use_container_width=True)


# ============================================================
# БЛОК 5: SCATTER PLOT — СУММА vs ПРОИЗВОД
# ============================================================
st.subheader("🎯 Эффективность сотрудников (Сумма vs Производ)")

employee_stats = df_filtered.groupby(["login", "platform"]).agg(
    total_sum=("sum", "sum"),
    avg_production=("production", "mean")
).reset_index()

fig_scatter = px.scatter(
    employee_stats,
    x="total_sum",
    y="avg_production",
    color="platform",
    hover_data=["login"],
    title="Каждый сотрудник — точка. Чем правее и выше — тем лучше",
    color_discrete_sequence=px.colors.qualitative.Set1
)
fig_scatter.update_layout(height=500)
st.plotly_chart(fig_scatter, use_container_width=True)


# ============================================================
# БЛОК 6: ТОП-10 СОТРУДНИКОВ
# ============================================================
col_top_sum, col_top_prod = st.columns(2)

with col_top_sum:
    st.subheader("🏆 Топ-10 по сумме")
    top_sum = employee_stats.nlargest(10, "total_sum")[["login", "platform", "total_sum"]]
    st.dataframe(top_sum, use_container_width=True, hide_index=True)

with col_top_prod:
    st.subheader(" Топ-10 по производству")
    top_prod = employee_stats.nlargest(10, "avg_production")[["login", "platform", "avg_production"]]
    st.dataframe(top_prod, use_container_width=True, hide_index=True)


# ============================================================
# БЛОК 7: ПОЛНАЯ ТАБЛИЦА
# ============================================================
st.markdown("---")
st.subheader("📋 Полная таблица данных")

with st.expander("Показать все данные"):
    display_df = df_filtered.sort_values(["date", "platform", "login"]).copy()
    display_df["date_str"] = display_df["date"].dt.strftime("%d.%m.%Y")
    display_df = display_df[["date_str", "login", "platform", "sum", "production"]]
    display_df.columns = ["Дата", "Login", "Площадка", "Сумма", "Производ"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    csv = display_df.to_csv(index=False, sep=";").encode("utf-8-sig")
    st.download_button(
        "⬇️ Скачать отфильтрованные данные (CSV)",
        data=csv,
        file_name="dashboard_export.csv",
        mime="text/csv"
    )


# ============================================================
# ФУТЕР
# ============================================================
st.markdown("---")
st.caption("Дашборд обновляется автоматически при изменении источника данных.")
