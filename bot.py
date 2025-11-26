import os
import telebot
import logging
from telebot.custom_filters import TextMatchFilter, TextStartsFilter


create_database()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация
class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
    ADMIN_IDS = [123456789]  # ID администраторов
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

bot = telebot.TeleBot(Config.BOT_TOKEN)

bot.add_custom_filter(TextMatchFilter())
bot.add_custom_filter(TextStartsFilter())

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


