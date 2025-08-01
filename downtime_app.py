import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from io import StringIO

st.set_page_config(layout="wide", page_title="Аналіз заявок по обладнанню", page_icon="⚙️")

st.title("⚙️ Аналіз заявок по обладнанню")

st.markdown("""
    Завантажте ваш **CSV-файл** з даними про заявки.
    
    **Особливості:**
    * **Пошук**: Використовуйте поле пошуку, щоб швидко знайти заявки за ідентифікатором або описом робіт.
    * **Єдина таблиця**: Ви бачите всі візуальні позначки (проблемний час, аномалії) в одній таблиці, де також можете додавати коментарі.
    * **Завантаження змін**: Тепер є дві кнопки для завантаження:
        1. **Оновлений CSV**: Завантажує повну таблицю з усіма вашими змінами.
        2. **Звіт по коментарях**: Завантажує файл лише з тими заявками, до яких ви додали коментарі.
    
    **Очікувані стовпці**:
    * "Дата створення" та "Час створення" (обов'язкові)
    * "Дата виконання" та "Час виконання" (якщо є)
    * А також: "Тип заявки", "Цех", "Лінія", "Обладнання", "Ідентифікатор", "Опис робіт", "Відповідальні служби".
""")

# --- Вибір джерела даних (тільки завантаження файлу з комп'ютера) ---
st.sidebar.header("Джерело даних")
df = None
uploaded_file = st.file_uploader("📂 Завантажте CSV-файл", type=["csv"])

if uploaded_file:
    try:
        uploaded_file.seek(0)
        try:
            df = pd.read_csv(uploaded_file, sep=';', encoding='utf-8')
        except Exception:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, sep=';', encoding='cp1251')
        
        if df.empty or len(df.columns) <= 2:
            uploaded_file.seek(0)
            try:
                df = pd.read_csv(uploaded_file, sep=',', encoding='utf-8')
            except Exception:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, sep=',', encoding='cp1251')
        
        if df.empty or len(df.columns) <= 2:
            uploaded_file.seek(0)
            try:
                df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
            except Exception:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding='cp1251')

        st.success("✅ Файл успішно завантажено!")
    except Exception as e:
        st.error(f"❌ Виникла помилка під час завантаження файлу: {e}")
        st.info("Будь ласка, перевірте, чи файл не пошкоджений та чи є у ньому дані.")
        df = None

