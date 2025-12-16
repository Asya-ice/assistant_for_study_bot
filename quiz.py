import logging
import random
from datetime import datetime, timedelta
from telebot import types
from utils.db_utils import with_connection, CardUtils, CategoryUtils, UserUtils, with_connection

logger = logging.getLogger(__name__)

# Словарь для хранения активных сессий тестирования
quiz_sessions = {}


# Регистрация всех обработчиков для тестирования и повторений
def register_quiz_handlers(bot):

# Начало тестирования - выбор режима
    @bot.message_handler(commands=['quiz', 'test', 'study'])
    @bot.message_handler(func=lambda message: message.text in ['🎯 Тестирование', '🎯 Начать тестирование', '🎯 Учить'])
    def start_quiz_command(message):
        try:
            user_id = message.from_user.id

            with with_connection() as conn:
                all_cards = CardUtils.get_user_cards(conn, user_id)

                if not all_cards:
                    markup = types.InlineKeyboardMarkup()
                    btn_add = types.InlineKeyboardButton('➕ Добавить карточки', callback_data='add_cards_first')
                    markup.add(btn_add)

                    bot.send_message(message.chat.id, "📭 *У вас пока нет карточек для тестирования*\n\n"
                                                     "Сначала добавьте карточки с помощью команды /add_card",
                                     parse_mode='Markdown', reply_markup=markup)
                    return

                due_cards = CardUtils.get_cards_for_review(conn, user_id)

                categories = CategoryUtils.get_user_categories(conn, user_id)

            text = (f"*Режимы тестирования*\n\nВаша статистика:\n• Всего карточек: *{len(all_cards)}*\n"
                    f"• Для повторения сегодня: *{len(due_cards)}*\n\n*Выберите режим:*")

            markup = types.InlineKeyboardMarkup(row_width=2)

            btn_review = types.InlineKeyboardButton('Повторение сегодня', callback_data='start_review_session')
            btn_random = types.InlineKeyboardButton('Случайные карточки', callback_data='start_random_session')
            btn_category = types.InlineKeyboardButton('По категории', callback_data='start_category_session')
            btn_difficult = types.InlineKeyboardButton('Сложные карточки', callback_data='start_difficult_session')
            btn_all = types.InlineKeyboardButton('Все карточки', callback_data='start_all_session')
            btn_new = types.InlineKeyboardButton('овые карточки', callback_data='start_new_session')

            markup.add(btn_review, btn_random, btn_category, btn_difficult, btn_all, btn_new)

            if categories:
                bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

                categories_text = "*Быстрый старт по категориям:*\n"
                categories_markup = types.InlineKeyboardMarkup(row_width=3)

                for i, category in enumerate(categories[:6]):
                    btn = types.InlineKeyboardButton(f"📁 {category['name'][:10]}",
                                                     callback_data=f'quiz_category_{category["id"]}')
                    if i % 3 == 0 and i > 0:
                        categories_markup.row(btn)
                    else:
                        categories_markup.add(btn)

                bot.send_message(message.chat.id, categories_text, parse_mode='Markdown', reply_markup=categories_markup)
            else:
                bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in start_quiz_command: {e}")
            bot.send_message(message.chat.id, "Ошибка при запуске тестирования")

# Запуск сессии тестирования
    def start_quiz_session(user_id, card_ids, session_type='review'):
        try:
            if not card_ids:
                return None

            random.shuffle(card_ids)

            session_id = f"{user_id}_{datetime.now().timestamp()}"

            quiz_sessions[session_id] = {'user_id': user_id, 'card_ids': card_ids, 'current_index': 0,
                                         'correct_answers': 0, 'wrong_answers': 0,'start_time': datetime.now(),
                                         'session_type': session_type, 'current_card_id': card_ids[0]
                if card_ids else None}

            return session_id

        except Exception as e:
            logger.error(f"Error in start_quiz_session: {e}")
            return None

