import sqlite3
import os


def check_and_update_schema(db_path='database/tutoring.db'):
    """Проверка и обновление структуры базы данных"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, db_path)

    print(f"📂 Проверка базы данных: {db_path}")

    # Создаем директорию для базы данных, если её нет
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    try:
        # Получаем список таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"📊 Найдено таблиц: {len(tables)}")

        # Проверяем таблицу schedule
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schedule'")
        if not cursor.fetchone():
            print("❌ Таблица schedule не существует!")
            return False

        # Проверяем колонки в таблице schedule
        cursor.execute("PRAGMA table_info(schedule)")
        schedule_columns = [column[1] for column in cursor.fetchall()]
        print(f"📝 Колонки в таблице schedule: {schedule_columns}")

        # Добавляем недостающие колонки в schedule
        if 'completed_at' not in schedule_columns:
            print("📝 Добавляем колонку completed_at в таблицу schedule...")
            cursor.execute('ALTER TABLE schedule ADD COLUMN completed_at DATETIME')
            print("✅ Колонка completed_at добавлена")

        if 'status' not in schedule_columns:
            print("📝 Добавляем колонку status в таблицу schedule...")
            cursor.execute('ALTER TABLE schedule ADD COLUMN status VARCHAR(20) DEFAULT "active"')
            print("✅ Колонка status добавлена")

        # Проверяем таблицу income
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='income'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(income)")
            income_columns = [column[1] for column in cursor.fetchall()]
            print(f"📝 Колонки в таблице income: {income_columns}")

            # Добавляем недостающие колонки в income
            if 'completed_at' not in income_columns:
                print("📝 Добавляем колонку completed_at в таблицу income...")
                cursor.execute('ALTER TABLE income ADD COLUMN completed_at DATETIME')
                print("✅ Колонка completed_at добавлена")

            if 'schedule_id' not in income_columns:
                print("📝 Добавляем колонку schedule_id в таблицу income...")
                cursor.execute('ALTER TABLE income ADD COLUMN schedule_id INTEGER')
                print("✅ Колонка schedule_id добавлена")

            if 'status' not in income_columns:
                print("📝 Добавляем колонку status в таблицу income...")
                cursor.execute('ALTER TABLE income ADD COLUMN status VARCHAR(20) DEFAULT "pending"')
                print("✅ Колонка status добавлена")

        connection.commit()
        print("✅ Структура базы данных обновлена")
        return True

    except sqlite3.Error as e:
        print(f"❌ Ошибка обновления структуры: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        connection.close()


def ensure_tutor_user(db_path='database/tutoring.db'):
    """Создание пользователя tutor, если его нет"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, db_path)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    try:
        # Проверяем, существует ли пользователь tutor
        cursor.execute("SELECT id FROM users WHERE username = 'tutor'")
        tutor = cursor.fetchone()

        if not tutor:
            print("👤 Создаем пользователя tutor...")
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, first_name, last_name, lesson_price, contact_info, is_active)
                VALUES ('tutor', 'tutor', 'tutor', 'Главный', 'Репетитор', 1500.00, 'tutor@example.com', 1)
            """)
            connection.commit()
            print("✅ Пользователь tutor создан")
            return True
        else:
            tutor_dict = dict(tutor)
            print(f"✅ Пользователь tutor уже существует (ID: {tutor_dict['id']})")
            # Обновляем пароль и статус
            cursor.execute("""
                UPDATE users 
                SET password_hash = 'tutor', 
                    is_active = 1,
                    role = 'tutor'
                WHERE username = 'tutor'
            """)
            connection.commit()
            print("✅ Данные пользователя tutor обновлены")
            return True

    except sqlite3.Error as e:
        print(f"❌ Ошибка работы с пользователем tutor: {e}")
        return False
    finally:
        connection.close()


if __name__ == '__main__':
    print("🔄 Обновление структуры базы данных...")
    check_and_update_schema()
    ensure_tutor_user()
    print("✅ Готово!")