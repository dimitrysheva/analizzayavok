import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px # Для кращих графіків, які можна масштабувати
from io import StringIO

st.set_page_config(layout="wide", page_title="Аналіз заявок по обладнанню", page_icon="⚙️")

st.title("⚙️ Аналіз заявок по обладнанню")

st.markdown("""
    Завантажте ваш **CSV-файл** з даними про заявки.
    
    **Особливості:**
    * **Редагування таблиці**: Ви можете додавати "Реакцію на заявки" у відповідний стовпець.
    * **Завантаження змін**: Після редагування ви можете завантажити оновлені дані у новому CSV-файлі.
    * **Розпізнавання даних**: Додаток намагається автоматично розпізнавати різні формати дат, часу та роздільники.
    * **Фільтрація**: Фільтри підтримують множинний вибір та діапазон дат.
    * **Виявлення підозрілих повторень**: Додаток аналізує дані на предмет повторень тієї ж проблеми на тому ж обладнанні протягом 3 днів та підсвічує такі випадки.
""")

# --- Вибір джерела даних (тільки завантаження файлу з комп'ютера) ---
st.sidebar.header("Джерело даних")

df = None # Ініціалізуємо DataFrame як None

uploaded_file = st.file_uploader("📂 Завантажте CSV-файл", type=["csv"])
if uploaded_file:
    try:
        uploaded_file.seek(0)
        # Спроба читання з різними роздільниками та кодуваннями
        try:
            df = pd.read_csv(uploaded_file, sep=';', encoding='utf-8')
        except Exception:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, sep=';', encoding='cp1251')
        
        if df.empty or len(df.columns) <= 2: # Якщо з ';' не вдалось або занадто мало колонок
            uploaded_file.seek(0)
            try:
                df = pd.read_csv(uploaded_file, sep=',', encoding='utf-8')
            except Exception:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, sep=',', encoding='cp1251')
        
        if df.empty or len(df.columns) <= 2: # Якщо з ',' не вдалось або занадто мало колонок
            uploaded_file.seek(0)
            try:
                df = pd.read_csv(uploaded_file, encoding='utf-8-sig') # Загальний випадок без явного роздільника
            except Exception:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding='cp1251')

        st.success("✅ Файл успішно завантажено!")
    except Exception as e:
        st.error(f"❌ Виникла помилка під час завантаження файлу: {e}")
        st.info("Будь ласка, перевірте, чи файл не пошкоджений та чи є у ньому дані.")
        df = None # Скидаємо df, щоб не продовжувати обробку


