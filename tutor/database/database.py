import sqlite3
import os
from typing import Optional, Dict, Any


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
                print(f"   Содержимое директории database: {os.listdir(current_dir) if os.path.exists(current_dir) else 'не существует'}")
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
            print(f"🔑 Сравнение паролей: введен '{password}', в базе '{user_dict['password_hash']}'")

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
                    exam_type, lesson_price, contact_info, created_by, is_active
                ) VALUES (?, ?, 'student', ?, ?, ?, ?, ?, ?, 1)
            ''', (username, password, first_name, last_name, exam_type, lesson_price, contact_info, tutor_id))

            student_id = cursor.lastrowid

            # Создаем тему для занятий
            cursor.execute('''
                INSERT INTO topics (title, description, created_by)
                VALUES (?, ?, ?)
            ''', (
            f'Занятия с {first_name} {last_name}', f'Регулярные занятия по подготовке к {exam_type.upper()}', tutor_id))

            topic_id = cursor.lastrowid

            # Вычисляем время окончания (занятие длится 1 час)
            from datetime import datetime, timedelta
            start_dt = datetime.strptime(lesson_time, '%H:%M')
            end_dt = start_dt + timedelta(hours=1)
            end_time = end_dt.strftime('%H:%M')

            # Создаем РЕГУЛЯРНОЕ расписание
            cursor.execute('''
                INSERT INTO schedule (student_id, tutor_id, topic_id, day_of_week, start_time, end_time, status, lesson_type)
                VALUES (?, ?, ?, ?, ?, ?, 'active', 'regular')
            ''', (student_id, tutor_id, topic_id, day_of_week, lesson_time, end_time))

            connection.commit()

            print(f"✅ Ученик создан: {first_name} {last_name} (ID: {student_id})")
            print(f"📅 Автоматическое расписание: {day_of_week} {lesson_time}-{end_time} (регулярное)")
            return student_id

        except sqlite3.Error as e:
            print(f"❌ Ошибка при создании ученика: {e}")
            return False
        finally:
            connection.close()


    def get_tutor_students(self, tutor_id: int):
        """Получение всех учеников репетитора с информацией о расписании"""
        connection = self.get_connection()
        if not connection:
            return []

        try:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT 
                    u.id, u.username, u.first_name, u.last_name, 
                    u.exam_type, u.lesson_price, u.contact_info, u.created_at,
                    s.day_of_week, s.start_time as lesson_time
                FROM users u
                LEFT JOIN schedule s ON u.id = s.student_id AND s.status = 'active'
                WHERE u.created_by = ? AND u.role = 'student' AND u.is_active = 1
                ORDER BY u.created_at DESC
            """, (tutor_id,))

            students = []
            for row in cursor.fetchall():
                student = dict(row)
                # Добавляем вычисляемые поля для отображения
                student['progress'] = self.calculate_student_progress(student['id'])
                student['lesson_count'] = self.get_student_lesson_count(student['id'])
                students.append(student)

            print(f"📊 Найдено учеников: {len(students)}")
            return students

        except sqlite3.Error as e:
            print(f"❌ Ошибка получения учеников: {e}")
            return []
        finally:
            connection.close()

    def update_schema(self):
        """Обновление схемы базы данных - добавление exam_type"""
        connection = self.get_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()

            # Проверяем существование колонки exam_type
            cursor.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in cursor.fetchall()]

            # Добавляем exam_type если его нет
            if 'exam_type' not in columns:
                print("📝 Добавляем колонку exam_type в таблицу users...")
                cursor.execute('ALTER TABLE users ADD COLUMN exam_type VARCHAR(10) CHECK (exam_type IN ("oge", "ege"))')
                connection.commit()
                print("✅ Колонка exam_type добавлена")

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

    def calculate_student_progress(self, student_id: int):
        """Расчет прогресса ученика (заглушка)"""
        # В реальном приложении здесь будет расчет прогресса на основе выполненных заданий
        import random
        return random.randint(50, 95)

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

    # Добавьте в класс Database следующие методы:

    def get_monthly_income(self, tutor_id, year, month):
        """Получение дохода за конкретный месяц"""
        connection = self.get_connection()
        if not connection:
            return 0

        try:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT COALESCE(SUM(l.amount), 0) as total_income
                FROM income l
                JOIN schedule s ON l.schedule_id = s.id
                WHERE s.tutor_id = ? 
                AND strftime('%Y', l.payment_date) = ?
                AND strftime('%m', l.payment_date) = ?
            """, (tutor_id, str(year), str(month).zfill(2)))

            result = cursor.fetchone()
            return result['total_income'] if result else 0

        except sqlite3.Error as e:
            print(f"❌ Ошибка получения дохода за месяц: {e}")
            return 0
        finally:
            connection.close()

    def get_yearly_income(self, tutor_id, year):
        """Получение дохода за год"""
        connection = self.get_connection()
        if not connection:
            return 0

        try:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT COALESCE(SUM(l.amount), 0) as total_income
                FROM income l
                JOIN schedule s ON l.schedule_id = s.id
                WHERE s.tutor_id = ? 
                AND strftime('%Y', l.payment_date) = ?
            """, (tutor_id, str(year)))

            result = cursor.fetchone()
            return result['total_income'] if result else 0

        except sqlite3.Error as e:
            print(f"❌ Ошибка получения дохода за год: {e}")
            return 0
        finally:
            connection.close()

    def get_average_lesson_price(self, tutor_id):
        """Получение средней стоимости занятия"""
        connection = self.get_connection()
        if not connection:
            return 0

        try:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT AVG(lesson_price) as avg_price
                FROM users 
                WHERE created_by = ? AND role = 'student' AND is_active = 1
            """, (tutor_id,))

            result = cursor.fetchone()
            return result['avg_price'] if result and result['avg_price'] else 0

        except sqlite3.Error as e:
            print(f"❌ Ошибка получения средней стоимости: {e}")
            return 0
        finally:
            connection.close()

    def get_monthly_income_forecast(self, tutor_id, year, month):
        """Прогноз дохода на месяц"""
        connection = self.get_connection()
        if not connection:
            return 0

        try:
            cursor = connection.cursor()
            # Получаем количество активных учеников
            cursor.execute("""
                SELECT COUNT(*) as student_count
                FROM users 
                WHERE created_by = ? AND role = 'student' AND is_active = 1
            """, (tutor_id,))

            student_count = cursor.fetchone()['student_count']

            # Получаем среднюю стоимость занятия
            avg_price = self.get_average_lesson_price(tutor_id)

            # Прогноз: 4 занятия в месяц на ученика
            forecast = student_count * 4 * avg_price

            return forecast

        except sqlite3.Error as e:
            print(f"❌ Ошибка расчета прогноза: {e}")
            return 0
        finally:
            connection.close()

    def get_income_statistics(self, tutor_id):
        """Полная статистика по доходам"""
        from datetime import datetime

        current_year = datetime.now().year
        current_month = datetime.now().month

        return {
            'current_month_income': self.get_monthly_income(tutor_id, current_year, current_month),
            'monthly_forecast': self.get_monthly_income_forecast(tutor_id, current_year, current_month),
            'average_lesson_price': self.get_average_lesson_price(tutor_id),
            'yearly_income': self.get_yearly_income(tutor_id, current_year),
            'student_count': self.get_active_students_count(tutor_id)
        }

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

    # Добавьте в класс Database следующие методы:

    # ЗАМЕНИТЕ метод get_tutor_quick_stats в database.py на этот:

    def get_tutor_quick_stats(self, tutor_id):
        """Получение быстрой статистики для репетитора - УПРОЩЕННАЯ ВЕРСИЯ БЕЗ ТАБЛИЦЫ INCOME"""
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
            from datetime import datetime, timedelta
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

            # 5. Расчет доходов на основе учеников (без таблицы income)
            cursor.execute("""
                SELECT COALESCE(SUM(lesson_price), 0) as total_lesson_price
                FROM users 
                WHERE created_by = ? AND role = 'student' AND is_active = 1
            """, (tutor_id,))
            total_price_result = cursor.fetchone()
            total_lesson_price = total_price_result['total_lesson_price'] if total_price_result else 0

            # Прогноз: 4 занятия в месяц на ученика
            monthly_forecast = total_lesson_price * 4
            # Текущий доход: 70% от прогноза (имитация проведенных занятий)
            monthly_income = monthly_forecast * 0.7

            print(f"💰 Прогноз дохода: {monthly_forecast}, Текущий: {monthly_income}")

            stats = {
                'total_students': total_students,
                'oge_students': oge_count,
                'ege_students': ege_count,
                'weekly_lessons': weekly_lessons,
                'tomorrow_lessons': tomorrow_lessons,
                'monthly_income': monthly_income,
                'monthly_forecast': monthly_forecast
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

    def create_schedule_entry(self, tutor_id, student_id, day_of_week, start_time, end_time, topic_id=None):
        """Создание новой записи в расписании"""
        connection = self.get_connection()
        if not connection:
            return False

        try:
            cursor = connection.cursor()

            # Если тема не указана, создаем тему по умолчанию
            if not topic_id:
                cursor.execute("""
                    INSERT INTO topics (title, description, created_by)
                    VALUES (?, ?, ?)
                """, (f'Занятие со студентом {student_id}', 'Индивидуальное занятие', tutor_id))
                topic_id = cursor.lastrowid

            # Создаем запись в расписании
            cursor.execute("""
                INSERT INTO schedule (student_id, tutor_id, topic_id, day_of_week, start_time, end_time, status)
                VALUES (?, ?, ?, ?, ?, ?, 'active')
            """, (student_id, tutor_id, topic_id, day_of_week, start_time, end_time))

            schedule_id = cursor.lastrowid
            connection.commit()

            print(f"✅ Создано занятие в расписании: ID {schedule_id}")
            return schedule_id

        except sqlite3.Error as e:
            print(f"❌ Ошибка создания занятия: {e}")
            connection.rollback()
            return False
        finally:
            if connection:
                connection.close()

    def get_schedule_for_date(self, tutor_id, date):
        """Получение расписания для конкретной даты - ВКЛЮЧАЕТ РЕГУЛЯРНЫЕ ЗАНЯТИЯ"""
        connection = self.get_connection()
        if not connection:
            return []

        try:
            # Определяем день недели для даты
            from datetime import datetime
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

            # Получаем ВСЕ активные регулярные занятия на этот день недели
            cursor.execute("""
                SELECT 
                    s.id,
                    s.day_of_week,
                    s.start_time,
                    s.end_time,
                    s.status,
                    s.lesson_type,
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
                AND (s.lesson_type = 'regular' OR s.lesson_type IS NULL)
                ORDER BY s.start_time
            """, (tutor_id, day_of_week))

            regular_lessons = [dict(row) for row in cursor.fetchall()]

            # Также получаем разовые занятия на конкретную дату
            cursor.execute("""
                SELECT 
                    s.id,
                    s.day_of_week,
                    s.start_time,
                    s.end_time,
                    s.status,
                    s.lesson_type,
                    u.first_name,
                    u.last_name,
                    u.exam_type,
                    u.lesson_price,
                    t.title as topic_title,
                    sl.lesson_date
                FROM schedule s
                JOIN single_lessons sl ON s.id = sl.schedule_id
                JOIN users u ON s.student_id = u.id
                LEFT JOIN topics t ON s.topic_id = t.id
                WHERE s.tutor_id = ? 
                AND sl.lesson_date = ?
                AND s.status = 'active'
                AND s.lesson_type = 'single'
                ORDER BY s.start_time
            """, (tutor_id, date))

            single_lessons = [dict(row) for row in cursor.fetchall()]

            # Объединяем регулярные и разовые занятия
            all_lessons = regular_lessons + single_lessons

            print(
                f"📅 На {date} ({day_of_week}): {len(regular_lessons)} регулярных + {len(single_lessons)} разовых = {len(all_lessons)} занятий")

            return all_lessons

        except sqlite3.Error as e:
            print(f"❌ Ошибка получения расписания на дату: {e}")
            return []
        finally:
            if connection:
                connection.close()

    def get_schedule_statistics(self, tutor_id, date):
        """Получение статистики расписания"""
        connection = self.get_connection()
        if not connection:
            return {}

        try:
            cursor = connection.cursor()

            # Получаем занятия на указанную дату
            schedule = self.get_schedule_for_date(tutor_id, date)
            lessons_count = len(schedule)

            # Считаем распределение по экзаменам
            oge_count = sum(1 for lesson in schedule if lesson.get('exam_type') == 'oge')
            ege_count = sum(1 for lesson in schedule if lesson.get('exam_type') == 'ege')

            # Считаем общее время и прогноз дохода
            total_minutes = 0
            total_income = 0

            for lesson in schedule:
                # Вычисляем длительность занятия
                start_time = datetime.strptime(lesson['start_time'], '%H:%M')
                end_time = datetime.strptime(lesson['end_time'], '%H:%M')
                duration = (end_time - start_time).seconds / 3600  # в часах
                total_minutes += duration

                # Получаем стоимость занятия ученика
                cursor.execute("""
                    SELECT lesson_price FROM users WHERE id = ?
                """, (lesson.get('student_id'),))
                student = cursor.fetchone()
                if student:
                    total_income += student['lesson_price']

            return {
                'lessons_count': lessons_count,
                'oge_count': oge_count,
                'ege_count': ege_count,
                'total_hours': round(total_minutes, 1),
                'income_forecast': total_income
            }

        except sqlite3.Error as e:
            print(f"❌ Ошибка получения статистики расписания: {e}")
            return {}
        finally:
            if connection:
                connection.close()