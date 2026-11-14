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
# ФИКСИРОВАННАЯ ЦВЕТОВАЯ ПАЛИТРА ПЛОЩАДОК
# ============================================================
PLATFORM_COLORS = {
    # Ламода — неоновые
    "Ламода Быково":    "#00BFFF",   # ⚡ Electric Blue (яркий голубой)
    "Ламода Софьино":   "#FF1493",   # 💖 Deep Pink (неоновый розовый)
    # Яндекс площадки — неоновые
    "Софьино":          "#1E90FF",   # 🔵 Dodger Blue (электрик)
    "Дзержинский":      "#FF4500",   # 🔴 Orange Red (яркий коралл)
    "Тарный":           "#32CD32",   # 🟢 Lime Green (неоновый зелёный)
    "Кувекино":         "#FFA500",   # 🟠 Orange (насыщенный оранжевый)
    "Домодедово":       "#B026FF",   # 🟣 Neon Purple (неоновый фиолетовый)
    "Грибки":           "#00CED1",   # 🩵 Dark Turquoise (яркая бирюза)
}

# ============================================================
# ФУНКЦИЯ ПАРСИНГА ДАТЫ
# ============================================================
def parse_date(val):
    val = str(val).strip()
    if not val or val.lower() in ['nan', 'none', 'операционный день', 'login', 
                                    'сумма', 'производ', 'площадка', '']:
        return pd.NaT
    if val.startswith("---"):
        return pd.NaT
    
    try:
        if "." in val:
            return pd.to_datetime(val, dayfirst=True)
        
        if "/" in val:
            parts = val.split("/")
            if len(parts) == 3:
                a, b, c = int(parts[0]), int(parts[1]), int(parts[2])
                year = 2000 + c if c < 100 else c
                
                if a > 12:
                    return pd.Timestamp(year=year, month=b, day=a)
                elif b > 12:
                    return pd.Timestamp(year=year, month=a, day=b)
                else:
                    return pd.Timestamp(year=year, month=b, day=a)
    except:
        pass
    
    return pd.NaT

# ============================================================
# ФУНКЦИЯ ОЧИСТКИ ЧИСЕЛ
# ============================================================
def clean_number(val):
    if pd.isna(val):
        return 0.0
    
    s = str(val).strip()
    if not s or s.lower() in ['nan', 'none', '—', '-', 
                                'сумма', 'производ', 'операционный день', 
                                'login', 'площадка', '']:
        return 0.0
    
    s = s.replace("%", "").strip()
    
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
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
    try:
        df = pd.read_csv(url, encoding='utf-8', sep=None, engine='python')
        
        if len(df.columns) == 1:
            df = pd.read_csv(url, encoding='utf-8', sep=';')
        
        first_col = df.iloc[:, 0].astype(str).str.strip().str.lower()
        garbage_mask = (
            first_col.isin(['операционный день', 'login', 'сумма', 'производ', 'площадка', '']) | 
            first_col.str.startswith('---')
        )
        df = df[~garbage_mask].copy()

        if len(df.columns) >= 5:
            df = df.iloc[:, :5].copy()
            df.columns = ["date", "login", "sum", "production", "platform"]
        else:
            st.error(f"Недостаточно колонок: {len(df.columns)}")
            return None, None

        df["date"] = df["date"].apply(parse_date)
        df = df.dropna(subset=["date"])

        df["sum"] = df["sum"].apply(clean_number)
        df["production"] = df["production"].apply(clean_number)
        
        df["platform"] = df["platform"].astype(str).str.strip()
        df = df[df["platform"] != "nan"]

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

# Создаём универсальную карту цветов на основе реальных площадок из данных
ALL_PLATFORMS = sorted(df_agg["platform"].unique())
FALLBACK_PALETTE = ["#34495E", "#95A5A6", "#D35400", "#16A085", "#C0392B", "#2980B9", "#E67E22", "#1ABC9C"]

COLOR_MAP = {}
for i, p in enumerate(ALL_PLATFORMS):
    COLOR_MAP[p] = PLATFORM_COLORS.get(p, FALLBACK_PALETTE[i % len(FALLBACK_PALETTE)])

if df_raw is None or df_agg is None:
    st.error("Не удалось загрузить данные")
    st.stop()

