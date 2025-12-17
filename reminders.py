import logging
import threading
import schedule
import time
from datetime import datetime, time as dt_time, timedelta
from telebot import types
from database import with_connection, ReminderUtils, CardUtils, UserUtils, with_connection

logger = logging.getLogger(__name__)

reminder_scheduler = None


# Регистрация всех обработчиков для работы с напоминаниями
def register_reminders_handlers(bot):

# Отправка напоминания пользователю
    def send_reminder(user_id, bot_instance):
        try:
            with with_connection() as conn:
                cards_for_review = CardUtils.get_cards_for_review(conn, user_id, limit=5)

                if not cards_for_review:
                    return

                cursor = conn.execute('SELECT first_name FROM users WHERE telegram_id = ?', (user_id,))
                user_data = cursor.fetchone()
                first_name = user_data['first_name'] if user_data else "друг"

            message_text = (f"*Напоминание, {first_name}!*\n\nУ вас есть карточки для повторения:\n"
                            f"• Всего для повторения: *{len(cards_for_review)}* карточек\n\n*Примеры карточек:*")

            for i, card in enumerate(cards_for_review[:3], 1):
                message_text += f"{i}. {card['front'][:30]}...\n"

            message_text += "Используйте /today чтобы начать повторение!"

            markup = types.InlineKeyboardMarkup(row_width=2)
            btn_start = types.InlineKeyboardButton('Начать повторение', callback_data='start_review_now')
            btn_today = types.InlineKeyboardButton('На сегодня', callback_data='view_today_cards')
            btn_settings = types.InlineKeyboardButton('Настройки', callback_data='reminder_settings')
            btn_snooze = types.InlineKeyboardButton('Напомнить позже', callback_data='snooze_reminder')

            markup.add(btn_start, btn_today, btn_settings, btn_snooze)

            bot_instance.send_message(user_id, message_text, parse_mode='Markdown', reply_markup=markup)

            logger.info(f"Reminder sent to user {user_id}")

        except Exception as e:
            logger.error(f"Error sending reminder to {user_id}: {e}")

# Проверка и отправка напоминаний всем пользователям
    def check_and_send_reminders(bot_instance):
        try:
            current_time = datetime.now().strftime("%H:%M")
            current_weekday = datetime.now().weekday() + 1

            logger.debug(f"Checking reminders at {current_time}, weekday {current_weekday}")

            with with_connection() as conn:
                reminders = ReminderUtils.get_active_reminders(conn)

                for reminder in reminders:
                    try:
                        user_id = reminder['user_id']
                        reminder_time = reminder['reminder_time']
                        days_of_week = reminder['days_of_week']

                        if days_of_week:
                            days_list = [int(d.strip()) for d in days_of_week.split(',') if d.strip()]
                            if current_weekday not in days_list:
                                continue

                        if reminder_time != current_time:
                            continue

                        send_reminder(user_id, bot_instance)

                        conn.execute('UPDATE reminders SET last_sent = CURRENT_TIMESTAMP WHERE user_id = ?', (user_id,))

                    except Exception as e:
                        logger.error(f"Error processing reminder for user {reminder.get('user_id')}: {e}")
                        continue

        except Exception as e:
            logger.error(f"Error in check_and_send_reminders: {e}")

# Запуск планировщика напоминаний
    def start_reminder_scheduler(bot_instance):
        global reminder_scheduler

        if reminder_scheduler and reminder_scheduler.is_alive():
            return

# Основной цикл планировщика
        def scheduler_loop():
            while True:
                try:
                    schedule.run_pending()
                    time.sleep(60)
                except Exception as e:
                    logger.error(f"Error in scheduler loop: {e}")
                    time.sleep(300)

        schedule.every().minute.do(check_and_send_reminders, bot_instance)

        reminder_scheduler = threading.Thread(target=scheduler_loop, daemon=True)
        reminder_scheduler.start()

        logger.info("Reminder scheduler started")

