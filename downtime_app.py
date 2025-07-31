import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px # Для кращих графіків, які можна масштабувати

st.set_page_config(layout="wide", page_title="Аналіз заявок по обладнанню", page_icon="⚙️")

st.title("⚙️ Аналіз заявок по обладнанню")

st.markdown("""
    Завантажте ваш **CSV-файл** з даними про заявки, або введіть URL до файлу онлайн.
    Цей застосунок тепер намагається автоматично розпізнавати різні формати дат та часу,
    враховуючи, що CSV-файли можуть використовувати крапку з комою (`;`) як роздільник
    і час може бути без секунд (наприклад, `ГГ:ХХ`).
    
    **Фільтри тепер підтримують множинний вибір**, що дозволяє комбінувати різні критерії, наприклад,
    вибрати декілька типів заявок або декілька цехів одночасно.
    
    **Очікувані стовпці**:
    * "Дата створення" та "Час створення" (обов'язкові)
    * "Дата виконання" та "Час виконання" (якщо є, окремо або в одному стовпці)
    * "Дата закриття" та "Час закриття" (якщо є, окремо або в одному стовпці)
    * А також: "Тип заявки", "Цех", "Лінія", "Обладнання", "Ідентифікатор", "Звіт про виконану роботу", "Відповідальні служби".
""")

# --- Вибір джерела даних ---
st.sidebar.header("Джерело даних")
data_source_option = st.sidebar.radio(
    "Оберіть, звідки завантажити дані:",
    ("Завантажити файл з комп'ютера", "Ввести URL файлу онлайн")
)

df = None # Ініціалізуємо DataFrame як None

if data_source_option == "Завантажити файл з комп'ютера":
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
            df = None # Скидаємо df, щоб не продовжувати обробку

