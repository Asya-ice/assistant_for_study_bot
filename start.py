import logging
from telebot import types
from database import UserUtils, with_connection

logger = logging.getLogger(__name__)


def register_start_handlers(bot):

    @bot.message_handler(commands=['start'])
    def start_command(message):
        try:
            user_id = message.from_user.id
            username = message.from_user.username
            first_name = message.from_user.first_name

            logger.info(f"User {user_id} (@{username}) started bot")

            # Сохраняем/обновляем пользователя в БД
            with with_connection() as conn:
                UserUtils.create_or_update_user(conn, telegram_id=user_id, username=username, first_name=first_name)

            # Создаем клавиатуру главного меню
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

            btn_cards = types.KeyboardButton('Мои карточки')
            btn_quiz = types.KeyboardButton('Тестирование')
            btn_add = types.KeyboardButton('Добавить карточку')
            btn_stats = types.KeyboardButton('Статистика')
            btn_settings = types.KeyboardButton('Настройки')
            btn_help = types.KeyboardButton('Помощь')

            markup.add(btn_cards, btn_quiz, btn_add, btn_stats, btn_settings, btn_help)

            welcome_text = (f"*Привет, {first_name}!* \n"
                            f"Я — бот для изучения по системе карточек (flashcards).\n"
                            f"Помогаю запоминать информацию с помощью интервальных повторений.\n\n"
                            f"*Что я умею:*\n"
                            f"• Создавать карточки с вопросами и ответами\n"
                            f"• Организовывать карточки по категориям\n"
                            f"• Проводить тестирование для проверки знаний\n"
                            f"• Напоминать о повторении карточек\n"
                            f"• Показывать статистику прогресса\n\n"
                            f"*Быстрый старт:*\n"
                            f"1. Создайте категорию командой /categories\n"
                            f"2. Добавьте карточку командой /add_card\n"
                            f"3. Начните тестирование командой /quiz\n"
                            f"Используйте кнопки ниже или команду /help для навигации.")

            bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown', reply_markup=markup)

            # Отправляем инлайн-кнопки для быстрых действий
            quick_actions_markup = types.InlineKeyboardMarkup(row_width=2)

            btn_quick_add = types.InlineKeyboardButton('Быстрая карточка', callback_data='quick_add_card')
            btn_tutorial = types.InlineKeyboardButton('Обучение', callback_data='show_tutorial')
            btn_demo = types.InlineKeyboardButton('Демо-режим', callback_data='start_demo')
            btn_feedback = types.InlineKeyboardButton('Обратная связь', callback_data='send_feedback')

            quick_actions_markup.add(btn_quick_add, btn_tutorial, btn_demo, btn_feedback)

            bot.send_message(message.chat.id, "*Быстрые действия:*", parse_mode='Markdown',
                             reply_markup=quick_actions_markup)

        except Exception as e:
            logger.error(f"Error in start_command: {e}")
            bot.send_message(
                message.chat.id,
                "Произошла ошибка при запуске. Попробуйте еще раз."
            )

    @bot.message_handler(commands=['help'])
    def help_command(message):
        try:
            help_text = ("*Справка по командам*\n\n"
                         "*Основные команды:*\n"
                         "/start - Главное меню\n"
                         "/help - Эта справка\n"
                         "/menu - Показать меню кнопок\n\n"
                         "*Работа с карточками:*\n"
                         "/cards - Управление карточками\n"
                         "/add_card - Добавить карточку (пошагово)\n"
                         "/quickadd - Быстрое добавление (формат: вопрос - ответ)\n"
                         "/mycards - Показать мои карточки\n"
                         "/search - Поиск по карточкам\n\n"
                         "*Тестирование:*\n"
                         "/quiz - Начать тестирование\n"
                         "/review - Повторить сложные карточки\n"
                         "/today - Карточки на сегодня\n\n"
                         "*Категории:*\n"
                         "/categories - Управление категориями\n\n"
                         "*Напоминания:*\n"
                         "/reminder - Настройка напоминаний\n"
                         "/toggle_reminders - Вкл/выкл напоминания\n\n"
                         "*Статистика:*\n"
                         "/stats - Моя статистика\n"
                         "/progress - Прогресс обучения\n"
                         "/streak - Текущая серия дней\n\n"
                         "*Настройки:*\n"
                         "/settings - Настройки бота\n\n"
                         "*Администрация:*\n"
                         "/admin - Админ-панель (только для админов)")

            bot.send_message(message.chat.id, help_text)

        except Exception as e:
            logger.error(f"Error in help_command: {e}")
            bot.send_message(message.chat.id, "Ошибка при загрузке справки")

    @bot.message_handler(commands=['menu'])
    def menu_command(message):
        try:
            # Создаем клавиатуру главного меню
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

            btn_cards = types.KeyboardButton('Мои карточки')
            btn_quiz = types.KeyboardButton('Тестирование')
            btn_add = types.KeyboardButton('Добавить карточку')
            btn_stats = types.KeyboardButton('Статистика')
            btn_settings = types.KeyboardButton('Настройки')
            btn_help = types.KeyboardButton('Помощь')

            markup.add(btn_cards, btn_quiz, btn_add, btn_stats, btn_settings, btn_help)

            bot.send_message(message.chat.id, "*Главное меню*\n\nВыберите действие:", parse_mode='Markdown',
                             reply_markup=markup)

        except Exception as e:
            logger.error(f"Error in menu_command: {e}")

    @bot.message_handler(commands=['about'])
    def about_command(message):
        about_text = ("*О боте*\n"
                      "*Flashcards Bot* — умный помощник для обучения\n\n"
                      "*Возможности:*\n"
                      "• Система интервальных повторений\n"
                      "• Умные напоминания\n"
                      "• Статистика прогресса\n\n"
                      "*Технологии:*\n"
                      "• Python 3.13\n"
                      "• pyTelegramBotAPI\n"
                      "• SQLite\n"
                      "• Spaced Repetition Algorithm\n\n"
                      "*Разработчик:* @my_username\n"
                      "*Исходный код:* [GitHub](https://github.com/my-repo)\n")

        markup = types.InlineKeyboardMarkup()
        btn_source = types.InlineKeyboardButton('Исходный код', url='https://github.com/my-repo')

        markup.add(btn_source)

        bot.send_message(message.chat.id, about_text, parse_mode='Markdown', reply_markup=markup,
                         disable_web_page_preview=True)

    # Обработчики callback-запросов для стартовых действий
    @bot.callback_query_handler(func=lambda call: call.data == 'quick_add_card')
    def quick_add_callback(call):
        try:
            from handlers.cards import quick_add_card
            quick_add_card(call.message)
            bot.answer_callback_query(call.id, "Быстрое добавление")
        except Exception as e:
            logger.error(f"Error in quick_add_callback: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

    @bot.callback_query_handler(func=lambda call: call.data == 'show_tutorial')
    def tutorial_callback(call):
        try:
            tutorial_text = ("*Обучение работе с ботом*\n\n"
                             "*1. Создание категории:*\n"
                             "Используйте /categories → 'Создать категорию'\n"
                             "Пример: 'Английские слова', 'Программирование'\n\n"
                             "*2. Добавление карточки:*\n"
                             "Используйте /add_card → выберите категорию\n"
                             "• Вопрос: 'Apple'\n"
                             "• Ответ: 'Яблоко'\n\n"
                             "*3. Тестирование:*\n"
                             "Используйте /quiz → выбирайте категории\n"
                             "Бот покажет вопрос, вы пытаетесь вспомнить ответ\n\n"
                             "*4. Статистика:*\n"
                             "/stats покажет ваш прогресс\n"
                             "Чем больше правильных ответов, тем реже показывается карточка\n\n"
                             "*5. Напоминания:*\n"
                             "/reminder → настройте время ежедневных уведомлений\n\n"
                             "*Советы:*\n"
                             "• Добавляйте карточки постепенно\n"
                             "• Регулярно проходите тестирование\n"
                             "• Используйте категории для организации")

            bot.edit_message_text(tutorial_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in tutorial_callback: {e}")

    @bot.callback_query_handler(func=lambda call: call.data == 'send_feedback')
    def feedback_callback(call):
        try:
            feedback_text = ("*Обратная связь*\n"
                             "Мне важно ваше мнение! Что улучшить в боте?)\n"
                             "Вы можете:\n"
                             "1. Написать разработчику: @my_username\n"
                             "2. Сообщить об ошибке\n"
                             "3. Предложить новую функцию\n"
                             "4. Задать вопрос\n"
                             "Или просто ответьте на это сообщение")

            bot.edit_message_text(feedback_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
            bot.answer_callback_query(call.id)

        except Exception as e:
            logger.error(f"Error in feedback_callback: {e}")

    # Обработчик текстовых сообщений для меню
    @bot.message_handler(text="Помощь")
    def help_button_handler(message):
        help_command(message)

    @bot.message_handler(text="Меню")
    def menu_button_handler(message):
        menu_command(message)

    logger.info("Start handlers registered successfully")
    return bot