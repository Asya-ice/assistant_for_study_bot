import logging
from telebot import types
from datetime import datetime, timedelta
from utils.db_utils import with_connection, CardUtils, CategoryUtils, UserUtils, ExportImportUtils

logger = logging.getLogger(__name__)

# Глобальный словарь для хранения состояний пользователей
user_sessions = {}


def register_cards_handlers(bot):

# Главное меню управления карточками
    @bot.message_handler(commands=['cards'])
    def cards_main_menu(message):
        try:
            user_id = message.from_user.id

            with with_connection() as conn:
                # Получаем статистику
                stats = UserUtils.get_user_stats(conn, user_id)
                total_cards = len(CardUtils.get_user_cards(conn, user_id))

                # Получаем карточки для повторения сегодня
                due_cards = len(CardUtils.get_cards_for_review(conn, user_id))

            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            btn_my_cards = types.KeyboardButton('Мои карточки')
            btn_add_card = types.KeyboardButton('Новая карточка')
            btn_search = types.KeyboardButton('Поиск')
            btn_today = types.KeyboardButton('На сегодня')
            btn_stats = types.KeyboardButton('Статистика')
            btn_back = types.KeyboardButton('Назад')
            markup.add(btn_my_cards, btn_add_card, btn_search, btn_today, btn_stats, btn_back)

            text = (f"*Управление карточками*\n\nВаша статистика:\n• Всего карточек: *{total_cards}*\n"
                    f"• Для повторения сегодня: *{due_cards}*\n\n*Выберите действие:*")

            inline_markup = types.InlineKeyboardMarkup(row_width=2)
            btn_quick_add = types.InlineKeyboardButton('Быстро добавить', callback_data='quick_add')
            btn_import = types.InlineKeyboardButton('Импорт', callback_data='import_cards')
            btn_export = types.InlineKeyboardButton('Экспорт', callback_data='export_cards')
            btn_manage = types.InlineKeyboardButton('Управление', callback_data='manage_cards')
            inline_markup.add(btn_quick_add, btn_import, btn_export, btn_manage)

            bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)
            bot.send_message(message.chat.id,"*Быстрые действия:*", parse_mode='Markdown', reply_markup=inline_markup)

        except Exception as e:
            logger.error(f"Error in cards_main_menu: {e}")
            bot.send_message(message.chat.id, "Ошибка при загрузке меню")

