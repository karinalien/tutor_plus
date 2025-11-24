-- Таблица пользователей (общая для репетитора и учеников)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('tutor', 'student')),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    exam_type VARCHAR(10) CHECK (exam_type IN ('oge', 'ege')),
    lesson_price DECIMAL(10,2) DEFAULT 0.00,
    contact_info TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_by INTEGER, -- ID репетитора, который создал ученика
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

-- Таблица тем/предметов
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    created_by INTEGER NOT NULL, -- Какой репетитор создал тему
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
);

-- Таблица расписания
CREATE TABLE IF NOT EXISTS schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    tutor_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    day_of_week VARCHAR(15) NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    lesson_link TEXT,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'cancelled', 'completed')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (tutor_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
);

-- Таблица проведенных уроков
CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    lesson_date DATE NOT NULL,
    is_paid BOOLEAN DEFAULT 0,
    homework TEXT,
    tutor_notes TEXT,
    student_feedback TEXT,
    conducted_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (schedule_id) REFERENCES schedule(id) ON DELETE CASCADE,
    FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
);

-- Таблица прогресса студентов
CREATE TABLE IF NOT EXISTS student_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    test_score DECIMAL(5,2),
    tutor_feedback_score INTEGER CHECK (tutor_feedback_score >= 1 AND tutor_feedback_score <= 5),
    overall_progress DECIMAL(5,2) DEFAULT 0.00,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE,
    UNIQUE(student_id, topic_id)
);

-- Таблица запросов на перенос
CREATE TABLE IF NOT EXISTS rescheduling_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    old_schedule_id INTEGER NOT NULL,
    new_day_of_week VARCHAR(15) NOT NULL,
    new_start_time TIME NOT NULL,
    new_end_time TIME NOT NULL,
    reason TEXT,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (old_schedule_id) REFERENCES schedule(id) ON DELETE CASCADE
);

-- Таблица доходов
CREATE TABLE IF NOT EXISTS income (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    payment_date DATE NOT NULL,
    month_year VARCHAR(7) NOT NULL,
    status VARCHAR(20) DEFAULT 'paid' CHECK (status IN ('paid', 'pending', 'overdue')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (schedule_id) REFERENCES schedule(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
);


-- Таблица учебных материалов
CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tutor_id INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    file_type VARCHAR(10) NOT NULL,
    file_size VARCHAR(20) DEFAULT '0 MB',
    file_path TEXT,
    category VARCHAR(50) DEFAULT 'other',
    exam_type VARCHAR(10) CHECK(exam_type IN ('oge', 'ege', 'both')) DEFAULT 'both',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    download_count INTEGER DEFAULT 0,
    FOREIGN KEY (tutor_id) REFERENCES users (id) ON DELETE CASCADE
);

-- Таблица для разовых занятий (если еще не существует)
CREATE TABLE IF NOT EXISTS single_lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL,
    lesson_date DATE NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (schedule_id) REFERENCES schedule (id) ON DELETE CASCADE
);


-- Создание индексов для оптимизации
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_created_by ON users(created_by);
CREATE INDEX IF NOT EXISTS idx_schedule_student_id ON schedule(student_id);
CREATE INDEX IF NOT EXISTS idx_schedule_tutor_id ON schedule(tutor_id);
CREATE INDEX IF NOT EXISTS idx_lessons_schedule_id ON lessons(schedule_id);
CREATE INDEX IF NOT EXISTS idx_lessons_date ON lessons(lesson_date);
CREATE INDEX IF NOT EXISTS idx_student_progress_student ON student_progress(student_id, topic_id);
CREATE INDEX IF NOT EXISTS idx_income_month ON income(month_year);
CREATE INDEX IF NOT EXISTS idx_materials_tutor_id ON materials(tutor_id);
CREATE INDEX IF NOT EXISTS idx_materials_category ON materials(category);

-- Вставка начальных данных (репетитор по умолчанию)
INSERT OR IGNORE INTO users (username, password_hash, role, first_name, last_name, lesson_price, contact_info)
VALUES ('tutor', 'tutor', 'tutor', 'Главный', 'Репетитор', 1500.00, 'tutor@example.com');

CREATE TABLE IF NOT EXISTS income_lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tutor_id INTEGER NOT NULL,
    lesson_date TEXT NOT NULL,          -- '2025-11-24'
    student_name TEXT NOT NULL,
    exam TEXT NOT NULL,                 -- 'ОГЭ' / 'ЕГЭ' или 'oge'/'ege'
    price INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'paid', 'overdue')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
