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
# ФУНКЦИЯ ОЧИСТКИ ЧИСЕЛ (ПУЛЕНЕПРОБИВАЕМАЯ)
# ============================================================
def clean_number(val):
    """Корректно парсит числа в любом формате: 12 960,00 / 12960.00 / -11.44"""
    if pd.isna(val):
        return 0.0
    
    s = str(val).strip()
    if not s or s.lower() in ['nan', 'none', '—', '-', 'сумма', 'производ', 'операционный день', 'login', 'площадка']:
        return 0.0
    
    s = s.replace("%", "").strip()
    
    # Если есть и точка, и запятая (например, 1.234,56 или 1,234.56)
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            # Европейский формат: убираем точки, запятую меняем на точку
            s = s.replace(".", "").replace(",", ".")
        else:
            # Американский формат: просто убираем запятые
            s = s.replace(",", "")
    else:
        # Только запятая или только точка: убираем пробелы, запятую меняем на точку
        s = s.replace(" ", "").replace(",", ".")
        
    try:
        return float(s)
    except:
        return 0.0

# ============================================================
# ФУНКЦИЯ ПАРСИНГА ДАТЫ
# ============================================================
def parse_date(val):
    val = str(val).strip()
    if not val or val.lower() in ['nan', 'none', 'операционный день', 'login', 'сумма', 'производ', 'площадка']:
        return pd.NaT
    if val.startswith("---"):
        return pd.NaT
    
    try:
        # Пробуем формат с точками (28.09.2026)
        if "." in val:
            return pd.to_datetime(val, dayfirst=True)
        
        # Пробуем формат с косой чертой (28/09/26 или 9/28/26)
        if "/" in val:
            parts = val.split("/")
            if len(parts) == 3:
                a, b, c = int(parts[0]), int(parts[1]), int(parts[2])
                year = 2000 + c if c < 100 else c
                
                if a > 12:
                    return pd.Timestamp(year=year, month=b, day=a) # ДД/ММ/ГГ
                elif b > 12:
                    return pd.Timestamp(year=year, month=a, day=b) # ММ/ДД/ГГ
                else:
                    return pd.Timestamp(year=year, month=b, day=a) # По умолчанию ДД/ММ/ГГ
    except:
        pass
    
    return pd.NaT