# Начало процесса добавления карточки
    @bot.message_handler(commands=['add_card'])
    @bot.message_handler(func=lambda message: message.text in ['➕ Новая карточка', '➕ Добавить карточку'])
    def add_card_start(message):
        try:
            user_id = message.from_user.id

            with with_connection() as conn:
                categories = CategoryUtils.get_user_categories(conn, user_id)

                if not categories:
                    # Если категорий нет, создаем дефолтную
                    category_id = CategoryUtils.create_category(conn, user_id, "Общее", "Основная категория")
                    categories = CategoryUtils.get_user_categories(conn, user_id)

            # Сохраняем состояние пользователя
            user_sessions[user_id] = {'step': 'waiting_category', 'data': {}}

            # Создаем инлайн-клавиатуру с категориями
            markup = types.InlineKeyboardMarkup(row_width=2)

            for category in categories[:10]:  # Показываем первые 10
                btn = types.InlineKeyboardButton(
                    f"📁 {category['name']}",
                    callback_data=f"add_card_category_{category['id']}"
                )
                markup.add(btn)

            if len(categories) > 10:
                btn_more = types.InlineKeyboardButton('Еще категории...', callback_data='more_categories')
                markup.add(btn_more)

            btn_new = types.InlineKeyboardButton('Новая категория', callback_data='new_category_for_card')
            btn_cancel = types.InlineKeyboardButton('Отмена', callback_data='cancel_add_card')
            markup.add(btn_new, btn_cancel)

            bot.send_message(message.chat.id, "*Создание новой карточки*\n\n*Шаг 1/3:* Выберите категорию:",
                             parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in add_card_start: {e}")
            bot.send_message(message.chat.id, "Ошибка при создании карточки")

# Выбор категории для новой карточки
    @bot.callback_query_handler(func=lambda call: call.data.startswith('add_card_category_'))
    def select_category_for_card(call):
        try:
            user_id = call.from_user.id
            category_id = call.data.replace('add_card_category_', '')

            with with_connection() as conn:
                category = CategoryUtils.get_category_by_id(conn, category_id)

            if not category:
                bot.answer_callback_query(call.id, "Категория не найдена")
                return

            # Сохраняем категорию в сессии
            if user_id not in user_sessions:
                user_sessions[user_id] = {'data': {}}

            user_sessions[user_id]['data']['category_id'] = category_id
            user_sessions[user_id]['data']['category_name'] = category['name']
            user_sessions[user_id]['step'] = 'waiting_front'

            bot.delete_message(call.message.chat.id, call.message.message_id)

            msg = bot.send_message(call.message.chat.id, f"*Создание карточки*\n\n"
                                                         f"*Шаг 2/3:* Введите *вопрос* или *слово*:\n"
                                                         f"Категория: *{category['name']}*\n\n"
                                                         f"*Примеры:*\n• Apple\n• Столица Франции\n• Что такое API?",
                                   parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_front_side)
            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in select_category_for_card: {e}")
            bot.answer_callback_query(call.id, "Ошибка при выборе категории")

# Обработка лицевой стороны карточки
    def process_front_side(message):
        try:
            user_id = message.from_user.id
            front_text = message.text.strip()

            if not front_text:
                msg = bot.send_message(message.chat.id, "Текст не может быть пустым. Введите вопрос:")
                bot.register_next_step_handler(msg, process_front_side)
                return

            if len(front_text) > 500:
                msg = bot.send_message(message.chat.id, "Слишком длинный текст (макс. 500 символов). Введите короче:")
                bot.register_next_step_handler(msg, process_front_side)
                return

            # Сохраняем лицевую сторону
            if user_id not in user_sessions:
                user_sessions[user_id] = {'data': {}}

            user_sessions[user_id]['data']['front'] = front_text
            user_sessions[user_id]['step'] = 'waiting_back'

            msg = bot.send_message(message.chat.id, f"*Создание карточки*\n\n"
                                                    f"*Шаг 3/3:* Введите *ответ* или *определение*:\n"
                                                    f"Вопрос: *{front_text}*\n\n"
                                                    f"*Примеры:*\n• Яблоко\n• Париж\n• Application Programming Interface",
                                   parse_mode='Markdown')

            bot.register_next_step_handler(msg, process_back_side)

        except Exception as e:
            logger.error(f"Error in process_front_side: {e}")
            bot.send_message(message.chat.id, "Ошибка при вводе вопроса")

# Обработка обратной стороны и сохранение карточки
    def process_back_side(message):
        try:
            user_id = message.from_user.id
            back_text = message.text.strip()

            if not back_text:
                msg = bot.send_message(message.chat.id, "Текст не может быть пустым. Введите ответ:")
                bot.register_next_step_handler(msg, process_back_side)
                return

            if len(back_text) > 1000:
                msg = bot.send_message(
                    message.chat.id,
                    "Слишком длинный текст (макс. 1000 символов). Введите короче:"
                )
                bot.register_next_step_handler(msg, process_back_side)
                return

            # Проверяем данные сессии
            if (user_id not in user_sessions or
                    'data' not in user_sessions[user_id] or
                    'front' not in user_sessions[user_id]['data'] or
                    'category_id' not in user_sessions[user_id]['data']):
                bot.send_message(
                    message.chat.id,
                    "Сессия устарела. Начните заново с /add_card"
                )
                return

            session_data = user_sessions[user_id]['data']

            with with_connection() as conn:
                # Сохраняем карточку в БД
                card_id = CardUtils.create_card(conn, user_id=user_id, front=session_data['front'], back=back_text,
                                                category_id=session_data['category_id'])

                if card_id:
                    # Очищаем сессию
                    if user_id in user_sessions:
                        del user_sessions[user_id]

                    markup = types.InlineKeyboardMarkup(row_width=2)
                    btn_add_more = types.InlineKeyboardButton('Еще карточку', callback_data='add_another_card')
                    btn_view = types.InlineKeyboardButton('Посмотреть', callback_data=f'view_card_{card_id}')
                    btn_edit = types.InlineKeyboardButton('Редактировать', callback_data=f'edit_card_{card_id}')

                    markup.add(btn_add_more, btn_view, btn_edit)

                    bot.send_message(message.chat.id, f"*Карточка создана!*\n\n*ID:* #{card_id}\n"
                                                      f"*Категория:* {session_data.get('category_name', 'Неизвестно')}\n"
                                                      f"*Вопрос:* {session_data['front']}\n*Ответ:* {back_text}\n\n"
                                                      f"Карточка добавлена в систему повторений.",
                                     parse_mode='Markdown', reply_markup=markup)
                else:
                    bot.send_message(message.chat.id, "Ошибка при сохранении карточки")

        except Exception as e:
            logger.error(f"Error in process_back_side: {e}")
            bot.send_message(message.chat.id, "Ошибка при создании карточки")

# Просмотр списка карточек с пагинацией
    @bot.message_handler(commands=['mycards', 'cards_list'])
    @bot.message_handler(func=lambda message: message.text in ['📚 Мои карточки', '👁️ Мои карточки'])
    def view_cards_list(message, page=1):
        try:
            user_id = message.from_user.id
            page_size = 10

            with with_connection() as conn:
                # Получаем карточки для текущей страницы
                offset = (page - 1) * page_size
                cards = CardUtils.get_user_cards(
                    conn, user_id, limit=page_size, offset=offset
                )

                total_cards = len(CardUtils.get_user_cards(conn, user_id))
                total_pages = (total_cards + page_size - 1) // page_size

            if not cards:
                markup = types.InlineKeyboardMarkup()
                btn_add = types.InlineKeyboardButton('Добавить первую карточку', callback_data='add_first_card')
                markup.add(btn_add)

                bot.send_message(message.chat.id,"*У вас пока нет карточек.*\n\n"
                                                 "Создайте свою первую карточку для начала обучения!",
                                 parse_mode='Markdown', reply_markup=markup)
                return

            # Формируем текст
            text = f"*Ваши карточки* (страница {page}/{total_pages})\n\n"

            for i, card in enumerate(cards, start=1):
                status_emoji = "🎯" if card['status'] == 'learning' else "✅"
                front_preview = card['front'][:30] + "..." if len(card['front']) > 30 else card['front']
                text += f"{i}. {status_emoji} *{front_preview}*\n"

            text += f"\nВсего карточек: *{total_cards}*"

            # Создаем инлайн-клавиатуру
            markup = types.InlineKeyboardMarkup(row_width=4)

            # Кнопки пагинации
            if page > 1:
                btn_prev = types.InlineKeyboardButton('◀️', callback_data=f'cards_page_{page - 1}')
                markup.add(btn_prev)

            if page < total_pages:
                btn_next = types.InlineKeyboardButton('▶️', callback_data=f'cards_page_{page + 1}')
                if page > 1:
                    markup.add(btn_next)
                else:
                    markup.add(btn_next)

            btn_view_all = types.InlineKeyboardButton('Просмотреть все', callback_data='view_all_cards')
            btn_search = types.InlineKeyboardButton('Поиск', callback_data='search_cards')
            btn_export = types.InlineKeyboardButton('Экспорт', callback_data='export_all_cards')

            markup.add(btn_view_all, btn_search, btn_export)

            bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in view_cards_list: {e}")
            bot.send_message(message.chat.id, "Ошибка при загрузке карточек")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('cards_page_'))
    def cards_page_callback(call):
        try:
            page = int(call.data.replace('cards_page_', ''))
            view_cards_list(call.message, page)
            bot.answer_callback_query(call.id)
        except Exception as e:
            logger.error(f"Error in cards_page_callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка при переключении страницы")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('view_card_'))
    def view_card_detail(call):
        try:
            card_id = call.data.replace('view_card_', '')

            with with_connection() as conn:
                card = CardUtils.get_card_by_id(conn, card_id)
                if not card:
                    bot.answer_callback_query(call.id, "Карточка не найдена")
                    return

                # Форматируем дату
                created_at = datetime.strptime(
                    card['created_at'], "%Y-%m-%d %H:%M:%S"
                ).strftime("%d.%m.%Y в %H:%M")

                if card['last_reviewed']:
                    last_reviewed = datetime.strptime(
                        card['last_reviewed'], "%Y-%m-%d %H:%M:%S"
                    ).strftime("%d.%m.%Y")
                else:
                    last_reviewed = "никогда"

                text = (f"*Карточка #{card['id']}*\n\n*Вопрос:*\n`{card['front']}`\n\n*Ответ:*\n`{card['back']}`\n\n"
                        f"*Информация:*\n• Категория: {card.get('category_name', 'Неизвестно')}\n"
                        f"• Статус: {"Изучается" if card['status'] == 'learning' else "Изучено"}\n"
                        f"• Сложность: {'⭐' * card['difficulty']}\n• Повторений: {card['review_count']}\n"
                        f"• Правильно: {card['correct_answers']}/{card['review_count'] if card['review_count'] > 0 else 1}\n"
                        f"• Создана: {created_at}\n• Последнее повторение: {last_reviewed}")

                markup = types.InlineKeyboardMarkup(row_width=2)

                btn_edit = types.InlineKeyboardButton('Редактировать', callback_data=f'edit_card_{card_id}')
                btn_delete = types.InlineKeyboardButton('Удалить', callback_data=f'delete_card_confirm_{card_id}')
                btn_toggle = types.InlineKeyboardButton('Сменить статус', callback_data=f'toggle_card_status_{card_id}')
                btn_review = types.InlineKeyboardButton('Повторить', callback_data=f'review_card_{card_id}')
                btn_back = types.InlineKeyboardButton('Назад к списку', callback_data='back_to_cards_list')
                markup.add(btn_edit, btn_delete, btn_toggle, btn_review, btn_back)
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown',
                                      reply_markup=markup)
                bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in view_card_detail: {e}")
            bot.answer_callback_query(call.id, "Ошибка при загрузке карточки")

    @bot.message_handler(commands=['quickadd'])
    def quick_add_command(message):
        try:
            msg = bot.send_message(message.chat.id, "*Быстрое добавление карточки*\n\n"
                                                    "Введите карточку в формате:\n`Вопрос - Ответ`\n\n"
                                                    "*Примеры:*\n`Apple - Яблоко`\n`Столица Франции - Париж`\n"
                                                    "`Что такое API? - Application Programming Interface`",
                                   parse_mode='Markdown')

            bot.register_next_step_handler(msg, process_quick_add)

        except Exception as e:
            logger.error(f"Error in quick_add_command: {e}")
            bot.send_message(message.chat.id, "Ошибка при быстром добавлении")

    def process_quick_add(message):
        try:
            text = message.text.strip()

            if '-' not in text:
                msg = bot.send_message(message.chat.id,"Неверный формат. Используйте: `Вопрос - Ответ`\n"
                                                       "Попробуйте еще раз:",parse_mode='Markdown')
                bot.register_next_step_handler(msg, process_quick_add)
                return

            parts = text.split('-', 1)  # Разделяем только по первому дефису
            front = parts[0].strip()
            back = parts[1].strip()

            if not front or not back:
                msg = bot.send_message(message.chat.id, "Вопрос и ответ не могут быть пустыми. Попробуйте еще раз:",
                                       parse_mode='Markdown')
                bot.register_next_step_handler(msg, process_quick_add)
                return

            user_id = message.from_user.id

            with with_connection() as conn:
                # Получаем или создаем категорию "По умолчанию"
                categories = CategoryUtils.get_user_categories(conn, user_id)
                quick_category = next((c for c in categories if c['name'] == 'По умолчанию'), None)

                if not quick_category:
                    category_id = CategoryUtils.create_category(conn, user_id, "По умолчанию",
                                                                "Автоматически созданные карточки")
                else:
                    category_id = quick_category['id']

                # Сохраняем карточку
                card_id = CardUtils.create_card(conn, user_id, front, back, category_id)

                if card_id:
                    bot.send_message(message.chat.id, f"*Карточка добавлена!*\n\n*Вопрос:* {front}\n"
                                                      f"*Ответ:* {back}\n*Категория:* Быстрые\n\n"
                                                      f"Используйте /mycards для просмотра", parse_mode='Markdown')
                else:
                    bot.send_message(message.chat.id, "Ошибка при сохранении")

        except Exception as e:
            logger.error(f"Error in process_quick_add: {e}")
            bot.send_message(message.chat.id, "Ошибка при добавлении карточки")

