import sqlite3
import logging
import json
from datetime import datetime, timedelta
from contextlib import contextmanager

logger = logging.getLogger(__name__)


# Менеджер для работы с базой данных
class DatabaseManager:

    def __init__(self, db_path='flashcards.db'):
        self.db_path = db_path
        self._init_database()

# Инициализация базы данных
    def _init_database(self):
        try:
            with self.get_connection() as conn:
                conn.execute('PRAGMA foreign_keys = ON')
                conn.execute('PRAGMA journal_mode = WAL')
                self.create_tables(conn)
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

# Создание таблиц, если они не существуют
    def create_tables(self, conn):
        tables = [
            '''
            CREATE TABLE IF NOT EXISTS users
            (
                id
                INTEGER
                PRIMARY
                KEY
                AUTOINCREMENT,
                telegram_id
                INTEGER
                UNIQUE
                NOT
                NULL,
                username
                TEXT,
                first_name
                TEXT,
                last_name
                TEXT,
                language_code
                TEXT
                DEFAULT
                'ru',
                created_at
                DATETIME
                DEFAULT
                CURRENT_TIMESTAMP,
                last_active
                DATETIME
                DEFAULT
                CURRENT_TIMESTAMP
            )
            ''',

            '''
            CREATE TABLE IF NOT EXISTS categories
            (
                id
                INTEGER
                PRIMARY
                KEY
                AUTOINCREMENT,
                user_id
                INTEGER
                NOT
                NULL,
                name
                TEXT
                NOT
                NULL,
                description
                TEXT,
                color
                TEXT
                DEFAULT
                '#3498db',
                created_at
                DATETIME
                DEFAULT
                CURRENT_TIMESTAMP,
                updated_at
                DATETIME
                DEFAULT
                CURRENT_TIMESTAMP,
                FOREIGN
                KEY
            (
                user_id
            ) REFERENCES users
            (
                telegram_id
            ) ON DELETE CASCADE
                )
            ''',

            '''
            CREATE TABLE IF NOT EXISTS cards
            (
                id
                INTEGER
                PRIMARY
                KEY
                AUTOINCREMENT,
                user_id
                INTEGER
                NOT
                NULL,
                front
                TEXT
                NOT
                NULL,
                back
                TEXT
                NOT
                NULL,
                category_id
                INTEGER
                NOT
                NULL,
                status
                TEXT
                DEFAULT
                'learning',
                difficulty
                INTEGER
                DEFAULT
                1,
                last_reviewed
                DATETIME,
                next_review
                DATETIME,
                review_count
                INTEGER
                DEFAULT
                0,
                correct_answers
                INTEGER
                DEFAULT
                0,
                wrong_answers
                INTEGER
                DEFAULT
                0,
                created_at
                DATETIME
                DEFAULT
                CURRENT_TIMESTAMP,
                updated_at
                DATETIME
                DEFAULT
                CURRENT_TIMESTAMP,
                FOREIGN
                KEY
            (
                user_id
            ) REFERENCES users
            (
                telegram_id
            ) ON DELETE CASCADE,
                FOREIGN KEY
            (
                category_id
            ) REFERENCES categories
            (
                id
            )
              ON DELETE CASCADE
                )
            ''',

            '''
            CREATE TABLE IF NOT EXISTS reminders
            (
                id
                INTEGER
                PRIMARY
                KEY
                AUTOINCREMENT,
                user_id
                INTEGER
                NOT
                NULL,
                enabled
                BOOLEAN
                DEFAULT
                1,
                reminder_time
                TIME
                DEFAULT
                '20:00',
                timezone
                TEXT
                DEFAULT
                'Europe/Moscow',
                days_of_week
                TEXT
                DEFAULT
                '1,2,3,4,5,6,7',
                last_sent
                DATETIME,
                next_sent
                DATETIME,
                created_at
                DATETIME
                DEFAULT
                CURRENT_TIMESTAMP,
                updated_at
                DATETIME
                DEFAULT
                CURRENT_TIMESTAMP,
                FOREIGN
                KEY
            (
                user_id
            ) REFERENCES users
            (
                telegram_id
            ) ON DELETE CASCADE
                )
            ''',

            '''
            CREATE TABLE IF NOT EXISTS study_sessions
            (
                id
                INTEGER
                PRIMARY
                KEY
                AUTOINCREMENT,
                user_id
                INTEGER
                NOT
                NULL,
                cards_studied
                INTEGER
                DEFAULT
                0,
                correct_answers
                INTEGER
                DEFAULT
                0,
                wrong_answers
                INTEGER
                DEFAULT
                0,
                session_duration
                INTEGER
                DEFAULT
                0,
                session_type
                TEXT
                DEFAULT
                'manual',
                created_at
                DATETIME
                DEFAULT
                CURRENT_TIMESTAMP,
                FOREIGN
                KEY
            (
                user_id
            ) REFERENCES users
            (
                telegram_id
            ) ON DELETE CASCADE
                )
            ''',

            '''
            CREATE TABLE IF NOT EXISTS user_stats
            (
                id
                INTEGER
                PRIMARY
                KEY
                AUTOINCREMENT,
                user_id
                INTEGER
                UNIQUE
                NOT
                NULL,
                total_cards
                INTEGER
                DEFAULT
                0,
                learned_cards
                INTEGER
                DEFAULT
                0,
                total_study_time
                INTEGER
                DEFAULT
                0,
                total_sessions
                INTEGER
                DEFAULT
                0,
                correct_answers
                INTEGER
                DEFAULT
                0,
                wrong_answers
                INTEGER
                DEFAULT
                0,
                streak_days
                INTEGER
                DEFAULT
                0,
                last_study_date
                DATE,
                created_at
                DATETIME
                DEFAULT
                CURRENT_TIMESTAMP,
                updated_at
                DATETIME
                DEFAULT
                CURRENT_TIMESTAMP,
                FOREIGN
                KEY
            (
                user_id
            ) REFERENCES users
            (
                telegram_id
            ) ON DELETE CASCADE
                )
            '''
        ]

        indexes = [
            'CREATE INDEX IF NOT EXISTS idx_cards_user_id ON cards(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_cards_category_id ON cards(category_id)',
            'CREATE INDEX IF NOT EXISTS idx_cards_status ON cards(status)',
            'CREATE INDEX IF NOT EXISTS idx_cards_next_review ON cards(next_review)',
            'CREATE INDEX IF NOT EXISTS idx_categories_user_id ON categories(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_reminders_enabled ON reminders(enabled)',
            'CREATE INDEX IF NOT EXISTS idx_study_sessions_user_id ON study_sessions(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_study_sessions_created_at ON study_sessions(created_at)',
        ]

        for table_sql in tables:
            conn.execute(table_sql)

        for index_sql in indexes:
            try:
                conn.execute(index_sql)
            except:
                pass

