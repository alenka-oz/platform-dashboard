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
DEFAULT_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQwCe2ojZU0gGMQ3U1ob4YDxhZW16FTeuOUCSOEj7jCDyTb6TyVTm21wwrWE62MWgr50Bglz4Ixw3E8/pub?output=csv"

# ============================================================
# ФУНКЦИЯ ПАРСИНГА ДАТЫ
# ============================================================
def parse_date(val):
    """Парсит даты: 28/09/26 (ДД/ММ/ГГ), 9/28/26 (ММ/ДД/ГГ), 28.09.2026"""
    val = str(val).strip()
    if not val or val.lower() in ['nan', 'none', 'операционный день', 'login', 
                                    'сумма', 'производ', 'площадка', '']:
        return pd.NaT
    if val.startswith("---"):
        return pd.NaT
    
    try:
        # Формат с точками: 28.09.2026
        if "." in val:
            return pd.to_datetime(val, dayfirst=True)
        
        # Формат с косой чертой: 28/09/26 или 9/28/26
        if "/" in val:
            parts = val.split("/")
            if len(parts) == 3:
                a, b, c = int(parts[0]), int(parts[1]), int(parts[2])
                year = 2000 + c if c < 100 else c
                
                if a > 12:
                    # ДД/ММ/ГГ (например, 28/09/26)
                    return pd.Timestamp(year=year, month=b, day=a)
                elif b > 12:
                    # ММ/ДД/ГГ (например, 9/28/26)
                    return pd.Timestamp(year=year, month=a, day=b)
                else:
                    # Неоднозначно — по умолчанию ДД/ММ/ГГ
                    return pd.Timestamp(year=year, month=b, day=a)
    except:
        pass
    
    return pd.NaT

# ============================================================
# ФУНКЦИЯ ОЧИСТКИ ЧИСЕЛ
# ============================================================
def clean_number(val):
    """Корректно парсит числа: 12 960,00 / 12960.00 / -11.44 / 0.98"""
    if pd.isna(val):
        return 0.0
    
    s = str(val).strip()
    if not s or s.lower() in ['nan', 'none', '—', '-', 
                                'сумма', 'производ', 'операционный день', 
                                'login', 'площадка', '']:
        return 0.0
    
    # Убираем процент
    s = s.replace("%", "").strip()
    
    # Если есть и точка, и запятая
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            # Европейский формат: 1.234,56
            s = s.replace(".", "").replace(",", ".")
        else:
            # Американский формат: 1,234.56
            s = s.replace(",", "")
    else:
        # Только запятая или только точка
        s = s.replace(" ", "").replace(",", ".")
    
    try:
        return float(s)
    except:
        return 0.0

# ============================================================
# ФУНКЦИЯ ЗАГРУЗКИ ДАННЫХ
# ============================================================
@st.cache_data(ttl=300)
def load_data(url):
    """Загружает и очищает данные из CSV."""
    try:
        # Автоопределение разделителя
        df = pd.read_csv(url, encoding='utf-8', sep=None, engine='python')
        
        # Если всё в одной колонке — пробуем точку с запятой
        if len(df.columns) == 1:
            df = pd.read_csv(url, encoding='utf-8', sep=';')
        
        # Удаляем дубли шапок и разделители
        first_col = df.iloc[:, 0].astype(str).str.strip().str.lower()
        garbage_mask = (
            first_col.isin(['операционный день', 'login', 'сумма', 'производ', 'площадка', '']) | 
            first_col.str.startswith('---')
        )
        df = df[~garbage_mask].copy()

        # Переименовываем колонки
        if len(df.columns) >= 5:
            df = df.iloc[:, :5].copy()
            df.columns = ["date", "login", "sum", "production", "platform"]
        else:
            st.error(f"Недостаточно колонок: {len(df.columns)}")
            return None, None

        # Парсим даты
        df["date"] = df["date"].apply(parse_date)
        df = df.dropna(subset=["date"])

        # Очищаем числа
        df["sum"] = df["sum"].apply(clean_number)
        df["production"] = df["production"].apply(clean_number)
        
        # Нормализуем площадки
        df["platform"] = df["platform"].astype(str).str.strip()
        df = df[df["platform"] != "nan"]

        # Агрегация: один сотрудник + одна дата + одна площадка = одна строка
        # СУММА суммируется, ПРОИЗВОД усредняется
        df_agg = df.groupby(["date", "login", "platform"], as_index=False).agg(
            sum=("sum", "sum"),
            production=("production", lambda x: x.dropna().mean() if len(x.dropna()) > 0 else 0.0)
        ).copy()

        return df, df_agg
    except Exception as e:
        st.error(f"Ошибка загрузки: {e}")
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
# ПРОВЕРКА ДАТ
# ============================================================
min_date = df_agg["date"].min()
max_date = df_agg["date"].max()

if pd.isna(min_date) or pd.isna(max_date):
    st.error("❌ Не удалось определить диапазон дат.")
    st.stop()

# ============================================================
# БОКОВАЯ ПАНЕЛЬ: ФИЛЬТРЫ
# ============================================================
st.sidebar.header("📅 Фильтры")

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

