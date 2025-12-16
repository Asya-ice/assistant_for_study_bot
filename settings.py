import logging
import json
import csv
import io
from datetime import datetime
from telebot import types
from utils.db_utils import with_connection, UserUtils, CategoryUtils, CardUtils, ReminderUtils, ExportImportUtils

logger = logging.getLogger(__name__)


# Регистрация всех обработчиков для настроек
def register_settings_handlers(bot):

# Главное меню настроек
    @bot.message_handler(commands=['settings'])
    def settings_main_menu(message):
        try:
            user_id = message.from_user.id

            with with_connection() as conn:
                user_stats = UserUtils.get_user_stats(conn, user_id)
                reminder = ReminderUtils.get_user_reminder(conn, user_id)
                categories = CategoryUtils.get_user_categories(conn, user_id)
                cards = CardUtils.get_user_cards(conn, user_id)

            text = (f"*Настройки бота*\n\n*Ваша статистика:*\n• Карточек: {len(cards)}\n• Категорий: {len(categories)}\n"
                    f"• Сессий обучения: {user_stats['total_sessions'] if user_stats else 0}\n"
                    f"• Напоминания: {'🔔 Вкл' if reminder and reminder['enabled'] else '🔕 Выкл'}\n\n"
                    f"*Управление данными:*\nЗдесь вы можете управлять своими карточками,\t"
                    f"категориями, настройками и экспортировать данные.")

            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

            btn_backup = types.KeyboardButton('Экспорт данных')
            btn_restore = types.KeyboardButton('Импорт данных')
            btn_notifications = types.KeyboardButton('Уведомления')
            btn_account = types.KeyboardButton('Аккаунт')
            btn_appearance = types.KeyboardButton('Внешний вид')
            btn_advanced = types.KeyboardButton('Дополнительно')
            btn_back = types.KeyboardButton('Назад')

            markup.add(btn_backup, btn_restore, btn_notifications, btn_account,
                       btn_appearance, btn_advanced, btn_back)

            inline_markup = types.InlineKeyboardMarkup(row_width=2)

            btn_quick_export = types.InlineKeyboardButton('Быстрый экспорт', callback_data='quick_export')
            btn_backup_now = types.InlineKeyboardButton('Создать бэкап', callback_data='create_backup')
            btn_cleanup = types.InlineKeyboardButton('Очистить данные', callback_data='cleanup_data')
            btn_reset_stats = types.InlineKeyboardButton('Сбросить статистику', callback_data='reset_stats')
            btn_help = types.InlineKeyboardButton('Помощь', callback_data='settings_help')

            inline_markup.add(btn_quick_export, btn_backup_now, btn_cleanup, btn_reset_stats, btn_help)

            bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

            bot.send_message(message.chat.id, "*Быстрые действия:*", parse_mode='Markdown', reply_markup=inline_markup)

        except Exception as e:
            logger.error(f"Error in settings_main_menu: {e}")
            bot.send_message(message.chat.id, "Ошибка при загрузке настроек")