# --- Вся подальша логіка обробки даних тепер виконується тільки якщо df не порожній ---
if df is not None and not df.empty:
    try:
        critical_date_time_cols = ["Дата створення", "Час створення"]
        for col in critical_date_time_cols:
            if col not in df.columns:
                st.error(f"❌ У файлі відсутній критично важливий стовпець: '{col}'. Будь ласка, перевірте ваш файл.")
                st.stop()

        if "Звіт про виконану роботу" not in df.columns:
            df["Звіт про виконану роботу"] = ""
            st.info("ℹ️ Стовпець 'Звіт про виконану роботу' відсутній у файлі і був доданий як порожній.")
        if "Реакція на заявки" not in df.columns:
            df["Реакція на заявки"] = ""
            st.info("ℹ️ Додано новий стовпець 'Реакція на заявки' для коментарів.")
        if "Ідентифікатор" not in df.columns:
            df["Ідентифікатор"] = df.index + 1
            st.info("ℹ️ Стовпець 'Ідентифікатор' відсутній у файлі і був доданий.")
        if "Обладнання" not in df.columns:
            df["Обладнання"] = "Не вказано"
            st.info("ℹ️ Стовпець 'Обладнання' відсутній у файлі і був доданий зі значенням 'Не вказано'.")
        if "Опис робіт" not in df.columns:
            df["Опис робіт"] = "Без опису"
            st.info("ℹ️ Стовпець 'Опис робіт' відсутній у файлі і був доданий зі значенням 'Без опису'.")
        if "Відповідальні служби" not in df.columns:
            df["Відповідальні служби"] = "Не вказано"
            st.info("ℹ️ Стовпець 'Відповідальні служби' відсутній у файлі і був доданий зі значенням 'Не вказано'.")
        
        date_formats = ["%Y-%m-%d", "%d.%m.%Y", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]
        time_formats = ["%H:%M:%S", "%H:%M"]
        combined_datetime_formats = [f"{d_fmt} {t_fmt}" for d_fmt in date_formats for t_fmt in time_formats]
        combined_datetime_formats = [
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M:%S",
            "%d.%m.%Y %H:%M", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M",
            "%Y-%m-%dT%H:%M:%S"
        ] + combined_datetime_formats
        combined_datetime_formats.extend(date_formats)
        combined_datetime_formats = list(dict.fromkeys(combined_datetime_formats))

        def combine_and_convert_datetime(row, date_col_name, time_col_name=None):
            date_val = row.get(date_col_name)
            time_val = row.get(time_col_name) if time_col_name else None
            if pd.isna(date_val) and (time_col_name is None or pd.isna(time_val)):
                return np.nan
            try:
                if pd.api.types.is_numeric_dtype(type(date_val)) and pd.notna(date_val):
                    base_date = pd.to_datetime('1899-12-30')
                    converted_date = base_date + pd.to_timedelta(date_val, unit='D')
                    if pd.notna(converted_date):
                        if time_col_name and pd.api.types.is_numeric_dtype(type(time_val)) and pd.notna(time_val):
                            converted_time = pd.to_timedelta(time_val, unit='D')
                            return converted_date + converted_time
                        return converted_date
            except Exception:
                pass
            date_str = str(date_val).strip() if pd.notna(date_val) else ""
            time_str = str(time_val).strip() if pd.notna(time_val) else ""
            combined_str = f"{date_str} {time_str}" if date_str and time_str else date_str or time_str
            if not combined_str:
                return np.nan
            for fmt in combined_datetime_formats:
                try:
                    return pd.to_datetime(combined_str, format=fmt)
                except (ValueError, TypeError):
                    continue
            try:
                return pd.to_datetime(combined_str, infer_datetime_format=True, errors='coerce')
            except (ValueError, TypeError):
                return np.nan

        df['Час створення (datetime)'] = df.apply(lambda row: combine_and_convert_datetime(row, 'Дата створення', 'Час створення'), axis=1)
        initial_rows = len(df)
        df.dropna(subset=["Час створення (datetime)"], inplace=True)
        if len(df) < initial_rows:
            st.warning(f"⚠️ Видалено {initial_rows - len(df)} рядків через некоректний 'Час створення'.")
        if df.empty:
            st.warning("⚠️ Після обробки дат у файлі не залишилося дійсних даних.")
            st.stop()
        
        df_for_anomaly_detection = df.drop_duplicates(subset=['Ідентифікатор']).copy()
        
        if "Обладнання" in df_for_anomaly_detection.columns and "Опис робіт" in df_for_anomaly_detection.columns and "Час створення (datetime)" in df_for_anomaly_detection.columns:
            df_for_anomaly_detection['problem_location'] = df_for_anomaly_detection['Обладнання'].fillna(df_for_anomaly_detection['Лінія'].fillna('Невідоме обладнання')).astype(str)
            df_for_anomaly_detection['problem_description'] = df_for_anomaly_detection['Опис робіт'].fillna('Без опису робіт').astype(str)
            df_for_anomaly_detection['problem_key'] = df_for_anomaly_detection['problem_location'] + " ### " + df_for_anomaly_detection['problem_description']
            df_for_anomaly_detection = df_for_anomaly_detection.sort_values(by=['problem_key', 'Час створення (datetime)'])
            df_for_anomaly_detection['time_diff'] = df_for_anomaly_detection.groupby('problem_key')['Час створення (datetime)'].diff()
            anomaly_min_delta = pd.Timedelta(days=0, minutes=1)
            anomaly_max_delta = pd.Timedelta(days=3)
            df_for_anomaly_detection['Підозріле повторення'] = (
                (df_for_anomaly_detection['time_diff'] > anomaly_min_delta) & 
                (df_for_anomaly_detection['time_diff'] <= anomaly_max_delta)
            )
            anomaly_flags = df_for_anomaly_detection[['Ідентифікатор', 'Підозріле повторення']].copy()
            anomaly_flags = anomaly_flags.drop_duplicates(subset='Ідентифікатор', keep='first')
            df = df.merge(anomaly_flags, on='Ідентифікатор', how='left')
            df['Підозріле повторення'] = df['Підозріле повторення'].fillna(False)
        else:
            st.warning("⚠️ Неможливо виконати аналіз аномалій.")
            df['Підозріле повторення'] = False

        df['Час виконання (datetime)'] = df.apply(lambda row: combine_and_convert_datetime(row, 'Дата виконання', 'Час виконання'), axis=1)
        df['Час закриття (datetime)'] = df.apply(lambda row: combine_and_convert_datetime(row, 'Дата закриття', 'Час закриття'), axis=1)
        df["Дата створення (для фільтра)"] = df["Час створення (datetime)"].dt.date
        df["Час до виконання (хв)"] = (df["Час виконання (datetime)"] - df["Час створення (datetime)"]).dt.total_seconds() / 60
        df["Час до закриття (хв)"] = (df["Час закриття (datetime)"] - df["Час створення (datetime)"]).dt.total_seconds() / 60

        if "Відповідальні служби" in df.columns:
            df["Відповідальні служби"] = df["Відповідальні служби"].fillna("")
            df["Відповідальні служби"] = df["Відповідальні служби"].apply(
                lambda x: [s.strip() for s in str(x).split(',') if s.strip()] if pd.notna(x) else ["Не вказано"]
            )
            df = df.explode("Відповідальні служби")
            st.info("ℹ️ Стовпець 'Відповідальні служби' було оброблено для розділення.")

        # --- Бокова панель для фільтрів ---
        st.sidebar.header("🔍 Фільтри даних")
        selected_types = st.sidebar.multiselect("Оберіть тип(и) заявки", sorted(df["Тип заявки"].dropna().unique().tolist()), default=df["Тип заявки"].dropna().unique().tolist()) if "Тип заявки" in df.columns else []
        selected_workshops = st.sidebar.multiselect("Оберіть цех(и)", sorted(df["Цех"].dropna().unique().tolist()), default=df["Цех"].dropna().unique().tolist()) if "Цех" in df.columns else []
        selected_responsible_services = st.sidebar.multiselect("Оберіть відповідальну(і) службу(и)", sorted(df["Відповідальні служби"].dropna().unique().tolist()), default=df["Відповідальні служби"].dropna().unique().tolist()) if "Відповідальні служби" in df.columns else []
        filter_anomalies = st.sidebar.checkbox("Показати лише підозрілі повторення", value=False)
        min_date_available = df["Дата створення (для фільтра)"].min()
        max_date_available = df["Дата створення (для фільтра)"].max()
        start_date = st.sidebar.date_input("Початкова дата", value=min_date_available, min_value=min_date_available, max_value=max_date_available)
        end_date = st.sidebar.date_input("Кінцева дата", value=max_date_available, min_value=min_date_available, max_value=max_date_available)

        # --- Застосування фільтрів ---
        filtered_df = df.copy()
        if selected_types: filtered_df = filtered_df[filtered_df["Тип заявки"].isin(selected_types)]
        if selected_workshops: filtered_df = filtered_df[filtered_df["Цех"].isin(selected_workshops)]
        if selected_responsible_services: filtered_df = filtered_df[filtered_df["Відповідальні служби"].isin(selected_responsible_services)]
        if filter_anomalies: filtered_df = filtered_df[filtered_df['Підозріле повторення'] == True]
        filtered_df = filtered_df[(filtered_df["Дата створення (для фільтра)"] >= start_date) & (filtered_df["Дата створення (для фільтра)"] <= end_date)]

        if filtered_df.empty:
            st.warning("⚠️ Після застосування вибраних фільтрів даних не знайдено.")
            st.stop()
        
        # --- Пошук по заявках ---
        search_query = st.text_input("🔍 Пошук по заявках (введіть ідентифікатор або опис робіт)", "")
        if search_query:
            filtered_df = filtered_df[
                filtered_df['Ідентифікатор'].astype(str).str.contains(search_query, case=False, na=False) |
                filtered_df['Опис робіт'].astype(str).str.contains(search_query, case=False, na=False)
            ]
            if filtered_df.empty:
                st.info("ℹ️ За вашим запитом нічого не знайдено.")
        
        # --- Створення нового стовпця з візуальними позначками ---
        def get_visual_status(row):
            statuses = []
            if pd.notna(row['Час до виконання (хв)']) and row['Час до виконання (хв)'] > 15:
                statuses.append("🔴 >15 хв")
            if row['Підозріле повторення']:
                statuses.append("⚠️ Повтор")
            return ", ".join(statuses) if statuses else ""

        filtered_df['Статус'] = filtered_df.apply(get_visual_status, axis=1)

        # --- Визначення стовпців для відображення та редагування ---
        columns_to_display = [
            "Статус", "Ідентифікатор", "Дата створення", "Час створення", "Тип заявки", "Цех", 
            "Лінія", "Обладнання", "Опис робіт", "Відповідальні служби", 
            "Час до виконання (хв)", "Час до закриття (хв)", "Звіт про виконану роботу",
            "Реакція на заявки"
        ]
        filtered_columns_to_display = [col for col in columns_to_display if col in filtered_df.columns]

        # --- Єдина таблиця для редагування та перегляду ---
        st.subheader("📋 Таблиця заявок")
        st.markdown("Ви можете додати свої коментарі в стовпець **'Реакція на заявки'**.")
        
        editable_df = st.data_editor(
            filtered_df[filtered_columns_to_display].copy(),
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Реакція на заявки": st.column_config.TextColumn("Реакція на заявки"),
                "Статус": st.column_config.TextColumn("Статус", disabled=True),
                "Час до виконання (хв)": st.column_config.NumberColumn("Час до виконання (хв)", format="%.1f", disabled=True),
                "Час до закриття (хв)": st.column_config.NumberColumn("Час до закриття (хв)", format="%.1f", disabled=True),
            },
            disabled=[col for col in filtered_columns_to_display if col not in ["Реакція на заявки"]]
        )

        st.markdown("---")

        # --- Кнопки завантаження ---
        col1, col2 = st.columns(2)

        @st.cache_data
        def convert_df_to_csv(df_to_convert):
            df_to_convert = df_to_convert.drop(columns=['Статус'], errors='ignore')
            
            if 'Реакція на заявки' not in df_to_convert.columns:
                df_to_convert['Реакція на заявки'] = ''
            
            # Тепер використовуємо кому як роздільник і кодування utf-8-sig
            return df_to_convert.to_csv(index=False, sep=',', encoding='utf-8-sig')

        with col1:
            st.download_button(
                label="⬇️ Завантажити оновлений CSV",
                data=convert_df_to_csv(editable_df),
                file_name=f'оновлені_заявки_{pd.Timestamp.now().strftime("%Y-%m-%d")}.csv',
                mime='text/csv',
                help='Завантажити відфільтровану та відредаговану таблицю у форматі CSV'
            )

        with col2:
            commented_df = editable_df[editable_df['Реакція на заявки'].str.strip() != '']
            if not commented_df.empty:
                st.download_button(
                    label="⬇️ Завантажити звіт по коментарях",
                    data=convert_df_to_csv(commented_df),
                    file_name=f'звіт_по_коментарях_{pd.Timestamp.now().strftime("%Y-%m-%d")}.csv',
                    mime='text/csv',
                    help='Завантажити тільки ті заявки, до яких ви додали коментарі'
                )
            else:
                st.info("Щоб завантажити звіт, додайте коментарі хоча б до однієї заявки.")

        st.markdown("---")

        # --- Статистика (використовуємо відредагований датафрейм) ---
        st.subheader("📊 Аналіз даних")
        unique_tasks_df = editable_df.drop_duplicates(subset=['Ідентифікатор'])
        
        col_avg1, col_avg2 = st.columns(2)
        avg_виконання = unique_tasks_df['Час до виконання (хв)'].dropna().mean()
        avg_закриття = unique_tasks_df['Час до закриття (хв)'].dropna().mean()
        col_avg1.metric("Середній час до виконання (хв)", f"{avg_виконання:.1f}" if pd.notna(avg_виконання) else "Немає даних")
        col_avg2.metric("Середній час до закриття (хв)", f"{avg_закриття:.1f}" if pd.notna(avg_закриття) else "Немає даних")
        
        st.markdown("---")
        col_total1, col_total2 = st.columns(2) 
        total_execution_time_minutes = unique_tasks_df["Час до виконання (хв)"].dropna().sum() if "Час до виконання (хв)" in unique_tasks_df.columns else 0.0
        col_total1.metric("Загальний час до виконання (хв)", f"{total_execution_time_minutes:.1f}" if pd.notna(total_execution_time_minutes) else "Немає даних")
        total_downtime_minutes = 0.0
        downtime_types = ["Простій", "Простій РЦ"]
        if "Тип заявки" in unique_tasks_df.columns and "Час до виконання (хв)" in unique_tasks_df.columns:
            downtime_df = unique_tasks_df[unique_tasks_df["Тип заявки"].isin(downtime_types)]
            total_downtime_minutes = downtime_df["Час до виконання (хв)"].dropna().sum()
        col_total2.metric("Загальний час простою (хв)", f"{total_downtime_minutes:.1f}" if pd.notna(total_downtime_minutes) else "Немає даних")
        st.markdown("---")

        st.subheader("⚙️ Аналіз часу на машину")
        if "Обладнання" in editable_df.columns and not editable_df["Обладнання"].empty:
            st.markdown("##### Середній час до закриття по обладнанню")
            if not editable_df["Час до закриття (хв)"].dropna().empty:
                agg_avg_closure = unique_tasks_df.groupby("Обладнання")["Час до закриття (хв)"].mean().sort_values(ascending=False)
                fig_avg_closure = px.bar(agg_avg_closure, x=agg_avg_closure.index, y=agg_avg_closure.values, labels={'x':'Обладнання', 'y':'Середній час до закриття (хв)'}, title='Середній час до закриття по обладнанню', height=400)
                st.plotly_chart(fig_avg_closure, use_container_width=True)
            else:
                st.info("Немає даних для побудови графіка середнього часу до закриття по обладнанню.")
            
            st.markdown("##### Загальний час до виконання по обладнанню")
            if not editable_df["Час до виконання (хв)"].dropna().empty:
                agg_total_execution = unique_tasks_df.groupby("Обладнання")["Час до виконання (хв)"].sum().sort_values(ascending=False)
                fig_total_execution = px.bar(agg_total_execution, x=agg_total_execution.index, y=agg_total_execution.values, labels={'x':'Обладнання', 'y':'Загальний час до виконання (хв)'}, title='Загальний час до виконання по обладнанню', height=400)
                st.plotly_chart(fig_total_execution, use_container_width=True)
            else:
                st.info("Немає даних для побудови графіка загального часу до виконання по обладнанню.")
        else:
            st.info("Немає достатньо даних (або стовпця 'Обладнання') для аналізу часу на машину.")
        st.success("✅ Аналіз успішно завершено!")
    except Exception as e:
        st.error(f"❌ Виникла помилка під час обробки файлу: {e}")
        st.info(f"Деталі помилки: {type(e).__name__}: {e}")
        st.info("Будь ласка, перевірте ваш файл. Можливо, деякі стовпці відсутні або дані мають неочікуваний формат.")
elif df is None:
    st.info("⬆️ Будь ласка, завантажте CSV-файл, щоб розпочати аналіз.")