# --- Вся подальша логіка обробки даних тепер виконується тільки якщо df не порожній ---
if df is not None and not df.empty:
    try:
        # Перевірка наявності критично важливих стовпців
        critical_date_time_cols = ["Дата створення", "Час створення"]
        for col in critical_date_time_cols:
            if col not in df.columns:
                st.error(f"❌ У файлі відсутній критично важливий стовпець: '{col}'. Будь ласка, перевірте ваш файл.")
                st.stop()

        # Додаємо порожні стовпці, якщо їх немає
        if "Звіт про виконану роботу" not in df.columns:
            df["Звіт про виконану роботу"] = ""
            st.info("ℹ️ Стовпець 'Звіт про виконану роботу' відсутній у файлі і був доданий як порожній.")

        # --- НОВИЙ СТОВПЕЦЬ "Реакція на заявки" ---
        if "Реакція на заявки" not in df.columns:
            df["Реакція на заявки"] = ""
            st.info("ℹ️ Додано новий стовпець 'Реакція на заявки' для коментарів.")
        
        # Додаємо стовпець "Ідентифікатор", якщо його немає (для відображення та мержу аномалій)
        if "Ідентифікатор" not in df.columns:
            df["Ідентифікатор"] = df.index + 1 # Простий ідентифікатор за номером рядка
            st.info("ℹ️ Стовпець 'Ідентифікатор' відсутній у файлі і був доданий.")
        
        # Додаємо стовпець "Обладнання" якщо його немає (для уникнення помилок при агрегації та аналізі аномалій)
        if "Обладнання" not in df.columns:
            df["Обладнання"] = "Не вказано"
            st.info("ℹ️ Стовпець 'Обладнання' відсутній у файлі і був доданий зі значенням 'Не вказано'.")
        
        # Додаємо стовпець "Опис робіт" якщо його немає (для аналізу аномалій)
        if "Опис робіт" not in df.columns:
            df["Опис робіт"] = "Без опису"
            st.info("ℹ️ Стовпець 'Опис робіт' відсутній у файлі і був доданий зі значенням 'Без опису'.")

        # Додаємо стовпець "Відповідальні служби" якщо його немає (для уникнення помилок при фільтрації/відображенні)
        if "Відповідальні служби" not in df.columns:
            df["Відповідальні служби"] = "Не вказано"
            st.info("ℹ️ Стовпець 'Відповідальні служби' відсутній у файлі і був доданий зі значенням 'Не вказано'.")
        
        # --- Список поширених форматів дати та часу для автоматичного розпізнавання ---
        date_formats = [
            "%Y-%m-%d",    # 2025-07-06
            "%d.%m.%Y",    # 06.07.2025
            "%m/%d/%Y",    # 07/06/2025
            "%d/%m/%Y",    # 06/07/2025
            "%Y/%m/%d"     # 2025/07/06
        ]
        time_formats = [
            "%H:%M:%S",    # 12:31:00
            "%H:%M"        # 12:31
        ]
        
        # Комбіновані формати "Дата Час"
        combined_datetime_formats = [
            f"{d_fmt} {t_fmt}" for d_fmt in date_formats for t_fmt in time_formats
        ]
        # Додаємо специфічні та ISO формати
        combined_datetime_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%d.%m.%Y %H:%M:%S",
            "%d.%m.%Y %H:%M",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%Y-%m-%dT%H:%M:%S", # ISO format (наприклад, 2025-07-06T12:30:00)
        ] + combined_datetime_formats
        
        # Додаємо формати тільки для дати (якщо час відсутній)
        combined_datetime_formats.extend(date_formats)
        combined_datetime_formats = list(dict.fromkeys(combined_datetime_formats)) # Видаляємо дублікати

        def combine_and_convert_datetime(row, date_col_name, time_col_name=None):
            date_val = row.get(date_col_name)
            time_val = row.get(time_col_name) if time_col_name else None

            if pd.isna(date_val) and (time_col_name is None or pd.isna(time_val)):
                return np.nan
            
            # Обробка числових дат (як Excel)
            try:
                if pd.api.types.is_numeric_dtype(type(date_val)) and pd.notna(date_val):
                    # Базова дата для Excel (1900-01-01, але Excel рахує з 1900-01-01 як день 1, а 1900-02-29 був неіснуючим днем)
                    # тому 1899-12-30 є правильною базою для дати 1 = 1900-01-01
                    base_date = pd.to_datetime('1899-12-30')
                    converted_date = base_date + pd.to_timedelta(date_val, unit='D')
                    
                    if pd.notna(converted_date):
                        if time_col_name and pd.api.types.is_numeric_dtype(type(time_val)) and pd.notna(time_val):
                            # Час в Excel це частка дня (0 до 1)
                            converted_time = pd.to_timedelta(time_val, unit='D')
                            return converted_date + converted_time
                        return converted_date
            except Exception:
                pass # Продовжуємо намагатися з строковими форматами
            
            # Обробка строкових дат
            date_str = str(date_val).strip() if pd.notna(date_val) else ""
            time_str = str(time_val).strip() if pd.notna(time_val) else ""

            combined_str = ""
            if date_str and time_str:
                combined_str = f"{date_str} {time_str}"
            elif date_str:
                combined_str = date_str
            elif time_str: # Якщо є лише час, і немає дати, це може бути проблемою, але спробуємо
                combined_str = time_str
            
            if not combined_str:
                return np.nan

            # Спроба парсингу з відомими форматами
            for fmt in combined_datetime_formats:
                try:
                    return pd.to_datetime(combined_str, format=fmt)
                except (ValueError, TypeError):
                    continue
            
            # Якщо відомі формати не спрацювали, спробуємо infer_datetime_format
            try:
                return pd.to_datetime(combined_str, infer_datetime_format=True, errors='coerce')
            except (ValueError, TypeError):
                return np.nan

        df['Час створення (datetime)'] = df.apply(lambda row: combine_and_convert_datetime(row, 'Дата створення', 'Час створення'), axis=1)

        # Видалення рядків, де "Час створення" не вдалося розпізнати (NaT)
        initial_rows = len(df)
        df.dropna(subset=["Час створення (datetime)"], inplace=True)
        if len(df) < initial_rows:
            st.warning(f"⚠️ Видалено {initial_rows - len(df)} рядків через некоректний 'Час створення'. Будь ласка, перевірте вихідний файл. Можливо, деякі значення не відповідали очікуваним форматам.")

        if df.empty:
            st.warning("⚠️ Після обробки дат у файлі не залишилося дійсних даних. Будь ласка, перевірте вихідний файл.")
            st.stop()
        
        # Створюємо копію DataFrame перед операцією explode для аналізу аномалій.
        df_for_anomaly_detection = df.drop_duplicates(subset=['Ідентифікатор']).copy()

        # --- АНАЛІЗ АНОМАЛІЙ (ПІДОЗРІЛИХ ПОВТОРЕНЬ) ---
        if "Обладнання" in df_for_anomaly_detection.columns and "Опис робіт" in df_for_anomaly_detection.columns and "Час створення (datetime)" in df_for_anomaly_detection.columns:
            st.info("🕵️ Запускаємо пошук аномалій: повторення проблеми на одному обладнанні/лінії з тим же описом робіт протягом 3 днів.")
            
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
            st.warning("⚠️ Неможливо виконати аналіз аномалій: відсутні стовпці 'Обладнання' (або 'Лінія'), 'Опис робіт' або 'Час створення'.")
            df['Підозріле повторення'] = False

        # Продовжуємо обробку дат для інших стовпців
        df['Час виконання (datetime)'] = df.apply(lambda row: combine_and_convert_datetime(row, 'Дата виконання', 'Час виконання'), axis=1)
        df['Час закриття (datetime)'] = df.apply(lambda row: combine_and_convert_datetime(row, 'Дата закриття', 'Час закриття'), axis=1)
        df["Дата створення (для фільтра)"] = df["Час створення (datetime)"].dt.date
        df["Час до виконання (хв)"] = (df["Час виконання (datetime)"] - df["Час створення (datetime)"]).dt.total_seconds() / 60
        df["Час до закриття (хв)"] = (df["Час закриття (datetime)"] - df["Час створення (datetime)"]).dt.total_seconds() / 60

        # --- Розділення та "вибух" стовпця "Відповідальні служби" ---
        if "Відповідальні служби" in df.columns:
            df["Відповідальні служби"] = df["Відповідальні служби"].fillna("")
            df["Відповідальні служби"] = df["Відповідальні служби"].apply(
                lambda x: [s.strip() for s in str(x).split(',') if s.strip()] if pd.notna(x) else ["Не вказано"]
            )
            df = df.explode("Відповідальні служби")
            st.info("ℹ️ Стовпець 'Відповідальні служби' було оброблено для розділення кількох служб в одній комірці.")

        # --- Бокова панель для фільтрів ---
        st.sidebar.header("🔍 Фільтри даних")
        selected_types = []
        if "Тип заявки" in df.columns and not df["Тип заявки"].dropna().empty:
            типи_заявок = df["Тип заявки"].dropna().unique().tolist()
            selected_types = st.sidebar.multiselect("Оберіть тип(и) заявки", sorted(типи_заявок), default=типи_заявок)
        else:
            st.sidebar.info("Стовпець 'Тип заявки' не знайдено або він порожній. Фільтр вимкнено.")
        
        selected_workshops = []
        if "Цех" in df.columns and not df["Цех"].dropna().empty:
            цехи = df["Цех"].dropna().unique().tolist()
            selected_workshops = st.sidebar.multiselect("Оберіть цех(и)", sorted(цехи), default=цехи)
        else:
            st.sidebar.info("Стовпець 'Цех' не знайдено або він порожній. Фільтр вимкнено.")

        selected_responsible_services = []
        if "Відповідальні служби" in df.columns and not df["Відповідальні служби"].dropna().empty:
            responsible_services = df["Відповідальні служби"].dropna().unique().tolist()
            if "Не вказано" in responsible_services:
                responsible_services.remove("Не вказано")
                responsible_services.sort()
                responsible_services.append("Не вказано")
            else:
                responsible_services.sort()
            
            selected_responsible_services = st.sidebar.multiselect(
                "Оберіть відповідальну(і) службу(и)", 
                responsible_services, 
                default=responsible_services
            )
        else:
            st.sidebar.info("Стовпець 'Відповідальні служби' не знайдено або він порожній. Фільтр вимкнено.")
        
        filter_anomalies = st.sidebar.checkbox("Показати лише підозрілі повторення", value=False)
        
        min_date_available = df["Дата створення (для фільтра)"].min()
        max_date_available = df["Дата створення (для фільтра)"].max()

        if pd.isna(min_date_available) or pd.isna(max_date_available):
            st.error("❌ Неможливо визначити діапазон дат для фільтрації. Перевірте стовпці 'Дата створення' та 'Час створення' у вашому файлі.")
            st.stop()

        start_date = st.sidebar.date_input("Початкова дата", value=min_date_available, min_value=min_date_available, max_value=max_date_available)
        end_date = st.sidebar.date_input("Кінцева дата", value=max_date_available, min_value=min_date_available, max_value=max_date_available)

        # --- Застосування фільтрів ---
        filtered_df = df.copy()
        if selected_types and "Тип заявки" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Тип заявки"].isin(selected_types)]
        if selected_workshops and "Цех" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Цех"].isin(selected_workshops)]
        if selected_responsible_services and "Відповідальні служби" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Відповідальні служби"].isin(selected_responsible_services)]
        if filter_anomalies:
            filtered_df = filtered_df[filtered_df['Підозріле повторення'] == True]
        filtered_df = filtered_df[(filtered_df["Дата створення (для фільтра)"] >= start_date) & (filtered_df["Дата створення (для фільтра)"] <= end_date)]

        if filtered_df.empty:
            st.warning("⚠️ Після застосування вибраних фільтрів даних не знайдено. Спробуйте змінити критерії фільтрації.")
            st.stop()
        
        # --- Визначення стовпців для відображення та редагування ---
        columns_to_display = [
            "Ідентифікатор", "Дата створення", "Час створення", "Тип заявки", "Цех", 
            "Лінія", "Обладнання", "Опис робіт", "Відповідальні служби", 
            "Час до виконання (хв)", "Час до закриття (хв)", "Звіт про виконану роботу",
            "Реакція на заявки", "Підозріле повторення"
        ]
        
        # Вибираємо тільки ті, що існують у DataFrame
        filtered_columns_to_display = [col for col in columns_to_display if col in filtered_df.columns]

        # --- Таблиця для редагування ---
        st.subheader("📝 Таблиця заявок (редагування коментарів)")
        st.markdown("Ви можете додати свої коментарі у стовпець 'Реакція на заявки'.")
        
        editable_df = st.data_editor(
            filtered_df[filtered_columns_to_display].copy(), # Робимо копію для редагування
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Реакція на заявки": st.column_config.TextColumn("Реакція на заявки"),
                "Час до виконання (хв)": st.column_config.NumberColumn("Час до виконання (хв)", format="%.1f"),
                "Час до закриття (хв)": st.column_config.NumberColumn("Час до закриття (хв)", format="%.1f"),
                "Підозріле повторення": st.column_config.CheckboxColumn("Підозріле повторення", disabled=True)
            },
            disabled=[col for col in filtered_columns_to_display if col != "Реакція на заявки"] # Дозволяємо редагувати лише цей стовпець
        )

        # --- Кнопка завантаження ---
        @st.cache_data
        def convert_df_to_csv(df_to_convert):
            return df_to_convert.to_csv(index=False, sep=';', encoding='utf-8-sig')

        st.download_button(
            label="⬇️ Завантажити оновлений CSV",
            data=convert_df_to_csv(editable_df),
            file_name=f'оновлені_заявки_{pd.Timestamp.now().strftime("%Y-%m-%d")}.csv',
            mime='text/csv',
            help='Завантажити відфільтровану та відредаговану таблицю у форматі CSV'
        )

        st.markdown("---")

        # --- Таблиця для перегляду з виділенням ---
        st.subheader("📋 Таблиця заявок (для перегляду з виділенням)")
        st.markdown("Тут ви можете побачити візуальні виділення:")
        
        # Функції для виділення
        def highlight_over_15(val):
            return 'background-color: lightcoral' if pd.notna(val) and val > 15 else ''
        
        def highlight_anomaly_row(row):
            is_anomaly = row.get('Підозріле повторення', False) 
            if is_anomaly:
                return ['background-color: #ffcccc'] * len(row)
            else:
                return [''] * len(row)

        styled_df = editable_df[filtered_columns_to_display].style.apply(
            highlight_anomaly_row, axis=1
        ).applymap(
            highlight_over_15, subset=[col for col in ["Час до виконання (хв)", "Час до закриття (хв)"] if col in editable_df.columns]
        )
        
        st.dataframe(styled_df, use_container_width=True, height=400)
        
        st.markdown("---")

        # --- Статистика (використовуємо відредагований датафрейм) ---
        st.subheader("📊 Аналіз даних")
        col_avg1, col_avg2 = st.columns(2)
        unique_tasks_df = editable_df.drop_duplicates(subset=['Ідентифікатор'])
        avg_виконання = unique_tasks_df['Час до виконання (хв)'].dropna().mean()
        avg_закриття = unique_tasks_df['Час до закриття (хв)'].dropna().mean()
        col_avg1.metric("Середній час до виконання (хв)", f"{avg_виконання:.1f}" if pd.notna(avg_виконання) else "Немає даних")
        col_avg2.metric("Середній час до закриття (хв)", f"{avg_закриття:.1f}" if pd.notna(avg_закриття) else "Немає даних")
        st.markdown("---")

        st.subheader("📊 Сумарні показники часу")
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
            st.markdown("##### Загальний час простою по обладнанню (тільки для типів 'Простій', 'Простій РЦ')")
            if "Тип заявки" in editable_df.columns and "Час до виконання (хв)" in editable_df.columns:
                downtime_types = ["Простій", "Простій РЦ"]
                downtime_per_machine_df = unique_tasks_df[unique_tasks_df["Тип заявки"].isin(downtime_types)]
                if not downtime_per_machine_df.empty:
                    agg_total_downtime = downtime_per_machine_df.groupby("Обладнання")["Час до виконання (хв)"].sum().sort_values(ascending=False)
                    fig_total_downtime = px.bar(agg_total_downtime, x=agg_total_downtime.index, y=agg_total_downtime.values, labels={'x':'Обладнання', 'y':'Загальний час простою (хв)'}, title='Загальний час простою по обладнанню', height=400)
                    st.plotly_chart(fig_total_downtime, use_container_width=True)
                else:
                    st.info(f"Немає даних для побудови графіка загального часу простою по обладнанню (тип(и) заявки: {', '.join(downtime_types)}).")
            else:
                st.info("Немає достатньо даних (або стовпців 'Тип заявки'/'Час до виконання') для побудови графіка загального часу простою по обладнанню.")
        else:
            st.info("Немає достатньо даних (або стовпця 'Обладнання') для аналізу часу на машину.")
        st.success("✅ Аналіз успішно завершено!")
    except Exception as e:
        st.error(f"❌ Виникла помилка під час обробки файлу: {e}")
        st.info(f"Деталі помилки: {type(e).__name__}: {e}")
        st.info("Будь ласка, перевірте ваш файл. Можливо, деякі стовпці відсутні або дані мають неочікуваний формат. Переконайтеся, що дати та час вказані коректно. Спробуйте завантажити файл ще раз.")
elif df is None:
    st.info("⬆️ Будь ласка, завантажте CSV-файл, щоб розпочати аналіз.")
