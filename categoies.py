import logging
from telebot import types
from datetime import datetime
from database import with_connection, CategoryUtils, CardUtils, UserUtils


logger = logging.getLogger(__name__)

# Словарь для хранения временных данных пользователей
user_sessions = {}


def register_categories_handlers(bot):

    @bot.message_handler(commands=['categories'])
    def categories_main_menu(message):
        try:
            user_id = message.from_user.id

            with with_connection() as conn:
                categories = CategoryUtils.get_user_categories(conn, user_id)

                # Статистика по категориям
                category_stats = []
                for category in categories:
                    cards = CardUtils.get_user_cards(conn, user_id, category_id=category['id'])
                    learned = len([c for c in cards if c['status'] == 'learned'])
                    category_stats.append({'name': category['name'], 'total': len(cards), 'learned': learned,
                                           'id': category['id']})

            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

            btn_create = types.KeyboardButton('Создать категорию')
            btn_view = types.KeyboardButton('Мои категории')
            btn_edit = types.KeyboardButton('Редактировать')
            btn_delete = types.KeyboardButton('Удалить')
            btn_stats = types.KeyboardButton('Статистика')
            btn_back = types.KeyboardButton('Назад')

            markup.add(btn_create, btn_view, btn_edit, btn_delete, btn_stats, btn_back)

            text = f"*Управление категориями*\n\nВсего категорий: *{len(categories)}*"

            if category_stats:
                text += "\n*Ваши категории:*\n"
                for i, stat in enumerate(category_stats[:5], 1):
                    progress = (stat['learned'] / stat['total']) * 100 if stat['total'] > 0 else 0
                    text += f"{i}. *{stat['name']}*: {stat['learned']}/{stat['total']} ({progress:.0f}%)\n"

                if len(category_stats) > 5:
                    text += f"... и еще *{len(category_stats) - 5}*\n"

            text += "\nИспользуйте кнопки ниже для управления."

            bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in categories_main_menu: {e}")
            bot.send_message(message.chat.id, "Ошибка при загрузке категорий")

    @bot.message_handler(commands=['create_category'])
    @bot.message_handler(func=lambda message: message.text in ['Создать категорию', 'Новая категория'])
    def create_category_start(message):
        try:
            user_id = message.from_user.id

            # Сохраняем состояние
            user_sessions[user_id] = {'step': 'waiting_category_name', 'data': {}}

            msg = bot.send_message(message.chat.id, "*Создание новой категории*\n\n"
                                                    "Введите название для новой категории:\n\n*Примеры:*\n"
                                                    "• Английские слова\n• Программирование\n• История\n"
                                                    "• Личные заметки", parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_category_name)

        except Exception as e:
            logger.error(f"Error in create_category_start: {e}")
            bot.send_message(message.chat.id, "Ошибка при создании категории")

    def process_category_name(message):
        try:
            user_id = message.from_user.id
            category_name = message.text.strip()

            if not category_name:
                msg = bot.send_message(message.chat.id, "Название не может быть пустым. Введите название:")
                bot.register_next_step_handler(msg, process_category_name)
                return

            if len(category_name) > 50:
                msg = bot.send_message(message.chat.id, "Название слишком длинное (макс. 50 символов). Введите короче:")
                bot.register_next_step_handler(msg, process_category_name)
                return

            # Проверяем, нет ли уже категории с таким именем
            with with_connection() as conn:
                existing_categories = CategoryUtils.get_user_categories(conn, user_id)
                for cat in existing_categories:
                    if cat['name'].lower() == category_name.lower():
                        markup = types.InlineKeyboardMarkup()
                        btn_use = types.InlineKeyboardButton('Использовать существующую',
                                                             callback_data=f'use_category_{cat["id"]}')
                        btn_rename = types.InlineKeyboardButton('Ввести другое название',
                                                                callback_data='enter_new_name')
                        markup.add(btn_use, btn_rename)

                        bot.send_message(message.chat.id, f"Категория *{category_name}* уже существует!\n"
                                                          f"Что вы хотите сделать?",
                                         parse_mode='Markdown', reply_markup=markup)
                        return

            # Сохраняем название и переходим к описанию
            if user_id not in user_sessions:
                user_sessions[user_id] = {'data': {}}

            user_sessions[user_id]['data']['name'] = category_name
            user_sessions[user_id]['step'] = 'waiting_category_description'

            msg = bot.send_message(message.chat.id, f"*Создание категории*\n\nНазвание: *{category_name}*\n\n"
                                                    f"Теперь введите описание категории (необязательно):\n\n"
                                                    f"*Пример:* \"Слова и фразы на английском языке для изучения\"\n"
                                                    f"*Или нажмите* /skip *чтобы пропустить*", parse_mode='Markdown')

            bot.register_next_step_handler(msg, process_category_description)

        except Exception as e:
            logger.error(f"Error in process_category_name: {e}")
            bot.send_message(message.chat.id, "Ошибка при создании категории")

    def process_category_description(message):
        """Обработка описания категории"""
        try:
            user_id = message.from_user.id

            # Проверяем команду /skip
            if message.text == '/skip':
                description = None
            else:
                description = message.text.strip()
                if len(description) > 200:
                    msg = bot.send_message(message.chat.id, "Описание слишком длинное (макс. 200 символов). Введите короче:")
                    bot.register_next_step_handler(msg, process_category_description)
                    return

            # Проверяем сессию
            if (user_id not in user_sessions or
                    'data' not in user_sessions[user_id] or
                    'name' not in user_sessions[user_id]['data']):
                bot.send_message(message.chat.id, "Сессия устарела. Начните заново.")
                return

            category_name = user_sessions[user_id]['data']['name']

            # Выбор цвета категории
            markup = types.InlineKeyboardMarkup(row_width=3)
            colors = [
                ('🔵 Синий', '#3498db'),
                ('🟢 Зеленый', '#2ecc71'),
                ('🟡 Желтый', '#f1c40f'),
                ('🟠 Оранжевый', '#e67e22'),
                ('🔴 Красный', '#e74c3c'),
                ('🟣 Фиолетовый', '#9b59b6'),
                ('⚫ Серый', '#95a5a6'),
                ('🌸 Розовый', '#fd79a8'),
                ('🌿 Бирюзовый', '#1abc9c')
            ]

            for color_name, color_code in colors:
                btn = types.InlineKeyboardButton(color_name, callback_data=f'category_color_{color_code}')
                markup.add(btn)

            btn_no_color = types.InlineKeyboardButton('Без цвета', callback_data='category_color_default')
            markup.add(btn_no_color)

            bot.send_message(message.chat.id,f"*Выбор цвета для категории*\n\nНазвание: *{category_name}*\n"
                                             f"Описание: {description or 'нет'}\n\nВыберите цвет для категории:",
                             parse_mode='Markdown', reply_markup=markup)

            # Сохраняем описание
            user_sessions[user_id]['data']['description'] = description

        except Exception as e:
            logger.error(f"Error in process_category_description: {e}")
            bot.send_message(message.chat.id, "Ошибка при создании категории")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('category_color_'))
    def select_category_color(call):
        """Выбор цвета и сохранение категории"""
        try:
            user_id = call.from_user.id
            color_data = call.data.replace('category_color_', '')

            # Проверяем сессию
            if (user_id not in user_sessions or
                    'data' not in user_sessions[user_id] or
                    'name' not in user_sessions[user_id]['data']):
                bot.answer_callback_query(call.id, "Сессия устарела")
                return

            session_data = user_sessions[user_id]['data']
            category_name = session_data['name']
            description = session_data.get('description')

            # Определяем цвет
            color = color_data if color_data != 'default' else None

            with with_connection() as conn:
                # Создаем категорию
                category_id = CategoryUtils.create_category(conn, user_id, category_name, description, color)

                if category_id:
                    # Очищаем сессию
                    if user_id in user_sessions:
                        del user_sessions[user_id]

                    # Сообщение об успехе
                    markup = types.InlineKeyboardMarkup(row_width=2)
                    btn_add_card = types.InlineKeyboardButton(
                        'Добавить карточку',
                        callback_data=f'add_to_category_{category_id}'
                    )
                    btn_view = types.InlineKeyboardButton(
                        'Посмотреть',
                        callback_data=f'view_category_{category_id}'
                    )
                    btn_another = types.InlineKeyboardButton('Еще категорию', callback_data='create_another_category')

                    markup.add(btn_add_card, btn_view, btn_another)

                    color_text = f"цвет {color}" if color else "цвет по умолчанию"

                    bot.edit_message_text(f"*Категория создана!*\n\n*Название:* {category_name}\n"
                                          f"*Описание:* {description or 'нет'}\n*Цвет:* {color_text}\n"
                                          f"*ID:* #{category_id}\n\nТеперь вы можете добавить карточки в эту категорию.",
                                          call.message.chat.id, call.message.message_id,
                                          parse_mode='Markdown', reply_markup=markup)
                else:
                    bot.edit_message_text("Ошибка при создании категории", call.message.chat.id, call.message.message_id)

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in select_category_color: {e}")
            bot.answer_callback_query(call.id, "Ошибка при создании")

    @bot.message_handler(commands=['my_categories'])
    @bot.message_handler(func=lambda message: message.text in ['Мои категории', 'Мои категории'])
    def view_categories_list(message, page=1):
        try:
            user_id = message.from_user.id
            page_size = 8

            with with_connection() as conn:
                categories = CategoryUtils.get_user_categories(conn, user_id)

                categories_with_stats = []
                for category in categories:
                    cards = CardUtils.get_user_cards(conn, user_id, category_id=category['id'])
                    learned = len([c for c in cards if c['status'] == 'learned'])

                    categories_with_stats.append({**category, 'total_cards': len(cards),
                                                  'learned_cards': learned,
                                                  'progress': (learned / len(cards)) * 100 if cards else 0})

            if not categories_with_stats:
                markup = types.InlineKeyboardMarkup()
                btn_create = types.InlineKeyboardButton('Создать первую категорию',
                                                        callback_data='create_first_category')
                markup.add(btn_create)

                bot.send_message(message.chat.id, "📭 *У вас пока нет категорий.*\n\n"
                                                  "Категории помогают организовать карточки по темам.\n"
                                                  "Создайте свою первую категорию!",
                                 parse_mode='Markdown', reply_markup=markup)
                return

            # Пагинация
            total_pages = (len(categories_with_stats) + page_size - 1) // page_size
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            page_categories = categories_with_stats[start_idx:end_idx]

            # Формируем текст
            text = f"*Ваши категории* (страница {page}/{total_pages})\n\n"

            for i, cat in enumerate(page_categories, start=1):
                progress_bar = "🟩" * int(cat['progress'] / 20) + "⬜" * (5 - int(cat['progress'] / 20))
                text += f"{start_idx + i}. *{cat['name']}*\n"
                text += f"   {cat['learned_cards']}/{cat['total_cards']} {progress_bar}\n"
                text += f"   {cat['description'][:30]}...\n" if cat['description'] else "   Без описания\n"
                text += "\n"

            text += f"\nВсего категорий: *{len(categories_with_stats)}*"

            # Создаем инлайн-клавиатуру
            markup = types.InlineKeyboardMarkup(row_width=4)

            # Пагинация
            btn_row = []
            if page > 1:
                btn_prev = types.InlineKeyboardButton('◀️', callback_data=f'categories_page_{page - 1}')
                btn_row.append(btn_prev)

            if page < total_pages:
                btn_next = types.InlineKeyboardButton('▶️', callback_data=f'categories_page_{page + 1}')
                btn_row.append(btn_next)

            if btn_row:
                markup.add(*btn_row)

            # Кнопки действий для категорий на этой странице
            for cat in page_categories:
                btn_text = f"{cat['name'][:15]}..." if len(cat['name']) > 15 else f"{cat['name']}"
                btn = types.InlineKeyboardButton(btn_text, callback_data=f'view_category_{cat["id"]}')
                markup.add(btn)

            btn_view_all = types.InlineKeyboardButton('Просмотреть все', callback_data='view_all_categories')
            btn_create = types.InlineKeyboardButton('Новая категория', callback_data='create_category_from_list')

            markup.add(btn_view_all, btn_create)

            bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in view_categories_list: {e}")
            bot.send_message(message.chat.id, "Ошибка при загрузке категорий")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('view_category_'))
    def view_category_detail(call):
        try:
            category_id = call.data.replace('view_category_', '')
            user_id = call.from_user.id

            with with_connection() as conn:
                category = CategoryUtils.get_category_by_id(conn, category_id)

                if not category:
                    bot.answer_callback_query(call.id, "Категория не найдена")
                    return

                cards = CardUtils.get_user_cards(conn, user_id, category_id=category_id)
                learned = len([c for c in cards if c['status'] == 'learned'])
                progress = (learned / len(cards)) * 100 if cards else 0

                created_at = datetime.strptime(category['created_at'], "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y")

            # Формируем текст
            text = (f"*Категория: {category['name']}*\n\n*Описание:*\n{category['description'] or 'Нет описания'}\n\n"
                    f"*Статистика:*\n• Всего карточек: *{len(cards)}*\n• Изучено: *{learned}*\n"
                    f"• Изучается: *{len(cards) - learned}*\n• Прогресс: *{progress:.1f}%*\n\n*Информация:*\n"
                    f"• ID: #{category['id']}\n• Создана: {created_at}\n"
                    f"• Цвет: {'🎨 Настроен' if category['color'] else '⚫ По умолчанию'}")

            markup = types.InlineKeyboardMarkup(row_width=2)

            btn_add_card = types.InlineKeyboardButton('Добавить карточку',
                                                      callback_data=f'add_to_category_{category_id}')
            btn_view_cards = types.InlineKeyboardButton('Карточки категории',
                                                        callback_data=f'view_cards_in_category_{category_id}')
            btn_edit = types.InlineKeyboardButton('Редактировать', callback_data=f'edit_category_{category_id}')
            btn_delete = types.InlineKeyboardButton('Удалить', callback_data=f'delete_category_confirm_{category_id}')
            btn_quiz = types.InlineKeyboardButton('Тестирование', callback_data=f'start_category_quiz_{category_id}')
            btn_back = types.InlineKeyboardButton('Назад к списку', callback_data='back_to_categories_list')

            markup.add(btn_add_card, btn_view_cards, btn_edit, btn_delete, btn_quiz, btn_back)

            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='Markdown', reply_markup=markup)

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in view_category_detail: {e}")
            bot.answer_callback_query(call.id, "Ошибка при загрузке категории")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('delete_category_confirm_'))
    def delete_category_confirm(call):
        try:
            category_id = call.data.replace('delete_category_confirm_', '')

            with with_connection() as conn:
                category = CategoryUtils.get_category_by_id(conn, category_id)

                if not category:
                    bot.answer_callback_query(call.id, "Категория не найдена")
                    return

                cards = CardUtils.get_user_cards(conn, call.from_user.id, category_id=category_id)

            markup = types.InlineKeyboardMarkup(row_width=2)
            btn_confirm = types.InlineKeyboardButton('Да, удалить',callback_data=f'delete_category_with_cards_{category_id}')
            btn_move = types.InlineKeyboardButton('Переместить карточки', callback_data=f'move_cards_from_{category_id}')
            btn_cancel = types.InlineKeyboardButton('Нет, отмена', callback_data=f'view_category_{category_id}')

            markup.add(btn_confirm, btn_move, btn_cancel)

            bot.edit_message_text(f"🗑️ *Удаление категории*\n\nВы уверены, что хотите удалить категорию:\n"
                                  f"*{category['name']}*?\n\nВ категории *{len(cards)}* карточек.\n"
                                  f"Они будут *удалены вместе с категорией*!\n\nВы можете:\n"
                                  f"1. Удалить категорию с карточками\n2. Переместить карточки в другую категорию\n"
                                  f"3. Отменить удаление",
                                  call.message.chat.id, call.message.message_id,
                                  parse_mode='Markdown', reply_markup=markup)

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in delete_category_confirm: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('delete_category_with_cards_'))
    def delete_category_execute(call):
        try:
            category_id = call.data.replace('delete_category_with_cards_', '')
            user_id = call.from_user.id

            with with_connection() as conn:
                category = CategoryUtils.get_category_by_id(conn, category_id)

                if not category:
                    bot.answer_callback_query(call.id, "Категория не найдена")
                    return
                success = CategoryUtils.delete_category(conn, category_id)

                if success:
                    bot.edit_message_text(f"Категория *{category['name']}* удалена вместе с карточками",
                                          call.message.chat.id, call.message.message_id, parse_mode='Markdown')
                else:
                    bot.edit_message_text("Ошибка при удалении категории", call.message.chat.id, call.message.message_id)

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in delete_category_execute: {e}")
            bot.answer_callback_query(call.id, "Ошибка при удалении")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('edit_category_'))
    def edit_category_start(call):
        try:
            category_id = call.data.replace('edit_category_', '')
            user_id = call.from_user.id

            with with_connection() as conn:
                category = CategoryUtils.get_category_by_id(conn, category_id)

                if not category:
                    bot.answer_callback_query(call.id, "Категория не найдена")
                    return

            markup = types.InlineKeyboardMarkup(row_width=2)
            btn_edit_name = types.InlineKeyboardButton('Название', callback_data=f'edit_category_name_{category_id}')
            btn_edit_desc = types.InlineKeyboardButton('Описание', callback_data=f'edit_category_desc_{category_id}')
            btn_edit_color = types.InlineKeyboardButton('Цвет', callback_data=f'edit_category_color_{category_id}')
            btn_cancel = types.InlineKeyboardButton('Отмена', callback_data=f'view_category_{category_id}')

            markup.add(btn_edit_name, btn_edit_desc, btn_edit_color, btn_cancel)

            bot.edit_message_text(f"*Редактирование категории*\n\n" 
                                  f"Что вы хотите изменить в категории *{category['name']}*?",
                                  call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in edit_category_start: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('edit_category_name_'))
    def edit_category_name(call):
        try:
            category_id = call.data.replace('edit_category_name_', '')
            user_id = call.from_user.id

            # Сохраняем в сессии
            user_sessions[user_id] = {'step': 'editing_category_name', 'data': {'category_id': category_id}}

            msg = bot.send_message(call.message.chat.id,
                                   "*Редактирование названия*\n\nВведите новое название категории:",
                                   parse_mode='Markdown')

            bot.register_next_step_handler(msg, process_edit_category_name)
            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in edit_category_name: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

    def process_edit_category_name(message):
        try:
            user_id = message.from_user.id
            new_name = message.text.strip()

            if not new_name:
                msg = bot.send_message(message.chat.id, "Название не может быть пустым. Попробуйте еще раз:")
                bot.register_next_step_handler(msg, process_edit_category_name)
                return

            if len(new_name) > 50:
                msg = bot.send_message(message.chat.id, "Название слишком длинное (макс. 50 символов). Введите короче:")
                bot.register_next_step_handler(msg, process_edit_category_name)
                return

            if user_id not in user_sessions or 'category_id' not in user_sessions[user_id]['data']:
                bot.send_message(message.chat.id, "Сессия устарела")
                return

            category_id = user_sessions[user_id]['data']['category_id']

            with with_connection() as conn:
                # Проверяем, нет ли уже категории с таким именем
                existing_categories = CategoryUtils.get_user_categories(conn, user_id)
                for cat in existing_categories:
                    if cat['id'] != category_id and cat['name'].lower() == new_name.lower():
                        bot.send_message(message.chat.id, f"Категория с названием *{new_name}* уже существует!",
                                         parse_mode='Markdown')
                        return

                # Обновляем название
                success = CategoryUtils.update_category(conn, category_id, name=new_name)

                if success:
                    # Очищаем сессию
                    if user_id in user_sessions:
                        del user_sessions[user_id]

                    bot.send_message(message.chat.id, f"Название категории изменено на *{new_name}*", parse_mode='Markdown')
                else:
                    bot.send_message(message.chat.id, "Ошибка при обновлении")

        except Exception as e:
            logger.error(f"Error in process_edit_category_name: {e}")
            bot.send_message(message.chat.id, "Ошибка")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('add_to_category_'))
    def add_card_to_category(call):
        try:
            category_id = call.data.replace('add_to_category_', '')
            user_id = call.from_user.id

            # Сохраняем состояние для процесса добавления карточки
            user_sessions[user_id] = {'step': 'waiting_front_for_category', 'data': {'category_id': category_id}}

            with with_connection() as conn:
                category = CategoryUtils.get_category_by_id(conn, category_id)

            msg = bot.send_message(call.message.chat.id, f"*Добавление карточки в категорию*\n\n" 
                                                         f"Категория: *{category['name']}*\n\n" 
                                                         f"Введите вопрос или слово для карточки:",
                                   parse_mode='Markdown')

            bot.register_next_step_handler(msg, process_front_for_category)
            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in add_card_to_category: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

    from cards import process_front_side
    def process_front_for_category(message, process_front_side=None):
        try:
            process_front_side(message)
        except Exception as e:
            logger.error(f"Error in process_front_for_category: {e}")
            bot.send_message(message.chat.id, "Ошибка")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('view_cards_in_category_'))
    def view_cards_in_category(call):
        try:
            category_id = call.data.replace('view_cards_in_category_', '')
            user_id = call.from_user.id

            with with_connection() as conn:
                category = CategoryUtils.get_category_by_id(conn, category_id)
                cards = CardUtils.get_user_cards(conn, user_id, category_id=category_id)

            if not cards:
                markup = types.InlineKeyboardMarkup()
                btn_add = types.InlineKeyboardButton('Добавить карточку',
                                                     callback_data=f'add_to_category_{category_id}')
                markup.add(btn_add)

                bot.send_message(call.message.chat.id, f"*В категории *{category['name']}* нет карточек.*\n\n"
                                                       f"Добавьте первую карточку!",
                                 parse_mode='Markdown', reply_markup=markup)
                return

            text = f"*Карточки в категории: {category['name']}*\n\n"
            text += f"Всего карточек: *{len(cards)}*\n\n"

            for i, card in enumerate(cards[:10], 1):
                status = "✅" if card['status'] == 'learned' else "🎯"
                text += f"{i}. {status} *{card['front'][:30]}...*\n"
                text += f"   → {card['back'][:30]}...\n\n"

            if len(cards) > 10:
                text += f"... и еще *{len(cards) - 10}* карточек\n"

            # Создаем кнопки для навигации по карточкам
            markup = types.InlineKeyboardMarkup(row_width=2)

            for i, card in enumerate(cards[:5], 1):
                btn_text = f"{i}. {card['front'][:15]}..."
                btn = types.InlineKeyboardButton(btn_text, callback_data=f'view_card_{card["id"]}')
                markup.add(btn)

            if len(cards) > 5:
                btn_more = types.InlineKeyboardButton(f"Еще карточки ({len(cards) - 5})",
                                                      callback_data=f'view_more_cards_{category_id}')
                markup.add(btn_more)

            btn_add = types.InlineKeyboardButton('Добавить карточку',
                                                 callback_data=f'add_to_category_{category_id}')
            btn_quiz = types.InlineKeyboardButton('Тестирование',
                                                  callback_data=f'start_category_quiz_{category_id}')
            btn_back = types.InlineKeyboardButton('Назад к категории',
                                                  callback_data=f'view_category_{category_id}')

            markup.add(btn_add, btn_quiz, btn_back)

            bot.send_message(call.message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in view_cards_in_category: {e}")
            bot.answer_callback_query(call.id, "Ошибка при загрузке карточек")

    @bot.message_handler(func=lambda message: message.text in ['Статистика'])
    def categories_stats(message):
        try:
            user_id = message.from_user.id

            with with_connection() as conn:
                categories = CategoryUtils.get_user_categories(conn, user_id)

                if not categories:
                    bot.send_message(
                        message.chat.id,
                        "📭 У вас пока нет категорий. Создайте первую категорию!"
                    )
                    return

                # Собираем статистику
                stats_text = "📊 *Статистика по категориям*\n\n"
                total_cards_all = 0
                total_learned_all = 0

                for category in categories:
                    cards = CardUtils.get_user_cards(conn, user_id, category_id=category['id'])
                    learned = len([c for c in cards if c['status'] == 'learned'])

                    total_cards_all += len(cards)
                    total_learned_all += learned

                    progress = (learned / len(cards)) * 100 if cards else 0
                    progress_bar = "🟩" * int(progress / 20) + "⬜" * (5 - int(progress / 20))

                    stats_text += f"*{category['name']}*\n"
                    stats_text += f"  {learned}/{len(cards)} {progress_bar} {progress:.0f}%\n\n"

                # Общая статистика
                overall_progress = (total_learned_all / total_cards_all) * 100 if total_cards_all > 0 else 0

                stats_text += f"*Общая статистика:*\n"
                stats_text += f"• Категорий: {len(categories)}\n"
                stats_text += f"• Всего карточек: {total}"
