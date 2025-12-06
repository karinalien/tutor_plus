import json

from flask import Flask, render_template, send_from_directory, send_file, request, jsonify, session
import os
import uuid
from werkzeug.utils import secure_filename
from database.database import Database
from services.auth_service import AuthService
from llm.llm_client import generate_test_from_text


# Инициализация БД
db = Database('database/tutoring.db')
auth_service = AuthService(db)

# Создаем таблицы при запуске
db.create_tables()
db.update_schema()
# Гарантируем наличие пользователя tutor
db.ensure_tutor_user()

app = Flask(__name__)
app.secret_key = 'tutoring-secret-key-2024'

@app.route('/api/login', methods=['POST'])
def api_login():
    """API endpoint для входа в систему"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    print(f"🔐 Попытка входа: username='{username}', password='{password}'")
    print(f"🔐 Типы данных: username={type(username)}, password={type(password)}")

    success, message, user = auth_service.login(username, password)

    if success:
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session['first_name'] = user.first_name
        session['last_name'] = user.last_name

        print(f"✅ Успешный вход: {user.role} {user.first_name} (ID: {user.id})")
        return jsonify({
            'success': True,
            'message': message,
            'user': {
                'id': user.id,
                'username': user.username,
                'role': user.role,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'lesson_price': user.lesson_price,
                'contact_info': user.contact_info
            },
            'redirect_url': '/tutor-cabinet' if user.role == 'tutor' else '/student-cabinet'
        })
    else:
        print(f"❌ Ошибка входа: {message}")
        return jsonify({
            'success': False,
            'message': message
        }), 401


@app.route('/api/logout', methods=['POST'])
def api_logout():
    """API endpoint для выхода из системы"""
    session.clear()
    auth_service.logout()
    return jsonify({
        'success': True,
        'message': 'Вы успешно вышли из системы'
    })


@app.route('/api/check-auth')
def check_auth():
    """Проверка статуса аутентификации"""
    if 'user_id' in session:
        return jsonify({
            'authenticated': True,
            'user': {
                'id': session['user_id'],
                'username': session['username'],
                'role': session['role'],
                'first_name': session['first_name'],
                'last_name': session['last_name']
            }
        })
    else:
        return jsonify({'authenticated': False})

@app.route('/api/schedule', methods=['GET'])
def get_schedule():
    """Получение расписания для текущего пользователя"""
    if 'user_id' not in session:
        return jsonify({'error': 'Не авторизован'}), 401

    user_id = session['user_id']
    role = session['role']

    if role == 'tutor':
        schedule = db.get_tutor_schedule(user_id)
    else:
        schedule = db.get_student_schedule(user_id)

    return jsonify({'schedule': schedule})


@app.route('/api/tutor/schedule', methods=['POST'])
def create_schedule():
    """Создание расписания (только для репетитора)"""
    if 'user_id' not in session or session['role'] != 'tutor':
        return jsonify({'error': 'Доступ запрещен'}), 403

    data = request.get_json()
    student_id = data.get('student_id')
    topic_id = data.get('topic_id')
    day_of_week = data.get('day_of_week')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    lesson_link = data.get('lesson_link', '')

    return jsonify({'success': True, 'message': 'Расписание создано'})


# Отладочные Routes
@app.route('/debug/templates')
def debug_templates():
    """Проверка доступности template файлов"""
    import os

    files_to_check = [
        'templates/cabinet.html',
        'templates/tutor_cabinet.html',
        'templates/student_cabinet.html'
    ]

    result = {}
    for file_path in files_to_check:
        exists = os.path.exists(file_path)
        result[file_path] = {
            'exists': exists,
            'absolute_path': os.path.abspath(file_path) if exists else None,
            'readable': os.access(file_path, os.R_OK) if exists else False
        }

        if exists:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    result[file_path]['size'] = len(content)
                    result[file_path]['first_100_chars'] = content[:100]
            except Exception as e:
                result[file_path]['error'] = str(e)

    return jsonify(result)

@app.route('/debug/students')
def debug_students():
    """Отладочная страница для проверки учеников"""
    if 'user_id' not in session or session['role'] != 'tutor':
        return "Доступ запрещен", 403

    students = db.get_tutor_students(session['user_id'])
    return jsonify({
        'tutor_id': session['user_id'],
        'total_students': len(students),
        'students': students
    })


@app.route('/api/tutor/delete-student/<int:student_id>', methods=['DELETE'])
def api_delete_student(student_id):
    """API для удаления ученика"""
    if 'user_id' not in session or session['role'] != 'tutor':
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403

    try:
        # Проверяем, что ученик принадлежит текущему репетитору
        connection = db.get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT created_by FROM users WHERE id = ?", (student_id,))
        student = cursor.fetchone()

        if not student:
            return jsonify({'success': False, 'message': 'Ученик не найден'}), 404

        if student['created_by'] != session['user_id']:
            return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403

        # Удаляем ученика (или помечаем как неактивного)
        cursor.execute("UPDATE users SET is_active = 0 WHERE id = ?", (student_id,))
        connection.commit()
        connection.close()

        print(f"✅ Ученик ID {student_id} удален")
        return jsonify({'success': True, 'message': 'Ученик успешно удален'})

    except Exception as e:
        print(f"❌ Ошибка при удалении ученика: {e}")
        return jsonify({'success': False, 'message': f'Ошибка при удалении ученика: {str(e)}'}), 500


@app.route('/debug/files')
def debug_files():
    """Отладочная страница для проверки файлов"""
    import os
    result = {
        'current_directory': os.getcwd(),
        'app_file_path': os.path.abspath(__file__),
        'templates_path': os.path.abspath('templates'),
        'templates_exists': os.path.exists('templates'),
    }

    if os.path.exists('templates'):
        result['files_in_templates'] = os.listdir('templates')
        # Проверим конкретные файлы
        result['cabinet_exists'] = os.path.exists('templates/cabinet.html')
        result['tutor_cabinet_exists'] = os.path.exists('templates/tutor_cabinet.html')
        result['student_cabinet_exists'] = os.path.exists('templates/student_cabinet.html')

    return jsonify(result)


@app.route('/debug/db')
def debug_db():
    """Отладочная страница для проверки базы данных"""
    try:
        connection = db.get_connection()
        cursor = connection.cursor()

        # Проверка таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()

        # Проверка пользователей
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()

        connection.close()

        result = {
            'tables': [dict(table) for table in tables],
            'users': [dict(user) for user in users],
            'total_users': len(users)
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/tutor-cabinet')
def tutor_cabinet():
    if 'user_id' not in session or session['role'] != 'tutor':
        return "Доступ запрещен. Только для репетиторов.", 403

    print(f"🔄 Рендеринг tutor_cabinet.html для пользователя {session.get('username')}")

    try:
        return render_template('tutor_cabinet.html')
    except Exception as e:
        print(f"❌ Ошибка при рендеринге шаблона: {e}")
        return f"Ошибка загрузки страницы: {e}", 500

@app.route('/student-cabinet')
def student_cabinet():
    """Кабинет ученика"""
    if 'user_id' not in session or session['role'] != 'student':
        return "Доступ запрещен. Только для учеников.", 403

    try:
        return render_template('student_cabinet.html')
    except Exception as e:
        print(f"❌ Ошибка при рендеринге шаблона: {e}")
        return f"Ошибка загрузки страницы: {e}", 500

@app.route('/tests')
#тесты
def tests():
    """Страница-меню со списком тестов."""
    if 'user_id' not in session or session['role'] != 'student':
        return "Доступ запрещен.", 403
    return render_template('student_tests.html')


@app.route('/tests/<int:test_id>')
def show_test(test_id):
    if 'user_id' not in session or session['role'] != 'student':
        return "Доступ запрещен. Необходима авторизация.", 403

    try:
        db = Database()
        connection = db.get_connection()
        cursor = connection.cursor()

        # Загружаем тест по ID
        cursor.execute(
            """
            SELECT * FROM tests
            WHERE student_id = ? AND id = ?
            """,
            (session['user_id'], test_id),
        )

        row = cursor.fetchone()
        connection.close()

        if not row:
            return "❌ Тест не найден.", 404

        import json
        test_json = row["json_content"]

        try:
            if isinstance(test_json, str):
                test_data = json.loads(test_json)
            else:
                test_data = test_json
        except (json.JSONDecodeError, TypeError):
            test_data = {"error": "Ошибка парсинга JSON", "raw": test_json}

        # Для ID-роута используем единый шаблон test_1.html
        return render_template("test_1.html", test=test_data, test_id=row["id"])

    except Exception as e:
        print("❌ Ошибка при загрузке теста:", e)
        return f"Ошибка загрузки теста: {e}", 500


@app.route('/tests/2')
def test_2():
    # Открываем тест по названию материала 'test2'
    return show_test_by_material('test2', 'test_2.html')

@app.route('/tests/3')
def test_3():
    # Открываем тест по названию материала 'test3'
    return show_test_by_material('test3', 'test_3.html')

def show_test_by_material(material_name: str, template_name: str):
    if 'user_id' not in session or session['role'] != 'student':
        return "Доступ запрещен. Необходима авторизация.", 403

    try:
        db = Database()
        connection = db.get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT * FROM tests
            WHERE student_id = ? AND material_name = ?
            """,
            (session['user_id'], material_name),
        )

        row = cursor.fetchone()
        connection.close()

        if not row:
            return "❌ Тест не найден.", 404

        import json
        test_json = row["json_content"]
        try:
            test_data = json.loads(test_json) if isinstance(test_json, str) else test_json
        except (json.JSONDecodeError, TypeError):
            test_data = {"error": "Ошибка парсинга JSON", "raw": test_json}

        return render_template(template_name, test=test_data, test_id=row["id"])

    except Exception as e:
        print("❌ Ошибка при загрузке теста по материалу:", e)
        return f"Ошибка загрузки теста: {e}", 500