#Поиск карточек
    @bot.message_handler(commands=['search'])
    @bot.message_handler(func=lambda message: message.text in ['Поиск', 'Поиск карточек'])
    def search_cards_command(message):
        try:
            msg = bot.send_message(message.chat.id, "*Поиск карточек*\n\nВведите слово или фразу для поиска:\n\n"
                                                    "*Примеры:*\n• `apple` - найдет все карточки с этим словом\n"
                                                    "• `програм` - найдет 'программирование', 'программа' и т.д.",
                                   parse_mode='Markdown')

            bot.register_next_step_handler(msg, process_search)

        except Exception as e:
            logger.error(f"Error in search_cards_command: {e}")
            bot.send_message(message.chat.id, "Ошибка при поиске")

    def process_search(message):
        try:
            user_id = message.from_user.id
            query = message.text.strip()

            if not query or len(query) < 2:
                bot.send_message(message.chat.id, "Поисковый запрос должен содержать минимум 2 символа")
                return

            with with_connection() as conn:
                results = CardUtils.search_cards(conn, user_id, query)

                if not results:
                    bot.send_message(message.chat.id, f"По запросу \"{query}\" ничего не найдено")
                    return

                # Группируем результаты по категориям
                categories = {}
                for card in results:
                    cat_name = card.get('category_name', 'Без категории')
                    if cat_name not in categories:
                        categories[cat_name] = []
                    categories[cat_name].append(card)

                text = f"*Результаты поиска:* \"{query}\"\n\n"
                text += f"Найдено карточек: *{len(results)}*\n\n"

                for cat_name, cards in categories.items():
                    text += f"*{cat_name}:* {len(cards)} карточек\n"

                # Создаем кнопки для просмотра результатов
                markup = types.InlineKeyboardMarkup(row_width=1)

                for i, card in enumerate(results[:5]):  # Показываем первые 5
                    btn_text = f"{card['front'][:20]}... → {card['back'][:20]}..."
                    btn = types.InlineKeyboardButton(btn_text, callback_data=f"view_card_{card['id']}")
                    markup.add(btn)

                if len(results) > 5:
                    btn_more = types.InlineKeyboardButton(f"📖 Показать все ({len(results)})",
                                                          callback_data=f"search_all_{query}")
                    markup.add(btn_more)

                bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in process_search: {e}")
            bot.send_message(message.chat.id, "Ошибка при поиске")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('delete_card_confirm_'))
    def delete_card_confirm(call):
        try:
            card_id = call.data.replace('delete_card_confirm_', '')

            markup = types.InlineKeyboardMarkup()
            btn_confirm = types.InlineKeyboardButton('Да, удалить', callback_data=f'delete_card_{card_id}')
            btn_cancel = types.InlineKeyboardButton('Нет, отмена', callback_data=f'view_card_{card_id}')

            markup.add(btn_confirm, btn_cancel)

            bot.edit_message_text("*Удаление карточки*\n\nВы уверены, что хотите удалить эту карточку?",
                                  call.message.chat.id, call.message.message_id, parse_mode='Markdown',
                                  reply_markup=markup)

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in delete_card_confirm: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('delete_card_'))
    def delete_card_execute(call):
        try:
            card_id = call.data.replace('delete_card_', '')

            with with_connection() as conn:
                success = CardUtils.delete_card(conn, card_id)

                if success:
                    bot.edit_message_text(
                        "Карточка успешно удалена",
                        call.message.chat.id,
                        call.message.message_id
                    )
                else:
                    bot.edit_message_text(
                        "Ошибка при удалении карточки",
                        call.message.chat.id,
                        call.message.message_id
                    )

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in delete_card_execute: {e}")
            bot.answer_callback_query(call.id, "Ошибка при удалении")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('toggle_card_status_'))
    def toggle_card_status(call):
        try:
            card_id = call.data.replace('toggle_card_status_', '')

            with with_connection() as conn:
                card = CardUtils.get_card_by_id(conn, card_id)

                if not card:
                    bot.answer_callback_query(call.id, "Карточка не найдена")
                    return

                new_status = 'learned' if card['status'] == 'learning' else 'learning'
                success = CardUtils.update_card(conn, card_id, status=new_status)

                if success:
                    # Обновляем сообщение
                    view_card_detail(call)
                    bot.answer_callback_query(
                        call.id,
                        f"Статус изменен на: {'Изучено' if new_status == 'learned' else 'Изучается'}"
                    )
                else:
                    bot.answer_callback_query(call.id, "Ошибка при изменении статуса")

        except Exception as e:
            logger.error(f"Error in toggle_card_status: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('edit_card_'))
    def edit_card_start(call):
        try:
            card_id = call.data.replace('edit_card_', '')
            user_id = call.from_user.id

            # Сохраняем в сессии
            user_sessions[user_id] = {'step': 'editing_card', 'data': {'card_id': card_id}}

            markup = types.InlineKeyboardMarkup(row_width=2)
            btn_edit_front = types.InlineKeyboardButton('Вопрос', callback_data=f'edit_card_front_{card_id}')
            btn_edit_back = types.InlineKeyboardButton('Ответ', callback_data=f'edit_card_back_{card_id}')
            btn_edit_category = types.InlineKeyboardButton('Категория', callback_data=f'edit_card_category_{card_id}')
            btn_cancel = types.InlineKeyboardButton('Отмена', callback_data=f'view_card_{card_id}')

            markup.add(btn_edit_front, btn_edit_back, btn_edit_category, btn_cancel)

            bot.edit_message_text("*Редактирование карточки*\n\nЧто вы хотите изменить?", call.message.chat.id,
                                  call.message.message_id, parse_mode='Markdown', reply_markup=markup)

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in edit_card_start: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('edit_card_front_'))
    def edit_card_front(call):
        try:
            card_id = call.data.replace('edit_card_front_', '')
            user_id = call.from_user.id

            # Сохраняем в сессии
            if user_id not in user_sessions:
                user_sessions[user_id] = {'data': {}}

            user_sessions[user_id]['data']['card_id'] = card_id
            user_sessions[user_id]['step'] = 'editing_front'

            msg = bot.send_message(call.message.chat.id, "*Редактирование вопроса*\n\nВведите новый текст вопроса:",
                                   parse_mode='Markdown')

            bot.register_next_step_handler(msg, process_edit_front)
            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in edit_card_front: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

    def process_edit_front(message):
        try:
            user_id = message.from_user.id
            new_front = message.text.strip()

            if not new_front:
                msg = bot.send_message(message.chat.id, "Вопрос не может быть пустым. Попробуйте еще раз:")
                bot.register_next_step_handler(msg, process_edit_front)
                return

            if user_id not in user_sessions or 'card_id' not in user_sessions[user_id]['data']:
                bot.send_message(message.chat.id, "Сессия устарела")
                return

            card_id = user_sessions[user_id]['data']['card_id']

            with with_connection() as conn:
                success = CardUtils.update_card(conn, card_id, front=new_front)

                if success:
                    # Очищаем сессию
                    if user_id in user_sessions:
                        del user_sessions[user_id]

                    # Показываем обновленную карточку
                    markup = types.InlineKeyboardMarkup()
                    btn_view = types.InlineKeyboardButton('Посмотреть', callback_data=f'view_card_{card_id}')
                    markup.add(btn_view)

                    bot.send_message(message.chat.id, "Вопрос успешно обновлен!", reply_markup=markup)
                else:
                    bot.send_message(message.chat.id, "Ошибка при обновлении")

        except Exception as e:
            logger.error(f"Error in process_edit_front: {e}")
            bot.send_message(message.chat.id, "Ошибка")

    # Показать карточки на сегодня
    @bot.message_handler(commands=['today'])
    @bot.message_handler(func=lambda message: message.text in ['На сегодня', 'На сегодня'])
    def cards_for_today(message):
        try:
            user_id = message.from_user.id

            with with_connection() as conn:
                cards = CardUtils.get_cards_for_review(conn, user_id, limit=20)

                if not cards:
                    bot.send_message(message.chat.id, "*Отличная работа!*\n\n"
                                                      "Сегодня нет карточек для повторения.\t"
                                                      "Вы успешно изучили все запланированные карточки!\n\n"
                                                      "Добавьте новые карточки или вернитесь завтра.",
                                     parse_mode='Markdown')
                    return

                text = f"*Карточки на сегодня*\n\n"
                text += f"Карточек для повторения: *{len(cards)}*\n\n"

                for i, card in enumerate(cards, start=1):
                    text += f"{i}. *{card['front'][:30]}...*\n"
                    text += f"   Сложность: {'⭐' * card['difficulty']}\n"
                    text += f"   Повторений: {card['review_count']}\n\n"

                # Кнопка для начала повторения
                markup = types.InlineKeyboardMarkup()
                btn_start = types.InlineKeyboardButton('Начать повторение', callback_data='start_today_review')
                markup.add(btn_start)

                bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in cards_for_today: {e}")
            bot.send_message(message.chat.id, "Ошибка при загрузке карточек")

# Начать тестирование на сегодня
    @bot.callback_query_handler(func=lambda call: call.data == 'start_today_review')
    def start_today_review(call):
        try:
            from handlers.quiz import start_review_session
            start_review_session(call)
            bot.answer_callback_query(call.id)
        except Exception as e:
            logger.error(f"Error in start_today_review: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

    logger.info("Cards handlers registered successfully")
    return bot