# Начать сессию повторения карточек на сегодня
    @bot.callback_query_handler(func=lambda call: call.data == 'start_review_session')
    def start_review_session(call):
        try:
            user_id = call.from_user.id

            with with_connection() as conn:
                cards = CardUtils.get_cards_for_review(conn, user_id, limit=20)

                if not cards:
                    bot.answer_callback_query(call.id, "🎉 Отличная работа! Сегодня нет карточек для повторения.",
                                              show_alert=True)
                    return

                card_ids = [card['id'] for card in cards]
                session_id = start_quiz_session(user_id, card_ids, 'review')

                if session_id:
                    show_next_card(bot, call.message.chat.id, session_id)
                    bot.answer_callback_query(call.id)
                else:
                    bot.answer_callback_query(call.id, "Ошибка при запуске сессии")

        except Exception as e:
            logger.error(f"Error in start_review_session: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Начать сессию со случайными карточками
    @bot.callback_query_handler(func=lambda call: call.data == 'start_random_session')
    def start_random_session(call):
        try:
            user_id = call.from_user.id

            with with_connection() as conn:
                all_cards = CardUtils.get_user_cards(conn, user_id)

                if not all_cards:
                    bot.answer_callback_query(call.id, "Нет карточек для тестирования")
                    return

                # Выбираем случайные карточки (макс 10)
                card_ids = [card['id'] for card in all_cards]
                random.shuffle(card_ids)
                selected_ids = card_ids[:10]

                session_id = start_quiz_session(user_id, selected_ids, 'random')

                if session_id:
                    show_next_card(bot, call.message.chat.id, session_id)
                    bot.answer_callback_query(call.id)
                else:
                    bot.answer_callback_query(call.id, "Ошибка")

        except Exception as e:
            logger.error(f"Error in start_random_session: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Начать тестирование по выбранной категории
    @bot.callback_query_handler(func=lambda call: call.data.startswith('quiz_category_'))
    def start_category_quiz(call):
        try:
            user_id = call.from_user.id
            category_id = call.data.replace('quiz_category_', '')

            with with_connection() as conn:
                category = CategoryUtils.get_category_by_id(conn, category_id)

                if not category:
                    bot.answer_callback_query(call.id, "Категория не найдена")
                    return

                cards = CardUtils.get_user_cards(conn, user_id, category_id=category_id)

                if not cards:
                    bot.answer_callback_query(call.id,
                                              f"📭 В категории *{category['name']}* нет карточек", show_alert=True)
                    return

                card_ids = [card['id'] for card in cards]
                session_id = start_quiz_session(user_id, card_ids, f'category_{category_id}')

                if session_id:
                    show_next_card(bot, call.message.chat.id, session_id)
                    bot.answer_callback_query(call.id)
                else:
                    bot.answer_callback_query(call.id, "Ошибка")

        except Exception as e:
            logger.error(f"Error in start_category_quiz: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Показать следующую карточку в сессии
    def show_next_card(bot_instance, chat_id, session_id):
        try:
            if session_id not in quiz_sessions:
                bot_instance.send_message(chat_id, "Сессия завершена или не найдена")
                return

            session = quiz_sessions[session_id]

            if session['current_index'] >= len(session['card_ids']):
                # Сессия завершена
                finish_quiz_session(bot_instance, chat_id, session_id)
                return

            current_card_id = session['card_ids'][session['current_index']]
            session['current_card_id'] = current_card_id

            with with_connection() as conn:
                card = CardUtils.get_card_by_id(conn, current_card_id)

                if not card:
                    session['current_index'] += 1
                    show_next_card(bot_instance, chat_id, session_id)
                    return

            card_number = session['current_index'] + 1
            total_cards = len(session['card_ids'])

            text = (f"*Карточка {card_number}/{total_cards}*\n\n*Вопрос:*\n`{card['front']}`\n\n"
                    f"Категория: *{card.get('category_name', 'Без категории')}*\nСложность: {'⭐' * card['difficulty']}\n\n"
                    f"Напишите ответ или нажмите кнопку:")

            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)

            btn_show = types.KeyboardButton('Показать ответ')
            btn_skip = types.KeyboardButton('Пропустить')
            btn_stop = types.KeyboardButton('Завершить')

            markup.add(btn_show, btn_skip, btn_stop)

            inline_markup = types.InlineKeyboardMarkup()
            btn_hint = types.InlineKeyboardButton('Подсказка', callback_data=f'hint_{session_id}')
            btn_difficult = types.InlineKeyboardButton('Сложная карточка',
                                                       callback_data=f'mark_difficult_{session_id}')

            inline_markup.add(btn_hint, btn_difficult)

            bot_instance.send_message(chat_id, text, parse_mode='Markdown', reply_markup=markup)

            bot_instance.send_message(chat_id, "*Дополнительные действия:*",
                                      parse_mode='Markdown', reply_markup=inline_markup)

            bot_instance.register_next_step_handler_by_chat_id(chat_id, process_user_answer, bot_instance, session_id)

        except Exception as e:
            logger.error(f"Error in show_next_card: {e}")
            bot_instance.send_message(chat_id, "Ошибка при показе карточки")

# Обработка ответа пользователя
    def process_user_answer(message, bot_instance, session_id):
        try:
            if session_id not in quiz_sessions:
                bot_instance.send_message(message.chat.id, "Сессия завершена")
                return

            session = quiz_sessions[session_id]
            user_id = message.from_user.id
            user_answer = message.text.strip()

            if user_answer == 'Показать ответ':
                show_answer(bot_instance, message.chat.id, session_id, was_shown=True)
                return
            elif user_answer == 'Пропустить':
                skip_card(bot_instance, message.chat.id, session_id)
                return
            elif user_answer == 'Завершить':
                finish_quiz_session(bot_instance, message.chat.id, session_id)
                return

            with with_connection() as conn:
                card = CardUtils.get_card_by_id(conn, session['current_card_id'])

                if not card:
                    bot_instance.send_message(message.chat.id, "Ошибка: карточка не найдена")
                    return

                correct_answer = card['back'].lower().strip()
                user_answer_clean = user_answer.lower().strip()

                is_correct = user_answer_clean == correct_answer

                CardUtils.update_card_after_review(
                    conn, session['current_card_id'], is_correct
                )

                if is_correct:
                    session['correct_answers'] += 1
                else:
                    session['wrong_answers'] += 1

            show_answer_result(
                bot_instance, message.chat.id, session_id,
                is_correct, user_answer, card['back']
            )

        except Exception as e:
            logger.error(f"Error in process_user_answer: {e}")
            bot_instance.send_message(message.chat.id, "Ошибка при обработке ответа")

# Показать правильный ответ
    def show_answer(bot_instance, chat_id, session_id, was_shown=False):
        try:
            if session_id not in quiz_sessions:
                return

            session = quiz_sessions[session_id]

            with with_connection() as conn:
                card = CardUtils.get_card_by_id(conn, session['current_card_id'])

                if not card:
                    return

            text = (f"*Правильный ответ:*\n\n`{card['back']}`\n\n"
                    f"*Объяснение:* {card.get('explanation', 'Нет дополнительного объяснения')}\n\n"
                    f"Статус: {"Изучено" if card['status'] == 'learned' else "Изучается"}\n"
                    f"Следующее повторение: *{card['next_review'][:10] if card['next_review'] else 'скоро'}*")

            markup = types.InlineKeyboardMarkup(row_width=2)

            if was_shown:
                btn_remember = types.InlineKeyboardButton('Запомнил', callback_data=f'remember_{session_id}')
                btn_forgot = types.InlineKeyboardButton('Не запомнил', callback_data=f'forgot_{session_id}')
                markup.add(btn_remember, btn_forgot)
            else:
                btn_next = types.InlineKeyboardButton('Далее', callback_data=f'next_card_{session_id}')
                markup.add(btn_next)

            bot_instance.send_message(chat_id, text, parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in show_answer: {e}")

# Показать результат ответа
    def show_answer_result(bot_instance, chat_id, session_id, is_correct, user_answer, correct_answer):
        try:
            if is_correct:
                text = f"*Правильно!*\n\nВаш ответ: `{user_answer}`\nПравильный ответ: `{correct_answer}`"
                emoji = "✅"
            else:
                text = f"*Неправильно*\n\nВаш ответ: `{user_answer}`\nПравильный ответ: `{correct_answer}`"
                emoji = "❌"

            markup = types.InlineKeyboardMarkup()
            btn_next = types.InlineKeyboardButton(f'{emoji} Далее', callback_data=f'next_card_{session_id}')
            markup.add(btn_next)

            bot_instance.send_message(chat_id, text, parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in show_answer_result: {e}")

# Пропустить текущую карточку
    def skip_card(bot_instance, chat_id, session_id):
        try:
            if session_id not in quiz_sessions:
                return

            session = quiz_sessions[session_id]

            session['current_index'] += 1

            remove_keyboard = types.ReplyKeyboardRemove()
            bot_instance.send_message(chat_id, "Карточка пропущена", reply_markup=remove_keyboard)

            show_next_card(bot_instance, chat_id, session_id)

        except Exception as e:
            logger.error(f"Error in skip_card: {e}")

# Переход к следующей карточке
    @bot.callback_query_handler(func=lambda call: call.data.startswith('next_card_'))
    def next_card_callback(call):
        try:
            session_id = call.data.replace('next_card_', '')

            if session_id not in quiz_sessions:
                bot.answer_callback_query(call.id, "Сессия завершена")
                return

            session = quiz_sessions[session_id]
            session['current_index'] += 1

            remove_keyboard = types.ReplyKeyboardRemove()
            bot.send_message(call.message.chat.id, "", reply_markup=remove_keyboard)

            show_next_card(bot, call.message.chat.id, session_id)
            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in next_card_callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Пользователь запомнил карточку (после показа ответа)
    @bot.callback_query_handler(func=lambda call: call.data.startswith('remember_'))
    def remember_card_callback(call):
        try:
            session_id = call.data.replace('remember_', '')

            if session_id not in quiz_sessions:
                bot.answer_callback_query(call.id, "Сессия завершена")
                return

            session = quiz_sessions[session_id]

            with with_connection() as conn:
                CardUtils.update_card_after_review(
                    conn, session['current_card_id'], True
                )
                session['correct_answers'] += 1

            session['current_index'] += 1
            remove_keyboard = types.ReplyKeyboardRemove()
            bot.send_message(call.message.chat.id, "", reply_markup=remove_keyboard)

            show_next_card(bot, call.message.chat.id, session_id)
            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in remember_card_callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Пользователь не запомнил карточку (после показа ответа)
    @bot.callback_query_handler(func=lambda call: call.data.startswith('forgot_'))
    def forgot_card_callback(call):
        try:
            session_id = call.data.replace('forgot_', '')

            if session_id not in quiz_sessions:
                bot.answer_callback_query(call.id, "Сессия завершена")
                return

            session = quiz_sessions[session_id]

            with with_connection() as conn:
                CardUtils.update_card_after_review(
                    conn, session['current_card_id'], False
                )
                session['wrong_answers'] += 1

            session['current_index'] += 1
            remove_keyboard = types.ReplyKeyboardRemove()
            bot.send_message(call.message.chat.id, "", reply_markup=remove_keyboard)

            show_next_card(bot, call.message.chat.id, session_id)
            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in forgot_card_callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

# Завершение сессии тестирования
    def finish_quiz_session(bot_instance, chat_id, session_id):
        try:
            if session_id not in quiz_sessions:
                bot_instance.send_message(chat_id, "Сессия не найдена")
                return

            session = quiz_sessions[session_id]
            user_id = session['user_id']

            total_answered = session['correct_answers'] + session['wrong_answers']
            total_cards = len(session['card_ids'])

            if total_answered > 0:
                accuracy = (session['correct_answers'] / total_answered) * 100
            else:
                accuracy = 0

            duration = (datetime.now() - session['start_time']).total_seconds()
            minutes = int(duration // 60)
            seconds = int(duration % 60)

            text = (f"*Сессия завершена!*\n\n*Результаты:*\n• Карточек в сессии: {total_cards}\n"
                    f"• Отвечено: {total_answered}\n• Правильно: {session['correct_answers']}\n"
                    f"• Ошибок: {session['wrong_answers']}\n• Точность: {accuracy:.1f}%\n"
                    f"• Время: {minutes} мин {seconds} сек\n\n*Рекомендации:*")

            if accuracy >= 80:
                text += "Отличный результат! Вы хорошо знаете материал."
            elif accuracy >= 60:
                text += "Хороший результат! Продолжайте практиковаться."
            else:
                text += "Нужно больше практики. Попробуйте повторить сложные карточки."

            with with_connection() as conn:
                cursor = conn.execute('''
                                      INSERT INTO study_sessions
                                      (user_id, cards_studied, correct_answers, wrong_answers, session_duration,
                                       session_type)
                                      VALUES (?, ?, ?, ?, ?, ?)
                                      ''', (user_id, total_answered, session['correct_answers'],
                                            session['wrong_answers'], duration, session['session_type']))

                conn.execute('''
                             UPDATE user_stats
                             SET total_sessions   = total_sessions + 1,
                                 total_study_time = total_study_time + ?,
                                 correct_answers  = correct_answers + ?,
                                 wrong_answers    = wrong_answers + ?,
                                 updated_at       = CURRENT_TIMESTAMP
                             WHERE user_id = ?
                             ''', (duration, session['correct_answers'], session['wrong_answers'], user_id))

            markup = types.InlineKeyboardMarkup(row_width=2)

            btn_repeat = types.InlineKeyboardButton('Повторить сессию', callback_data='repeat_session')
            btn_new = types.InlineKeyboardButton('Новая сессия', callback_data='new_quiz_session')
            btn_difficult = types.InlineKeyboardButton('Сложные карточки', callback_data='review_difficult')
            btn_stats = types.InlineKeyboardButton('Статистика', callback_data='view_session_stats')
            btn_main = types.InlineKeyboardButton('Главное меню', callback_data='main_menu')

            markup.add(btn_repeat, btn_new, btn_difficult, btn_stats, btn_main)

            bot_instance.send_message(chat_id, text, parse_mode='Markdown', reply_markup=markup)

            if session_id in quiz_sessions:
                del quiz_sessions[session_id]

        except Exception as e:
            logger.error(f"Error in finish_quiz_session: {e}")
            bot_instance.send_message(chat_id, "Ошибка при завершении сессии")

# Показать карточки для повторения сегодня
    @bot.message_handler(commands=['today'])
    @bot.message_handler(func=lambda message: message.text in ['На сегодня', 'На сегодня'])
    def cards_for_today_command(message):
        try:
            user_id = message.from_user.id

            with with_connection() as conn:
                cards = CardUtils.get_cards_for_review(conn, user_id, limit=50)

                if not cards:
                    markup = types.InlineKeyboardMarkup()
                    btn_add = types.InlineKeyboardButton('Добавить карточки', callback_data='add_more_cards')
                    btn_review_all = types.InlineKeyboardButton('Повторить все', callback_data='review_all_cards')

                    markup.add(btn_add, btn_review_all)

                    bot.send_message(message.chat.id, "*Отличная работа!*\n\n"
                                                      "Сегодня нет карточек для повторения по системе\t"
                                                      "интервальных повторений.\n\nВы можете:\n"
                                                      "• Добавить новые карточки\n• Повторить все карточки\n"
                                                      "• Подождать до завтра",
                                     parse_mode='Markdown', reply_markup=markup)
                    return

                easy_cards = [c for c in cards if c['difficulty'] <= 2]
                medium_cards = [c for c in cards if 3 <= c['difficulty'] <= 4]
                hard_cards = [c for c in cards if c['difficulty'] == 5]

                text = (f"*Карточки на сегодня*\n\nВсего для повторения: *{len(cards)}*\n\n*По сложности:*\n"
                        f"• 🟢 Легкие: {len(easy_cards)}\n• 🟡 Средние: {len(medium_cards)}\n"
                        f"• 🔴 Сложные: {len(hard_cards)}\n\n*Примеры карточек:*")

                for i, card in enumerate(cards[:5], 1):
                    difficulty_emoji = "🟢" if card['difficulty'] <= 2 else "🟡" if card['difficulty'] <= 4 else "🔴"
                    text += f"{i}. {difficulty_emoji} {card['front'][:30]}...\n"

                markup = types.InlineKeyboardMarkup(row_width=2)

                btn_start = types.InlineKeyboardButton('Начать повторение', callback_data='start_review_session')
                btn_easy = types.InlineKeyboardButton('Только легкие', callback_data='review_easy_only')
                btn_hard = types.InlineKeyboardButton('Только сложные', callback_data='review_hard_only')
                btn_all = types.InlineKeyboardButton('Все карточки', callback_data='review_all_today')

                markup.add(btn_start, btn_easy, btn_hard, btn_all)

                bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in cards_for_today_command: {e}")
            bot.send_message(message.chat.id, "Ошибка при загрузке карточек")

# Повторение сложных карточек
    @bot.message_handler(commands=['review'])
    def review_difficult_command(message):
        try:
            user_id = message.from_user.id

            with with_connection() as conn:
                all_cards = CardUtils.get_user_cards(conn, user_id)

                if not all_cards:
                    bot.send_message(message.chat.id, "Нет карточек для повторения")
                    return

                difficult_cards = []
                for card in all_cards:
                    total_answers = card['correct_answers'] + card['wrong_answers']
                    if total_answers > 0:
                        success_rate = card['correct_answers'] / total_answers
                        if success_rate < 0.5:
                            difficult_cards.append(card)

                if not difficult_cards:
                    bot.send_message(message.chat.id,
                                     "*Отлично!*\n\nУ вас нет сложных карточек. Все карточки усвоены хорошо!")
                    return

                difficult_cards = difficult_cards[:20]
                card_ids = [card['id'] for card in difficult_cards]

                session_id = start_quiz_session(user_id, card_ids, 'difficult_review')

                if session_id:
                    show_next_card(bot, message.chat.id, session_id)
                else:
                    bot.send_message(message.chat.id, "Ошибка при запуске сессии")

        except Exception as e:
            logger.error(f"Error in review_difficult_command: {e}")
            bot.send_message(message.chat.id, "Ошибка")

# Статистика обучения
    @bot.message_handler(commands=['stats', 'progress'])
    def quiz_stats_command(message):
        try:
            user_id = message.from_user.id

            with with_connection() as conn:
                user_stats = UserUtils.get_user_stats(conn, user_id)

                cursor = conn.execute('''
                                      SELECT *
                                      FROM study_sessions
                                      WHERE user_id = ?
                                      ORDER BY created_at DESC LIMIT 5
                                      ''', (user_id,))

                recent_sessions = cursor.fetchall()

                due_cards = CardUtils.get_cards_for_review(conn, user_id, limit=100)

            if not user_stats:
                bot.send_message(message.chat.id, "Статистика недоступна")
                return

            total_answers = user_stats['correct_answers'] + user_stats['wrong_answers']
            accuracy = (user_stats['correct_answers'] / total_answers * 100) if total_answers > 0 else 0

            avg_session_time = (user_stats['total_study_time'] / user_stats['total_sessions']) \
                if user_stats['total_sessions'] > 0 else 0
            avg_minutes = int(avg_session_time // 60)

            text = (f"*Статистика обучения*\n\n*Общая статистика:*\n• Всего сессий: {user_stats['total_sessions']}\n"
                    f"• Общее время: {user_stats['total_study_time'] // 60} мин\n"
                    f"• Правильных ответов: {user_stats['correct_answers']}\n• Ошибок: {user_stats['wrong_answers']}\n"
                    f"• Точность: {accuracy:.1f}%\n• Средняя сессия: {avg_minutes} мин\n\n*Текущий статус:*\n"
                    f"• Карточек для повторения: {len(due_cards)}\n• Дней подряд: {user_stats['streak_days']}\n"
                    f"• Последнее занятие: {user_stats['last_study_date'] or 'никогда'}\n\n*Последние сессии:*")

            for i, session in enumerate(recent_sessions[:3], 1):
                session_date = session['created_at'][:10]
                session_accuracy = (session['correct_answers'] / (session['correct_answers'] + session['wrong_answers']) *
                                    100) if (session['correct_answers'] + session['wrong_answers']) > 0 else 0
                text += f"{i}. {session_date}: {session['cards_studied']} карт., {session_accuracy:.0f}%\n"

            # Создаем кнопки
            markup = types.InlineKeyboardMarkup(row_width=2)
            btn_today = types.InlineKeyboardButton('На сегодня', callback_data='view_today_stats')
            btn_sessions = types.InlineKeyboardButton('График прогресса', callback_data='view_progress_chart')
            btn_reset = types.InlineKeyboardButton('Сбросить прогресс', callback_data='reset_progress_confirm')

            markup.add(btn_today, btn_sessions, btn_reset)

            bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in quiz_stats_command: {e}")
            bot.send_message(message.chat.id, "Ошибка при загрузке статистики")

    logger.info("Quiz handlers registered successfully")
    return bot