elif data_source_option == "Ввести URL файлу онлайн":
    data_url = st.text_input("Введіть повний URL до CSV файлу (наприклад, https://example.com/my_data.csv):")
    if data_url:
        try:
            if data_url.endswith('.csv'):
                df = pd.read_csv(data_url, sep=';', encoding='utf-8')
                if df.empty or len(df.columns) <= 2:
                     df = pd.read_csv(data_url, sep=',', encoding='utf-8')
                     if df.empty or len(df.columns) <= 2:
                         df = pd.read_csv(data_url, encoding='utf-8-sig')
                         if df.empty or len(df.columns) <= 2:
                             df = pd.read_csv(data_url, encoding='cp1251')
            else:
                st.error("❌ Непідтримуваний формат файлу за URL. Будь ласка, введіть URL тільки до файлу .csv.")
                df = None
            st.success(f"✅ Дані успішно завантажено з: {data_url}")
        except Exception as e:
            st.error(f"❌ Не вдалося завантажити дані з URL: {e}. Перевірте URL, переконайтеся, що файл доступний публічно та його формат коректний.")
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

        # Додаємо порожній стовпець "Звіт про виконану роботу", якщо його немає
        if "Звіт про виконану роботу" not in df.columns:
            df["Звіт про виконану роботу"] = ""
            st.info("ℹ️ Стовпець 'Звіт про виконану роботу' відсутній у файлі і був доданий як порожній.")
        
        # Додаємо стовпець "Ідентифікатор", якщо його немає (для відображення)
        if "Ідентифікатор" not in df.columns:
            df["Ідентифікатор"] = df.index + 1 # Простий ідентифікатор за номером рядка
            st.info("ℹ️ Стовпець 'Ідентифікатор' відсутній у файлі і був доданий.")
        
        # Додаємо стовпець "Обладнання" якщо його немає (для уникнення помилок при агрегації)
        if "Обладнання" not in df.columns:
            df["Обладнання"] = "Не вказано"
            st.info("ℹ️ Стовпець 'Обладнання' відсутній у файлі і був доданий зі значенням 'Не вказано'.")

        # Додаємо стовпець "Відповідальні служби" якщо його немає (для уникнення помилок при фільтрації/відображенні)
        if "Відповідальні служби" not in df.columns:
            df["Відповідальні служби"] = "Не вказано"
            st.info("ℹ️ Стовпець 'Відповідальні служби' відсутній у файлі і був доданий зі значенням 'Не вказано'.")

        # --- НОВА ЛОГІКА: Розділення та "вибух" стовпця "Відповідальні служби" ---
        if "Відповідальні служби" in df.columns:
            # Замінюємо NaN на порожній рядок, щоб уникнути помилок при str.split
            df["Відповідальні служби"] = df["Відповідальні служби"].fillna("")
            
            # Розділяємо рядок за комою з можливими пробілами, потім обрізаємо пробіли
            # та видаляємо порожні рядки після розділення
            df["Відповідальні служби"] = df["Відповідальні служби"].apply(
                lambda x: [s.strip() for s in str(x).split(',') if s.strip()] if pd.notna(x) else ["Не вказано"]
            )
            
            # "Вибухаємо" DataFrame, створюючи новий рядок для кожної служби
            # Це дозволить коректно фільтрувати та аналізувати кожну службу окремо
            df = df.explode("Відповідальні служби")
            st.info("ℹ️ Стовпець 'Відповідальні служби' було оброблено для розділення кількох служб в одній комірці.")


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
        
        # Комбіновані формати (дата + пробіл + час)
        combined_datetime_formats = [
            f"{d_fmt} {t_fmt}" for d_fmt in date_formats for t_fmt in time_formats
        ]
        
        # Додаємо формати, де стовпець може містити лише повний datetime рядок (без розділення)
        # або лише дату. Додаємо їх на початку, щоб вони мали пріоритет, якщо вже повний рядок.
        combined_datetime_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%d.%m.%Y %H:%M:%S",
            "%d.%m.%Y %H:%M",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%Y-%m-%dT%H:%M:%S", # ISO format
        ] + combined_datetime_formats
        
        # Додаємо формати, що містять лише дату (без часу)
        combined_datetime_formats.extend(date_formats)
        
        # Видаляємо дублікати, зберігаючи порядок першої появи
        combined_datetime_formats = list(dict.fromkeys(combined_datetime_formats))


        # Функція для об'єднання дати та часу та спроби конвертації з декількома форматами
        def combine_and_convert_datetime(row, date_col_name, time_col_name=None):
            date_val = row.get(date_col_name)
            time_val = row.get(time_col_name) if time_col_name else None

            if pd.isna(date_val) and pd.isna(time_val):
                return np.nan

            # 1. Залишаємо спробу обробити числові дати на випадок, якщо CSV містить такі
            try:
                if pd.api.types.is_numeric_dtype(type(date_val)) and pd.notna(date_val):
                    base_date = pd.to_datetime('1899-12-30')
                    converted_date = base_date + pd.to_timedelta(date_val, unit='D')
                    
                    if pd.notna(converted_date):
                        if pd.api.types.is_numeric_dtype(type(time_val)) and pd.notna(time_val):
                            converted_time = pd.to_timedelta(time_val, unit='D')
                            return converted_date + converted_time
                        return converted_date
            except Exception:
                pass
            
            # 2. Якщо не вдалося обробити як числову дату, обробляємо як рядки
            date_str = str(date_val).strip() if pd.notna(date_val) else ""
            time_str = str(time_val).strip() if pd.notna(time_val) else ""

            combined_str = ""
            if date_str and time_str:
                combined_str = f"{date_str} {time_str}"
            elif date_str:
                combined_str = date_str
            elif time_str:
                combined_str = time_str
            
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

        # Обробка "Час створення"
        df['Час створення (datetime)'] = df.apply(lambda row: combine_and_convert_datetime(row, 'Дата створення', 'Час створення'), axis=1)

        # Обробка "Час виконання"
        if "Дата виконання" in df.columns and "Час виконання" in df.columns:
            df['Час виконання (datetime)'] = df.apply(lambda row: combine_and_convert_datetime(row, 'Дата виконання', 'Час виконання'), axis=1)
        elif "Час виконання" in df.columns:
            df['Час виконання (datetime)'] = df['Час виконання'].apply(lambda x: combine_and_convert_datetime({'val': x}, 'val'))
        else:
            df['Час виконання (datetime)'] = np.nan

        # Обробка "Час закриття"
        if "Дата закриття" in df.columns and "Час закриття" in df.columns:
            df['Час закриття (datetime)'] = df.apply(lambda row: combine_and_convert_datetime(row, 'Дата закриття', 'Час закриття'), axis=1)
        elif "Час закриття" in df.columns:
            df['Час закриття (datetime)'] = df['Час закриття'].apply(lambda x: combine_and_convert_datetime({'val': x}, 'val'))
        else:
            df['Час закриття (datetime)'] = np.nan

        # Видалення рядків, де "Час створення" не вдалося розпізнати (NaT)
        initial_rows = len(df)
        df.dropna(subset=["Час створення (datetime)"], inplace=True)
        if len(df) < initial_rows:
            st.warning(f"⚠️ Видалено {initial_rows - len(df)} рядків через некоректний 'Час створення'. Будь ласка, перевірте вихідний файл. Можливо, деякі значення не відповідали очікуваним форматам.")

        # Перевірка, чи є дані після очищення
        if df.empty:
            st.warning("⚠️ Після обробки дат у файлі не залишилося дійсних даних. Будь ласка, перевірте вихідний файл.")
            st.stop()

        # Дата створення заявки (для фільтра) - тепер беремо з нового об'єднаного стовпця
        df["Дата створення (для фільтра)"] = df["Час створення (datetime)"].dt.date

        # Розрахунок тривалості, використовуючи об'єднані datetime стовпці
        df["Час до виконання (хв)"] = (df["Час виконання (datetime)"] - df["Час створення (datetime)"]).dt.total_seconds() / 60
        df["Час до закриття (хв)"] = (df["Час закриття (datetime)"] - df["Час створення (datetime)"]).dt.total_seconds() / 60

        # --- Бокова панель для фільтрів ---
        st.sidebar.header("🔍 Фільтри даних")

        # Фільтр по типу заявки (тепер multiselect)
        selected_types = []
        if "Тип заявки" in df.columns and not df["Тип заявки"].dropna().empty:
            типи_заявок = df["Тип заявки"].dropna().unique().tolist()
            selected_types = st.sidebar.multiselect("Оберіть тип(и) заявки", sorted(типи_заявок), default=типи_заявок)
            
        else:
            st.sidebar.info("Стовпець 'Тип заявки' не знайдено або він порожній. Фільтр вимкнено.")
        

        # Фільтр по цеху (тепер multiselect)
        selected_workshops = []
        if "Цех" in df.columns and not df["Цех"].dropna().empty:
            цехи = df["Цех"].dropna().unique().tolist()
            selected_workshops = st.sidebar.multiselect("Оберіть цех(и)", sorted(цехи), default=цехи)
        else:
            st.sidebar.info("Стовпець 'Цех' не знайдено або він порожній. Фільтр вимкнено.")

        # --- ФІЛЬТР: Відповідальні служби (тепер коректно розділені) ---
        selected_responsible_services = []
        if "Відповідальні служби" in df.columns and not df["Відповідальні служби"].dropna().empty:
            # Тепер unique() поверне коректні окремі служби завдяки df.explode() вище
            responsible_services = df["Відповідальні служби"].dropna().unique().tolist()
            # Фільтруємо "Не вказано", якщо воно є, і переміщуємо в кінець
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


        # Фільтр по даті створення (використовуємо "Дата створення (для фільтра)")
        min_date_available = df["Дата створення (для фільтра)"].min()
        max_date_available = df["Дата створення (для фільтра)"].max()

        if pd.isna(min_date_available) or pd.isna(max_date_available):
            st.error("❌ Неможливо визначити діапазон дат для фільтрації. Перевірте стовпці 'Дата створення' та 'Час створення' у вашому файлі. Можливо, всі значення є недійсними.")
            st.stop()

        start_date = st.sidebar.date_input("Початкова дата", value=min_date_available, min_value=min_date_available, max_value=max_date_available)
        end_date = st.sidebar.date_input("Кінцева дата", value=max_date_available, min_value=min_date_available, max_value=max_date_available)


        # --- Застосування фільтрів ---
        filtered_df = df.copy()

        # Фільтруємо за Типом заявки
        if selected_types and "Тип заявки" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Тип заявки"].isin(selected_types)]

        # Фільтруємо за Цехом
        if selected_workshops and "Цех" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Цех"].isin(selected_workshops)]
        
        # --- ЗАСТОСУВАННЯ ВДОСКОНАЛЕНОГО ФІЛЬТРУ ---
        if selected_responsible_services and "Відповідальні служби" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Відповідальні служби"].isin(selected_responsible_services)]


        # Фільтруємо за "Дата створення (для фільтра)"
        filtered_df = filtered_df[(filtered_df["Дата створення (для фільтра)"] >= start_date) & (filtered_df["Дата створення (для фільтра)"] <= end_date)]

        if filtered_df.empty:
            st.warning("⚠️ Після застосування вибраних фільтрів даних не знайдено. Спробуйте змінити критерії фільтрації.")
            st.stop()

        # --- Підсвічування значень понад 15 хв ---
        def highlight_over_15(val):
            return 'background-color: lightcoral' if pd.notna(val) and val > 15 else ''

        # --- Таблиця ---
        стовпці = [
            "Ідентифікатор",
            "Дата створення",
            "Час створення",
            "Дата виконання",
            "Час виконання",
            "Дата закриття",
            "Час закриття",
            "Тип заявки",
            "Цех",
            "Лінія",
            "Обладнання",
            "Відповідальні служби", 
            "Час до виконання (хв)",
            "Час до закриття (хв)",
            "Звіт про виконану роботу"
        ]

        # Для відображення в таблиці, можливо, краще згрупувати назад, або просто показувати як є
        # Але для фільтрів і подальшого аналізу "вибух" є критичним.
        # Якщо потрібно, щоб у таблиці знову відображалося кілька служб через кому,
        # але фільтри працювали по окремих службах, то це складніша логіка з duplcated() та ін.
        # Наразі, таблиця буде показувати по одній службі на рядок, дублюючи інші дані.
        # Це стандартна поведінка після df.explode().

        стовпці_для_відображення = [col for col in стовпці if col in filtered_df.columns]

        if not стовпці_для_відображення:
            st.warning("⚠️ Немає відповідних стовпців для відображення в таблиці. Перевірте імена стовпців.")
            st.stop()

        styled_df = filtered_df[стовпці_для_відображення].style.applymap(
            highlight_over_15, subset=[col for col in ["Час до виконання (хв)", "Час до закриття (хв)"] if col in filtered_df.columns and col in стовпці_для_відображення]
        )

        st.subheader("📋 Таблиця заявок")
        st.dataframe(styled_df, use_container_width=True, height=500)

        st.markdown("---")

        # --- Статистика ---
        st.subheader("📊 Середні показники часу")
        col_avg1, col_avg2 = st.columns(2)

        # Оскільки df.explode() дублює рядки, для середніх значень потрібно бути обережними.
        # Якщо кожна служба окремо подана на заявку, тоді все ок.
        # Якщо одна заявка має кілька служб, і ми хочемо уникнути дублювання при розрахунку середнього
        # часу для *самої заявки*, то треба використовувати вихідний DataFrame або видаляти дублікати
        # за "Ідентифікатором" для розрахунку агрегацій, які стосуються унікальних заявок.
        # Наразі, розрахунок агрегацій після explode буде враховувати кожну пару (заявка, служба) окремо.
        # Це може бути бажаною поведінкою, якщо ми хочемо бачити, наскільки ефективні служби
        # для заявок, які до них надходять (навіть якщо одна заявка пішла до кількох).

        # Для агрегації за унікальними заявками, можна тимчасово видалити дублікати за Ідентифікатором
        # або групувати за Ідентифікатором перед агрегацією.
        # Залишаю як є, тому що для подальших графіків "по обладнанню" така денормалізація може бути корисною.
        
        avg_виконання = filtered_df['Час до виконання (хв)'].dropna().mean()
        avg_закриття = filtered_df['Час до закриття (хв)'].dropna().mean()

        col_avg1.metric("Середній час до виконання (хв)", f"{avg_виконання:.1f}" if pd.notna(avg_виконання) else "Немає даних")
        col_avg2.metric("Середній час до закриття (хв)", f"{avg_закриття:.1f}" if pd.notna(avg_закриття) else "Немає даних")

        st.markdown("---")

        st.subheader("📊 Сумарні показники часу")
        col_total1, col_total2 = st.columns(2) 

        # Для сумарних показників часу, щоб уникнути подвійного обліку,
        # ми повинні унікалізувати заявки перед сумуванням, якщо заявка подавалася до кількох служб.
        # Або ж, якщо мета – сумувати "зусилля" по службах, то поточний підхід після explode підходить.
        # Припустімо, що для загального часу ми хочемо сумувати час унікальних завдань.
        
        # Створимо тимчасовий DF з унікальними Ідентифікаторами для коректного сумування
        unique_tasks_df = filtered_df.drop_duplicates(subset=['Ідентифікатор'])

        total_execution_time_minutes = 0.0
        if "Час до виконання (хв)" in unique_tasks_df.columns:
            total_execution_time_minutes = unique_tasks_df["Час до виконання (хв)"].dropna().sum()
        
        col_total1.metric("Загальний час до виконання (хв)", f"{total_execution_time_minutes:.1f}" if pd.notna(total_execution_time_minutes) else "Немає даних")

        total_downtime_minutes = 0.0
        downtime_types = ["Простій", "Простій РЦ"] 

        if "Тип заявки" in unique_tasks_df.columns and "Час до виконання (хв)" in unique_tasks_df.columns:
            downtime_df = unique_tasks_df[unique_tasks_df["Тип заявки"].isin(downtime_types)]
            total_downtime_minutes = downtime_df["Час до виконання (хв)"].dropna().sum()
        
        col_total2.metric("Загальний час простою (хв)", f"{total_downtime_minutes:.1f}" if pd.notna(total_downtime_minutes) else "Немає даних")
        
        if total_downtime_minutes == 0 and ("Тип заявки" not in unique_tasks_df.columns or not unique_tasks_df[unique_tasks_df["Тип заявки"].isin(downtime_types)].empty):
            st.info(f"ℹ️ Для розрахунку 'Загального часу простою' враховуються заявки з типом: {', '.join(downtime_types)} та розраховується як час до виконання. Переконайтеся, що такі типи присутні у відфільтрованих даних.")


        st.markdown("---")

        # --- Аналіз часу на машину ---
        st.subheader("⚙️ Аналіз часу на машину")

        if "Обладнання" in filtered_df.columns and not filtered_df["Обладнання"].empty:
            # Для агрегації по обладнанню, денормалізований DF підходить, оскільки кожна "заявка-служба" пара важлива
            
            # 1. Середній час до закриття по обладнанню
            st.markdown("##### Середній час до закриття по обладнанню")
            if not filtered_df["Час до закриття (хв)"].dropna().empty:
                agg_avg_closure = filtered_df.groupby("Обладнання")["Час до закриття (хв)"].mean().sort_values(ascending=False)
                fig_avg_closure = px.bar(agg_avg_closure, 
                                        x=agg_avg_closure.index, 
                                        y=agg_avg_closure.values,
                                        labels={'x':'Обладнання', 'y':'Середній час до закриття (хв)'},
                                        title='Середній час до закриття по обладнанню')
                st.plotly_chart(fig_avg_closure, use_container_width=True)
            else:
                st.info("Немає даних для побудови графіка середнього часу до закриття по обладнанню.")

            # 2. Загальний час до виконання по обладнанню
            st.markdown("##### Загальний час до виконання по обладнанню")
            if not filtered_df["Час до виконання (хв)"].dropna().empty:
                agg_total_execution = filtered_df.groupby("Обладнання")["Час до виконання (хв)"].sum().sort_values(ascending=False)
                fig_total_execution = px.bar(agg_total_execution, 
                                            x=agg_total_execution.index, 
                                            y=agg_total_execution.values,
                                            labels={'x':'Обладнання', 'y':'Загальний час до виконання (хв)'},
                                            title='Загальний час до виконання по обладнанню')
                st.plotly_chart(fig_total_execution, use_container_width=True)
            else:
                st.info("Немає даних для побудови графіка загального часу до виконання по обладнанню.")

            # 3. Загальний час простою по обладнанню
            st.markdown("##### Загальний час простою по обладнанню (тільки для типів 'Простій', 'Простій РЦ')")
            if "Тип заявки" in filtered_df.columns and "Час до виконання (хв)" in filtered_df.columns:
                downtime_types = ["Простій", "Простій РЦ"]
                downtime_per_machine_df = filtered_df[filtered_df["Тип заявки"].isin(downtime_types)]
                
                if not downtime_per_machine_df.empty:
                    agg_total_downtime = downtime_per_machine_df.groupby("Обладнання")["Час до виконання (хв)"].sum().sort_values(ascending=False)
                    fig_total_downtime = px.bar(agg_total_downtime, 
                                                x=agg_total_downtime.index, 
                                                y=agg_total_downtime.values,
                                                labels={'x':'Обладнання', 'y':'Загальний час простою (хв)'},
                                                title='Загальний час простою по обладнанню')
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
        st.info("Будь ласка, перевірте ваш файл. Можливо, деякі стовпці відсутні або дані мають неочікуваний формат. Переконайтеся, що дати та час вказані коректно. Спробуйте завантажити файл ще раз.")
elif df is None:
    st.info("⬆️ Будь ласка, завантажте CSV-файл, або введіть URL, щоб розпочати аналіз.")