# ============================================================
# ФУНКЦИЯ ЗАГРУЗКИ ДАННЫХ С ПОШАГОВОЙ ОТЛАДКОЙ
# ============================================================
@st.cache_data(ttl=300)
def load_data(url):
    try:
        # 1. Автоопределение разделителя (запятая или точка с запятой)
        df = pd.read_csv(url, encoding='utf-8', sep=None, engine='python')
        
        # Если автоопределение не сработало и всё в одной колонке, пробуем явно ';'
        if len(df.columns) == 1:
            df = pd.read_csv(url, encoding='utf-8', sep=';')
            
        st.sidebar.markdown("### 🔍 Пошаговая отладка")
        st.sidebar.write(f"**1. Всего строк в CSV:** {len(df)}")
        
        # Сумма "как есть" до любой обработки (поможет найти, если данные уже потеряны тут)
        raw_sum_col = df.iloc[:, 2] if len(df.columns) > 2 else pd.Series(dtype=float)
        raw_sum = pd.to_numeric(raw_sum_col, errors='coerce').sum()
        st.sidebar.write(f"**2. Сумма колонки 'Сумма' до очистки:** {raw_sum:,.2f} ₽")

        # 2. Жесткая фильтрация мусорных строк
        first_col = df.iloc[:, 0].astype(str).str.strip().str.lower()
        garbage_mask = (
            first_col.isin(['операционный день', 'login', 'сумма', 'производ', 'площадка', '']) | 
            first_col.str.startswith('---')
        )
        df = df[~garbage_mask].copy()
        st.sidebar.write(f"**3. Строк после удаления мусора:** {len(df)}")

        # 3. Переименование колонок
        if len(df.columns) >= 5:
            df = df.iloc[:, :5].copy()
            df.columns = ["date", "login", "sum", "production", "platform"]
        else:
            st.error(f"Критическая ошибка: всего {len(df.columns)} колонок вместо 5.")
            return None, None

        # 4. Парсинг дат
        df["date"] = df["date"].apply(parse_date)
        df_before_date = len(df)
        df = df.dropna(subset=["date"])
        st.sidebar.write(f"**4. Строк с валидной датой:** {len(df)} (потеряно: {df_before_date - len(df)})")

        # 5. Очистка чисел
        df["sum"] = df["sum"].apply(clean_number)
        df["production"] = df["production"].apply(clean_number)
        
        sum_after_clean = df["sum"].sum()
        st.sidebar.write(f"**5. Сумма после очистки чисел:** {sum_after_clean:,.2f} ₽")

        # 6. Нормализация площадок
        df["platform"] = df["platform"].astype(str).str.strip()
        df = df[df["platform"] != "nan"]
        st.sidebar.write(f"**6. Уникальных площадок:** {df['platform'].nunique()}")
        st.sidebar.write(f"   → {', '.join(sorted(df['platform'].unique()))}")

        # 7. Агрегация
        df_agg = df.groupby(["date", "login", "platform"], as_index=False).agg(
            sum=("sum", "sum"),
            production=("production", lambda x: x.dropna().mean() if len(x.dropna()) > 0 else 0.0)
        ).copy()
        
        final_sum = df_agg["sum"].sum()
        st.sidebar.write(f"**7. ИТОГОВАЯ СУММА после агрегации:** {final_sum:,.2f} ₽")
        st.sidebar.write(f"**8. Итоговых записей:** {len(df_agg)}")
        
        # Предупреждение, если сумма сильно отличается от сырой
        if abs(raw_sum - final_sum) > 1000000: # Разница больше 1 млн
            st.sidebar.warning(f"⚠️ Внимание! Потеряно ~{(raw_sum - final_sum)/1000000:.1f} млн ₽. Проверьте шаги выше.")

        return df, df_agg
    except Exception as e:
        st.error(f"Критическая ошибка загрузки: {e}")
        import traceback
        st.code(traceback.format_exc())
        return None, None

# ============================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================
df_raw, df_agg = load_data(DEFAULT_CSV_URL)

if df_raw is None or df_agg is None:
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
st.sidebar.markdown("---")
st.sidebar.header("📅 Фильтры")

st.sidebar.markdown("**Быстрый выбор:**")
col_b1, col_b2, col_b3 = st.sidebar.columns(3)
with col_b1:
    if st.button("День", use_container_width=True): st.session_state.period = "day"
with col_b2:
    if st.button("Неделя", use_container_width=True): st.session_state.period = "week"
with col_b3:
    if st.button("Всё время", use_container_width=True): st.session_state.period = "all"

if "period" not in st.session_state: st.session_state.period = "all"

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
    min_value=min_date, max_value=max_date, format="DD.MM.YYYY"
)
start_date, end_date = selected_dates if len(selected_dates) == 2 else (min_date, max_date)

all_platforms = sorted(df_agg["platform"].unique())
selected_platforms = st.sidebar.multiselect("🏢 Площадка:", options=all_platforms, default=all_platforms)

all_logins = sorted(df_agg["login"].unique())
search_login = st.sidebar.text_input("🔎 Поиск сотрудника:", "")
filtered_logins = [l for l in all_logins if search_login.lower() in l.lower()] if search_login else all_logins
selected_logins = st.sidebar.multiselect("👤 Сотрудник:", options=filtered_logins, default=filtered_logins)

df_filtered = df_agg[
    (df_agg["date"] >= pd.to_datetime(start_date)) &
    (df_agg["date"] <= pd.to_datetime(end_date)) &
    (df_agg["platform"].isin(selected_platforms)) &
    (df_agg["login"].isin(selected_logins))
].copy()