# Главное меню управления напоминаниями
    @bot.message_handler(commands=['reminder', 'reminders'])
    def reminders_main_menu(message):
        try:
            user_id = message.from_user.id

            with with_connection() as conn:
                reminder = ReminderUtils.get_user_reminder(conn, user_id)

                if not reminder:
                    ReminderUtils.update_reminder(conn, user_id, enabled=True, reminder_time="20:00")
                    reminder = ReminderUtils.get_user_reminder(conn, user_id)

            status_emoji = "🔔" if reminder['enabled'] else "🔕"
            status_text = "Включены" if reminder['enabled'] else "Выключены"

            if reminder['days_of_week']:
                days_map = {'1': 'Пн', '2': 'Вт', '3': 'Ср', '4': 'Чт', '5': 'Пт', '6': 'Сб', '7': 'Вс'}
                days_list = [days_map[d.strip()] for d in reminder['days_of_week'].split(',') if d.strip()]
                days_text = ', '.join(days_list)
            else:
                days_text = "Каждый день"

            text = (f"*Управление напоминаниями*\n\n*Текущие настройки:*\n• Статус: {status_emoji} {status_text}\n"
                    f"• Время: {reminder['reminder_time']}\n• Дни: {days_text}\n• Часовой пояс: {reminder['timezone']}\n\n"
                    f"*Что делает бот:*\nЕжедневно в указанное время я буду напоминать вам о карточках,\t"
                    f"которые нужно повторить.\n\n*Как это работает:*\n"
                    f"1. Бот проверяет карточки по системе интервальных повторений\n"
                    f"2. Если есть карточки для повторения - отправляет уведомление\n"
                    f"3. Вы нажимаете 'Начать повторение' и учитесь")

            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

            btn_toggle = types.KeyboardButton('Вкл/Выкл')
            btn_set_time = types.KeyboardButton('Изменить время')
            btn_set_days = types.KeyboardButton('Дни недели')
            btn_test = types.KeyboardButton('Тестовое напоминание')
            btn_stats = types.KeyboardButton('Статистика')
            btn_back = types.KeyboardButton('Назад')

            markup.add(btn_toggle, btn_set_time, btn_set_days, btn_test, btn_stats, btn_back)

            inline_markup = types.InlineKeyboardMarkup(row_width=2)

            btn_enable = types.InlineKeyboardButton('Включить', callback_data='enable_reminder')
            btn_disable = types.InlineKeyboardButton('Выключить', callback_data='disable_reminder')
            btn_set_20 = types.InlineKeyboardButton('20:00', callback_data='set_time_20:00')
            btn_set_9 = types.InlineKeyboardButton('09:00', callback_data='set_time_09:00')
            btn_set_22 = types.InlineKeyboardButton('22:00', callback_data='set_time_22:00')
            btn_custom = types.InlineKeyboardButton('Другое время', callback_data='set_custom_time')

            inline_markup.add(btn_enable, btn_disable, btn_set_20, btn_set_9, btn_set_22, btn_custom)

            bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

            bot.send_message(message.chat.id, "*Быстрые настройки:*", parse_mode='Markdown', reply_markup=inline_markup)

        except Exception as e:
            logger.error(f"Error in reminders_main_menu: {e}")
            bot.send_message(message.chat.id, "Ошибка при загрузке настроек")

# Переключение статуса напоминаний
    @bot.message_handler(func=lambda message: message.text == 'Вкл/Выкл')
    def toggle_reminder(message):
        try:
            user_id = message.from_user.id

            with with_connection() as conn:
                reminder = ReminderUtils.get_user_reminder(conn, user_id)

                if not reminder:
                    bot.send_message(message.chat.id, "Настройки не найдены")
                    return

                new_status = not reminder['enabled']
                success = ReminderUtils.update_reminder(conn, user_id, enabled=new_status)

                if success:
                    status_text = "включены" if new_status else "выключены"
                    emoji = "🔔" if new_status else "🔕"

                    bot.send_message(message.chat.id, f"{emoji} Напоминания *{status_text}*", parse_mode='Markdown')
                else:
                    bot.send_message(message.chat.id, "Ошибка при изменении настроек")

        except Exception as e:
            logger.error(f"Error in toggle_reminder: {e}")
            bot.send_message(message.chat.id, "Ошибка")

