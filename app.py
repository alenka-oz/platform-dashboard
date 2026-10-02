import streamlit as st
import pandas as pd
import plotly.express as px
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
# ВШИТАЯ ССЫЛКА НА ДАННЫЕ
# ============================================================
DEFAULT_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTZo-jTlBdgD75RfNHsz8YOz4L_dFIq4m7SFvAUWu45SKqw2aHRRiwCWjR1pQhx67LLFKEdsNqqWM-A/pub?output=csv"

# ============================================================
# ФУНКЦИЯ ПАРСИНГА ДАТЫ
# ============================================================
def parse_date(val):
    """Парсит даты: 28/09/26 (ДД/ММ/ГГ) и 9/28/26 (ММ/ДД/ГГ)."""
    val = str(val).strip()
    if val in ["nan", "NaT", "", "None", "Операционный день", "login", "площадка"]:
        return pd.NaT
    
    parts = val.replace(".", "/").split("/")
    if len(parts) != 3:
        return pd.NaT
    
    try:
        a, b, c = int(parts[0]), int(parts[1]), int(parts[2])
    except:
        return pd.NaT
    
    year = 2000 + c if c < 100 else c
    
    if a > 12:
        day, month = a, b
    elif b > 12:
        month, day = a, b
    else:
        day, month = a, b
    
    try:
        return pd.Timestamp(year=year, month=month, day=day)
    except:
        return pd.NaT

# ============================================================
# ФУНКЦИЯ ОЧИСТКИ ЧИСЕЛ
# ============================================================
def clean_number(val):
    """Очищает строку от форматирования и конвертирует в число."""
    if pd.isna(val):
        return float('nan')
    
    s = str(val).strip()
    
    if s in ["", "nan", "None", "—", "-", "Сумма", "Производ"]:
        return float('nan')
    
    s = s.replace(" ", "")
    s = s.replace(",", ".")
    
    try:
        return float(s)
    except:
        return float('nan')

# ============================================================
# ФУНКЦИЯ ЗАГРУЗКИ ДАННЫХ (БЕЗ ОГРАНИЧЕНИЙ)
# ============================================================
@st.cache_data(ttl=300)
def load_data(url):
    """Загружает ВСЕ данные из CSV без ограничений."""
    try:
        # Загружаем ВСЕ строки без ограничений
        df = pd.read_csv(url, encoding='utf-8', dtype=str)  # dtype=str чтобы не терять данные
        
        # ОТЛАДКА: показываем сколько строк загружено
        st.sidebar.markdown("### 📊 Статистика загрузки")
        st.sidebar.write(f"**Всего строк в CSV:** {len(df)}")
        st.sidebar.write(f"**Колонки:** {list(df.columns)}")
        
        # Берём первые 5 колонок и переименовываем
        if len(df.columns) >= 5:
            df = df.iloc[:, :5].copy()
            df.columns = ["date", "login", "sum", "production", "platform"]
        else:
            st.error(f"Недостаточно колонок: {len(df.columns)}")
            return None, None
        
        # Парсим даты
        df["date"] = df["date"].apply(parse_date)
        
        # Фильтруем только строки с валидной датой
        df_before = len(df)
        df = df.dropna(subset=["date"])
        df_after = len(df)
        st.sidebar.write(f"**Строк с валидной датой:** {df_after} из {df_before}")
        
        # Очищаем числа
        df["sum"] = df["sum"].apply(clean_number)
        df["production"] = df["production"].apply(clean_number)
        
        # Нормализуем площадки
        df["platform"] = df["platform"].astype(str).str.strip()
        df = df[df["platform"] != "nan"]
        
        st.sidebar.write(f"**Уникальных площадок:** {df['platform'].nunique()}")
        st.sidebar.write(f"**Список площадок:** {sorted(df['platform'].unique())}")
        
        # Агрегация: один сотрудник + одна дата + одна площадка
        df_agg = df.groupby(["date", "login", "platform"], as_index=False).agg(
            sum=("sum", "sum"),
            production=("production", lambda x: x.dropna().mean() if len(x.dropna()) > 0 else 0)
        ).copy()
        
        st.sidebar.success(f"✅ Загружено {len(df_agg)} записей после агрегации")
        st.sidebar.write(f"**Общая сумма:** {df_agg['sum'].sum():,.2f} ₽")
        st.sidebar.write(f"**Средний производ:** {df_agg['production'].mean():.3f}")
        
        return df, df_agg
    except Exception as e:
        st.error(f"Ошибка: {e}")
        import traceback
        st.code(traceback.format_exc())
        return None, None

# ============================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================
df_raw, df_agg = load_data(DEFAULT_CSV_URL)

if df_raw is None or df_agg is None:
    st.error("Не удалось загрузить данные")
    st.stop()

# ============================================================
# БОКОВАЯ ПАНЕЛЬ: ФИЛЬТРЫ
# ============================================================
st.sidebar.header("📅 Фильтры")

min_date = df_agg["date"].min()
max_date = df_agg["date"].max()

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

if st.session_state.period == "day":
    default_start, default_end = max_date, max_date
elif st.session_state.period == "week":
    default_start = max_date - timedelta(days=6)
    default_end = max_date
else:
    default_start, default_end = min_date, max_date

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

all_platforms = sorted(df_agg["platform"].unique())
selected_platforms = st.sidebar.multiselect(
    "🏢 Площадка:",
    options=all_platforms,
    default=all_platforms
)

all_logins = sorted(df_agg["login"].unique())
search_login = st.sidebar.text_input("🔎 Поиск сотрудника:", "")
if search_login:
    filtered_logins = [l for l in all_logins if search_login.lower() in l.lower()]
else:
    filtered_logins = all_logins

selected_logins = st.sidebar.multiselect(
    "👤 Сотрудник:",
    options=filtered_logins,
    default=filtered_logins
)

df_filtered = df_agg[
    (df_agg["date"] >= pd.to_datetime(start_date)) &
    (df_agg["date"] <= pd.to_datetime(end_date)) &
    (df_agg["platform"].isin(selected_platforms)) &
    (df_agg["login"].isin(selected_logins))
].copy()

st.sidebar.success(f"✅ Записей после фильтрации: {len(df_filtered)}")

# ============================================================
# БЛОК 1: KPI КАРТОЧКИ
# ============================================================
st.subheader("📌 Общие показатели")

col1, col2, col3, col4 = st.columns(4)

total_sum = df_filtered["sum"].sum()
avg_production = df_filtered["production"].mean()
total_employees = df_filtered["login"].nunique()
total_records = len(df_filtered)

col1.metric("💰 Общая сумма", f"{total_sum:,.0f} ₽")
col2.metric("📈 Средний производ", f"{avg_production:.3f}")
col3.metric(" Сотрудников", total_employees)
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
st.subheader("📅 Динамика среднего производства по дням")

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
# БЛОК 5: SCATTER PLOT
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
# БЛОК 6: ТОП-10
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
st.caption("Дашборд обновляется автоматически при изменении данных в Google Таблице (кэш 5 минут).")