st.sidebar.success(f"✅ Записей: {len(df_filtered)}")

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
col2.metric("📈 Средний производ", f"{avg_production * 100:.1f}%")
col3.metric("👥 Сотрудников", total_employees)
col4.metric("📋 Записей", total_records)

st.markdown("---")

# ============================================================
# БЛОК 2: СРЕДНИЙ ПРОИЗВОД ПО ПЛОЩАДКАМ (В ПРОЦЕНТАХ)
# ============================================================
st.subheader("🏢 Средний производ по площадкам")

platform_stats = df_filtered.groupby("platform").agg(
    avg_production=("production", "mean"),
    total_sum=("sum", "sum"),
    employees=("login", "nunique")
).reset_index().sort_values("avg_production", ascending=True)

# Переводим в проценты для отображения
platform_stats["avg_production_pct"] = platform_stats["avg_production"] * 100

fig_platform = px.bar(
    platform_stats,
    x="avg_production_pct",
    y="platform",
    orientation="h",
    color="platform",
    text="avg_production_pct",
    title="Средний производ по площадкам (%)",
    color_discrete_sequence=px.colors.qualitative.Set2
)
fig_platform.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
fig_platform.update_layout(showlegend=False, height=400, xaxis_title="Производ (%)")
st.plotly_chart(fig_platform, use_container_width=True)

# ============================================================
# БЛОК 3: ДИНАМИКА ПО ДНЯМ
# ============================================================
st.subheader("📅 Динамика среднего производства по дням")

daily_platform = df_filtered.groupby(["date", "platform"])["production"].mean().reset_index()
daily_platform["production_pct"] = daily_platform["production"] * 100

fig_daily = px.line(
    daily_platform,
    x="date",
    y="production_pct",
    color="platform",
    markers=True,
    title="Средний производ по площадкам в разрезе дней (%)",
    color_discrete_sequence=px.colors.qualitative.Bold
)
fig_daily.update_layout(height=450, yaxis_title="Производ (%)")
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
employee_stats["avg_production_pct"] = employee_stats["avg_production"] * 100

fig_scatter = px.scatter(
    employee_stats,
    x="total_sum",
    y="avg_production_pct",
    color="platform",
    hover_data=["login"],
    title="Каждый сотрудник — точка. Чем правее и выше — тем лучше",
    color_discrete_sequence=px.colors.qualitative.Set1
)
fig_scatter.update_layout(height=500, yaxis_title="Производ (%)")
st.plotly_chart(fig_scatter, use_container_width=True)

# ============================================================
# БЛОК 6: ТОП-10
# ============================================================
col_top_sum, col_top_prod = st.columns(2)

with col_top_sum:
    st.subheader("🏆 Топ-10 по сумме")
    top_sum = employee_stats.nlargest(10, "total_sum")[["login", "platform", "total_sum"]].copy()
    top_sum["total_sum"] = top_sum["total_sum"].apply(lambda x: f"{x:,.0f} ₽")
    top_sum.columns = ["Login", "Площадка", "Сумма"]
    st.dataframe(top_sum, use_container_width=True, hide_index=True)

with col_top_prod:
    st.subheader(" Топ-10 по производству")
    top_prod = employee_stats.nlargest(10, "avg_production")[["login", "platform", "avg_production"]].copy()
    top_prod["avg_production"] = top_prod["avg_production"].apply(lambda x: f"{x * 100:.1f}%")
    top_prod.columns = ["Login", "Площадка", "Производ"]
    st.dataframe(top_prod, use_container_width=True, hide_index=True)

# ============================================================
# БЛОК 7: ПОЛНАЯ ТАБЛИЦА
# ============================================================
st.markdown("---")
st.subheader("📋 Полная таблица данных")

with st.expander("Показать все данные"):
    display_df = df_filtered.sort_values(["date", "platform", "login"]).copy()
    display_df["date_str"] = display_df["date"].dt.strftime("%d.%m.%Y")
    display_df["production_pct"] = display_df["production"] * 100
    display_df = display_df[["date_str", "login", "platform", "sum", "production_pct"]]
    display_df.columns = ["Дата", "Login", "Площадка", "Сумма", "Производ (%)"]
    display_df["Сумма"] = display_df["Сумма"].apply(lambda x: f"{x:,.2f}")
    display_df["Производ (%)"] = display_df["Производ (%)"].apply(lambda x: f"{x:.1f}")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    csv = df_filtered.sort_values(["date", "platform", "login"]).copy()
    csv["date_str"] = csv["date"].dt.strftime("%d.%m.%Y")
    csv["production_pct"] = csv["production"] * 100
    csv = csv[["date_str", "login", "platform", "sum", "production_pct"]]
    csv.columns = ["Дата", "Login", "Площадка", "Сумма", "Производ"]
    csv_data = csv.to_csv(index=False, sep=";").encode("utf-8-sig")
    st.download_button(
        "⬇️ Скачать отфильтрованные данные (CSV)",
        data=csv_data,
        file_name="dashboard_export.csv",
        mime="text/csv"
    )

# ============================================================
# ФУТЕР
# ============================================================
st.markdown("---")
st.caption("Дашборд обновляется автоматически при изменении данных в Google Таблице (кэш 5 минут).")
