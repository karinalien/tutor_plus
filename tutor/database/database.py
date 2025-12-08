import sqlite3
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta


class Database:
    def __init__(self, db_path='database/tutoring.db'):
        # Если путь относительный, делаем его абсолютным относительно текущего файла
        if not os.path.isabs(db_path):
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Если путь начинается с 'database/', ищем относительно текущего файла
            if db_path.startswith('database/'):
                self.db_path = os.path.join(current_dir, os.path.basename(db_path))
            else:
                self.db_path = os.path.join(os.path.dirname(current_dir), db_path)
        else:
            self.db_path = db_path
        print(f"📂 Путь к базе данных: {self.db_path}")

    def get_connection(self):
        try:
            # Создаем директорию для базы данных, если её нет
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            connection = sqlite3.connect(self.db_path)
            connection.row_factory = sqlite3.Row
            return connection
        except sqlite3.Error as e:
            print(f"❌ Ошибка подключения: {e}")
            return None

    def connect(self):
        return self.get_connection()

    def create_tables(self):
        """Создание таблиц из SQL скрипта"""
        connection = self.get_connection()
        if not connection:
            print("❌ Не удалось подключиться к базе данных")
            return

        try:
            # Определяем путь к schema.sql относительно текущего файла database.py
            current_dir = os.path.dirname(os.path.abspath(__file__))
            schema_path = os.path.join(current_dir, 'schema.sql')

            if not os.path.exists(schema_path):
                print(f"❌ Файл schema.sql не найден!")
                print(f"   Искали в: {schema_path}")
                print(f"   Текущая директория файла: {current_dir}")
                print(f"   Рабочая директория: {os.getcwd()}")
                return

            print(f"📁 Чтение {schema_path}...")
            with open(schema_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()
                print(f"📄 Размер скрипта: {len(sql_script)} символов")

            cursor = connection.cursor()
            cursor.executescript(sql_script)
            connection.commit()
            print("✅ Таблицы созданы")

            # Проверка, создалась ли таблица users
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            table_exists = cursor.fetchone()
            if table_exists:
                print("✅ Таблица users существует")
                # Проверка, создался ли пользователь tutor
                cursor.execute("SELECT COUNT(*) as count FROM users WHERE username = 'tutor'")
                result = cursor.fetchone()
                print(f"👤 Пользователей 'tutor' в базе: {result['count']}")
            else:
                print("❌ Таблица users не создана!")

        except Exception as e:
            print(f"❌ Ошибка создания таблиц: {e}")
            import traceback
            traceback.print_exc()
        finally:
            connection.close()

    def check_and_update_schema(self):
        """Проверка и обновление структуры базы данных"""
        connection = self.get_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()

            # Проверяем существование таблицы schedule
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schedule'")
            if not cursor.fetchone():
                print("❌ Таблица schedule не существует!")
                return False

            # Проверяем существование колонки lesson_type в таблице schedule
            cursor.execute("PRAGMA table_info(schedule)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'lesson_type' not in columns:
                print("📝 Добавляем колонку lesson_type в таблицу schedule...")
                cursor.execute('ALTER TABLE schedule ADD COLUMN lesson_type VARCHAR(20) DEFAULT "regular"')
                connection.commit()
                print("✅ Колонка lesson_type добавлена в таблицу schedule")

            # Проверяем таблицу income для недостающих колонок
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='income'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(income)")
                income_columns = [column[1] for column in cursor.fetchall()]

                # Проверяем наличие колонки schedule_id
                if 'schedule_id' not in income_columns:
                    print("📝 Добавляем колонку schedule_id в таблицу income...")
                    cursor.execute('ALTER TABLE income ADD COLUMN schedule_id INTEGER')
                    print("✅ Колонка schedule_id добавлена в таблицу income")

                # Проверяем наличие колонки status
                if 'status' not in income_columns:
                    print("📝 Добавляем колонку status в таблицу income...")
                    cursor.execute('ALTER TABLE income ADD COLUMN status VARCHAR(20) DEFAULT "pending"')
                    print("✅ Колонка status добавлена в таблицу income")

                # Проверяем наличие колонки completed_at
                if 'completed_at' not in income_columns:
                    print("📝 Добавляем колонку completed_at в таблицу income...")
                    cursor.execute('ALTER TABLE income ADD COLUMN completed_at DATETIME')
                    print("✅ Колонка completed_at добавлена в таблицу income")

            connection.commit()
            return True

        except sqlite3.Error as e:
            print(f"❌ Ошибка проверки структуры базы данных: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            connection.close()

    def authenticate_user(self, username: str, password: str):
        """Аутентификация пользователя"""
        connection = self.get_connection()
        if not connection:
            return None

        try:
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()

            if not user:
                print(f"❌ Пользователь '{username}' не найден")
                return None

            user_dict = dict(user)
            print(f"✅ Пользователь найден: {user_dict}")

            # Простое сравнение паролей
            if user_dict['password_hash'] == password:
                print("✅ Пароль верный!")
                return user_dict
            else:
                print("❌ Неверный пароль")
                return None

        except sqlite3.Error as e:
            print(f"❌ Ошибка аутентификации: {e}")
            return None
        finally:
            connection.close()

    def create_student(self, username, password, first_name, last_name, tutor_id, contact_info, exam_type, lesson_price,
                       day_of_week, lesson_time):
        """Создание нового ученика с автоматическим расписанием"""
        connection = self.get_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()

            # Проверяем, существует ли уже пользователь с таким логином
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            if cursor.fetchone():
                print(f"❌ Пользователь с логином '{username}' уже существует")
                return False

            # Создаем пользователя
            cursor.execute('''
                INSERT INTO users (
                    username, password_hash, role, first_name, last_name, 
                    exam_type, lesson_price, contact_info, created_by, is_active,
                    schedule_day, schedule_time  # Добавляем поля расписания в пользователя
                ) VALUES (?, ?, 'student', ?, ?, ?, ?, ?, ?, 1, ?, ?)
            ''', (username, password, first_name, last_name, exam_type, lesson_price, contact_info, tutor_id,
                  day_of_week, lesson_time))

            student_id = cursor.lastrowid

            # Создаем тему для занятий
            cursor.execute('''
                INSERT INTO topics (title, description, created_by)
                VALUES (?, ?, ?)
            ''', (
                f'Занятия с {first_name} {last_name}', f'Регулярные занятия по подготовке к {exam_type.upper()}',
                tutor_id))

            topic_id = cursor.lastrowid

            # Вычисляем время окончания (занятие длится 1 час)
            start_dt = datetime.strptime(lesson_time, '%H:%M')
            end_dt = start_dt + timedelta(hours=1)
            end_time = end_dt.strftime('%H:%M')

            # Создаем РЕГУЛЯРНОЕ расписание
            cursor.execute('''
                INSERT INTO schedule (student_id, tutor_id, topic_id, day_of_week, start_time, end_time, status, lesson_type)
                VALUES (?, ?, ?, ?, ?, ?, 'active', 'regular')
            ''', (student_id, tutor_id, topic_id, day_of_week, lesson_time, end_time))

            schedule_id = cursor.lastrowid

            # Создаем запись о доходе (предварительную, без статуса paid)
            current_date = datetime.now()
            month_year = current_date.strftime('%Y-%m')

            cursor.execute('''
                INSERT INTO income (schedule_id, student_id, amount, payment_date, month_year, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
            ''', (schedule_id, student_id, lesson_price, current_date.strftime('%Y-%m-%d'), month_year))

            connection.commit()

            print(f"✅ Ученик создан: {first_name} {last_name} (ID: {student_id})")
            print(f"📅 Автоматическое расписание: {day_of_week} {lesson_time}-{end_time} (регулярное)")
            return student_id

        except sqlite3.Error as e:
            print(f"❌ Ошибка при создании ученика: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            connection.close()

    def get_tutor_students(self, tutor_id: int):
        """Получение всех учеников репетитора без дублирования"""
        connection = self.get_connection()
        if not connection:
            return []

        try:
            cursor = connection.cursor()

            # Используем GROUP BY чтобы получить уникальных учеников
            cursor.execute("""
                SELECT 
                    u.id, u.username, u.first_name, u.last_name, 
                    u.exam_type, u.lesson_price, u.contact_info, u.created_at,
                    GROUP_CONCAT(DISTINCT s.day_of_week || ' ' || s.start_time) as schedule_info
                FROM users u
                LEFT JOIN schedule s ON u.id = s.student_id AND s.status = 'active'
                WHERE u.created_by = ? AND u.role = 'student' AND u.is_active = 1
                GROUP BY u.id
                ORDER BY u.created_at DESC
            """, (tutor_id,))

            students = []
            for row in cursor.fetchall():
                student = dict(row)
                # Добавляем вычисляемые поля для отображения
                student['lesson_count'] = self.get_student_lesson_count(student['id'])
                student['schedule_info'] = student.get('schedule_info', '')
                students.append(student)

            print(f"📊 Найдено уникальных учеников: {len(students)}")
            return students

        except sqlite3.Error as e:
            print(f"❌ Ошибка получения учеников: {e}")
            return []
        finally:
            connection.close()

    def update_schema(self):
        """Обновление схемы базы данных - добавление недостающих колонок"""
        connection = self.get_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()

            # Проверяем существование колонки exam_type в users
            cursor.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in cursor.fetchall()]

            # Добавляем exam_type если его нет
            if 'exam_type' not in columns:
                print("📝 Добавляем колонку exam_type в таблицу users...")
                cursor.execute('ALTER TABLE users ADD COLUMN exam_type VARCHAR(10) CHECK (exam_type IN ("oge", "ege"))')
                connection.commit()
                print("✅ Колонка exam_type добавлена в таблицу users")

            return True

        except sqlite3.Error as e:
            print(f"❌ Ошибка обновления схемы: {e}")
            return False
        finally:
            connection.close()

    def ensure_tutor_user(self):
        """Создание пользователя tutor, если его нет"""
        connection = self.get_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()

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
                # Обновляем пароль и статус на случай, если они были изменены
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
            print(f"❌ Ошибка создания пользователя tutor: {e}")
            return False
        finally:
            connection.close()

    def get_student_schedule(self, student_id: int):
        """Получение расписания ученика"""
        connection = self.get_connection()
        if not connection:
            return []

        try:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT s.id, s.day_of_week, s.start_time, s.end_time, s.lesson_link, s.status,
                       t.title as topic_title, u.first_name as tutor_name
                FROM schedule s
                JOIN topics t ON s.topic_id = t.id
                JOIN users u ON s.tutor_id = u.id
                WHERE s.student_id = ? AND s.status = 'active'
                ORDER BY 
                    CASE s.day_of_week
                        WHEN 'monday' THEN 1
                        WHEN 'tuesday' THEN 2
                        WHEN 'wednesday' THEN 3
                        WHEN 'thursday' THEN 4
                        WHEN 'friday' THEN 5
                        WHEN 'saturday' THEN 6
                        WHEN 'sunday' THEN 7
                    END,
                    s.start_time
            """, (student_id,))
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"❌ Ошибка получения расписания: {e}")
            return []
        finally:
            connection.close()

    def get_tutor_schedule(self, tutor_id: int):
        """Получение расписания репетитора"""
        connection = self.get_connection()
        if not connection:
            return []

        try:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT s.id, s.day_of_week, s.start_time, s.end_time, s.lesson_link, s.status,
                       t.title as topic_title, 
                       u.first_name as student_name, u.last_name as student_last_name
                FROM schedule s
                JOIN topics t ON s.topic_id = t.id
                JOIN users u ON s.student_id = u.id
                WHERE s.tutor_id = ? AND s.status = 'active'
                ORDER BY 
                    CASE s.day_of_week
                        WHEN 'monday' THEN 1
                        WHEN 'tuesday' THEN 2
                        WHEN 'wednesday' THEN 3
                        WHEN 'thursday' THEN 4
                        WHEN 'friday' THEN 5
                        WHEN 'saturday' THEN 6
                        WHEN 'sunday' THEN 7
                    END,
                    s.start_time
            """, (tutor_id,))
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"❌ Ошибка получения расписания репетитора: {e}")
            return []
        finally:
            connection.close()

    def get_student_lesson_count(self, student_id: int):
        """Получение количества занятий ученика"""
        connection = self.get_connection()
        if not connection:
            return 0

        try:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM lessons 
                WHERE schedule_id IN (
                    SELECT id FROM schedule WHERE student_id = ?
                )
            """, (student_id,))

            result = cursor.fetchone()
            return result['count'] if result else 0

        except sqlite3.Error as e:
            print(f"❌ Ошибка получения количества занятий: {e}")
            return 0
        finally:
            connection.close()

    def get_monthly_income_by_month(self, tutor_id, year, month):
        """Получение дохода за конкретный месяц из таблицы income"""
        connection = self.get_connection()
        if not connection:
            return 0

        try:
            cursor = connection.cursor()
            # Сумма по всем статусам за указанный месяц
            cursor.execute("""
                SELECT COALESCE(SUM(i.amount), 0) as total_income
                FROM income i
                JOIN schedule s ON i.schedule_id = s.id
                WHERE s.tutor_id = ? 
                AND strftime('%Y', i.payment_date) = ?
                AND strftime('%m', i.payment_date) = ?
            """, (tutor_id, str(year), str(month).zfill(2)))

            result = cursor.fetchone()
            return result['total_income'] if result else 0

        except sqlite3.Error as e:
            print(f"❌ Ошибка получения дохода за месяц {month}.{year}: {e}")
            return 0
        finally:
            connection.close()

    def get_current_month_income(self, tutor_id):
        """Получение дохода за текущий месяц (декабрь 2025)"""
        current_date = datetime.now()
        current_year = current_date.year
        current_month = current_date.month

        # Если сейчас декабрь 2025, считаем за декабрь
        if current_year == 2025 and current_month == 12:
            return self.get_monthly_income_by_month(tutor_id, 2025, 12)

        return self.get_monthly_income_by_month(tutor_id, current_year, current_month)

    def get_yearly_income_2025_sep_nov(self, tutor_id):
        """Получение дохода за 2025 год (сентябрь-ноябрь)"""
        current_date = datetime.now()
        current_year = current_date.year

        # Если не 2025 год, возвращаем 0
        if current_year != 2025:
            return 0

        total_income = 0

        # Суммируем доходы за сентябрь, октябрь, ноябрь 2025 года
        # Независимо от текущего месяца, считаем только сентябрь-ноябрь
        for month in range(9, 12):  # сентябрь(9), октябрь(10), ноябрь(11)
            month_income = self.get_monthly_income_by_month(tutor_id, 2025, month)
            total_income += month_income

        return total_income

    def get_monthly_forecast_december_2025(self, tutor_id):
        """Прогноз дохода на декабрь 2025"""
        connection = self.get_connection()
        if not connection:
            return 0

        try:
            cursor = connection.cursor()

            # Получаем всех активных учеников с их стоимостью занятий
            cursor.execute("""
                SELECT lesson_price, exam_type
                FROM users 
                WHERE created_by = ? AND role = 'student' AND is_active = 1
            """, (tutor_id,))

            students = cursor.fetchall()

            # Прогноз на декабрь: 4 занятия в месяц на ученика
            total_forecast = 0
            for student in students:
                lesson_price = student['lesson_price'] or 1500
                total_forecast += lesson_price * 4

            return total_forecast

        except sqlite3.Error as e:
            print(f"❌ Ошибка расчета прогноза на декабрь: {e}")
            return 0
        finally:
            connection.close()

    def get_average_lesson_price_active(self, tutor_id):
        """Средняя стоимость занятия по активным ученикам"""
        connection = self.get_connection()
        if not connection:
            return 1500

        try:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT AVG(lesson_price) as avg_price
                FROM users 
                WHERE created_by = ? AND role = 'student' AND is_active = 1
            """, (tutor_id,))

            result = cursor.fetchone()
            return result['avg_price'] if result and result['avg_price'] else 1500

        except sqlite3.Error as e:
            print(f"❌ Ошибка получения средней стоимости: {e}")
            return 1500
        finally:
            connection.close()

    def get_active_students_count(self, tutor_id):
        """Количество активных учеников"""
        connection = self.get_connection()
        if not connection:
            return 0

        try:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM users 
                WHERE created_by = ? AND role = 'student' AND is_active = 1
            """, (tutor_id,))

            result = cursor.fetchone()
            return result['count'] if result else 0

        except sqlite3.Error as e:
            print(f"❌ Ошибка получения количества учеников: {e}")
            return 0
        finally:
            connection.close()

    def get_tutor_quick_stats(self, tutor_id):
        """Получение быстрой статистики для репетитора (декабрь 2025)"""
        connection = self.get_connection()
        if not connection:
            return {}

        try:
            cursor = connection.cursor()

            print(f"🔍 Получение статистики для репетитора ID: {tutor_id}")

            # 1. Количество активных учеников
            cursor.execute("""
                SELECT COUNT(*) as total_students
                FROM users 
                WHERE created_by = ? AND role = 'student' AND is_active = 1
            """, (tutor_id,))
            total_students_result = cursor.fetchone()
            total_students = total_students_result['total_students'] if total_students_result else 0
            print(f"📊 Всего учеников: {total_students}")

            # 2. Количество учеников по типам экзаменов
            cursor.execute("""
                SELECT exam_type, COUNT(*) as count
                FROM users 
                WHERE created_by = ? AND role = 'student' AND is_active = 1
                GROUP BY exam_type
            """, (tutor_id,))

            exam_stats = cursor.fetchall()
            oge_count = 0
            ege_count = 0
            for stat in exam_stats:
                if stat['exam_type'] == 'oge':
                    oge_count = stat['count']
                elif stat['exam_type'] == 'ege':
                    ege_count = stat['count']
            print(f"🎯 ОГЭ: {oge_count}, ЕГЭ: {ege_count}")

            # 3. Занятия на неделю
            cursor.execute("""
                SELECT COUNT(*) as weekly_lessons
                FROM schedule 
                WHERE tutor_id = ? AND status = 'active'
            """, (tutor_id,))
            weekly_lessons_result = cursor.fetchone()
            weekly_lessons = weekly_lessons_result['weekly_lessons'] if weekly_lessons_result else 0
            print(f"📅 Занятий на неделю: {weekly_lessons}")

            # 4. Занятия на завтра
            tomorrow_date = datetime.now() + timedelta(days=1)
            day_map = {
                0: 'monday', 1: 'tuesday', 2: 'wednesday', 3: 'thursday',
                4: 'friday', 5: 'saturday', 6: 'sunday'
            }
            tomorrow_weekday = day_map[tomorrow_date.weekday()]

            cursor.execute("""
                SELECT COUNT(*) as tomorrow_lessons
                FROM schedule 
                WHERE tutor_id = ? AND day_of_week = ? AND status = 'active'
            """, (tutor_id, tomorrow_weekday))
            tomorrow_result = cursor.fetchone()
            tomorrow_lessons = tomorrow_result['tomorrow_lessons'] if tomorrow_result else 0
            print(f"📆 Занятий на завтра: {tomorrow_lessons}")

            # 5. Получаем среднюю стоимость занятия
            avg_price = self.get_average_lesson_price_active(tutor_id)

            # 6. Прогноз на декабрь 2025
            december_forecast = self.get_monthly_forecast_december_2025(tutor_id)

            # 7. Доход за декабрь 2025 (текущий месяц)
            current_month_income = self.get_current_month_income(tutor_id)

            # 8. Доход за сентябрь-ноябрь 2025
            yearly_income_2025 = self.get_yearly_income_2025_sep_nov(tutor_id)

            print(
                f"💰 Прогноз на декабрь: {december_forecast}, Доход за декабрь: {current_month_income}, Доход за сентябрь-ноябрь 2025: {yearly_income_2025}")

            stats = {
                'total_students': total_students,
                'oge_students': oge_count,
                'ege_students': ege_count,
                'weekly_lessons': weekly_lessons,
                'tomorrow_lessons': tomorrow_lessons,
                'monthly_forecast': december_forecast,
                'current_month_income': current_month_income,
                'yearly_income_2025': yearly_income_2025,
                'average_lesson_price': avg_price
            }

            print(f"✅ Статистика собрана: {stats}")
            return stats

        except sqlite3.Error as e:
            print(f"❌ Ошибка получения быстрой статистики: {e}")
            import traceback
            traceback.print_exc()
            return {}
        finally:
            if connection:
                connection.close()

    def get_tutor_students_for_schedule(self, tutor_id):
        """Получение учеников репетитора для выбора в расписании"""
        connection = self.get_connection()
        if not connection:
            return []

        try:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT 
                    u.id, 
                    u.first_name, 
                    u.last_name,
                    u.exam_type,
                    u.lesson_price
                FROM users u
                WHERE u.created_by = ? AND u.role = 'student' AND u.is_active = 1
                ORDER BY u.first_name, u.last_name
            """, (tutor_id,))

            students = [dict(row) for row in cursor.fetchall()]
            return students

        except sqlite3.Error as e:
            print(f"❌ Ошибка получения учеников для расписания: {e}")
            return []
        finally:
            if connection:
                connection.close()

    def create_schedule_entry(self, tutor_id, student_id, day_of_week, start_time, end_time, topic_title=None):
        """Создание новой записи в расписании"""
        connection = self.get_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()

            # Получаем или создаем тему для ученика
            topic_id = self.get_or_create_topic_for_student(student_id, tutor_id, topic_title)

            if not topic_id:
                print(f"❌ Не удалось получить тему для ученика {student_id}")
                return False

            # Проверяем, нет ли уже занятия в это время
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM schedule 
                WHERE tutor_id = ? 
                AND day_of_week = ? 
                AND start_time = ? 
                AND student_id = ?
                AND status = 'active'
            """, (tutor_id, day_of_week, start_time, student_id))

            existing_lesson = cursor.fetchone()
            if existing_lesson and existing_lesson['count'] > 0:
                print(f"⚠️ У ученика {student_id} уже есть занятие в {day_of_week} в {start_time}")
                return False

            # Создаем запись в расписании
            cursor.execute("""
                INSERT INTO schedule (student_id, tutor_id, topic_id, day_of_week, start_time, end_time, status)
                VALUES (?, ?, ?, ?, ?, ?, 'active')
            """, (student_id, tutor_id, topic_id, day_of_week, start_time, end_time))

            schedule_id = cursor.lastrowid
            connection.commit()

            print(f"✅ Создано занятие в расписании: ученик {student_id}, {day_of_week} {start_time}-{end_time}")
            return schedule_id

        except sqlite3.Error as e:
            print(f"❌ Ошибка создания занятия: {e}")
            connection.rollback()
            return False
        finally:
            if connection:
                connection.close()

    def get_or_create_topic_for_student(self, student_id, tutor_id, title=None):
        """Получает или создает тему для ученика"""
        connection = self.get_connection()
        if not connection:
            return None

        try:
            cursor = connection.cursor()

            # Пробуем найти существующую тему для этого ученика
            cursor.execute("""
                SELECT t.id 
                FROM topics t
                JOIN schedule s ON t.id = s.topic_id
                WHERE s.student_id = ? AND s.tutor_id = ?
                LIMIT 1
            """, (student_id, tutor_id))

            existing_topic = cursor.fetchone()

            if existing_topic:
                print(f"✅ Найдена существующая тема для ученика {student_id}: ID {existing_topic['id']}")
                return existing_topic['id']

            # Если тема не найдена, создаем новую
            topic_title = title or f'Занятие с учеником {student_id}'
            cursor.execute("""
                INSERT INTO topics (title, description, created_by)
                VALUES (?, ?, ?)
            """, (topic_title, 'Индивидуальное занятие', tutor_id))

            topic_id = cursor.lastrowid
            connection.commit()

            print(f"✅ Создана новая тема для ученика {student_id}: ID {topic_id}")
            return topic_id

        except sqlite3.Error as e:
            print(f"❌ Ошибка при работе с темой: {e}")
            connection.rollback()
            return None
        finally:
            if connection:
                connection.close()

    def get_schedule_for_date(self, tutor_id, date):
        """Получение расписания для конкретной даты - ТОЛЬКО АКТИВНЫЕ ЗАНЯТИЯ"""
        connection = self.get_connection()
        if not connection:
            return []

        try:
            # Определяем день недели для даты
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            day_map = {
                0: 'monday',
                1: 'tuesday',
                2: 'wednesday',
                3: 'thursday',
                4: 'friday',
                5: 'saturday',
                6: 'sunday'
            }
            day_of_week = day_map[date_obj.weekday()]

            cursor = connection.cursor()

            # Получаем только АКТИВНЫЕ занятия на этот день недели
            cursor.execute("""
                SELECT 
                    s.id,
                    s.day_of_week,
                    s.start_time,
                    s.end_time,
                    s.status,
                    u.first_name,
                    u.last_name,
                    u.exam_type,
                    u.lesson_price,
                    t.title as topic_title
                FROM schedule s
                JOIN users u ON s.student_id = u.id
                LEFT JOIN topics t ON s.topic_id = t.id
                WHERE s.tutor_id = ? 
                AND s.day_of_week = ? 
                AND s.status = 'active'
                ORDER BY s.start_time
            """, (tutor_id, day_of_week))

            lessons = [dict(row) for row in cursor.fetchall()]

            print(f"📅 На {date} ({day_of_week}): {len(lessons)} активных занятий")

            return lessons

        except sqlite3.Error as e:
            print(f"❌ Ошибка получения расписания на дату: {e}")
            return []
        finally:
            if connection:
                connection.close()

    def get_income_details(self, tutor_id):
        """Получение детализации доходов"""
        connection = self.get_connection()
        if not connection:
            return []

        try:
            cursor = connection.cursor()

            cursor.execute("""
                SELECT 
                    i.id,
                    i.amount,
                    i.payment_date,
                    i.status,
                    u.first_name,
                    u.last_name,
                    u.exam_type,
                    s.day_of_week,
                    s.start_time
                FROM income i
                JOIN users u ON i.student_id = u.id
                LEFT JOIN schedule s ON i.schedule_id = s.id
                WHERE i.student_id IN (
                    SELECT id FROM users WHERE created_by = ? AND role = 'student'
                )
                ORDER BY i.payment_date DESC
                LIMIT 50
            """, (tutor_id,))

            income_details = [dict(row) for row in cursor.fetchall()]
            return income_details

        except sqlite3.Error as e:
            print(f"❌ Ошибка получения детализации доходов: {e}")
            return []
        finally:
            if connection:
                connection.close()

    def complete_lesson(self, schedule_id, tutor_id):
        """Завершение занятия и начисление дохода"""
        connection = self.get_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()

            # Получаем информацию о занятии и ученике
            cursor.execute("""
                SELECT s.*, u.lesson_price, u.exam_type, u.first_name, u.last_name, u.id as student_id
                FROM schedule s
                JOIN users u ON s.student_id = u.id
                WHERE s.id = ? AND s.tutor_id = ?
            """, (schedule_id, tutor_id))

            lesson = cursor.fetchone()
            if not lesson:
                print(f"❌ Занятие {schedule_id} не найдено или доступ запрещен")
                return False

            lesson_dict = dict(lesson)

            # Проверяем, не было ли уже начислено за это занятие
            cursor.execute("""
                SELECT id FROM income 
                WHERE schedule_id = ? AND status = 'paid'
            """, (schedule_id,))

            if cursor.fetchone():
                print(f"⚠️ Доход за занятие {schedule_id} уже начислен")
                return False

            # Начисляем доход
            current_date = datetime.now()
            month_year = current_date.strftime('%Y-%m')
            completed_at = current_date.strftime('%Y-%m-%d %H:%M:%S')

            # Сначала пытаемся с completed_at
            try:
                cursor.execute("""
                    INSERT INTO income (
                        schedule_id, student_id, amount, payment_date, 
                        month_year, status, completed_at
                    ) VALUES (?, ?, ?, ?, ?, 'paid', ?)
                """, (
                    schedule_id, lesson_dict['student_id'], lesson_dict['lesson_price'],
                    current_date.strftime('%Y-%m-%d'), month_year, completed_at
                ))
                income_id = cursor.lastrowid
            except sqlite3.Error:
                # Если нет колонки completed_at, создаем без нее
                cursor.execute("""
                    INSERT INTO income (
                        schedule_id, student_id, amount, payment_date, 
                        month_year, status
                    ) VALUES (?, ?, ?, ?, ?, 'paid')
                """, (
                    schedule_id, lesson_dict['student_id'], lesson_dict['lesson_price'],
                    current_date.strftime('%Y-%m-%d'), month_year
                ))
                income_id = cursor.lastrowid

            # Помечаем занятие как завершенное
            try:
                cursor.execute("""
                    UPDATE schedule 
                    SET status = 'completed', completed_at = ?
                    WHERE id = ?
                """, (completed_at, schedule_id))
            except:
                # Если поля completed_at нет, просто обновляем статус
                cursor.execute("""
                    UPDATE schedule 
                    SET status = 'completed'
                    WHERE id = ?
                """, (schedule_id,))

            connection.commit()

            print(f"✅ Занятие {schedule_id} завершено. Доход {lesson_dict['lesson_price']}₽ начислен")
            return {
                'income_id': income_id,
                'amount': lesson_dict['lesson_price'],
                'student_name': f"{lesson_dict['first_name']} {lesson_dict['last_name']}",
                'exam_type': lesson_dict['exam_type'],
                'completed_at': completed_at
            }

        except sqlite3.Error as e:
            print(f"❌ Ошибка завершения занятия: {e}")
            connection.rollback()
            return False
        finally:
            connection.close()