@app.route('/timetable')
#расписание
def timetable():
    return render_template('timetable.html')

@app.route('/')
def index():
    """Главная страница с React приложением"""
    return render_template('index.html')

@app.route('/cabinet')
def cabinet():
    """Страница личного кабинета"""
    return render_template('cabinet.html')
@app.route('/materials')
def materials():
    """Страница учебных материалов"""
    if 'user_id' not in session or session['role'] != 'tutor':
        return "Доступ запрещен. Только для репетиторов.", 403
    return render_template('materials.html')

@app.route('/requests')
def requests():
    """Страница запросов на перенос"""
    if 'user_id' not in session or session['role'] != 'tutor':
        return "Доступ запрещен. Только для репетиторов.", 403
    return render_template('requests.html')

@app.route('/reschedule')
def reschedule():
    """Страница запросов на перенос"""
    if 'user_id' not in session or session['role'] != 'tutor':
        return "Доступ запрещен. Только для репетиторов.", 403

    try:
        with open('templates/reschedule.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Страница запросов на перенос не найдена", 404

@app.route('/add-student')
def add_student():
    """Страница добавления нового ученика"""
    if 'user_id' not in session or session['role'] != 'tutor':
        return "Доступ запрещен. Только для репетиторов.", 403
    return render_template('add_student.html')

@app.route('/api/tutor/create-student', methods=['POST'])
def api_create_student():
    """API для создания нового ученика"""
    if 'user_id' not in session or session['role'] != 'tutor':
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403

    data = request.get_json()

    print(f"📨 Получены данные для создания ученика: {data}")

    # Валидация данных
    required_fields = ['last_name', 'first_name', 'birth_date', 'exam_type', 'username', 'password', 'lesson_price', 'day_of_week', 'lesson_time']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'success': False, 'message': f'Поле {field} обязательно'}), 400

    try:
        # Формируем contact_info из даты рождения
        contact_info = f"Дата рождения: {data['birth_date']}"

        # Создаем ученика в базе данных
        student_id = db.create_student(
            username=data['username'],
            password=data['password'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            tutor_id=session['user_id'],
            contact_info=contact_info,
            exam_type=data['exam_type'],
            lesson_price=data['lesson_price'],
            day_of_week=data['day_of_week'],
            lesson_time=data['lesson_time']
        )

        if student_id:
            print(f"✅ Ученик успешно создан с ID: {student_id}")
            return jsonify({
                'success': True,
                'message': 'Ученик успешно создан',
                'student_id': student_id
            })
        else:
            print("❌ Ошибка: не удалось создать ученика")
            return jsonify(
                {'success': False, 'message': 'Ошибка при создании ученика (возможно, логин уже занят)'}), 500

    except Exception as e:
        print(f"❌ Ошибка при создании ученика: {e}")
        return jsonify({'success': False, 'message': f'Внутренняя ошибка сервера: {str(e)}'}), 500

@app.route('/api/tutor/students')
def api_get_students():
    """API для получения списка учеников репетитора"""
    if 'user_id' not in session or session['role'] != 'tutor':
        return jsonify({'error': 'Доступ запрещен'}), 403

    try:
        students = db.get_tutor_students(session['user_id'])
        print(f"✅ Получено учеников: {len(students)}")
        return jsonify({'success': True, 'students': students})

    except Exception as e:
        print(f"❌ Ошибка при получении учеников: {e}")
        return jsonify({'success': False, 'message': 'Ошибка при загрузке учеников'}), 500

@app.route('/income')
def income():
    """Страница доходов"""
    if 'user_id' not in session or session['role'] != 'tutor':
        return "Доступ запрещен. Только для репетиторов.", 403
    return render_template('income.html')

@app.route('/App.js')
def serve_app_js():
    """Обслуживание App.js"""
    return send_file('App.js', mimetype='application/javascript')

@app.route('/index.js')
def serve_index_js():
    """Обслуживание index.js"""
    return send_file('index.js', mimetype='application/javascript')

@app.route('/styles.css')
def serve_css():
    """Обслуживание styles.css"""
    return send_file('styles.css', mimetype='text/css')

@app.route('/me.jpg')
def serve_photo():
    """Обслуживание фото"""
    return send_file('me.jpg', mimetype='image/jpeg')

@app.route('/Cabinet.js')
def serve_cabinet_js():
    """Обслуживание Cabinet.js"""
    return send_file('Cabinet.js', mimetype='application/javascript')

@app.route('/cabinet-index.js')
def serve_cabinet_index_js():
    """Обслуживание cabinet-index.js"""
    return send_file('cabinet-index.js', mimetype='application/javascript')

@app.route('/students')
def students():
    """Страница управления учениками"""
    if 'user_id' not in session or session['role'] != 'tutor':
        return "Доступ запрещен. Только для репетиторов.", 403
    return render_template('students.html')


@app.route('/student-tests')
def student_tests():
    """Страница тестов с меню для учеников"""
    if 'user_id' not in session or session['role'] != 'student':
        return "Доступ запрещен. Только для учеников.", 403

    return render_template('student_tests.html')


@app.route('/test-result')
def test_result():
    generated_test = session.get('generated_test', '')
    test_material = session.get('test_material', '')

    if not generated_test:
        return "Результаты не найдены. Пожалуйста, сгенерируйте тест сначала.", 404

    return render_template('test_result.html', test=generated_test, material=test_material)


@app.route('/generate-test', methods=['POST'])
def generate_test():
    data = request.get_json()
    material = data.get("text", "")

    if not material:
        return jsonify({"test": "❌ Ошибка: Не указан материал для генерации теста"}), 400

    result = generate_test_from_text(material)

    session['generated_test'] = result
    session['test_material'] = material

    return jsonify({"test": result, "redirect": "/test-result"})


@app.route('/student-schedule')
def student_schedule():
    """Страница расписания для учеников"""
    if 'user_id' not in session or session['role'] != 'student':
        return "Доступ запрещен. Только для учеников.", 403

    return render_template('student_schedule.html')


@app.route('/student-materials')
def student_materials():
    """Страница материалов для учеников"""
    if 'user_id' not in session or session['role'] != 'student':
        return "Доступ запрещен. Только для учеников.", 403

    return render_template('student_materials.html')


@app.route('/api/materials')
def api_get_materials():
    """API для получения учебных материалов"""
    if 'user_id' not in session:
        return jsonify({'error': 'Не авторизован'}), 401

    try:
        connection = db.get_connection()
        cursor = connection.cursor()

        if session['role'] == 'tutor':
            # Репетитор видит все свои материалы
            cursor.execute("""
                SELECT * FROM materials 
                WHERE tutor_id = ? 
                ORDER BY created_at DESC
            """, (session['user_id'],))
        else:
            # Ученик видит материалы своего репетитора
            cursor.execute("""
                SELECT m.* 
                FROM materials m
                JOIN users u ON m.tutor_id = u.created_by
                WHERE u.id = ?
                ORDER BY m.created_at DESC
            """, (session['user_id'],))

        materials = [dict(row) for row in cursor.fetchall()]
        connection.close()

        return jsonify({
            'success': True,
            'materials': materials
        })

    except Exception as e:
        print(f"❌ Ошибка получения материалов: {e}")
        # Возвращаем тестовые данные если таблицы еще нет
        return jsonify({
            'success': True,
            'materials': []
        })

@app.route('/api/tutor/materials', methods=['POST'])
def api_create_material():
    """API для создания учебного материала (только для репетитора)"""
    if 'user_id' not in session or session['role'] != 'tutor':
        return jsonify({'error': 'Доступ запрещен'}), 403

    data = request.get_json()

    try:
        connection = db.get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO materials (tutor_id, title, description, file_type, file_size, file_path, category, exam_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session['user_id'],
            data['title'],
            data.get('description', ''),
            data['file_type'],
            data.get('file_size', '0 MB'),
            data.get('file_path', ''),
            data.get('category', 'other'),
            data.get('exam_type', 'both')
        ))

        material_id = cursor.lastrowid
        connection.commit()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Материал успешно создан',
            'material_id': material_id
        })

    except Exception as e:
        print(f"❌ Ошибка создания материала: {e}")
        return jsonify({'success': False, 'message': 'Ошибка создания материала'}), 500


