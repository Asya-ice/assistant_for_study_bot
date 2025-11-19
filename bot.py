import telebot

bot = telebot.TeleBot()

create_database()

# обрабатываем команду /start
@bot.message_handler(commands=['start'])
def start_func(message):
    bot.send_message(message.from_user.id, "Привет! Если ты хочешь выучить новые слова на английском или на\t"
                                           "любом другом языке или тебе надо выучить термины, определения,\t"
                                           "или ты просто хочешь подготовиться с экзаменам/сессии, то я тот кто тебе нужен!\n"
                                           "Для начала, напиши свое имя: \n"
                                           "Больше о моих возможностях: /help")


# обрабатываем команду /help
@bot.message_handler(commands=['help'])
def help_func(message):
    bot.send_message(message.from_user.id, "Вот список команд которые помогу тебе:\n"
                                           "/add_card - добавить карточку\n"
                                           "/review - начать сессию повторения\n"
                                           "/stats - показать статистику\n"
                                           "/settings - настройки управления")


# обрабатываем команду /settings
@bot.message_handler(commands=['settings'])
def settings_func(message):
    bot.send_message(message.from_user.id, "Здесь ты можешь управлять своими карточками и напоминаниями:\n"
                                           "/cards - управление карточками\n"
                                           "/categories - управление категориями\n"
                                           "/export - экспорт данных\n"
                                           "/import - импорт карточек\n"
                                           "/reminder - настройка напоминаний")


# обработываем команду /add_card
@bot.message_handler(commands=['add_card'])
def add_card_func(message):
    bot.send_message(message.from_user.id, "Давай добавим новую карточку.\n"
                                           "Сначала введи вопрос:")