# Контекстный менеджер для соединения с БД
    @contextmanager
    def get_connection(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()


db_manager = DatabaseManager()


# Декоратор для автоматического предоставления соединения с БД
def with_connection(func):

    def wrapper(*args, **kwargs):
        with db_manager.get_connection() as conn:
            return func(conn, *args, **kwargs)

    return wrapper


# УТИЛИТЫ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ
class UserUtils:

# Создание или обновление пользователя
    @staticmethod
    @with_connection
    def create_or_update_user(conn, telegram_id, username=None, first_name=None, last_name=None, language_code='ru'):
        try:
            cursor = conn.execute(
                'SELECT id FROM users WHERE telegram_id = ?',
                (telegram_id,)
            )
            user_exists = cursor.fetchone()

            if user_exists:
                conn.execute('''
                             UPDATE users
                             SET username      = ?,
                                 first_name    = ?,
                                 last_name     = ?,
                                 language_code = ?,
                                 last_active   = CURRENT_TIMESTAMP
                             WHERE telegram_id = ?
                             ''', (username, first_name, last_name, language_code, telegram_id))
            else:
                conn.execute('''
                             INSERT INTO users
                                 (telegram_id, username, first_name, last_name, language_code)
                             VALUES (?, ?, ?, ?, ?)
                             ''', (telegram_id, username, first_name, last_name, language_code))

                UserUtils._create_default_user_data(conn, telegram_id)

            return True
        except Exception as e:
            logger.error(f"Error creating/updating user: {e}")
            return False

# Создание дефолтных данных для пользователя
    @staticmethod
    def _create_default_user_data(conn, telegram_id):
        try:
            conn.execute('''
                         INSERT INTO categories (user_id, name, description)
                         VALUES (?, 'По умолчанию', 'Основная категория для карточек')
                         ''', (telegram_id,))

            conn.execute('''
                         INSERT INTO reminders (user_id)
                         VALUES (?)
                         ''', (telegram_id,))

            conn.execute('''
                         INSERT INTO user_stats (user_id)
                         VALUES (?)
                         ''', (telegram_id,))

        except Exception as e:
            logger.error(f"Error creating default user data: {e}")

# Получение статистики пользователя
    @staticmethod
    @with_connection
    def get_user_stats(conn, telegram_id):
        try:
            cursor = conn.execute('''
                                  SELECT *
                                  FROM user_stats
                                  WHERE user_id = ?
                                  ''', (telegram_id,))

            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return None

# Обновление времени последней активности
    @staticmethod
    @with_connection
    def update_user_activity(conn, telegram_id):
        try:
            conn.execute('''
                         UPDATE users
                         SET last_active = CURRENT_TIMESTAMP
                         WHERE telegram_id = ?
                         ''', (telegram_id,))

            UserUtils._update_streak(conn, telegram_id)

            return True
        except Exception as e:
            logger.error(f"Error updating user activity: {e}")
            return False

# Обновление счетчика дней подряд
    @staticmethod
    def _update_streak(conn, telegram_id):
        try:
            cursor = conn.execute('''
                                  SELECT last_study_date
                                  FROM user_stats
                                  WHERE user_id = ?
                                  ''', (telegram_id,))

            result = cursor.fetchone()
            last_study_date = result['last_study_date'] if result else None

            today = datetime.now().date()

            if last_study_date:
                last_date = datetime.strptime(last_study_date, '%Y-%m-%d').date()
                days_diff = (today - last_date).days

                if days_diff == 1:
                    conn.execute('''
                                 UPDATE user_stats
                                 SET streak_days     = streak_days + 1,
                                     last_study_date = DATE ('now')
                                 WHERE user_id = ?
                                 ''', (telegram_id,))
                elif days_diff > 1:
                    conn.execute('''
                                 UPDATE user_stats
                                 SET streak_days     = 1,
                                     last_study_date = DATE ('now')
                                 WHERE user_id = ?
                                 ''', (telegram_id,))
            else:
                conn.execute('''
                             UPDATE user_stats
                             SET streak_days     = 1,
                                 last_study_date = DATE ('now')
                             WHERE user_id = ?
                             ''', (telegram_id,))

        except Exception as e:
            logger.error(f"Error updating streak: {e}")


# УТИЛИТЫ ДЛЯ РАБОТЫ С КАТЕГОРИЯМИ
class CategoryUtils:

# Получение всех категорий пользователя
    @staticmethod
    @with_connection
    def get_user_categories(conn, telegram_id):
        try:
            cursor = conn.execute('''
                                  SELECT id, name, description, color, created_at
                                  FROM categories
                                  WHERE user_id = ?
                                  ORDER BY name
                                  ''', (telegram_id,))

            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting user categories: {e}")
            return []

# Создание новой категории
    @staticmethod
    @with_connection
    def create_category(conn, telegram_id, name, description=None, color=None):
        try:
            cursor = conn.execute('''
                                  INSERT INTO categories (user_id, name, description, color, updated_at)
                                  VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                                  ''', (telegram_id, name, description, color))

            category_id = cursor.lastrowid
            return category_id
        except Exception as e:
            logger.error(f"Error creating category: {e}")
            return None

# Обновление категории
    @staticmethod
    @with_connection
    def update_category(conn, category_id, name=None, description=None, color=None):
        try:
            update_fields = []
            params = []

            if name:
                update_fields.append("name = ?")
                params.append(name)
            if description is not None:
                update_fields.append("description = ?")
                params.append(description)
            if color:
                update_fields.append("color = ?")
                params.append(color)

            if not update_fields:
                return False

            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(category_id)

            query = f"UPDATE categories SET {', '.join(update_fields)} WHERE id = ?"
            conn.execute(query, params)
            return True
        except Exception as e:
            logger.error(f"Error updating category: {e}")
            return False

# Удаление категории и всех её карточек (каскадно)
    @staticmethod
    @with_connection
    def delete_category(conn, category_id):
        try:
            conn.execute('DELETE FROM categories WHERE id = ?', (category_id,))
            return True
        except Exception as e:
            logger.error(f"Error deleting category: {e}")
            return False

# Получение категории по ID
    @staticmethod
    @with_connection
    def get_category_by_id(conn, category_id):
        try:
            cursor = conn.execute('''
                                  SELECT id, user_id, name, description, color, created_at
                                  FROM categories
                                  WHERE id = ?
                                  ''', (category_id,))

            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error getting category: {e}")
            return None


# УТИЛИТЫ ДЛЯ РАБОТЫ С КАРТОЧКАМИ
class CardUtils:

# Создание новой карточки
    @staticmethod
    @with_connection
    def create_card(conn, telegram_id, front, back, category_id, status='learning'):
        try:
            next_review = datetime.now() + timedelta(hours=12)

            cursor = conn.execute('''
                                  INSERT INTO cards
                                  (user_id, front, back, category_id, status, next_review,
                                   created_at, updated_at)
                                  VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                                  ''', (telegram_id, front, back, category_id, status, next_review))

            card_id = cursor.lastrowid

            CardUtils._update_user_stats_after_card_creation(conn, telegram_id)

            return card_id
        except Exception as e:
            logger.error(f"Error creating card: {e}")
            return None

# Обновление статистики после создания карточки
    @staticmethod
    def _update_user_stats_after_card_creation(conn, telegram_id):
        try:
            conn.execute('''
                         UPDATE user_stats
                         SET total_cards = total_cards + 1,
                             updated_at  = CURRENT_TIMESTAMP
                         WHERE user_id = ?
                         ''', (telegram_id,))
        except Exception as e:
            logger.error(f"Error updating stats after card creation: {e}")

# Получение карточек пользователя с фильтрами
    @staticmethod
    @with_connection
    def get_user_cards(conn, telegram_id, category_id=None, status=None, limit=None, offset=0):
        try:
            query = '''
                    SELECT c.*, cat.name as category_name
                    FROM cards c
                             LEFT JOIN categories cat ON c.category_id = cat.id
                    WHERE c.user_id = ? \
                    '''
            params = [telegram_id]

            if category_id:
                query += ' AND c.category_id = ?'
                params.append(category_id)

            if status:
                query += ' AND c.status = ?'
                params.append(status)

            query += ' ORDER BY c.created_at DESC'

            if limit:
                query += ' LIMIT ? OFFSET ?'
                params.extend([limit, offset])

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting user cards: {e}")
            return []

# Получение карточки по ID
    @staticmethod
    @with_connection
    def get_card_by_id(conn, card_id):
        try:
            cursor = conn.execute('''
                                  SELECT c.*, cat.name as category_name
                                  FROM cards c
                                           LEFT JOIN categories cat ON c.category_id = cat.id
                                  WHERE c.id = ?
                                  ''', (card_id,))

            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error getting card: {e}")
            return None

# Обновление карточки
    @staticmethod
    @with_connection
    def update_card(conn, card_id, front=None, back=None, category_id=None, status=None):
        try:
            update_fields = []
            params = []

            if front:
                update_fields.append("front = ?")
                params.append(front)
            if back:
                update_fields.append("back = ?")
                params.append(back)
            if category_id:
                update_fields.append("category_id = ?")
                params.append(category_id)
            if status:
                update_fields.append("status = ?")
                params.append(status)

            if not update_fields:
                return False

            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(card_id)

            query = f"UPDATE cards SET {', '.join(update_fields)} WHERE id = ?"
            conn.execute(query, params)
            return True
        except Exception as e:
            logger.error(f"Error updating card: {e}")
            return False

# Удаление карточки
    @staticmethod
    @with_connection
    def delete_card(conn, card_id):
        try:
            cursor = conn.execute('SELECT user_id FROM cards WHERE id = ?', (card_id,))
            result = cursor.fetchone()

            if result:
                user_id = result['user_id']
                conn.execute('DELETE FROM cards WHERE id = ?', (card_id,))

                conn.execute('''
                             UPDATE user_stats
                             SET total_cards = total_cards - 1,
                                 updated_at  = CURRENT_TIMESTAMP
                             WHERE user_id = ?
                             ''', (user_id,))

            return True
        except Exception as e:
            logger.error(f"Error deleting card: {e}")
            return False

# Поиск карточек по запросу
    @staticmethod
    @with_connection
    def search_cards(conn, telegram_id, search_query, category_id=None):
        try:
            query = '''
                    SELECT c.id, c.front, c.back, c.status, cat.name as category_name
                    FROM cards c
                             LEFT JOIN categories cat ON c.category_id = cat.id
                    WHERE c.user_id = ? \
                      AND (c.front LIKE ? OR c.back LIKE ?) \
                    '''
            params = [telegram_id, f'%{search_query}%', f'%{search_query}%']

            if category_id:
                query += ' AND c.category_id = ?'
                params.append(category_id)

            query += ' ORDER BY c.front'

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error searching cards: {e}")
            return []

# Получение карточек для повторения (система интервальных повторений)
    @staticmethod
    @with_connection
    def get_cards_for_review(conn, telegram_id, limit=20):
        try:
            cursor = conn.execute('''
                                  SELECT c.*, cat.name as category_name
                                  FROM cards c
                                           LEFT JOIN categories cat ON c.category_id = cat.id
                                  WHERE c.user_id = ?
                                    AND (c.next_review IS NULL OR c.next_review <= CURRENT_TIMESTAMP)
                                    AND c.status = 'learning'
                                  ORDER BY CASE
                                               WHEN c.difficulty >= 4 THEN 1
                                               WHEN c.difficulty >= 2 THEN 2
                                               ELSE 3
                                               END,
                                           c.review_count ASC,
                                           c.correct_answers / CAST(c.review_count AS REAL) ASC LIMIT ?
                                  ''', (telegram_id, limit))

            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting cards for review: {e}")
            return []

# Обновление карточки после повторения (алгоритм SM-2)
    @staticmethod
    @with_connection
    def update_card_after_review(conn, card_id, is_correct):
        try:
            cursor = conn.execute('''
                                  SELECT review_count,
                                         correct_answers,
                                         wrong_answers,
                                         difficulty,
                                         status
                                  FROM cards
                                  WHERE id = ?
                                  ''', (card_id,))

            card = cursor.fetchone()
            if not card:
                return False

            review_count = card['review_count'] + 1

            if is_correct:
                correct_answers = card['correct_answers'] + 1
                wrong_answers = card['wrong_answers']
            else:
                correct_answers = card['correct_answers']
                wrong_answers = card['wrong_answers'] + 1

            total_answers = correct_answers + wrong_answers
            success_rate = correct_answers / total_answers if total_answers > 0 else 0

            # Преобразуем успешность в сложность 1-5
            if success_rate >= 0.9:
                difficulty = 1
            elif success_rate >= 0.7:
                difficulty = 2
            elif success_rate >= 0.5:
                difficulty = 3
            elif success_rate >= 0.3:
                difficulty = 4
            else:
                difficulty = 5

            status = card['status']
            if correct_answers >= 5 and success_rate >= 0.8:
                status = 'learned'
            elif status == 'learned' and not is_correct:
                status = 'learning'

            next_review = CardUtils._calculate_next_review(
                difficulty, review_count, is_correct
            )

            conn.execute('''
                         UPDATE cards
                         SET review_count    = ?,
                             correct_answers = ?,
                             wrong_answers   = ?,
                             difficulty      = ?,
                             status          = ?,
                             last_reviewed   = CURRENT_TIMESTAMP,
                             next_review     = ?,
                             updated_at      = CURRENT_TIMESTAMP
                         WHERE id = ?
                         ''', (review_count, correct_answers, wrong_answers,
                               difficulty, status, next_review, card_id))

            return True
        except Exception as e:
            logger.error(f"Error updating card after review: {e}")
            return False

# Расчет следующей даты повторения по алгоритму SM-2
    @staticmethod
    def _calculate_next_review(difficulty, review_count, is_correct):
        now = datetime.now()

        if not is_correct:
            return now + timedelta(minutes=10)

        # Базовые интервалы в днях в зависимости от сложности
        base_intervals = {1: 7,  2: 5,  3: 3,  4: 2,   5: 1  }

        base_interval = base_intervals.get(difficulty, 1)

        multiplier = 1.5 ** (review_count - 1)
        days = base_interval * multiplier

        days = min(days, 90)

        return now + timedelta(days=days)


# УТИЛИТЫ ДЛЯ РАБОТЫ С НАПОМИНАНИЯМИ
class ReminderUtils:

# Получение настроек напоминаний пользователя
    @staticmethod
    @with_connection
    def get_user_reminder(conn, telegram_id):
        try:
            cursor = conn.execute('''
                                  SELECT id,
                                         enabled,
                                         reminder_time,
                                         timezone,
                                         days_of_week,
                                         last_sent,
                                         next_sent
                                  FROM reminders
                                  WHERE user_id = ?
                                  ''', (telegram_id,))

            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error getting reminder: {e}")
            return None

# Обновление настроек напоминаний
    @staticmethod
    @with_connection
    def update_reminder(conn, telegram_id, enabled=None, reminder_time=None,
                        timezone=None, days_of_week=None):
        try:
            update_fields = []
            params = []

            if enabled is not None:
                update_fields.append("enabled = ?")
                params.append(1 if enabled else 0)
            if reminder_time:
                update_fields.append("reminder_time = ?")
                params.append(reminder_time)
            if timezone:
                update_fields.append("timezone = ?")
                params.append(timezone)
            if days_of_week:
                update_fields.append("days_of_week = ?")
                params.append(days_of_week)

            if not update_fields:
                return False

            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(telegram_id)

            query = f"UPDATE reminders SET {', '.join(update_fields)} WHERE user_id = ?"
            conn.execute(query, params)
            return True
        except Exception as e:
            logger.error(f"Error updating reminder: {e}")
            return False

# Получение всех активных напоминаний
    @staticmethod
    @with_connection
    def get_active_reminders(conn):
        try:
            cursor = conn.execute('''
                                  SELECT r.user_id,
                                         r.reminder_time,
                                         r.timezone,
                                         r.days_of_week,
                                         u.first_name,
                                         u.username
                                  FROM reminders r
                                           JOIN users u ON r.user_id = u.telegram_id
                                  WHERE r.enabled = 1
                                  ''')

            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting active reminders: {e}")
            return []


# УТИЛИТЫ ДЛЯ ЭКСПОРТА/ИМПОРТА
class ExportImportUtils:

# Экспорт данных пользователя
    @staticmethod
    @with_connection
    def export_user_data(conn, telegram_id, format='json'):
        try:
            categories = CategoryUtils.get_user_categories(conn, telegram_id)

            cards = CardUtils.get_user_cards(conn, telegram_id)

            reminder = ReminderUtils.get_user_reminder(conn, telegram_id)

            user_stats = UserUtils.get_user_stats(conn, telegram_id)

            data = {
                'user_id': telegram_id,
                'export_date': datetime.now().isoformat(),
                'format_version': '1.0',
                'categories': categories,
                'cards': cards,
                'reminder': reminder,
                'user_stats': user_stats
            }

            if format == 'json':
                return json.dumps(data, ensure_ascii=False, indent=2, default=str)
            elif format == 'csv':
                return ExportImportUtils._convert_to_csv(data)
            else:
                return None

        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            return None

# Конвертация данных в CSV формат
    @staticmethod
    def _convert_to_csv(data):
        try:
            import io
            import csv

            output = io.StringIO()
            writer = csv.writer(output)

            writer.writerow(['Front', 'Back', 'Category', 'Status', 'Difficulty',
                             'Review Count', 'Correct Answers', 'Wrong Answers'])

            for card in data['cards']:
                writer.writerow([card['front'], card['back'], card.get('category_name', ''), card['status'],
                                 card['difficulty'], card['review_count'], card['correct_answers'], card['wrong_answers']])

            return output.getvalue()
        except Exception as e:
            logger.error(f"Error converting to CSV: {e}")
            return None

# Импорт данных пользователя
    @staticmethod
    @with_connection
    def import_user_data(conn, telegram_id, data, format='json'):
        try:
            imported_count = 0

            if format == 'json':
                try:
                    import_data = json.loads(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    return 0

                category_map = {}

                if 'categories' in import_data:
                    for category in import_data['categories']:
                        if category['name'] in ['Общее', 'По умолчанию']:
                            continue

                        existing_categories = CategoryUtils.get_user_categories(conn, telegram_id)
                        exists = any(c['name'].lower() == category['name'].lower()
                                     for c in existing_categories)

                        if not exists:
                            new_category_id = CategoryUtils.create_category(
                                conn, telegram_id,
                                category['name'],
                                category.get('description'),
                                category.get('color')
                            )

                            if new_category_id:
                                category_map[category['id']] = new_category_id
                                imported_count += 1

            return imported_count

        except Exception as e:
            logger.error(f"Error importing data: {e}")
            return 0


# УТИЛИТЫ ДЛЯ СТАТИСТИКИ И АНАЛИТИКИ
class AnalyticsUtils:

# Получение ежедневной статистики за указанный период
    @staticmethod
    @with_connection
    def get_daily_stats(conn, telegram_id, days=30):
        try:
            cursor = conn.execute('''
                                  SELECT
                                      DATE (created_at) as date, COUNT (*) as cards_studied, SUM (correct_answers) as correct, SUM (wrong_answers) as wrong, SUM (session_duration) as total_time
                                  FROM study_sessions
                                  WHERE user_id = ? AND created_at >= DATE ('now', ?)
                                  GROUP BY DATE (created_at)
                                  ORDER BY date DESC
                                  ''', (telegram_id, f'-{days} days'))

            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting daily stats: {e}")
            return []

# Получение статистики по категориям
    @staticmethod
    @with_connection
    def get_category_stats(conn, telegram_id):
        try:
            cursor = conn.execute('''
                                  SELECT c.name                                                    as category_name,
                                         COUNT(cards.id)                                           as total_cards,
                                         SUM(CASE WHEN cards.status = 'learned' THEN 1 ELSE 0 END) as learned_cards,
                                         AVG(cards.difficulty)                                     as avg_difficulty,
                                         SUM(cards.review_count)                                   as total_reviews
                                  FROM categories c
                                           LEFT JOIN cards ON c.id = cards.category_id
                                  WHERE c.user_id = ?
                                  GROUP BY c.id, c.name
                                  ORDER BY total_cards DESC
                                  ''', (telegram_id,))

            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting category stats: {e}")
            return []

# Получение прогресса обучения
    @staticmethod
    @with_connection
    def get_learning_progress(conn, telegram_id):
        try:
            cursor = conn.execute('''
                                  SELECT strftime('%Y-%m', created_at) as month,
                    COUNT(*) as sessions,
                    SUM(cards_studied) as cards_studied,
                    AVG(correct_answers * 100.0 / (correct_answers + wrong_answers)) as accuracy
                                  FROM study_sessions
                                  WHERE user_id = ?
                                  GROUP BY strftime('%Y-%m', created_at)
                                  ORDER BY month DESC
                                      LIMIT 12
                                  ''', (telegram_id,))

            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting learning progress: {e}")
            return []


# УТИЛИТЫ ДЛЯ ОЧИСТКИ И ОПТИМИЗАЦИИ
class MaintenanceUtils:

# Очистка старых данных"
    @staticmethod
    @with_connection
    def cleanup_old_data(conn, telegram_id, days_old=180):
        try:
            # Удаляем старые сессии
            cursor = conn.execute('''
                                  DELETE
                                  FROM study_sessions
                                  WHERE user_id = ?
                                    AND created_at < DATE ('now'
                                      , ?)
                                  ''', (telegram_id, f'-{days_old} days'))

            deleted_sessions = cursor.rowcount

            return {
                'deleted_sessions': deleted_sessions,
                'total_deleted': deleted_sessions
            }
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
            return {'deleted_sessions': 0, 'total_deleted': 0}

# Удаление пустых категорий
    @staticmethod
    @with_connection
    def delete_empty_categories(conn, telegram_id):
        try:
            cursor = conn.execute('''
                                  DELETE
                                  FROM categories
                                  WHERE user_id = ?
                                    AND id NOT IN (SELECT DISTINCT category_id
                                                   FROM cards
                                                   WHERE user_id = ?)
                                  ''', (telegram_id, telegram_id))

            return cursor.rowcount
        except Exception as e:
            logger.error(f"Error deleting empty categories: {e}")
            return 0

# Сброс статистики пользователя
    @staticmethod
    @with_connection
    def reset_user_stats(conn, telegram_id):
        try:
            conn.execute('''
                         UPDATE user_stats
                         SET total_sessions   = 0,
                             total_study_time = 0,
                             correct_answers  = 0,
                             wrong_answers    = 0,
                             streak_days      = 0,
                             last_study_date  = NULL,
                             updated_at       = CURRENT_TIMESTAMP
                         WHERE user_id = ?
                         ''', (telegram_id,))

            return True
        except Exception as e:
            logger.error(f"Error resetting user stats: {e}")
            return False


# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# Получение количества карточек пользователя
@with_connection
def get_user_cards_count(conn, telegram_id):
    cursor = conn.execute('SELECT COUNT(*) as count FROM cards WHERE user_id = ?', (telegram_id,))
    result = cursor.fetchone()
    return result['count'] if result else 0


#  Получение недавно созданных карточек
@with_connection
def get_recent_cards(conn, telegram_id, days=7):

    cursor = conn.execute('''
                          SELECT COUNT(*) as count
                          FROM cards
                          WHERE user_id = ? AND created_at >= DATE ('now', ?)
                          ''', (telegram_id, f'-{days} days'))

    result = cursor.fetchone()
    return result['count'] if result else 0


# Получение информации о серии дней подряд
@with_connection
def get_streak_info(conn, telegram_id):
    cursor = conn.execute('''
                          SELECT streak_days, last_study_date
                          FROM user_stats
                          WHERE user_id = ?
                          ''', (telegram_id,))

    result = cursor.fetchone()
    return dict(result) if result else None


# Инициализация базы данных при импорте модуля
try:
    db_manager._init_database()
    logger.info("Database utilities module loaded successfully")
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")