st.sidebar.success(f"✅ Записей после фильтров: {len(df_filtered)}")

# ============================================================
# ОСНОВНОЙ ДАШБОРД (KPI и Графики)
# ============================================================
st.subheader("📌 Общие показатели")
col1, col2, col3, col4 = st.columns(4)
col1.metric("💰 Общая сумма", f"{df_filtered['sum'].sum():,.0f} ₽")
col2.metric("📈 Средний производ", f"{df_filtered['production'].mean():.3f}")
col3.metric("👥 Сотрудников", df_filtered["login"].nunique())
col4.metric("📋 Записей", len(df_filtered))
st.markdown("---")

st.subheader("🏢 Средний производ по площадкам")
platform_stats = df_filtered.groupby("platform").agg(
    avg_production=("production", "mean"),
    total_sum=("sum", "sum"),
    employees=("login", "nunique")
).reset_index().sort_values("avg_production", ascending=True)

fig_platform = px.bar(platform_stats, x="avg_production", y="platform", orientation="h", color="platform", text="avg_production", color_discrete_sequence=px.colors.qualitative.Set2)
fig_platform.update_traces(texttemplate="%{text:.3f}", textposition="outside")
fig_platform.update_layout(showlegend=False, height=400)
st.plotly_chart(fig_platform, use_container_width=True)

st.subheader("📅 Динамика среднего производства по дням")
daily_platform = df_filtered.groupby(["date", "platform"])["production"].mean().reset_index()
fig_daily = px.line(daily_platform, x="date", y="production", color="platform", markers=True, color_discrete_sequence=px.colors.qualitative.Bold)
fig_daily.update_layout(height=450)
st.plotly_chart(fig_daily, use_container_width=True)

col_left, col_right = st.columns(2)
with col_left:
    fig_pie = px.pie(platform_stats, values="total_sum", names="platform", hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
    fig_pie.update_traces(textinfo="percent+label")
    st.plotly_chart(fig_pie, use_container_width=True)
with col_right:
    fig_bar_emp = px.bar(platform_stats, x="platform", y="employees", color="platform", text="employees", color_discrete_sequence=px.colors.qualitative.Set2)
    fig_bar_emp.update_traces(texttemplate="%{text}", textposition="outside")
    fig_bar_emp.update_layout(showlegend=False)
    st.plotly_chart(fig_bar_emp, use_container_width=True)

st.subheader("🎯 Эффективность сотрудников (Сумма vs Производ)")
employee_stats = df_filtered.groupby(["login", "platform"]).agg(total_sum=("sum", "sum"), avg_production=("production", "mean")).reset_index()
fig_scatter = px.scatter(employee_stats, x="total_sum", y="avg_production", color="platform", hover_data=["login"], color_discrete_sequence=px.colors.qualitative.Set1)
fig_scatter.update_layout(height=500)
st.plotly_chart(fig_scatter, use_container_width=True)

col_top_sum, col_top_prod = st.columns(2)
with col_top_sum:
    st.subheader("🏆 Топ-10 по сумме")
    st.dataframe(employee_stats.nlargest(10, "total_sum")[["login", "platform", "total_sum"]], use_container_width=True, hide_index=True)
with col_top_prod:
    st.subheader("🏆 Топ-10 по производству")
    st.dataframe(employee_stats.nlargest(10, "avg_production")[["login", "platform", "avg_production"]], use_container_width=True, hide_index=True)

st.markdown("---")
with st.expander("📋 Показать полную таблицу данных"):
    display_df = df_filtered.sort_values(["date", "platform", "login"]).copy()
    display_df["date_str"] = display_df["date"].dt.strftime("%d.%m.%Y")
    display_df = display_df[["date_str", "login", "platform", "sum", "production"]]
    display_df.columns = ["Дата", "Login", "Площадка", "Сумма", "Производ"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("Дашборд обновляется автоматически при изменении данных в Google Таблице (кэш 5 минут).")
