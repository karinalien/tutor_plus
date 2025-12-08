from database.database import Database

db = Database('database/tutoring.db')
db.create_tables()
db.check_and_update_schema()
db.ensure_tutor_user()

print("✅ База данных инициализирована")
print("👤 Пользователь tutor: логин 'tutor', пароль 'tutor'")