# ============================================================
# КОРРЕКТИРОВКА ДАННЫХ ПО ЛАМОДЕ (×2)
# Данные по Ламоде загружены с коэффициентом 0.5,
# поэтому умножаем суммы на 2. Производ не трогаем.
# ============================================================
LAMODA_PLATFORMS = ["Ламода Софьино", "Ламода Быково"]
CORRECTION_FACTOR = 2.0

mask_raw = df_raw["platform"].isin(LAMODA_PLATFORMS)
df_raw.loc[mask_raw, "sum"] = df_raw.loc[mask_raw, "sum"] * CORRECTION_FACTOR

mask_agg = df_agg["platform"].isin(LAMODA_PLATFORMS)
df_agg.loc[mask_agg, "sum"] = df_agg.loc[mask_agg, "sum"] * CORRECTION_FACTOR

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
# БЛОК 2: СРЕДНИЙ ПРОИЗВОД ПО ПЛОЩАДКАМ
# ============================================================
st.subheader("🏢 Средний производ по площадкам")

platform_stats = df_filtered.groupby("platform").agg(
    avg_production=("production", "mean"),
    total_sum=("sum", "sum"),
    employees=("login", "nunique")
).reset_index().sort_values("avg_production", ascending=True)

platform_stats["avg_production_pct"] = platform_stats["avg_production"] * 100

fig_platform = px.bar(
    platform_stats,
    x="avg_production_pct",
    y="platform",
    orientation="h",
    color="platform",
    text="avg_production_pct",
    title="Средний производ по площадкам (%)",
    color_discrete_map=PLATFORM_COLORS
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
    color_discrete_map=PLATFORM_COLORS
)
fig_daily.update_layout(height=450, yaxis_title="Производ (%)")
st.plotly_chart(fig_daily, use_container_width=True)

# БЛОК 4: РАСПРЕДЕЛЕНИЕ СУММЫ И СОТРУДНИКОВ
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("💵 Доля площадок в общей сумме")
    fig_pie = px.pie(
        platform_stats,
        values="total_sum",
        names="platform",
        color="platform",          # ← ДОБАВИТЬ ЭТУ СТРОКУ
        title="Распределение суммы по площадкам",
        hole=0.4,
        color_discrete_map=COLOR_MAP
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
        color_discrete_map=COLOR_MAP
    )
    fig_bar_emp.update_traces(texttemplate="%{text}", textposition="outside")
    fig_bar_emp.update_layout(showlegend=False)
    st.plotly_chart(fig_bar_emp, use_container_width=True)

# БЛОК 4.5: СРЕДНИЙ ДНЕВНОЙ ЗАРАБОТОК НА СОТРУДНИКА ПО ПЛОЩАДКАМ
st.subheader("💼 Средний дневной заработок на сотрудника по площадкам")

# Шаг 1: считаем по каждому логину — сумма и количество отработанных дней
employee_daily = df_filtered.groupby(["login", "platform"]).agg(
    total_sum=("sum", "sum"),
    days_worked=("date", "nunique")
).reset_index()

# Шаг 2: дневной заработок каждого сотрудника
employee_daily["daily_earnings"] = employee_daily.apply(
    lambda row: row["total_sum"] / row["days_worked"] if row["days_worked"] > 0 else 0,
    axis=1
)

# Шаг 3: среднее по площадке (среднее дневных заработков её сотрудников)
platform_daily = employee_daily.groupby("platform").agg(
    avg_daily_earnings=("daily_earnings", "mean"),
    employees=("login", "nunique"),
    total_days=("days_worked", "sum")
).reset_index().sort_values("avg_daily_earnings", ascending=False)

# График
fig_earnings = px.bar(
    platform_daily,
    x="avg_daily_earnings",
    y="platform",
    orientation="h",
    color="platform",
    text="avg_daily_earnings",
    title="Средний дневной заработок на одного сотрудника (₽/день)",
    color_discrete_map=PLATFORM_COLORS,
    labels={
        "avg_daily_earnings": "₽ в день на сотрудника",
        "platform": "Площадка"
    }
)

fig_earnings.update_traces(
    texttemplate="%{text:,.0f} ₽",
    textposition="outside",
    hovertemplate=(
        "<b>%{y}</b><br>"
        "Средний дневной заработок: %{x:,.0f} ₽<br>"
        "Сотрудников: %{customdata[0]}<br>"
        "Всего отработанных человеко-дней: %{customdata[1]:,}<extra></extra>"
    ),
    customdata=platform_daily[["employees", "total_days"]].values
)

