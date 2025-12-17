import os
import logging
import sys
from datetime import datetime

# Добавляем корневую директорию в путь для импортов
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from telebot import TeleBot, types
from telebot.custom_filters import TextMatchFilter, TextStartsFilter

from config import BOT_TOKEN, ADMIN_IDS, DEBUG
from database import db_manager

from start import register_start_handlers
from cards import register_cards_handlers
from categoies import register_categories_handlers
from reminders import register_reminders_handlers
from quiz import register_quiz_handlers
from settings import register_settings_handlers

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler('bot.log', encoding='utf-8'),logging.StreamHandler()])
logger = logging.getLogger(__name__)

bot = TeleBot(BOT_TOKEN, parse_mode='Markdown')

bot.add_custom_filter(TextMatchFilter())
bot.add_custom_filter(TextStartsFilter())

user_sessions = {}


# Инициализация бота
def init_bot():
    try:
        logger.info("Initializing bot...")

        with db_manager.get_connection() as conn:
            logger.info("Database connection established")

        if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
            logger.error("Please set BOT_TOKEN environment variable or in .env file")
            sys.exit(1)

        register_all_handlers()

        logger.info("Bot initialized successfully")

        if not ADMIN_IDS:
            logger.warning("No admin IDs configured. Admin commands will not work.")

    except Exception as e:
        logger.error(f"Bot initialization failed: {e}")
        sys.exit(1)


# Регистрация всех обработчиков команд
def register_all_handlers():
    logger.info("Registering handlers...")

    register_start_handlers(bot)
    register_cards_handlers(bot)
    register_categories_handlers(bot)
    register_reminders_handlers(bot)
    register_quiz_handlers(bot)
    register_settings_handlers(bot)

    register_base_handlers()

    logger.info("All handlers registered")


# Регистрация базовых обработчиков (команды, не вошедшие в модули)
def register_base_handlers():

    @bot.message_handler(commands=['help', 'помощь'])
    def help_command(message):
        try:
            help_text = ("*Доступные команды:*\n\n*Основные команды:*\n/start - Начать работу с ботом\n"
                         "/help - Показать эту справку\n/menu - Показать меню кнопок\n/about - Информация о боте\n\n"
                         "*Работа с карточками:*\n/cards - Управление карточками\n/add_card - Добавить карточку (пошагово)\n"
                         "/quickadd - Быстрое добавление (формат: вопрос - ответ)\n/mycards - Показать мои карточки\n"
                         "/search - Поиск по карточкам\n\n*Тестирование и обучение:*\n/quiz - Начать тестирование\n"
                         "/today - Карточки для повторения сегодня\n/review - Повторить сложные карточки\n\n"
                         "*Категории:*\n/categories - Управление категориями\n\n*Напоминания:*\n"
                         "/reminder - Настройка напоминаний\n\n*Статистика:*\n/stats - Моя статистика обучения\n"
                         "/progress - Прогресс обучения\n\n*Настройки:*\n/settings - Настройки бота\n"
                         "/export - Экспорт данных\n/import - Импорт карточек")
            bot.send_message(message.chat.id, help_text)

        except Exception as e:
            logger.error(f"Error in help_command: {e}")
            bot.send_message(message.chat.id, "Ошибка при загрузке справки")