# Начало изменения времени напоминания
    @bot.message_handler(func=lambda message: message.text == 'Изменить время')
    def set_reminder_time_start(message):
        try:
            user_id = message.from_user.id

            user_sessions[user_id] = {'step': 'setting_reminder_time', 'data': {}}

            markup = types.InlineKeyboardMarkup(row_width=3)

            times = ['07:00', '08:00', '09:00', '10:00', '12:00', '15:00', '18:00', '19:00', '20:00', '21:00', '22:00']

            for t in times:
                btn = types.InlineKeyboardButton(f'🕒 {t}', callback_data=f'set_time_{t}')
                markup.add(btn)

            btn_custom = types.InlineKeyboardButton('Свое время', callback_data='enter_custom_time')
            btn_cancel = types.InlineKeyboardButton('Отмена', callback_data='cancel_time_setting')

            markup.add(btn_custom, btn_cancel)

            bot.send_message(message.chat.id, "*Выберите время для напоминаний:*\n\n"
                                              "Рекомендуемое время: *20:00-22:00*\n"
                                              "Вечером лучше всего запоминается информация.",
                             parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in set_reminder_time_start: {e}")
            bot.send_message(message.chat.id, "Ошибка")

# Установка времени напоминания через callback
    @bot.callback_query_handler(func=lambda call: call.data.startswith('set_time_'))
    def set_reminder_time_callback(call):
        try:
            user_id = call.from_user.id
            time_str = call.data.replace('set_time_', '')

            # Проверяем формат времени
            try:
                datetime.strptime(time_str, "%H:%M")
            except ValueError:
                bot.answer_callback_query(call.id, "Неверный формат времени")
                return

            with with_connection() as conn:
                success = ReminderUtils.update_reminder(conn, user_id, reminder_time=time_str)

                if success:
                    bot.edit_message_text(f"Время напоминаний установлено на *{time_str}*", call.message.chat.id,
                                          call.message.message_id, parse_mode='Markdown')

                    markup = types.InlineKeyboardMarkup()
                    btn_test = types.InlineKeyboardButton('Тестовое уведомление', callback_data='send_test_reminder')
                    btn_back = types.InlineKeyboardButton('Назад к настройкам', callback_data='back_to_reminders')

                    markup.add(btn_test, btn_back)

                    bot.send_message(call.message.chat.id, f"*Напоминание настроено*\n\n"
                                                           f"Каждый день в *{time_str}* бот будет проверять,\t"
                                                           f"есть ли у вас карточки для повторения.\n\n"
                                                           f"*Следующая проверка:* завтра в {time_str}",
                                     parse_mode='Markdown', reply_markup=markup)
                else:
                    bot.edit_message_text("Ошибка при сохранении времени", call.message.chat.id, call.message.message_id)

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in set_reminder_time_callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Ввод своего времени
    @bot.callback_query_handler(func=lambda call: call.data == 'enter_custom_time')
    def enter_custom_time(call):
        try:
            user_id = call.from_user.id

            user_sessions[user_id] = {'step': 'entering_custom_time', 'data': {}}

            msg = bot.send_message(call.message.chat.id,"*Введите свое время*\n\nФормат: *ЧЧ:MM*\nНапример: 21:30\n\n"
                                                        "*Рекомендации:*\n• Утро (07:00-10:00) - для жаворонков\n"
                                                        "• День (12:00-15:00) - во время перерыва\n"
                                                        "• Вечер (20:00-22:00) - оптимальное время",
                                   parse_mode='Markdown')

            bot.register_next_step_handler(msg, process_custom_time)
            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in enter_custom_time: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Обработка введенного времени
    def process_custom_time(message):
        try:
            user_id = message.from_user.id
            time_str = message.text.strip()
            try:
                datetime.strptime(time_str, "%H:%M")
            except ValueError:
                msg = bot.send_message(message.chat.id, "Неверный формат времени. Используйте ЧЧ:MM\n"
                                                        "Например: 21:30\n\nПопробуйте еще раз:")
                bot.register_next_step_handler(msg, process_custom_time)
                return

            with with_connection() as conn:
                success = ReminderUtils.update_reminder(conn, user_id, reminder_time=time_str)

                if success:
                    bot.send_message(message.chat.id, f"Время установлено на *{time_str}*", parse_mode='Markdown')
                else:
                    bot.send_message(message.chat.id, "Ошибка при сохранении")

        except Exception as e:
            logger.error(f"Error in process_custom_time: {e}")
            bot.send_message(message.chat.id, "Ошибка")

# Настройка дней недели для напоминаний
    @bot.message_handler(func=lambda message: message.text == 'Дни недели')
    def set_reminder_days(message):
        try:
            user_id = message.from_user.id

            with with_connection() as conn:
                reminder = ReminderUtils.get_user_reminder(conn, user_id)

                current_days = []
                if reminder and reminder['days_of_week']:
                    current_days = [int(d.strip()) for d in reminder['days_of_week'].split(',') if d.strip()]

            text = ("*Выбор дней для напоминаний*\n\nВыберите дни недели, когда вы хотите получать напоминания:\n\n"
                    "*Рекомендации:*\n• Пн-Пт (1-5) - для ежедневной практики\n• Пн, Ср, Пт (1,3,5) - через день\n"
                    "• Сб-Вс (6-7) - на выходных\n• Все дни (1-7) - каждый день")

            markup = types.InlineKeyboardMarkup(row_width=3)

            days = [(1, 'Понедельник', 'Пн'), (2, 'Вторник', 'Вт'), (3, 'Среда', 'Ср'), (4, 'Четверг', 'Чт'),
                    (5, 'Пятница', 'Пт'), (6, 'Суббота', 'Сб'), (7, 'Воскресенье', 'Вс')]

            for day_num, day_name, day_short in days:
                is_selected = day_num in current_days
                emoji = "✅" if is_selected else "⚪"
                btn_text = f"{emoji} {day_short}"

                btn = types.InlineKeyboardButton(btn_text, callback_data=f'toggle_day_{day_num}')
                markup.add(btn)

            btn_select_all = types.InlineKeyboardButton('Все дни', callback_data='select_all_days')
            btn_weekdays = types.InlineKeyboardButton('Только будни', callback_data='select_weekdays')
            btn_weekend = types.InlineKeyboardButton('Только выходные', callback_data='select_weekend')
            btn_save = types.InlineKeyboardButton('Сохранить', callback_data='save_days_selection')
            btn_cancel = types.InlineKeyboardButton('Отмена', callback_data='cancel_days_selection')

            markup.add(btn_select_all, btn_weekdays, btn_weekend, btn_save, btn_cancel)

            bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in set_reminder_days: {e}")
            bot.send_message(message.chat.id, "Ошибка")

# Переключение выбора дня недели
    @bot.callback_query_handler(func=lambda call: call.data.startswith('toggle_day_'))
    def toggle_day_callback(call):
        try:
            user_id = call.from_user.id
            day_num = int(call.data.replace('toggle_day_', ''))

            message_text = call.message.text
            markup = call.message.reply_markup

            new_markup = types.InlineKeyboardMarkup(row_width=3)

            for row in markup.keyboard:
                new_row = []
                for button in row:
                    btn_data = button.callback_data

                    if btn_data == call.data:
                        emoji = "⚪" if "✅" in button.text else "✅"
                        btn_text = f"{emoji} {button.text[2:]}"
                        new_button = types.InlineKeyboardButton(btn_text, callback_data=btn_data)
                    else:
                        new_button = button

                    new_row.append(new_button)

                new_markup.add(*new_row)

            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=new_markup)

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in toggle_day_callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

 # Сохранение выбранных дней недели
    @bot.callback_query_handler(func=lambda call: call.data == 'save_days_selection')
    def save_days_selection(call):
        try:
            user_id = call.from_user.id
            markup = call.message.reply_markup

            selected_days = []
            for row in markup.keyboard:
                for button in row:
                    if button.callback_data and button.callback_data.startswith('toggle_day_'):
                        if "✅" in button.text:
                            day_num = int(button.callback_data.replace('toggle_day_', ''))
                            selected_days.append(day_num)

            selected_days.sort()
            days_str = ','.join(str(d) for d in selected_days)

            with with_connection() as conn:
                success = ReminderUtils.update_reminder(conn, user_id, days_of_week=days_str)

                if success:
                    days_map = {1: 'Пн', 2: 'Вт', 3: 'Ср', 4: 'Чт', 5: 'Пт', 6: 'Сб', 7: 'Вс'}
                    days_text = ', '.join(days_map[d] for d in selected_days)

                    bot.edit_message_text(f"Дни недели сохранены:\n*{days_text}*",
                                          call.message.chat.id, call.message.message_id, parse_mode='Markdown')
                else:
                    bot.edit_message_text("Ошибка при сохранении", call.message.chat.id, call.message.message_id)

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in save_days_selection: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Отправка тестового напоминания
    @bot.message_handler(func=lambda message: message.text == 'Тестовое напоминание')
    def send_test_reminder(message):
        try:
            user_id = message.from_user.id

            send_reminder(user_id, bot)

            bot.send_message(message.chat.id, "*Тестовое напоминание отправлено!*\n\n"
                                              "Проверьте, получили ли вы уведомление.\n"
                                              "Если нет, проверьте настройки уведомлений Telegram.",
                             parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error in send_test_reminder: {e}")
            bot.send_message(message.chat.id, "Ошибка при отправке тестового напоминания")

# Статистика напоминаний
    @bot.message_handler(func=lambda message: message.text == 'Статистика')
    def reminders_stats(message):
        try:
            user_id = message.from_user.id

            with with_connection() as conn:
                reminder = ReminderUtils.get_user_reminder(conn, user_id)

                if not reminder:
                    bot.send_message(message.chat.id, "Настройки не найдены")
                    return

                cursor = conn.execute('''
                                      SELECT COUNT(*)        AS total_reminders_sent,
                                             MAX(last_sent)  AS last_reminder_sent,
                                             MIN(created_at) AS reminders_since
                                      FROM reminders
                                      WHERE user_id = ?
                                        AND last_sent IS NOT NULL
                                      ''', (user_id,))

                stats = cursor.fetchone()

                cards_for_review = CardUtils.get_cards_for_review(conn, user_id, limit=50)

            status_emoji = "🔔" if reminder['enabled'] else "🔕"
            status_text = "Включены" if reminder['enabled'] else "Выключены"

            text = (f"*Статистика напоминаний*\n\n*Настройки:*\n• Статус: {status_emoji} {status_text}\n"
                    f"• Время: {reminder['reminder_time']})\n• Часовой пояс: {reminder['timezone']}\n\n"
                    f"*Статистика:*\n• Карточек для повторения: *{len(cards_for_review)}*\n"
                    f"• Всего отправлено напоминаний:\t"
                    f"*{stats['total_reminders_sent'] if stats['total_reminders_sent'] else 0}*\n"
                    f"• Последнее напоминание:\t"
                    f"*{stats['last_reminder_sent'] if stats['last_reminder_sent'] else 'никогда'}*\n"
                    f"• Используется с: *{stats['reminders_since'][:10] if stats['reminders_since'] else 'недавно'}*\n\n"
                    f"*Следующая проверка:* сегодня в {reminder['reminder_time']}")

            if cards_for_review:
                text += "\n\n*Карточки для повторения:*\n"
                for i, card in enumerate(cards_for_review[:5], 1):
                    text += f"{i}. {card['front'][:30]}...\n"

                if len(cards_for_review) > 5:
                    text += f"... и еще {len(cards_for_review) - 5}\n"

            bot.send_message(
                message.chat.id,
                text,
                parse_mode='Markdown'
            )

        except Exception as e:
            logger.error(f"Error in reminders_stats: {e}")
            bot.send_message(message.chat.id, "Ошибка при загрузке статистики")

# Включение напоминаний через callback
    @bot.callback_query_handler(func=lambda call: call.data == 'enable_reminder')
    def enable_reminder_callback(call):
        try:
            user_id = call.from_user.id

            with with_connection() as conn:
                success = ReminderUtils.update_reminder(
                    conn, user_id, enabled=True
                )

                if success:
                    bot.answer_callback_query(
                        call.id,
                        "Напоминания включены",
                        show_alert=True
                    )

                    reminders_main_menu(call.message)
                else:
                    bot.answer_callback_query(call.id, "Ошибка")

        except Exception as e:
            logger.error(f"Error in enable_reminder_callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Выключение напоминаний через callback
    @bot.callback_query_handler(func=lambda call: call.data == 'disable_reminder')
    def disable_reminder_callback(call):
        try:
            user_id = call.from_user.id

            with with_connection() as conn:
                success = ReminderUtils.update_reminder(
                    conn, user_id, enabled=False
                )

                if success:
                    bot.answer_callback_query(
                        call.id,
                        "Напоминания выключены",
                        show_alert=True
                    )

                    reminders_main_menu(call.message)
                else:
                    bot.answer_callback_query(call.id, "Ошибка")

        except Exception as e:
            logger.error(f"Error in disable_reminder_callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Отправка тестового напоминания через callback
    @bot.callback_query_handler(func=lambda call: call.data == 'send_test_reminder')
    def send_test_reminder_callback(call):
        try:
            user_id = call.from_user.id
            send_reminder(user_id, bot)

            bot.answer_callback_query(
                call.id,
                "Тестовое напоминание отправлено!",
                show_alert=True
            )

        except Exception as e:
            logger.error(f"Error in send_test_reminder_callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Начало повторения из напоминания
    @bot.callback_query_handler(func=lambda call: call.data == 'start_review_now')
    def start_review_from_reminder(call):
        try:
            from quiz import start_review_session
            start_review_session(call)
            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in start_review_from_reminder: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Отложить напоминание
    @bot.callback_query_handler(func=lambda call: call.data == 'snooze_reminder')
    def snooze_reminder_callback(call):
        try:
            bot.answer_callback_query(
                call.id,
                "Напоминание отложено на 1 час",
                show_alert=True
            )

        except Exception as e:
            logger.error(f"Error in snooze_reminder_callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

    start_reminder_scheduler(bot)

    logger.info("Reminders handlers registered successfully")
    return bot