fig_earnings.update_layout(
    showlegend=False,
    height=400,
    xaxis_title="Средний дневной заработок на сотрудника (₽/день)",
    yaxis={"categoryorder": "total ascending"}
)

st.plotly_chart(fig_earnings, use_container_width=True)

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
    color_discrete_map=PLATFORM_COLORS
)
fig_scatter.update_layout(height=500, yaxis_title="Производ (%)")
st.plotly_chart(fig_scatter, use_container_width=True)

# ============================================================
# БЛОК 5.5: КОНЦЕНТРАЦИЯ ВЫРУЧКИ (РИСК ЗАВИСИМОСТИ ОТ «ЗВЁЗД»)
# ============================================================
st.subheader("⚖️ Концентрация выручки: доля топ-20% сотрудников")
st.markdown(
    "Показывает, какой процент общей суммы площадки генерируют лучшие 20% сотрудников. "
    "Высокое значение (>65%) означает риск: уход ключевых людей сильно ударит по результатам."
)

# 1. Считаем сумму по каждому сотруднику на каждой площадке (на основе отфильтрованных данных)
emp_sums = df_filtered.groupby(["platform", "login"])["sum"].sum().reset_index()

concentration_data = []

for platform, group in emp_sums.groupby("platform"):
    total_emp = len(group)
    if total_emp == 0:
        continue

    # Сортируем сотрудников по убыванию суммы (от самых результативных к остальным)
    group_sorted = group.sort_values("sum", ascending=False)

    # Считаем кумулятивную (накопительную) сумму
    group_sorted["cumsum"] = group_sorted["sum"].cumsum()
    total_platform_sum = group_sorted["sum"].sum()

    # Сколько человек составляют топ-20% (минимум 1 человек, чтобы не было 0)
    top_20_count = max(1, round(total_emp * 0.2))

    # Доля выручки, которую приносит этот топ-20%
    top_20_revenue = group_sorted.iloc[:top_20_count]["cumsum"].max()
    top_20_revenue_share_pct = (top_20_revenue / total_platform_sum * 100) if total_platform_sum > 0 else 0

    # Оценка уровня риска
    if top_20_revenue_share_pct > 65:
        risk = "🔴 Высокий"
    elif top_20_revenue_share_pct > 50:
        risk = "🟡 Средний"
    else:
        risk = "🟢 Низкий (равномерная нагрузка)"

    concentration_data.append({
        "platform": platform,
        "total_employees": total_emp,
        "top_20_count": top_20_count,
        "top_20_revenue_share_pct": top_20_revenue_share_pct,
        "risk_level": risk
    })

# Создаем датафрейм и сортируем от самых рискованных к стабильным
conc_df = pd.DataFrame(concentration_data).sort_values("top_20_revenue_share_pct", ascending=False)

# === ГРАФИК ===
fig_conc = px.bar(
    conc_df,
    x="top_20_revenue_share_pct",
    y="platform",
    orientation="h",
    color="platform",
    text="top_20_revenue_share_pct",
    title="Доля выручки, которую генерируют лучшие 20% сотрудников",
    color_discrete_map=PLATFORM_COLORS,
    hover_data={
        "total_employees": "Всего сотрудников", 
        "top_20_count": "Человек в топ-20%", 
        "risk_level": True
    }
)

fig_conc.update_traces(
    texttemplate="%{text:.1f}%",
    textposition="outside",
    hovertemplate=(
        "<b>%{y}</b><br>"
        "Доля выручки топ-20%: %{x:.1f}%<br>"
        "Всего сотрудников: %{customdata[0]}<br>"
        "Из них в топ-20%: %{customdata[1]} чел.<br>"
        "Риск: %{customdata[2]}<extra></extra>"
    )
)

# Добавляем вертикальную линию-порог (65% - зона высокого риска)
fig_conc.add_vline(
    x=65, 
    line_dash="dash", 
    line_color="red", 
    annotation_text="Зона высокого риска (>65%)", 
    annotation_position="top right"
)

fig_conc.update_layout(
    showlegend=False,
    height=400,
    xaxis_title="Доля выручки топ-20% (%)",
    xaxis=dict(range=[0, 100])  # Фиксируем шкалу от 0 до 100% для наглядности
)

st.plotly_chart(fig_conc, use_container_width=True)

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
    st.subheader("🏆 Топ-10 по производству")
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
