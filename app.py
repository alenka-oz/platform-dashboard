# ============================================================
# БОКОВАЯ ПАНЕЛЬ: ФИЛЬТРЫ (УЛУЧШЕННАЯ ВЕРСИЯ С КАЛЕНДАРЕМ)
# ============================================================
st.sidebar.markdown("---")
st.sidebar.header("📅 Фильтры по периоду и данным")

# --- 1. Кнопки быстрого выбора периода ---
st.sidebar.markdown("**Быстрый выбор периода:**")
col_b1, col_b2, col_b3, col_b4 = st.sidebar.columns(4)

min_date = df_agg["date"].min()
max_date = df_agg["date"].max()

with col_b1:
    if st.button("День", use_container_width=True):
        st.session_state.period = "day"
with col_b2:
    if st.button("Неделя", use_container_width=True):
        st.session_state.period = "week"
with col_b3:
    if st.button("Месяц", use_container_width=True):
        st.session_state.period = "month"
with col_b4:
    if st.button("Всё время", use_container_width=True):
        st.session_state.period = "all"

# Если период не выбран, берем всё время
if "period" not in st.session_state:
    st.session_state.period = "all"

# --- 2. Вычисление дат на основе выбранного периода ---
if st.session_state.period == "day":
    default_start = max_date
    default_end = max_date
elif st.session_state.period == "week":
    from datetime import timedelta
    default_start = max_date - timedelta(days=6)
    default_end = max_date
elif st.session_state.period == "month":
    from datetime import timedelta
    default_start = max_date - timedelta(days=29)
    default_end = max_date
else:
    default_start = min_date
    default_end = max_date

# --- 3. Календарь выбора диапазона дат ---
selected_dates = st.sidebar.date_input(
    "Выберите диапазон дат:",
    value=(default_start, default_end),
    min_value=min_date,
    max_value=max_date,
    format="DD.MM.YYYY"
)

# Обработка выбора (календарь возвращает кортеж из 2 дат)
if len(selected_dates) == 2:
    start_date, end_date = selected_dates
else:
    start_date, end_date = min_date, max_date

# --- 4. Фильтр по Площадке ---
all_platforms = sorted(df_agg["platform"].unique())
selected_platforms = st.sidebar.multiselect(
    "🏢 Площадка:",
    options=all_platforms,
    default=all_platforms
)

# --- 5. Фильтр по Сотруднику (с поиском) ---
all_logins = sorted(df_agg["login"].unique())
search_login = st.sidebar.text_input("🔎 Поиск сотрудника (login):", "")
if search_login:
    filtered_logins = [l for l in all_logins if search_login.lower() in l.lower()]
else:
    filtered_logins = all_logins

selected_logins = st.sidebar.multiselect(
    "👤 Сотрудник (по умолчанию первые 50):",
    options=filtered_logins,
    default=filtered_logins[:50] 
)

# --- 6. ПРИМЕНЕНИЕ ВСЕХ ФИЛЬТРОВ К ДАННЫМ ---
df_filtered = df_agg[
    (df_agg["date"] >= pd.to_datetime(start_date)) &
    (df_agg["date"] <= pd.to_datetime(end_date)) &
    (df_agg["platform"].isin(selected_platforms)) &
    (df_agg["login"].isin(selected_logins))
].copy()

st.sidebar.success(f"✅ Записей за период: {len(df_filtered)}")