# Меню экспорта данных
    @bot.message_handler(commands=['export'])
    @bot.message_handler(func=lambda message: message.text in ['💾 Экспорт данных', '📤 Экспорт'])
    def export_data_menu(message):
        try:
            user_id = message.from_user.id

            with with_connection() as conn:
                categories = CategoryUtils.get_user_categories(conn, user_id)
                cards = CardUtils.get_user_cards(conn, user_id)

            text = (f"*Экспорт данных*\n\n*Доступные данные:*\n• Карточки: {len(cards)}\n• Категории: {len(categories)}\n"
                    f"• Настройки и статистика\n\n*Выберите формат экспорта:*")

            markup = types.InlineKeyboardMarkup(row_width=2)

            btn_json = types.InlineKeyboardButton('JSON', callback_data='export_json')
            btn_csv = types.InlineKeyboardButton('CSV', callback_data='export_csv')
            btn_txt = types.InlineKeyboardButton('Текстовый файл', callback_data='export_txt')
            btn_backup = types.InlineKeyboardButton('Полный бэкап', callback_data='export_backup')
            btn_selective = types.InlineKeyboardButton('Выборочный экспорт', callback_data='export_selective')
            btn_back = types.InlineKeyboardButton('Назад', callback_data='back_to_settings')

            markup.add(btn_json, btn_csv, btn_txt, btn_backup, btn_selective, btn_back)

            bot.send_message( message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in export_data_menu: {e}")
            bot.send_message(message.chat.id, "Ошибка при загрузке меню экспорта")

# Экспорт данных в JSON формате
    @bot.callback_query_handler(func=lambda call: call.data == 'export_json')
    def export_json_callback(call):
        try:
            user_id = call.from_user.id

            with with_connection() as conn:
                json_data = ExportImportUtils.export_user_data(conn, user_id, format='json')

                if not json_data:
                    bot.answer_callback_query(call.id, "Ошибка при экспорте данных")
                    return

            file_name = f"flashcards_backup_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            file_data = io.BytesIO(json_data.encode('utf-8'))
            file_data.name = file_name

            bot.send_document(call.message.chat.id, file_data, caption=f"📄 *Экспорт данных в JSON*\n\n"
                                                                       f"Файл: `{file_name}`\n"
                                                                       f"Содержит все ваши карточки и категории.\n\n"
                                                                       f"*Для импорта:* используйте команду /import",
                              parse_mode='Markdown')

            bot.answer_callback_query(call.id, "Файл отправлен")

        except Exception as e:
            logger.error(f"Error in export_json_callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка при экспорте")

# Экспорт данных в CSV формате
    @bot.callback_query_handler(func=lambda call: call.data == 'export_csv')
    def export_csv_callback(call):
        try:
            user_id = call.from_user.id

            with with_connection() as conn:
                csv_data = ExportImportUtils.export_user_data(conn, user_id, format='csv')

                if not csv_data:
                    bot.answer_callback_query(call.id, "Ошибка при экспорте данных")
                    return

            file_name = f"flashcards_export_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            file_data = io.BytesIO(csv_data.encode('utf-8-sig'))  # utf-8-sig для Excel
            file_data.name = file_name

            bot.send_document(call.message.chat.id, file_data, caption=f"*Экспорт данных в CSV*\n\n"
                                                                       f"Файл: `{file_name}`\n"
                                                                       f"Формат: Вопрос, Ответ, Категория, Статус\n\n"
                                                                       f"*Можно открыть в:* Excel, Google Sheets, Numbers",
                              parse_mode='Markdown')

            bot.answer_callback_query(call.id, "Файл отправлен")

        except Exception as e:
            logger.error(f"Error in export_csv_callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка при экспорте")

# Экспорт данных в текстовом формате
    @bot.callback_query_handler(func=lambda call: call.data == 'export_txt')
    def export_txt_callback(call):
        try:
            user_id = call.from_user.id

            with with_connection() as conn:
                categories = CategoryUtils.get_user_categories(conn, user_id)
                cards = CardUtils.get_user_cards(conn, user_id)

                txt_content = (f"Экспорт карточек Flashcards Bot\nПользователь: {user_id}\n"
                               f"Дата экспорта: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                               f"Всего категорий: {len(categories)}\nВсего карточек: {len(cards)}\n\n{'=' * 50}")

                for category in categories:
                    txt_content += f"\n\n{'=' * 50}\n"
                    txt_content += f"КАТЕГОРИЯ: {category['name']}\n"
                    if category.get('description'):
                        txt_content += f"Описание: {category['description']}\n"
                    txt_content += f"{'=' * 50}\n\n"

                    category_cards = [c for c in cards if c.get('category_id') == category['id']]

                    for i, card in enumerate(category_cards, 1):
                        status = "ИЗУЧЕНО" if card['status'] == 'learned' else "ИЗУЧАЕТСЯ"
                        txt_content += f"{i}. [{status}] {card['front']}\n"
                        txt_content += f"   Ответ: {card['back']}\n"
                        txt_content += f"   Повторений: {card['review_count']}, "
                        txt_content += f"Правильно: {card['correct_answers']}/{card['review_count'] if card['review_count'] > 0 else 1}\n\n"

            file_name = f"flashcards_export_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            file_data = io.BytesIO(txt_content.encode('utf-8'))
            file_data.name = file_name

            bot.send_document(call.message.chat.id,file_data, caption=f"*Экспорт в текстовом формате*\n\n"
                                                                      f"Файл: `{file_name}`\n"
                                                                      f"Удобно для печати или чтения.",
                              parse_mode='Markdown')

            bot.answer_callback_query(call.id, "Файл отправлен")

        except Exception as e:
            logger.error(f"Error in export_txt_callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка при экспорте")

# Меню выборочного экспорта
    @bot.callback_query_handler(func=lambda call: call.data == 'export_selective')
    def export_selective_menu(call):
        try:
            user_id = call.from_user.id

            with with_connection() as conn:
                categories = CategoryUtils.get_user_categories(conn, user_id)

            text = "*Выборочный экспорт*\n\nВыберите категории для экспорта:"

            markup = types.InlineKeyboardMarkup(row_width=1)

            for category in categories:
                btn = types.InlineKeyboardButton(f"📁 {category['name']}", callback_data=f'export_category_{category["id"]}')
                markup.add(btn)

            btn_all = types.InlineKeyboardButton('Все категории', callback_data='export_all_categories')
            btn_by_status = types.InlineKeyboardButton('Только изучаемые', callback_data='export_learning')
            btn_by_date = types.InlineKeyboardButton('За последние 7 дней', callback_data='export_recent')
            btn_back = types.InlineKeyboardButton('Назад', callback_data='back_to_export_menu')

            markup.add(btn_all, btn_by_status, btn_by_date, btn_back)

            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='Markdown', reply_markup=markup)

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in export_selective_menu: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Меню импорта данных
    @bot.message_handler(commands=['import'])
    @bot.message_handler(func=lambda message: message.text in ['📥 Импорт данных', '📥 Импорт'])
    def import_data_menu(message):
        try:
            text = ("*Импорт данных*\n\nВы можете импортировать карточки из файла.\n\n*Поддерживаемые форматы:*\n"
                    "• JSON (экспорт из этого бота)\n• CSV (столбцы: Вопрос, Ответ, Категория)\n"
                    "• Текстовый файл (формат: Вопрос - Ответ)\n\n*Как импортировать:*\n1. Выберите формат файла\n"
                    "2. Отправьте файл боту\n3. Выберите категорию для импорта\n4. Подтвердите импорт\n\n"
                    "*Внимание:* Импорт добавит новые карточки, не удаляя старые.")

            markup = types.InlineKeyboardMarkup(row_width=2)

            btn_import_json = types.InlineKeyboardButton('Из JSON', callback_data='import_json')
            btn_import_csv = types.InlineKeyboardButton('Из CSV', callback_data='import_csv')
            btn_import_txt = types.InlineKeyboardButton('Из текста', callback_data='import_txt')
            btn_template = types.InlineKeyboardButton('Шаблон файла', callback_data='download_template')
            btn_help = types.InlineKeyboardButton('Инструкция', callback_data='import_help')
            btn_back = types.InlineKeyboardButton('Назад', callback_data='back_to_settings')

            markup.add(btn_import_json, btn_import_csv, btn_import_txt, btn_template, btn_help, btn_back)

            bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in import_data_menu: {e}")
            bot.send_message(message.chat.id, "Ошибка при загрузке меню импорта")

# Начало импорта из JSON
    @bot.callback_query_handler(func=lambda call: call.data == 'import_json')
    def import_json_callback(call):
        try:
            bot.send_message(call.message.chat.id,"*Импорт из JSON*\n\n"
                                                  "Отправьте JSON файл, полученный при экспорте из этого бота.\n\n"
                                                  "*Требования:*\n• Файл должен быть в формате JSON\n"
                                                  "• Должен содержать поля 'cards' и 'categories'\n"
                                                  "• Максимальный размер: 10MB", parse_mode='Markdown')

            # Сохраняем состояние для ожидания файла
            user_sessions[call.from_user.id] = {'step': 'waiting_json_file', 'data': {'import_type': 'json'}}

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in import_json_callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Обработка загруженных файлов
    @bot.message_handler(content_types=['document'])
    def handle_document(message):
        try:
            user_id = message.from_user.id

            if user_id not in user_sessions or 'step' not in user_sessions[user_id]:
                bot.send_message(message.chat.id, "Сначала выберите тип импорта")
                return

            step = user_sessions[user_id]['step']

            if step != 'waiting_json_file' and step != 'waiting_csv_file' and step != 'waiting_txt_file':
                return

            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)

            file_name = message.document.file_name.lower()

            if file_name.endswith('.json'):
                import_type = 'json'
                content = downloaded_file.decode('utf-8')
            elif file_name.endswith('.csv'):
                import_type = 'csv'
                content = downloaded_file.decode('utf-8-sig')
            elif file_name.endswith('.txt'):
                import_type = 'txt'
                content = downloaded_file.decode('utf-8')
            else:
                bot.send_message(message.chat.id, "Неподдерживаемый формат файла")
                return

            user_sessions[user_id]['data']['file_content'] = content
            user_sessions[user_id]['data']['file_name'] = file_name
            user_sessions[user_id]['step'] = 'select_import_category'

            with with_connection() as conn:
                categories = CategoryUtils.get_user_categories(conn, user_id)

            markup = types.InlineKeyboardMarkup(row_width=2)

            for category in categories[:8]:
                btn = types.InlineKeyboardButton(f"📁 {category['name']}", callback_data=f'import_to_category_{category["id"]}')
                markup.add(btn)

            btn_new = types.InlineKeyboardButton('Новая категория', callback_data='create_category_for_import')
            btn_existing = types.InlineKeyboardButton('Существующие категории',
                                                      callback_data='use_existing_categories')
            btn_cancel = types.InlineKeyboardButton('Отмена', callback_data='cancel_import')

            markup.add(btn_new, btn_existing, btn_cancel)

            bot.send_message(message.chat.id, f"📥 *Файл получен:* {file_name}\n\n"
                                              f"Выберите категорию для импорта карточек:",
                             parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in handle_document: {e}")
            bot.send_message(message.chat.id, "Ошибка при обработке файла")

# Настройки уведомлений
    @bot.message_handler(func=lambda message: message.text == 'Уведомления')
    def notifications_settings(message):
        try:
            user_id = message.from_user.id

            with with_connection() as conn:
                reminder = ReminderUtils.get_user_reminder(conn, user_id)

                if not reminder:
                    ReminderUtils.update_reminder(conn, user_id, enabled=True, reminder_time="20:00")
                    reminder = ReminderUtils.get_user_reminder(conn, user_id)

            status_emoji = "🔔" if reminder['enabled'] else "🔕"
            days_text = "каждый день" if not reminder['days_of_week'] else f"дни: {reminder['days_of_week']}"

            text = (f"*Настройки уведомлений*\n\n*Текущие настройки:*\n"
                    f"• Статус: {status_emoji} {'Включены' if reminder['enabled'] else 'Выключены'}\n"
                    f"• Время: {reminder['reminder_time']}\n• Часовой пояс: {reminder['timezone']}\n"
                    f"• Дни недели: {days_text}\n\n*Типы уведомлений:*\n1. Ежедневные напоминания о повторении\n"
                    f"2. Уведомления о прогрессе\n3. Советы по обучению")

            markup = types.InlineKeyboardMarkup(row_width=2)

            btn_toggle = types.InlineKeyboardButton('Вкл/Выкл', callback_data='toggle_notifications')
            btn_time = types.InlineKeyboardButton('Изменить время', callback_data='change_notification_time')
            btn_days = types.InlineKeyboardButton('Дни недели', callback_data='set_notification_days')
            btn_test = types.InlineKeyboardButton('Тестовое уведомление', callback_data='test_notification')
            btn_types = types.InlineKeyboardButton('Типы уведомлений', callback_data='notification_types')
            btn_back = types.InlineKeyboardButton('Назад', callback_data='back_to_settings')

            markup.add(btn_toggle, btn_time, btn_days, btn_test, btn_types, btn_back)

            bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in notifications_settings: {e}")
            bot.send_message(message.chat.id, "Ошибка при загрузке настроек")

# Настройки аккаунта
    @bot.message_handler(func=lambda message: message.text == 'Аккаунт')
    def account_settings(message):
        try:
            user_id = message.from_user.id

            with with_connection() as conn:
                cursor = conn.execute('''
                                      SELECT username, first_name, last_name, language_code, created_at, last_active
                                      FROM users
                                      WHERE telegram_id = ?
                                      ''', (user_id,))

                user_data = cursor.fetchone()

                if not user_data:
                    bot.send_message(message.chat.id, "Данные пользователя не найдены")
                    return

            created_at = datetime.strptime(user_data['created_at'], "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y")

            last_active = datetime.strptime(user_data['last_active'], "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")

            text = (f"*Настройки аккаунта*\n\n*Основная информация:*\n• ID: `{user_id}`\n"
                    f"• Имя: {user_data['first_name']} {user_data['last_name'] or ''}\n"
                    f"• Username: @{user_data['username'] or 'не указан'}\n• Язык: {user_data['language_code'].upper()}\n\n"
                    f"*Статистика аккаунта:*\n• Зарегистрирован: {created_at}\n• Последняя активность: {last_active}\n"
                    f"• Часовой пояс: Автоматически\n\n*Управление аккаунтом:*\n"
                    f"Здесь вы можете управлять своими данными и настройками.")

            markup = types.InlineKeyboardMarkup(row_width=2)

            btn_change_name = types.InlineKeyboardButton('Изменить имя', callback_data='change_name')
            btn_change_lang = types.InlineKeyboardButton('Изменить язык', callback_data='change_language')
            btn_privacy = types.InlineKeyboardButton('Конфиденциальность', callback_data='privacy_settings')
            btn_delete = types.InlineKeyboardButton('Удалить аккаунт', callback_data='delete_account_confirm')
            btn_export = types.InlineKeyboardButton('Экспорт данных', callback_data='export_all_data')
            btn_back = types.InlineKeyboardButton('Назад', callback_data='back_to_settings')

            markup.add(btn_change_name, btn_change_lang, btn_privacy, btn_delete, btn_export, btn_back)

            bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in account_settings: {e}")
            bot.send_message(message.chat.id, "Ошибка при загрузке настроек аккаунта")

# Настройки внешнего вида
    @bot.message_handler(func=lambda message: message.text == 'Внешний вид')
    def appearance_settings(message):
        try:
            text = ("*Настройки внешнего вида*\n\n*Темы интерфейса:*\n"
                    "Вы можете изменить внешний вид бота для более комфортного использования.\n\n*Доступные настройки:*\n"
                    "1. Тема оформления (светлая/темная)\n2. Размер текста\n3. Отображение эмодзи\n4. Формат дат и времени")

            markup = types.InlineKeyboardMarkup(row_width=2)

            btn_theme = types.InlineKeyboardButton('Тема оформления', callback_data='change_theme')
            btn_font = types.InlineKeyboardButton('Размер текста', callback_data='change_font_size')
            btn_emoji = types.InlineKeyboardButton('Эмодзи', callback_data='toggle_emoji')
            btn_date = types.InlineKeyboardButton('Формат дат', callback_data='date_format')
            btn_preview = types.InlineKeyboardButton('Предпросмотр', callback_data='preview_appearance')
            btn_reset = types.InlineKeyboardButton('Сбросить настройки', callback_data='reset_appearance')
            btn_back = types.InlineKeyboardButton('Назад', callback_data='back_to_settings')

            markup.add(btn_theme, btn_font, btn_emoji, btn_date, btn_preview, btn_reset, btn_back)

            bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in appearance_settings: {e}")
            bot.send_message(message.chat.id, "Ошибка")

# Дополнительные настройки
    @bot.message_handler(func=lambda message: message.text == '⚙️ Дополнительно')
    def advanced_settings(message):
        try:
            user_id = message.from_user.id

            with with_connection() as conn:
                cursor = conn.execute('SELECT COUNT(*) as count FROM cards WHERE user_id = ?', (user_id,))
                cards_count = cursor.fetchone()['count']

                cursor = conn.execute('SELECT COUNT(*) as count FROM categories WHERE user_id = ?', (user_id,))
                categories_count = cursor.fetchone()['count']

            text = (f"*Дополнительные настройки*\n\n*Статистика базы данных:*\n• Карточек: {cards_count}\n"
                    f"• Категорий: {categories_count}\n\n*Дополнительные функции:*\n1. Настройки алгоритма повторений\n"
                    f"2. Автоматическое резервное копирование\n3. Расширенные статистики\n4. Экспорт в разные форматы\n"
                    f"5. Интеграции с другими сервисами")

            markup = types.InlineKeyboardMarkup(row_width=2)

            btn_algorithm = types.InlineKeyboardButton('Алгоритм повторений',
                                                       callback_data='spaced_repetition_settings')
            btn_backup = types.InlineKeyboardButton('Автобэкап', callback_data='auto_backup_settings')
            btn_stats = types.InlineKeyboardButton('Расширенные статистики', callback_data='advanced_stats')
            btn_integrations = types.InlineKeyboardButton('Интеграции', callback_data='integrations')
            btn_debug = types.InlineKeyboardButton('Режим отладки', callback_data='toggle_debug')
            btn_reset = types.InlineKeyboardButton('Сбросить все данные', callback_data='reset_all_data_confirm')
            btn_back = types.InlineKeyboardButton('Назад', callback_data='back_to_settings')

            markup.add(btn_algorithm, btn_backup, btn_stats, btn_integrations, btn_debug, btn_reset, btn_back)

            bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in advanced_settings: {e}")
            bot.send_message(message.chat.id, "Ошибка")

# Очистка данных
    @bot.callback_query_handler(func=lambda call: call.data == 'cleanup_data')
    def cleanup_data_callback(call):
        try:
            user_id = call.from_user.id

            markup = types.InlineKeyboardMarkup(row_width=2)

            btn_old_cards = types.InlineKeyboardButton('Удалить старые карточки', callback_data='delete_old_cards')
            btn_empty_categories = types.InlineKeyboardButton('Удалить пустые категории',
                                                              callback_data='delete_empty_categories')
            btn_duplicates = types.InlineKeyboardButton('Удалить дубликаты', callback_data='delete_duplicates')
            btn_all = types.InlineKeyboardButton('Удалить все данные', callback_data='delete_all_data_confirm')
            btn_back = types.InlineKeyboardButton('Назад', callback_data='back_to_settings')

            markup.add(btn_old_cards, btn_empty_categories, btn_duplicates, btn_all, btn_back)

            bot.edit_message_text("*Очистка данных*\n\nВыберите тип очистки:",
                                  call.message.chat.id, call.message.message_id,
                                  parse_mode='Markdown', reply_markup=markup)

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in cleanup_data_callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Удаление старых карточек
    @bot.callback_query_handler(func=lambda call: call.data == 'delete_old_cards')
    def delete_old_cards_callback(call):
        try:
            user_id = call.from_user.id

            markup = types.InlineKeyboardMarkup(row_width=3)

            btn_30_days = types.InlineKeyboardButton('30 дней', callback_data='delete_cards_30_days')
            btn_90_days = types.InlineKeyboardButton('90 дней', callback_data='delete_cards_90_days')
            btn_180_days = types.InlineKeyboardButton('180 дней', callback_data='delete_cards_180_days')
            btn_custom = types.InlineKeyboardButton('Свой период', callback_data='delete_cards_custom')
            btn_back = types.InlineKeyboardButton('Назад', callback_data='cleanup_data')

            markup.add(btn_30_days, btn_90_days, btn_180_days, btn_custom, btn_back)

            bot.edit_message_text("*Удаление старых карточек*\n\n"
                                  "Удалить карточки, которые не использовались дольше указанного периода:",
                                  call.message.chat.id, call.message.message_id,
                                  parse_mode='Markdown', reply_markup=markup)

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in delete_old_cards_callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Сброс статистики
    @bot.callback_query_handler(func=lambda call: call.data == 'delete_empty_categories')
    def delete_empty_categories_callback(call):
        try:
            user_id = call.from_user.id

            with with_connection() as conn:
                cursor = conn.execute('''
                                      SELECT c.id, c.name
                                      FROM categories c
                                               LEFT JOIN cards ON c.id = cards.category_id AND cards.user_id = c.user_id
                                      WHERE c.user_id = ?
                                        AND cards.id IS NULL
                                      ''', (user_id,))

                empty_categories = cursor.fetchall()

                if not empty_categories:
                    bot.answer_callback_query(call.id, "Пустых категорий не найдено!", show_alert=True)
                    return

            categories_text = "*Пустые категории для удаления:*\n\n"
            for cat in empty_categories:
                categories_text += f"• {cat['name']}\n"

            markup = types.InlineKeyboardMarkup()
            btn_confirm = types.InlineKeyboardButton('Удалить все', callback_data='confirm_delete_empty_categories')
            btn_cancel = types.InlineKeyboardButton('Отмена', callback_data='cleanup_data')

            markup.add(btn_confirm, btn_cancel)

            bot.edit_message_text(f"{categories_text}\nВсего категорий: {len(empty_categories)}\n\nУдалить эти категории?",
                                  call.message.chat.id, call.message.message_id,
                                  parse_mode='Markdown', reply_markup=markup)

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in delete_empty_categories_callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Сброс статистики
    @bot.callback_query_handler(func=lambda call: call.data == 'reset_stats')
    def reset_stats_callback(call):
        try:
            user_id = call.from_user.id

            markup = types.InlineKeyboardMarkup(row_width=2)

            btn_reset_progress = types.InlineKeyboardButton('Сбросить прогресс карточек',
                                                            callback_data='reset_cards_progress')
            btn_reset_sessions = types.InlineKeyboardButton('Сбросить статистику сессий',
                                                            callback_data='reset_sessions_stats')
            btn_reset_all = types.InlineKeyboardButton('Сбросить всю статистику',
                                                       callback_data='reset_all_stats_confirm')
            btn_back = types.InlineKeyboardButton('Назад', callback_data='back_to_settings')

            markup.add(btn_reset_progress, btn_reset_sessions, btn_reset_all, btn_back)

            bot.edit_message_text("*Сброс статистики*\n\nВыберите, какую статистику сбросить:",
                                  call.message.chat.id, call.message.message_id,
                                  parse_mode='Markdown', reply_markup=markup)

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in reset_stats_callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Сброс прогресса карточек
    @bot.callback_query_handler(func=lambda call: call.data == 'reset_cards_progress')
    def reset_cards_progress_callback(call):
        try:
            user_id = call.from_user.id

            with with_connection() as conn:
                cursor = conn.execute('SELECT COUNT(*) as count FROM cards WHERE user_id = ?', (user_id,))
                cards_count = cursor.fetchone()['count']

            markup = types.InlineKeyboardMarkup()
            btn_confirm = types.InlineKeyboardButton('Да, сбросить', callback_data='confirm_reset_cards_progress')
            btn_cancel = types.InlineKeyboardButton('Нет, отмена', callback_data='reset_stats')

            markup.add(btn_confirm, btn_cancel)

            bot.edit_message_text(f"🔄 *Сброс прогресса карточек*\n\nЭто действие сбросит:\n"
                                  f"• Статус всех карточек на 'learning'\n• Счетчики повторений\n"
                                  f"• Статистику правильных/неправильных ответов\n• Даты следующего повторения\n\n"
                                  f"Затронет карточек: *{cards_count}*\n\nВы уверены?",
                                  call.message.chat.id, call.message.message_id,
                                  parse_mode='Markdown', reply_markup=markup)

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in reset_cards_progress_callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Подтверждение сброса прогресса карточек
    @bot.callback_query_handler(func=lambda call: call.data == 'confirm_reset_cards_progress')
    def confirm_reset_cards_progress(call):
        try:
            user_id = call.from_user.id

            with with_connection() as conn:
                conn.execute('''
                             UPDATE cards
                             SET status          = 'learning',
                                 review_count    = 0,
                                 correct_answers = 0,
                                 wrong_answers   = 0,
                                 difficulty      = 1,
                                 last_reviewed   = NULL,
                                 next_review     = NULL
                             WHERE user_id = ?
                             ''', (user_id,))

            bot.edit_message_text("✅ Прогресс карточек сброшен!\n\n"
                                  "Все карточки теперь помечены как 'изучается'.",
                                  call.message.chat.id, call.message.message_id)

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in confirm_reset_cards_progress: {e}")
            bot.answer_callback_query(call.id, "Ошибка при сбросе")

# Возврат к настройкам
    @bot.callback_query_handler(func=lambda call: call.data == 'back_to_settings')
    def back_to_settings_callback(call):
        try:
            settings_main_menu(call.message)
            bot.answer_callback_query(call.id)
        except Exception as e:
            logger.error(f"Error in back_to_settings_callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Помощь по настройкам
    @bot.callback_query_handler(func=lambda call: call.data == 'settings_help')
    def settings_help_callback(call):
        try:
            text = ("*Помощь по настройкам*\n\n*Основные разделы:*\n\n"
                    "1. *Экспорт данных* - сохранение карточек в файл\n"
                    "2. *Импорт данных* - загрузка карточек из файла\n"
                    "3. *Уведомления* - настройка напоминаний\n"
                    "4. *Аккаунт* - управление профилем\n5. *Внешний вид* - темы и оформление\n"
                    "6. *Дополнительно* - продвинутые настройки\n\n*Советы:*\n"
                    "• Регулярно экспортируйте данные для бэкапа\n• Настройте удобное время напоминаний\n"
                    "• Используйте разные категории для организации\n• Очищайте старые данные для оптимизации\n\n"
                    "*Форматы экспорта:*\n• JSON - полный бэкап со всеми данными\n"
                    "• CSV - для работы в табличных редакторах\n• TXT - для печати или чтения")

            markup = types.InlineKeyboardMarkup()
            btn_back = types.InlineKeyboardButton('Назад', callback_data='back_to_settings')
            markup.add(btn_back)

            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='Markdown', reply_markup=markup)

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in settings_help_callback: {e}")
            bot.answer_callback_query(call.id, "❌ Ошибка")

    logger.info("Settings handlers registered successfully")
    return bot


# Глобальный словарь для хранения состояний пользователей
user_sessions = {}