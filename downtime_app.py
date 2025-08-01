import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from io import StringIO, BytesIO

st.set_page_config(layout="wide", page_title="Аналіз заявок по обладнанню", page_icon="⚙️")

st.title("⚙️ Аналіз заявок по обладнання")

st.markdown("""
    Завантажте ваш **CSV-файл** або **Excel-файл** з даними про заявки.
    
    **Особливості:**
    * **Пошук**: Використовуйте поле пошуку, щоб швидко знайти заявки за ідентифікатором або описом робіт.
    * **Єдина таблиця**: Ви бачите всі візуальні позначки (проблемний час, аномалії) в одній таблиці, де також можете додавати коментарі.
    * **Завантаження змін**: Тепер є дві кнопки для завантаження:
        1. **Оновлений Excel**: Завантажує повну таблицю з усіма вашими змінами.
        2. **Звіт по коментарях**: Завантажує файл лише з тими заявками, до яких ви додали коментарі.
    
    **Очікувані стовпці**:
    * "Дата створення" та "Час створення" (обов'язкові)
    * "Дата виконання" та "Час виконання" (якщо є)
    * А також: "Тип заявки", "Цех", "Лінія", "Обладнання", "Ідентифікатор", "Опис робіт", "Відповідальні служби".
""")

# --- Вибір джерела даних (тільки завантаження файлу з комп'ютера) ---
st.sidebar.header("Джерело даних")
df = None
uploaded_file = st.file_uploader("📂 Завантажте CSV або Excel файл", type=["csv", "xlsx"])

if uploaded_file:
    try:
        uploaded_file.seek(0)
        
        # Перевірка типу файлу за розширенням
        if uploaded_file.name.endswith('.csv'):
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

        elif uploaded_file.name.endswith('.xlsx'):
            df = pd.read_excel(uploaded_file, engine='openpyxl')
        
        st.success("✅ Файл успішно завантажено!")
    except Exception as e:
        st.error(f"❌ Виникла помилка під час завантаження файлу: {e}")
        st.info("Будь ласка, перевірте, чи файл не пошкоджений та чи є у ньому дані. Також переконайтесь, що формат файлу коректний (CSV або XLSX).")
        df = None

# --- Вся подальша логіка обробки даних тепер виконується тільки якщо df не порожній ---
if df is not None and not df.empty:
    try:
        # Перевірка наявності критично важливих стовпців
        critical_cols = ["Дата створення", "Час створення"]
        if not all(col in df.columns for col in critical_cols):
            missing_cols = [col for col in critical_cols if col not in df.columns]
            st.error(f"❌ У файлі відсутні критично важливі стовпці: {', '.join(missing_cols)}. Будь ласка, перевірте ваш файл.")
            st.stop()

        # Додавання відсутніх стовпців з дефолтними значеннями
        missing_cols_to_add = {
            "Звіт про виконану роботу": "",
            "Реакція на заявки": "",
            "Ідентифікатор": df.index + 1,
            "Обладнання": "Не вказано",
            "Опис робіт": "Без опису",
            "Відповідальні служби": "Не вказано"
        }
        for col, default_val in missing_cols_to_add.items():
            if col not in df.columns:
                df[col] = default_val
                st.info(f"ℹ️ Стовпець '{col}' відсутній у файлі і був доданий.")
        
        # --- Спрощена і надійна обробка дат та часу ---
        st.info("⚙️ Обробка стовпців з датами та часом...")
        
        # Об'єднання та перетворення стовпців дати і часу в один формат
        df['Час створення (datetime)'] = pd.to_datetime(df['Дата створення'].astype(str) + ' ' + df['Час створення'].astype(str), errors='coerce', dayfirst=True)
        if 'Дата виконання' in df.columns and 'Час виконання' in df.columns:
            df['Час виконання (datetime)'] = pd.to_datetime(df['Дата виконання'].astype(str) + ' ' + df['Час виконання'].astype(str), errors='coerce', dayfirst=True)
        else:
            df['Час виконання (datetime)'] = pd.NaT

        if 'Дата закриття' in df.columns and 'Час закриття' in df.columns:
            df['Час закриття (datetime)'] = pd.to_datetime(df['Дата закриття'].astype(str) + ' ' + df['Час закриття'].astype(str), errors='coerce', dayfirst=True)
        else:
            df['Час закриття (datetime)'] = pd.NaT
        
        # Видалення рядків з некоректними датами створення
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
        
        # Розрахунок різниці в часі, тепер це безпечно
        df["Час до виконання (хв)"] = (df["Час виконання (datetime)"] - df["Час створення (datetime)"]).dt.total_seconds() / 60
        df["Час до закриття (хв)"] = (df["Час закриття (datetime)"] - df["Час створення (datetime)"]).dt.total_seconds() / 60
        df["Дата створення (для фільтра)"] = df["Час створення (datetime)"].dt.date

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
        def convert_df_to_excel(df_to_convert):
            df_to_convert = df_to_convert.drop(columns=['Статус'], errors='ignore')
            
            if 'Реакція на заявки' not in df_to_convert.columns:
                df_to_convert['Реакція на заявки'] = ''
            
            output = BytesIO()
            df_to_convert.to_excel(output, index=False, engine='openpyxl')
            processed_data = output.getvalue()
            return processed_data

        with col1:
            st.download_button(
                label="⬇️ Завантажити оновлений Excel",
                data=convert_df_to_excel(editable_df),
                file_name=f'оновлені_заявки_{pd.Timestamp.now().strftime("%Y-%m-%d")}.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                help='Завантажити відфільтровану та відредаговану таблицю у форматі Excel'
            )

        with col2:
            commented_df = editable_df[editable_df['Реакція на заявки'].str.strip() != '']
            if not commented_df.empty:
                st.download_button(
                    label="⬇️ Завантажити звіт по коментарях",
                    data=convert_df_to_excel(commented_df),
                    file_name=f'звіт_по_коментарях_{pd.Timestamp.now().strftime("%Y-%m-%d")}.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
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
    st.info("⬆️ Будь ласка, завантажте CSV або Excel файл, щоб розпочати аналіз.")
    
