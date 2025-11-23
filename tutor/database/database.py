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
        """Создание нового ученика с расписанием"""
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

            # Создаем пользователя с exam_type
            cursor.execute('''
                INSERT INTO users (
                    username, password_hash, role, first_name, last_name, 
                    exam_type, lesson_price, contact_info, created_by, is_active
                ) VALUES (?, ?, 'student', ?, ?, ?, ?, ?, ?, 1)
            ''', (username, password, first_name, last_name, exam_type, lesson_price, contact_info, tutor_id))

            student_id = cursor.lastrowid

            # Создаем расписание для ученика
            # Сначала нужно создать тему (topic) для занятий
            cursor.execute('''
                INSERT INTO topics (title, description, created_by)
                VALUES (?, ?, ?)
            ''', (f'Занятия с {first_name} {last_name}', f'Индивидуальные занятия по подготовке к {exam_type.upper()}',
                  tutor_id))

            topic_id = cursor.lastrowid

            # Создаем расписание
            start_time = lesson_time
            # Вычисляем время окончания (занятие длится 1 час)
            from datetime import datetime, timedelta
            start_dt = datetime.strptime(start_time, '%H:%M')
            end_dt = start_dt + timedelta(hours=1)
            end_time = end_dt.strftime('%H:%M')

            cursor.execute('''
                INSERT INTO schedule (student_id, tutor_id, topic_id, day_of_week, start_time, end_time, status)
                VALUES (?, ?, ?, ?, ?, ?, 'active')
            ''', (student_id, tutor_id, topic_id, day_of_week, start_time, end_time))

            connection.commit()

            print(
                f"✅ Ученик создан: {first_name} {last_name} (ID: {student_id}) с расписанием: {day_of_week} {start_time}-{end_time}")
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
                SELECT 
                    s.id,
                    s.day_of_week,
                    s.start_time,
                    s.end_time,
                    s.lesson_link,
                    s.status,
                    t.title        AS topic_title,
                    u.first_name   AS student_name,
                    u.last_name    AS student_last_name,
                    u.lesson_price AS lesson_price,
                    u.exam_type    AS exam_type
                FROM schedule s
                JOIN topics t ON s.topic_id = t.id
                JOIN users  u ON s.student_id = u.id
                WHERE s.tutor_id = ? AND s.status = 'active'
                ORDER BY 
                    CASE s.day_of_week
                        WHEN 'monday'   THEN 1
                        WHEN 'tuesday'  THEN 2
                        WHEN 'wednesday'THEN 3
                        WHEN 'thursday' THEN 4
                        WHEN 'friday'   THEN 5
                        WHEN 'saturday' THEN 6
                        WHEN 'sunday'   THEN 7
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

    # ====== Блок работы с доходами (income_lessons) ======

    def add_income_lesson(self, tutor_id, date, student, exam, price, status='pending'):
        """
        Добавить запись о проведённом занятии в income_lessons.
        """
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO income_lessons (tutor_id, lesson_date, student_name, exam, price, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tutor_id, date, student, exam, price, status))
        lesson_id = cur.lastrowid
        conn.commit()
        conn.close()
        return lesson_id

    def get_income_lessons(self, tutor_id):
        """
        Получить все записи доходов данного репетитора.
        Поля приводим к фронтенд-формату: date, student, exam, price, status.
        """
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT
                id,
                tutor_id,
                lesson_date   AS date,
                student_name  AS student,
                exam,
                price,
                status,
                created_at
            FROM income_lessons
            WHERE tutor_id = ?
            ORDER BY lesson_date DESC, id DESC
        """, (tutor_id,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def update_income_status(self, lesson_id, tutor_id, new_status):
        """
        Обновить статус оплаты занятия.
        """
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE income_lessons
               SET status = ?
             WHERE id = ? AND tutor_id = ?
        """, (new_status, lesson_id, tutor_id))
        conn.commit()
        conn.close()

    def reset_income(self, tutor_id):
        """
        Полностью очистить доходы репетитора.
        """
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM income_lessons WHERE tutor_id = ?", (tutor_id,))
        conn.commit()
        conn.close()