# Показать статистику пользователя
    @bot.message_handler(commands=['stats', 'статистика'])
    def stats_command(message):
        try:
            from database import UserUtils, CardUtils, CategoryUtils, with_connection

            user_id = message.from_user.id

            with with_connection() as conn:
                stats = UserUtils.get_user_stats(conn, user_id)
                all_cards = CardUtils.get_user_cards(conn, user_id)
                categories = CategoryUtils.get_user_categories(conn, user_id)

                if not stats:
                    bot.send_message(message.chat.id, "Статистика пока недоступна. Создайте первые карточки!")
                    return

                total_cards = len(all_cards)
                learned_cards = len([c for c in all_cards if c['status'] == 'learned'])
                learning_cards = len([c for c in all_cards if c['status'] == 'learning'])

                total_answers = stats['correct_answers'] + stats['wrong_answers']
                if total_answers > 0:
                    success_rate = (stats['correct_answers'] / total_answers) * 100
                else:
                    success_rate = 0

                total_minutes = stats['total_study_time'] // 60
                hours = total_minutes // 60
                minutes = total_minutes % 60

                stats_text = (f"*Ваша статистика*\n\n*Карточки:*\n• Всего: {total_cards}\n• Изучено: {learned_cards}\n"
                              f"• Изучается: {learning_cards}\n\n*Прогресс обучения:*\n"
                              f"• Сессий: {stats['total_sessions']}\n• Правильных ответов: {stats['correct_answers']}\n"
                              f"• Ошибок: {stats['wrong_answers']}\n• Успешность: {success_rate:.1f}%\n\n*Активность:*\n"
                              f"• Дней подряд: {stats['streak_days']}\n• Общее время: {hours}ч {minutes}м\n\n"
                              f"*Организация:*\n• Категорий: {len(categories)}")

                markup = types.InlineKeyboardMarkup(row_width=2)
                btn_detailed = types.InlineKeyboardButton('Детальная статистика', callback_data='detailed_stats')
                btn_category_stats = types.InlineKeyboardButton('По категориям', callback_data='category_stats')
                btn_reset = types.InlineKeyboardButton('Сбросить прогресс', callback_data='reset_stats_confirm')

                markup.add(btn_detailed, btn_category_stats, btn_reset)

                bot.send_message(message.chat.id, stats_text, parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in stats_command: {e}")
            bot.send_message(message.chat.id, "Ошибка при получении статистики")

# Админ-панель (только для администраторов)
    @bot.message_handler(commands=['admin'])
    def admin_command(message):
        try:
            user_id = message.from_user.id

            if user_id not in ADMIN_IDS:
                bot.send_message(message.chat.id, "У вас нет доступа к этой команде")
                return

            from database import with_connection

            with with_connection() as conn:
                cursor = conn.execute('SELECT COUNT(*) as users FROM users')
                total_users = cursor.fetchone()['users']

                cursor = conn.execute('SELECT COUNT(*) as cards FROM cards')
                total_cards = cursor.fetchone()['cards']

                cursor = conn.execute('SELECT COUNT(*) as categories FROM categories')
                total_categories = cursor.fetchone()['categories']

                cursor = conn.execute('''
                                      SELECT COUNT(*) as active_users
                                      FROM users
                                      WHERE last_active >= DATE ('now', '-7 days')
                                      ''')
                active_users = cursor.fetchone()['active_users']

            admin_text = (f"*Админ-панель*\n\n*Общая статистика:*\n• Пользователей: {total_users}\n"
                          f"• Активных (7 дней): {active_users}\n• Карточек: {total_cards}\n"
                          f"• Категорий: {total_categories}\n\n*Действия администратора:*")

            markup = types.InlineKeyboardMarkup(row_width=2)
            btn_broadcast = types.InlineKeyboardButton('Рассылка', callback_data='admin_broadcast')
            btn_export_all = types.InlineKeyboardButton('Экспорт всех данных', callback_data='admin_export')
            btn_cleanup = types.InlineKeyboardButton('Очистка БД', callback_data='admin_cleanup')
            btn_stats = types.InlineKeyboardButton('Подробная статистика', callback_data='admin_stats')
            btn_logs = types.InlineKeyboardButton('Просмотр логов', callback_data='admin_logs')

            markup.add(btn_broadcast, btn_export_all, btn_cleanup, btn_stats, btn_logs)

            bot.send_message(message.chat.id, admin_text, parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in admin_command: {e}")
            bot.send_message(message.chat.id, "Ошибка в админ-панели")

# Показать меню кнопок
    @bot.message_handler(commands=['menu'])
    def menu_command(message):
        try:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

            btn_cards = types.KeyboardButton('Мои карточки')
            btn_quiz = types.KeyboardButton('Тестирование')
            btn_add = types.KeyboardButton('Добавить карточку')
            btn_stats = types.KeyboardButton('Статистика')
            btn_settings = types.KeyboardButton('Настройки')
            btn_help = types.KeyboardButton('Помощь')

            markup.add(btn_cards, btn_quiz, btn_add, btn_stats, btn_settings, btn_help)

            bot.send_message(message.chat.id, "📱 *Главное меню*\n\nВыберите действие:",
                             parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in menu_command: {e}")

# Информация о боте
    @bot.message_handler(commands=['about'])
    def about_command(message):
        try:
            from database import with_connection

            with with_connection() as conn:
                cursor = conn.execute('SELECT COUNT(*) as users FROM users')
                total_users = cursor.fetchone()['users']

                cursor = conn.execute('SELECT COUNT(*) as cards FROM cards')
                total_cards = cursor.fetchone()['cards']

            about_text = (f"*О боте*\n\n*Flashcards Bot* — умный помощник для обучения\n\n*Возможности:*\n"
                          f"• Система интервальных повторений (SM-2)\n• Умные напоминания о повторении\n"
                          f"• Детальная статистика прогресса\n• Экспорт/импорт данных\n• Организация по категориям\n\n"
                          f"*Статистика бота:*\n\n• Пользователей: {total_users}\n• Карточек: {total_cards}\n\n"
                          f"*Технологии:*\n• Python 3.10+\n• pyTelegramBotAPI\n• SQLite с WAL режимом\n"
                          f"• Алгоритм SuperMemo 2\n\n*Разработчик:* @your_username\n"
                          f"*Поддержка:* {f"@{ADMIN_IDS[0]}" if ADMIN_IDS else "Не настроена"}")

            markup = types.InlineKeyboardMarkup()
            btn_source = types.InlineKeyboardButton('Исходный код', url='https://github.com/')
            btn_donate = types.InlineKeyboardButton('Поддержать проект', callback_data='donate')

            markup.add(btn_source, btn_donate)

            bot.send_message(message.chat.id, about_text, parse_mode='Markdown',
                             reply_markup=markup, disable_web_page_preview=True)

        except Exception as e:
            logger.error(f"Error in about_command: {e}")
            bot.send_message(message.chat.id, "Ошибка при загрузке информации")

    # Обработчики текстовых сообщений (кнопки меню)
    @bot.message_handler(func=lambda message: True)
    def handle_text_messages(message):
        try:
            from database import UserUtils, with_connection

            user_id = message.from_user.id
            text = message.text.strip()

            with with_connection() as conn:
                UserUtils.update_user_activity(conn, user_id)

            if text == 'Мои карточки':
                from cards import view_cards_list
                view_cards_list(message)
            elif text == 'Тестирование':
                from quiz import start_quiz_command
                start_quiz_command(message)
            elif text == 'Добавить карточку':
                from cards import add_card_start
                add_card_start(message)
            elif text == 'Статистика':
                stats_command(message)
            elif text == 'Настройки':
                from settings import settings_main_menu
                settings_main_menu(message)
            elif text == 'Помощь':
                help_command(message)
            elif text == 'Назад':
                from start import start_command
                start_command(message)
            elif text == 'Меню':
                menu_command(message)
            else:
                bot.send_message(message.chat.id, "Не понимаю эту команду. Используйте /help для списка команд",
                                 reply_markup=types.ReplyKeyboardRemove())

        except Exception as e:
            logger.error(f"Error handling text message: {e}")

# Обработчики callback-запросов
    @bot.callback_query_handler(func=lambda call: True)
    def handle_callback_queries(call):
        try:
            from database import UserUtils, with_connection

            user_id = call.from_user.id

            with with_connection() as conn:
                UserUtils.update_user_activity(conn, user_id)

            if call.data == 'main_menu':
                from start import start_command
                start_command(call.message)
            elif call.data == 'detailed_stats':
                show_detailed_stats(call)
            elif call.data == 'reset_stats_confirm':
                confirm_reset_stats(call)
            elif call.data.startswith('admin_'):
                handle_admin_callbacks(call)
            else:
                bot.answer_callback_query(call.id, "Эта функция в разработке")

        except Exception as e:
            logger.error(f"Error handling callback: {e}")
            bot.answer_callback_query(call.id, "Произошла ошибка")

# Показать детальную статистику
    def show_detailed_stats(call):
        try:
            from database import CategoryUtils, CardUtils, AnalyticsUtils, with_connection

            user_id = call.from_user.id

            with with_connection() as conn:
                category_stats = AnalyticsUtils.get_category_stats(conn, user_id)
                daily_stats = AnalyticsUtils.get_daily_stats(conn, user_id, days=7)
                learning_progress = AnalyticsUtils.get_learning_progress(conn, user_id)

            detailed_text = "*Детальная статистика*\n\n"

            if category_stats:
                detailed_text += "*Статистика по категориям:*\n"
                for stat in category_stats[:5]:  # Показываем топ-5
                    if stat['total_cards'] > 0:
                        progress = (stat['learned_cards'] / stat['total_cards']) * 100
                        detailed_text += f"• {stat['category_name']}: {stat['learned_cards']}/{stat['total_cards']} ({progress:.0f}%)\n"

            if daily_stats:
                detailed_text += "\n*Активность за 7 дней:*\n"
                for stat in daily_stats:
                    date = stat['date']
                    cards = stat['cards_studied']
                    accuracy = stat['correct'] / (stat['correct'] + stat['wrong']) * 100 if (stat['correct'] + stat[
                        'wrong']) > 0 else 0
                    detailed_text += f"• {date}: {cards} карт., {accuracy:.0f}%\n"

            bot.edit_message_text(detailed_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error showing detailed stats: {e}")
            bot.answer_callback_query(call.id, "Ошибка при загрузке статистики")

# Подтверждение сброса статистики
    def confirm_reset_stats(call):
        try:
            markup = types.InlineKeyboardMarkup()
            btn_confirm = types.InlineKeyboardButton('Да, сбросить', callback_data='reset_stats_execute')
            btn_cancel = types.InlineKeyboardButton('Нет, отмена', callback_data='cancel_reset_stats')

            markup.add(btn_confirm, btn_cancel)

            bot.edit_message_text("*Сброс статистики*\n\nВы уверены, что хотите сбросить всю статистику?\n"
                                  "Это действие нельзя отменить.\n\nБудут сброшены:\n• Прогресс всех карточек\n"
                                  "• Статистика сессий\n• Дни подряд (streak)",
                                  call.message.chat.id, call.message.message_id,
                                  parse_mode='Markdown', reply_markup=markup)

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in confirm_reset_stats: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Обработка админских callback'ов
    def handle_admin_callbacks(call):
        try:
            if call.data == 'admin_broadcast':
                msg = bot.send_message(
                    call.message.chat.id,
                    "*Рассылка сообщения*\n\n"
                    "Введите сообщение для рассылки всем пользователям:",
                    parse_mode='Markdown'
                )
                bot.register_next_step_handler(msg, process_broadcast_message)
            elif call.data == 'admin_export':
                export_all_data(call)
            elif call.data == 'admin_cleanup':
                cleanup_database(call)
            elif call.data == 'admin_stats':
                show_admin_stats(call)
            elif call.data == 'admin_logs':
                send_logs(call)

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in admin callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Обработка сообщения для рассылки
    def process_broadcast_message(message):
        try:
            if message.from_user.id not in ADMIN_IDS:
                return

            broadcast_text = message.text
            users_sent = 0
            users_failed = 0

            from database import with_connection

            with with_connection() as conn:
                cursor = conn.execute('SELECT telegram_id FROM users')
                users = cursor.fetchall()

            progress_msg = bot.send_message(message.chat.id, f"*Начало рассылки*\n\nПолучателей: {len(users)}\n"
                                                             f"Сообщение: {broadcast_text[:50]}...\n\n"
                                                             f"Отправка...", parse_mode='Markdown')

            for user in users:
                try:
                    bot.send_message(user['telegram_id'], broadcast_text)
                    users_sent += 1

                    if users_sent % 10 == 0:
                        bot.edit_message_text(f"*Рассылка в процессе*\n\nОтправлено: {users_sent}/{len(users)}\n"
                                              f"Ошибок: {users_failed}", message.chat.id,
                                              progress_msg.message_id, parse_mode='Markdown')

                except Exception as e:
                    users_failed += 1
                    logger.error(f"Failed to send to {user['telegram_id']}: {e}")

            bot.edit_message_text(f"*Рассылка завершена*\n\n• Всего получателей: {len(users)}\n"
                                  f"• Успешно отправлено: {users_sent}\n• Не удалось отправить: {users_failed}\n\n"
                                  f"Успешность: {(users_sent / len(users)) * 100:.1f}%",
                                  message.chat.id, progress_msg.message_id, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error in broadcast: {e}")
            bot.send_message(message.chat.id, "Ошибка при рассылке")

# Экспорт всех данных пользователей
    def export_all_data(call):
        try:
            from database import with_connection, ExportImportUtils
            import io

            with with_connection() as conn:
                cursor = conn.execute('SELECT telegram_id FROM users')
                users = cursor.fetchall()

            # Создаем общий файл с данными всех пользователей
            all_data = {'export_date': datetime.now().isoformat(), 'total_users': len(users), 'users_data': []}

            for user in users[:10]:  # Ограничиваем 10 пользователями для безопасности
                user_data = ExportImportUtils.export_user_data(conn, user['telegram_id'])
                if user_data:
                    all_data['users_data'].append(user_data)

            import json
            json_data = json.dumps(all_data, ensure_ascii=False, indent=2, default=str)

            file_name = f"all_users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            file_data = io.BytesIO(json_data.encode('utf-8'))
            file_data.name = file_name

            bot.send_document(call.message.chat.id, file_data, caption=f"*Экспорт всех данных*\n\n"
                                                                       f"Файл содержит данные {len(all_data['users_data'])}\t"
                                                                       f"пользователей.", parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error exporting all data: {e}")
            bot.answer_callback_query(call.id, "Ошибка при экспорте")

# Очистка базы данных
    def cleanup_database(call):
        try:
            from database import with_connection, MaintenanceUtils

            with with_connection() as conn:
                cursor = conn.execute('''
                                      DELETE
                                      FROM users
                                      WHERE last_active < DATE ('now', '-30 days')
                                      ''')
                deleted_users = cursor.rowcount

                cleanup_stats = MaintenanceUtils.cleanup_old_data(conn, call.from_user.id, days_old=90)

            result_text = (f"*Очистка завершена*\n\n*Удалено:*\n• Пользователей: {deleted_users}\n"
                           f"• Сессий: {cleanup_stats['deleted_sessions']}\n\n"
                           f"*Всего удалено записей:* {deleted_users + cleanup_stats['total_deleted']}")

            bot.edit_message_text(result_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error cleaning database: {e}")
            bot.edit_message_text("Ошибка при очистке базы данных", call.message.chat.id, call.message.message_id)

# Показать расширенную статистику для админа
    def show_admin_stats(call):
        try:
            from database import with_connection

            with with_connection() as conn:
                cursor = conn.execute('''
                                      SELECT COUNT(*)                                                           as total_users,
                                             COUNT(CASE WHEN last_active >= DATE ('now', '-7 days') THEN 1 END) as active_week,
                                             COUNT(CASE WHEN last_active >= DATE ('now', '-1 day') THEN 1 END)  as active_today,
                                             (SELECT COUNT(*) FROM cards)                                       as total_cards,
                                             (SELECT COUNT(*) FROM categories)                                  as total_categories,
                                             (SELECT COUNT(*) FROM study_sessions)                              as total_sessions
                                      FROM users
                                      ''')
                stats = cursor.fetchone()

                cursor = conn.execute('''
                                      SELECT u.telegram_id,
                                             u.first_name,
                                             u.username,
                                             COUNT(c.id) as cards_count
                                      FROM users u
                                               LEFT JOIN cards c ON u.telegram_id = c.user_id
                                      GROUP BY u.telegram_id
                                      ORDER BY cards_count DESC LIMIT 5
                                      ''')
                top_users = cursor.fetchall()

            stats_text = (f"*Расширенная статистика*\n\n*Общая статистика:*\n• Пользователей: {stats['total_users']}\n"
                          f"• Активных за неделю: {stats['active_week']}\n• Активных сегодня: {stats['active_today']}\n"
                          f"• Карточек: {stats['total_cards']}\n• Категорий: {stats['total_categories']}\n"
                          f"• Сессий обучения: {stats['total_sessions']}\n\n*Топ-5 пользователей по карточкам:*")

            for i, user in enumerate(top_users, 1):
                username = f"@{user['username']}" if user['username'] else user['first_name']
                stats_text += f"{i}. {username}: {user['cards_count']} карточек\n"

            bot.edit_message_text(stats_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error showing admin stats: {e}")

# Отправить логи бота
    def send_logs(call):
        try:
            log_file = 'bot.log'

            if os.path.exists(log_file):
                with open(log_file, 'rb') as f:
                    bot.send_document(call.message.chat.id, f,
                                      caption="*Логи бота*\n\nФайл содержит последние записи логов.",
                                      parse_mode='Markdown')
            else:
                bot.answer_callback_query(call.id, "Файл логов не найден", show_alert=True)

        except Exception as e:
            logger.error(f"Error sending logs: {e}")
            bot.answer_callback_query(call.id, "Ошибка при отправке логов")

    @bot.message_handler(content_types=['audio', 'document', 'photo', 'sticker',
                                        'video', 'voice', 'location', 'contact'])
    def handle_unsupported_content(message):
        bot.send_message(message.chat.id, "Этот тип контента не поддерживается.\n\n"
                                          "Используйте текстовые сообщения или команды.\n"
                                          "Для импорта карточек используйте команду /import")


# ЗАПУСК БОТА
def main():
    try:
        logger.info("=" * 50)
        logger.info("Starting Flashcards Bot...")
        logger.info(f"Start time: {datetime.now()}")
        logger.info(f"Debug mode: {DEBUG}")
        logger.info(f"Admin IDs: {ADMIN_IDS}")
        logger.info("=" * 50)

        init_bot()

        bot_info = bot.get_me()
        logger.info(f"Bot info: @{bot_info.username} ({bot_info.first_name})")
        logger.info(f"Bot link: https://t.me/{bot_info.username}")

        logger.info("Bot is running. Press Ctrl+C to stop.")

        if DEBUG:
            while True:
                try:
                    bot.infinity_polling(timeout=60, long_polling_timeout=60)
                except Exception as e:
                    logger.error(f"Bot crashed: {e}")
                    logger.info("Restarting bot in 5 seconds...")
                    import time
                    time.sleep(5)
        else:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        sys.exit(1)
    finally:
        logger.info("Bot stopped")


if __name__ == "__main__":
    main()