UPLOAD_FOLDER = 'uploads/materials'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'zip', 'rar'}


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/api/tutor/upload-material', methods=['POST'])
def api_upload_material():
    """API для загрузки учебного материала"""
    if 'user_id' not in session or session['role'] != 'tutor':
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403

    try:
        # Проверяем наличие файла
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'Файл не выбран'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'Файл не выбран'}), 400

        if file and allowed_file(file.filename):
            # Создаем уникальное имя файла
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"

            # Создаем папку если не существует
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            file_path = os.path.join(UPLOAD_FOLDER, unique_filename)

            # Сохраняем файл
            file.save(file_path)

            # Получаем данные из формы
            title = request.form.get('title')
            description = request.form.get('description', '')
            category = request.form.get('category', 'other')
            exam_type = request.form.get('exam_type', 'both')

            # Получаем размер файла
            file_size = f"{os.path.getsize(file_path) / 1024 / 1024:.1f} MB"
            file_type = filename.rsplit('.', 1)[1].lower()

            # Сохраняем в базу данных
            connection = db.get_connection()
            cursor = connection.cursor()

            cursor.execute("""
                INSERT INTO materials (tutor_id, title, description, file_type, file_size, file_path, category, exam_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session['user_id'],
                title,
                description,
                file_type,
                file_size,
                file_path,
                category,
                exam_type
            ))

            material_id = cursor.lastrowid
            connection.commit()
            connection.close()

            print(f"✅ Материал загружен: {title} (ID: {material_id})")

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    material_text = f.read()

                print("🧠 Автогенерация теста для нового материала...")
                test_json = generate_test_from_text(material_text)

                connection = db.get_connection()
                cursor = connection.cursor()

                cursor.execute("SELECT id FROM users WHERE created_by = ?", (session['user_id'],))
                students = cursor.fetchall()

                for s in students:
                    student_id = s['id']
                    db.save_generated_test(
                        student_id=student_id,
                        material_name=title,
                        json_content=test_json
                    )

                connection.close()
                print("✅ Тест успешно создан и отправлен ученикам!")

            except Exception as e:
                print(f"⚠️ Ошибка автогенерации теста: {e}")

            return jsonify({
                'success': True,
                'message': 'Материал успешно загружен',
                'material_id': material_id
            })
        else:
            return jsonify({'success': False, 'message': 'Недопустимый тип файла'}), 400

    except Exception as e:
        print(f"❌ Ошибка загрузки материала: {e}")
        return jsonify({'success': False, 'message': f'Ошибка загрузки: {str(e)}'}), 500


@app.route('/api/materials/<int:material_id>/download')
def download_material(material_id):
    """Скачивание материала"""
    try:
        connection = db.get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM materials WHERE id = ?", (material_id,))
        material = cursor.fetchone()

        if not material:
            connection.close()
            return jsonify({'error': 'Материал не найден'}), 404

        material_dict = dict(material)

        # Проверяем права доступа
        if session['role'] == 'student':
            cursor.execute("""
                SELECT u.created_by FROM users u 
                WHERE u.id = ? AND u.created_by = ?
            """, (session['user_id'], material_dict['tutor_id']))
            if not cursor.fetchone():
                connection.close()
                return jsonify({'error': 'Доступ запрещен'}), 403

        connection.close()

        file_path = material_dict['file_path']

        if not file_path or not os.path.exists(file_path):
            temp_content = f"Материал: {material_dict['title']}\n\n"
            temp_content += f"Описание: {material_dict.get('description', '')}\n"
            temp_content += f"Тип: {material_dict['file_type']}\n"
            temp_content += f"Дата создания: {material_dict['created_at']}"

            temp_filename = f"material_{material_id}.txt"
            temp_path = os.path.join(UPLOAD_FOLDER, temp_filename)

            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(temp_content)

            return send_file(temp_path, as_attachment=True, download_name=f"{material_dict['title']}.txt")

        return send_file(file_path, as_attachment=True,
                         download_name=f"{material_dict['title']}.{material_dict['file_type']}")

    except Exception as e:
        print(f"❌ Ошибка скачивания материала: {e}")
        return jsonify({'error': 'Ошибка скачивания'}), 500

@app.route('/api/student/tests')
def api_student_tests():
    if 'user_id' not in session or session['role'] != 'student':
        return jsonify({'success': False}), 403

    student_id = session['user_id']
    connection = db.get_connection()
    cursor = connection.cursor()

    # Получаем все тесты и присоединяем результаты, если они есть
    cursor.execute("""
        SELECT 
            t.id,
            t.material_name,
            t.created_at,
            tr.percentage,
            tr.submitted_at
        FROM tests t
        LEFT JOIN test_results tr ON t.id = tr.test_id AND tr.student_id = t.student_id
        WHERE t.student_id = ?
        ORDER BY t.created_at DESC
    """, (student_id,))
    
    tests = [dict(r) for r in cursor.fetchall()]

    connection.close()
    return jsonify({'success': True, 'tests': tests})


@app.route('/api/materials/<int:material_id>/preview')
def preview_material(material_id):
    """Просмотр материала"""
    try:
        connection = db.get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM materials WHERE id = ?", (material_id,))
        material = cursor.fetchone()
        connection.close()

        if not material:
            return jsonify({'error': 'Материал не найден'}), 404

        material_dict = dict(material)
        file_path = material_dict['file_path']

        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': 'Файл не найден'}), 404

        # Для PDF файлов отправляем как PDF
        if material_dict['file_type'] == 'pdf':
            return send_file(file_path, mimetype='application/pdf')

        # Для текстовых файлов
        elif material_dict['file_type'] == 'txt':
            return send_file(file_path, mimetype='text/plain')

        # Для других типов предлагаем скачать
        else:
            return send_file(file_path, as_attachment=True,
                             download_name=f"{material_dict['title']}.{material_dict['file_type']}")

    except Exception as e:
        print(f"❌ Ошибка просмотра материала: {e}")
        return jsonify({'error': 'Ошибка просмотра'}), 500


@app.route('/api/tutor/materials/<int:material_id>', methods=['DELETE'])
def delete_material(material_id):
    """Удаление материала (только для репетитора)"""
    if 'user_id' not in session or session['role'] != 'tutor':
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403

    try:
        connection = db.get_connection()
        cursor = connection.cursor()

        # Проверяем, что материал принадлежит текущему репетитору
        cursor.execute("SELECT * FROM materials WHERE id = ? AND tutor_id = ?", (material_id, session['user_id']))
        material = cursor.fetchone()

        if not material:
            return jsonify({'success': False, 'message': 'Материал не найден'}), 404

        material_dict = dict(material)

        # Удаляем файл с диска
        file_path = material_dict['file_path']
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        # Удаляем запись из базы данных
        cursor.execute("DELETE FROM materials WHERE id = ?", (material_id,))
        connection.commit()
        connection.close()

        print(f"✅ Материал удален: {material_dict['title']} (ID: {material_id})")

        return jsonify({
            'success': True,
            'message': 'Материал успешно удален'
        })

    except Exception as e:
        print(f"❌ Ошибка удаления материала: {e}")
        return jsonify({'success': False, 'message': f'Ошибка удаления: {str(e)}'}), 500


@app.route('/api/materials/<int:material_id>/download-stats', methods=['POST'])
def update_download_stats(material_id):
    """Обновление статистики скачиваний"""
    try:
        connection = db.get_connection()
        cursor = connection.cursor()

        # Здесь можно добавить логику для отслеживания статистики скачиваний
        # Например, создать таблицу download_stats или обновлять поле в materials
        cursor.execute("UPDATE materials SET download_count = COALESCE(download_count, 0) + 1 WHERE id = ?",
                       (material_id,))

        connection.commit()
        connection.close()

        return jsonify({'success': True})

    except Exception as e:
        print(f"❌ Ошибка обновления статистики: {e}")
        return jsonify({'success': False}), 500

@app.route('/api/test/submit', methods=['POST'])
def submit_test():
    """API для обработки результатов теста и подсчета процента правильных ответов."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Необходима авторизация'}), 401

    data = request.get_json()
    test_id = data.get('test_id')
    answers = data.get('answers')  # Ожидаем объект вида {'1': 'A', '2': 'C'}

    if not test_id or not answers:
        return jsonify({'success': False, 'message': 'Неполные данные'}), 400

    try:
        connection = db.get_connection()
        cursor = connection.cursor()

        # Получаем тест из базы, чтобы узнать правильные ответы
        cursor.execute("SELECT json_content FROM tests WHERE id = ?", (test_id,))
        row = cursor.fetchone()

        if not row:
            return jsonify({'success': False, 'message': 'Тест не найден'}), 404

        import json
        test_data = json.loads(row['json_content'])
        questions = test_data.get('questions', [])

        correct_answers_count = 0
        total_questions = len(questions)

        # Сравниваем ответы и формируем детальный результат
        detailed_results = []
        for question in questions:
            question_id = str(question['id'])
            correct_answer = question['correct']
            student_answer = answers.get(question_id)
            is_correct = student_answer == correct_answer

            if is_correct:
                correct_answers_count += 1
            
            detailed_results.append({
                'question_id': question_id,
                'question_text': question['question'],
                'student_answer': student_answer,
                'correct_answer': correct_answer,
                'is_correct': is_correct
            })
        
        # Считаем процент
        percentage = (correct_answers_count / total_questions) * 100 if total_questions > 0 else 0

        # Сохраняем результат в базу данных
        db.save_test_result(
            student_id=session['user_id'],
            test_id=test_id,
            percentage=percentage,
            correct_count=correct_answers_count,
            total_count=total_questions
        )

        connection.close()

        return jsonify({
            'success': True,
            'message': 'Результат успешно рассчитан',
            'percentage': round(percentage, 2),
            'correct_count': correct_answers_count,
            'total_count': total_questions,
            'results': detailed_results
        })

    except Exception as e:
        print(f"❌ Ошибка при обработке результатов теста: {e}")
        return jsonify({'success': False, 'message': 'Внутренняя ошибка сервера'}), 500


@app.route('/api/tests/<int:test_id>', methods=['DELETE'])
def delete_test(test_id):
    """Удаление теста текущего ученика"""
    try:
        student_id = session['user_id']
        if db.delete_test(test_id, student_id):
            return jsonify({'success': True, 'message': 'Тест успешно удален'})
        else:
            return jsonify({'success': False, 'message': 'Тест не найден или нет прав'}), 404
    except Exception as e:
        print(f"❌ Ошибка удаления теста {test_id}: {e}")
        return jsonify({'success': False, 'message': 'Ошибка при удалении теста'}), 500
# Удаление тестов отключено по запросу пользователя



if __name__ == '__main__':
    print("Flask сервер запущен!")
    print("Откройте: http://localhost:5000")
    print("Тестовые данные:")
    print("Репетитор: логин 'tutor', пароль 'tutor'")
    app.run(debug=True, host='0.0.0.0', port=5000)


