import logging
import random
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, BotCommandScopeChat
from telegram.ext import Application, ApplicationBuilder, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.constants import ParseMode
import json
import os
import asyncio
import re
import nest_asyncio
import datetime
import pytz
import updater
from warnings import filterwarnings
from telegram.warnings import PTBUserWarning
from telegram.error import BadRequest

# Применение nest_asyncio
nest_asyncio.apply()

filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

ADMIN_IDS = [647850100, 918094104] # 918094104
cycle_users = []
user_data = {}
feedback_data = {}
not_cycle_users = {}

# Статусы для ConversationHandler
ASKING_EMAIL, ASKING_NAME, ASKING_POSITION, CONFIRMING_NAME, CONFIRMING_POSITION, SHOWING_CARD, LEAVING_FEEDBACK = range(7)

# Функции загрузки и сохранения данных
def load_data(filename, default):
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as file:
                data = json.load(file)
                logger.info(f"Данные загружены из {filename}: {data}")
                return data
        return default
    except Exception as e:
        logger.error(f"Не удалось загрузить данные из {filename}: {e}")
        return default

def save_data(data, filename):
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
            logger.info(f"Данные сохранены в {filename}: {data}")
    except Exception as e:
        logger.error(f"Не удалось сохранить данные в {filename}: {e}")

user_data = load_data('user_data.json', {})
cycle_users = load_data('cycle_users.json', {})
feedback_data = load_data('feedback_data.json', {})
not_cycle_users = load_data('not_cycle_users.json', {})
logger.info(f"Загружены cycle users: {cycle_users}")
logger.info(f"Загружены user data: {user_data}")

def handle_cycle_start(update: Update, context):
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id

    # Проверяем, есть ли уже UUID для данного пользователя в user_data
    for uuid_key, user_info in user_data.items():
        if user_info.get('id') == user_id:
            context.user_data['uuid'] = uuid_key
            return context.user_data['uuid']

    # Если UUID не найден, создаем новый
    user_uuid = str(uuid.uuid4())
    context.user_data['uuid'] = user_uuid
    user_data[user_uuid] = {
        'id': user_id,
        'email': '',
        'name': '',
        'position': ''
    }
    save_data(user_data, 'user_data.json')
    return user_uuid

# Обновление функции start для вызова handle_cycle_start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Получена команда /start")
    user_id = update.message.from_user.id
    context.user_data['id'] = user_id

    for uuid_key, user_info in user_data.items():
        if user_info.get('id') == user_id:
            context.user_data['uuid'] = uuid_key
            context.user_data['email'] = user_info.get('email', '')
            context.user_data['name'] = user_info.get('name', '')
            context.user_data['position'] = user_info.get('position', '')
            await update.message.reply_text(
                f"Ваши текущие данные:\nИмя: {context.user_data['name']}\nПочта: {context.user_data['email']}\nДолжность: {context.user_data['position']}\n\n"
                "Хотите изменить что-нибудь или начать новый цикл?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Изменить данные", callback_data='new_cycle')],
                    [InlineKeyboardButton("Начать новый цикл", callback_data='join_cycle')]
                ])
            )
            return SHOWING_CARD
    return await start_registration(update, context)


async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Начало регистрации")
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id

    for uuid_key, user_info in user_data.items():
        if user_info.get('id') == user_id:
            await update.message.reply_text("Вы уже зарегистрированы в боте. Используйте команду /start для начала.")
            return ConversationHandler.END

    if user_id in ADMIN_IDS:
        commands = [
            BotCommand("start", "Начать работу"),
            BotCommand("show_all_users", "Показать пользователей в сессии"),
            BotCommand("match", "Выбрать пару"),
            BotCommand("clear_database", "Очистить базу данных"),
            BotCommand("leave_feedback", "Оставить фидбек")
        ]
    else:
        commands = [
            BotCommand("start", "Начать работу"),
            BotCommand("leave_feedback", "Оставить фидбек")
        ]

    await context.bot.set_my_commands(commands, scope=BotCommandScopeChat(user_id))

    keyboard = [[InlineKeyboardButton("Поехали 🚀", callback_data='start_registration')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    image_url = 'https://i.ibb.co/rfMcqY5/img.png'
    
    try:
        await context.bot.send_photo(
            chat_id=update.message.chat.id if update.message else update.callback_query.message.chat.id,
            photo=image_url,
            caption="Привет! Я чат бот random-coffee, созданный для лучшего знакомства среди друзей компании! Давай начнем?",
            reply_markup=reply_markup,
        )
    except Exception as e:
        logger.error(f"Не удалось отправить изображение: {e}")
        await update.message.reply_text(f"Ошибка при отправке изображения: {e}")
    
    return ASKING_EMAIL

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    logger.info(f"Получен callback_query: {query.data}")

    if query.data == 'start_registration':
        context.user_data.clear()
        logger.info("Состояние сброшено. Начинаем регистрацию, состояние ASKING_EMAIL")
        await query.message.reply_text(
            text="Отлично! Для начала давай узнаем твою почту? Напиши её ниже 😉"
        )
        return ASKING_EMAIL
    elif query.data == 'use_existing':
        user_info = context.user_data
        if user_info:
            logger.info("Используем существующие данные пользователя")
            await query.message.reply_text(
                f"Ваши текущие данные:\nИмя: {user_info.get('name', 'Не указано')}\nПочта: {user_info.get('email', 'Не указана')}\nДолжность: {user_info.get('position', 'Не указана')}\n\nХотите изменить что-нибудь или начать новый цикл?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Изменить данные", callback_data='new_cycle')],
                    [InlineKeyboardButton("Начать новый цикл", callback_data='join_cycle')]
                ])
            )
        else:
            logger.error("Ошибка: данные пользователя не найдены.")
            await query.message.reply_text("Ошибка: данные пользователя не найдены.")
        return SHOWING_CARD
    elif query.data == 'new_cycle':
        logger.info("Начинаем новый цикл, сбрасываем данные и запрашиваем новое имя")
        context.user_data['name'] = ""
        context.user_data['position'] = ""
        await query.message.reply_text(
            text="Отлично! Давайте начнем сначала. Введите ваше имя:"
        )
        return ASKING_NAME
    elif query.data == 'join_cycle':
        logger.info("Пользователь участвует в текущем цикле")
        await query.message.reply_text("Вы участвуете в текущем цикле!")
        return ConversationHandler.END

    logger.info("Обработчик кнопок завершен")
    return ConversationHandler.END

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data['name'] = update.message.text
        logger.info(f"User name: {context.user_data['name']}")

        if 'email' in context.user_data:
            await update.message.reply_text("Записал! Теперь введи свою должность 🧑‍🏭")
            return ASKING_POSITION
        else:
            await update.message.reply_text("Записал! Теперь введи свою почту 📫")
            return ASKING_EMAIL
    except Exception as e:
        logger.error(f"Ошибка в get_name: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте снова позже.")
        return ConversationHandler.END

async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text

    if not is_valid_email(email):
        await update.message.reply_text("Неверный формат электронной почты. Пожалуйста, введите почту в формате email@domen.domen")
        return ASKING_EMAIL

    user_id = context.user_data.get('id')
    if not user_id:
        user_id = update.message.from_user.id
        context.user_data['id'] = user_id

    for uuid_key, info in user_data.items():
        if info.get('id') == user_id:
            context.user_data['email'] = email
            context.user_data['uuid'] = uuid_key
            user_data[uuid_key]['email'] = email
            save_data(user_data, 'user_data.json')
            await update.message.reply_text(
                f"Ваши текущие данные:\nИмя: {info.get('name', 'Не указано')}\nПочта: {email}\nДолжность: {info.get('position', 'Не указана')}\n\nХотите изменить что-нибудь или начать новый цикл?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Изменить данные", callback_data='new_cycle')],
                    [InlineKeyboardButton("Начать новый цикл", callback_data='join_cycle')]
                ])
            )
            return SHOWING_CARD

    new_user_uuid = str(uuid.uuid4())
    context.user_data['email'] = email
    context.user_data['uuid'] = new_user_uuid
    user_data[new_user_uuid] = {
        'id': user_id,
        'email': email,
        'name': '',
        'position': ''
    }
    save_data(user_data, 'user_data.json')
    await update.message.reply_text("Записал! Теперь введи своё имя и фамилию 😉")
    return ASKING_NAME


def is_valid_email(email):
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(email_regex, email) is not None

async def confirm_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == 'change_name':
        await query.message.reply_text("Пожалуйста, введите новое имя и фамилию 😉")
        return ASKING_NAME
    else:
        await query.message.reply_text(
            f"Отлично! В прошлой сессии твоя должность была - {context.user_data['position']}. Изменилась ли твоя должность?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Да", callback_data='change_position')],
                [InlineKeyboardButton("Нет", callback_data='keep_position')]
            ])
        )
        return CONFIRMING_POSITION

async def confirm_position(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == 'change_position':
        await query.message.reply_text("Пожалуйста, введите новую должность 🧑‍🏭")
        return ASKING_POSITION
    else:
        user_id = context.user_data['uuid']
        user_data[user_id] = {
            'id': context.user_data['id'],
            'name': context.user_data['name'],
            'email': context.user_data['email'],
            'position': context.user_data['position']
        }
        save_data(user_data, 'user_data.json')
        keyboard = [
            [InlineKeyboardButton("Я участвую в текущем цикле 👍", callback_data='join_cycle')],
            [InlineKeyboardButton("Пока не хочу участвовать 👎", callback_data='not_join_cycle')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            f"Супер! Твоя карточка готова, давай посмотрим, как она выглядит :)\n\n"
            f"Имя: {context.user_data['name']} 🌸\n"
            f"Почта: {context.user_data['email']} 📫\n"
            f"Должность: {context.user_data['position']} 👀",
            reply_markup=reply_markup
        )
        return SHOWING_CARD

async def get_position(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if 'name' not in context.user_data or 'email' not in context.user_data:
        await update.message.reply_text("Кажется, я еще не знаю твое имя или почту. Пожалуйста, введи ваше имя, фамилию и почту.")
        return ASKING_NAME
    context.user_data['position'] = update.message.text

    user_id = context.user_data['uuid']
    user_data[user_id] = {
        'id': context.user_data['id'],
        'name': context.user_data['name'],
        'email': context.user_data['email'],
        'position': context.user_data['position']
    }
    save_data(user_data, 'user_data.json')
    logger.info(f"User position: {context.user_data['position']}")
    keyboard = [
        [InlineKeyboardButton("Я участвую в текущем цикле 👍", callback_data='join_cycle')],
        [InlineKeyboardButton("Пока не хочу участвовать 👎", callback_data='not_join_cycle')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Супер! Твоя карточка готова, давай посмотрим, как она выглядит :)\n\n"
        f"Имя: {context.user_data['name']} 🌸\n"
        f"Почта: {context.user_data['email']} 📫\n"
        f"Должность: {context.user_data['position']} 👀",
        reply_markup=reply_markup
    )
    return SHOWING_CARD

async def cycle_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_uuid = context.user_data['uuid']
    chat_id = update.effective_chat.id

    # Загрузка данных из cycle_users.json
    cycle_users = load_data('cycle_users.json', {})

    if query.data == 'join_cycle':
        if user_uuid not in cycle_users:
            cycle_users[user_uuid] = chat_id
            save_data(cycle_users, 'cycle_users.json')
        if user_uuid in not_cycle_users:
            del not_cycle_users[user_uuid]
            save_data(not_cycle_users, 'not_cycle_users.json')
        logger.info(f"Добавлен пользователь {user_uuid} в цикл: {list(cycle_users.keys())}")
        num_users_text = get_user_count_text(len(cycle_users))
        await query.message.reply_text(
            text=f"Отлично! На данный момент в текущем цикле участвует {num_users_text}. Ожидайте, пока наберется достаточное количество людей для выбора пары :) Сообщение о результате придет в этот чат."
        )
        await notify_cycle_user_count(context)
    elif query.data == 'not_join_cycle':
        if user_uuid not in not_cycle_users:
            not_cycle_users[user_uuid] = chat_id
            save_data(not_cycle_users, 'not_cycle_users.json')
        if user_uuid in cycle_users:
            del cycle_users[user_uuid]
            save_data(cycle_users, 'cycle_users.json')
        logger.info(f"Пользователь {user_uuid} не в цикле: {list(not_cycle_users.keys())}")
        keyboard = [[InlineKeyboardButton("Ну ладно, я передумал - участвую!", callback_data='join_cycle')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            text="Ничего страшного, если передумаешь - нажми кнопку ниже и я добавлю тебя в текущий цикл :)",
            reply_markup=reply_markup
        )
        await notify_cycle_user_count(context)
    return SHOWING_CARD


async def notify_cycle_users_command(update: Update = None, context: ContextTypes.DEFAULT_TYPE = None):
    if update:
        if update.message.from_user.id not in ADMIN_IDS:
            await update.message.reply_text("OOPS! Эта команда доступна только администраторам.")
            return
        await notify_cycle_user_count(context)
        await update.message.reply_text("Уведомление о количестве пользователей в текущем цикле отправлено администраторам.")
    else:
        await notify_cycle_user_count(context)

async def show_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_IDS:
        await update.message.reply_text("OOPS! Эта команда доступна только администраторам.")
        return

    data = load_data('user_data.json', {})
    if not data:
        await update.message.reply_text("Нет данных пользователей.")
        return

    message = "Карточки пользователей:\n"
    for user_id, info in data.items():
        logger.info(f"user_id: {user_id}, info: {info}, type(info): {type(info)}")
        
        if isinstance(info, dict):
            name = info.get('name', 'Не указано')
            email = info.get('email', 'Не указано')
            position = info.get('position', 'Не указано')
            message += f"Имя: {name}\nПочта: {email}\nДолжность: {position}\n\n"
        else:
            logger.error(f"Ожидался словарь, но получен {type(info)} для user_id {user_id}")

    await update.message.reply_text(message)

async def match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_IDS:
        await update.message.reply_text("OOPS! Эта команда доступна только администраторам.")
        return

    await match_logic(user_data, context)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    logger.info(f"context.user_data в button_handler: {context.user_data}")

    if query.data == 'yes_meet':
        meet_link = "https://calendar.google.com/calendar/u/0/r/eventedit?vcon=meet&dates=now&hl=ru"
        await query.message.reply_text(
            text=f"А вот и твоя ссылка - 🔗 [Ссылка на встречу]({meet_link})\n\n Надеюсь, что все пройдет хорошо!\n\n Не забудь потом оставить отзыв :)",
            parse_mode='Markdown'
        )
    elif query.data == 'no_meet':
        keyboard = [[InlineKeyboardButton("Я передумал, давай сделаем встречу!", callback_data='yes_meet')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            text="Хорошо, если вдруг передумаете - нажмите на кнопку ниже и я сделаю встречу :)",
            reply_markup=reply_markup
        )

async def scheduled_match(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    await match_logic(job_data['user_data'], context)

async def match_logic(user_data_dict, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Функция match вызвана")
    
    # Загрузка данных из cycle_users.json
    cycle_users_data = load_data('cycle_users.json', {})

    if len(cycle_users_data) < 2:
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(chat_id=admin_id, text="OOPS! Недостаточно пользователей для создания пары.")
        return

    cycle_users_in_data = [user_uuid for user_uuid in cycle_users_data if user_uuid in user_data_dict]
    missing_users = [user_uuid for user_uuid in cycle_users_data if user_uuid not in user_data_dict]

    if missing_users:
        logger.warning(f"Пользователи без данных: {missing_users}")

    if len(cycle_users_in_data) < 2:
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(chat_id=admin_id, text="OOPS! Недостаточно данных для пользователей, чтобы создать пару.")
        return

    random.shuffle(cycle_users_in_data)
    pairs = []
    used_users = set()

    while len(cycle_users_in_data) >= 2:
        user1_uuid = cycle_users_in_data.pop()
        user2_uuid = cycle_users_in_data.pop()
        
        if user1_uuid in used_users or user2_uuid in used_users:
            continue

        pairs.append((user1_uuid, user2_uuid))
        used_users.update([user1_uuid, user2_uuid])

    # Обработка пользователей, которым не удалось найти пару
    remaining_users = [user_uuid for user_uuid in cycle_users_in_data if user_uuid not in used_users]
    
    if pairs:
        for user1_uuid, user2_uuid in pairs:
            user1 = user_data_dict.get(user1_uuid, {})
            user2 = user_data_dict.get(user2_uuid, {})

            if not user1 or not user2:
                logger.error(f"Данные пользователей не найдены: {user1_uuid}, {user2_uuid}")
                continue

            user1_chat_id = cycle_users_data.get(user1_uuid)
            user2_chat_id = cycle_users_data.get(user2_uuid)

            if not user1_chat_id or not user2_chat_id:
                logger.error(f"Chat ID не найден для пользователей: {user1_uuid}, {user2_uuid}")
                continue

            keyboard = [
                [InlineKeyboardButton("Да, давай :)", callback_data='yes_meet')],
                [InlineKeyboardButton("Нет, пока не нужно!", callback_data='no_meet')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            logger.info(f"Отправка сообщения пользователю {user1_uuid} ({user1_chat_id}) и {user2_uuid} ({user2_chat_id})")
            try:
                await context.bot.send_message(
                    chat_id=user1_chat_id,
                    text=f"ВЖУХХ! И я создал пару! Это {user1.get('name', 'Пользователь')} и {user2.get('name', 'Пользователь')} 😊!\n\n"
                         f"Напишите друг другу, и договоритесь о времени встречи или видеозвонка. Вы можете устроить онлайн-коворкинг 💻 или запланировать совместный кофе-брейк ☕️\n\n"
                         f"А можем вообще прямо сейчас сделать встречу в Google Meet, что скажешь? 🧐",
                    reply_markup=reply_markup
                )
            except BadRequest as e:
                logger.error(f"Ошибка при отправке сообщения пользователю {user1_uuid} ({user1_chat_id}): {e}")

            try:
                await context.bot.send_message(
                    chat_id=user2_chat_id,
                    text=f"ВЖУХХ! И я создал пару! Это {user1.get('name', 'Пользователь')} и {user2.get('name', 'Пользователь')} 😊!\n\n"
                         f"Напишите друг другу, и договоритесь о времени встречи или видеозвонка. Вы можете устроить онлайн-коворкинг 💻 или запланировать совместный кофе-брейк ☕️\n\n"
                         f"А можем вообще прямо сейчас сделать встречу в Google Meet, что скажешь? 🧐",
                    reply_markup=reply_markup
                )
            except BadRequest as e:
                logger.error(f"Ошибка при отправке сообщения пользователю {user2_uuid} ({user2_chat_id}): {e}")

    if remaining_users:
        for user_uuid in remaining_users:
            user = user_data_dict.get(user_uuid, {})
            user_chat_id = cycle_users_data.get(user_uuid)
            if not user_chat_id:
                logger.error(f"Chat ID не найден для пользователя: {user_uuid}")
                continue

            try:
                await context.bot.send_message(
                    chat_id=user_chat_id,
                    text=f"К сожалению, на этот раз не удалось найти пару для встречи. Но не волнуйтесь, вы автоматически будете включены в следующий цикл."
                )
            except BadRequest as e:
                logger.error(f"Ошибка при отправке сообщения пользователю {user_uuid} ({user_chat_id}): {e}")

    # Сохраняем оставшихся пользователей в cycle_users.json
    for user_uuid in remaining_users:
        cycle_users_data[user_uuid] = user_data_dict[user_uuid]['id']
    save_data(cycle_users_data, 'cycle_users.json')

    logger.info("Функция match завершена")

    # Удаление использованных пользователей из cycle_users
    cycle_users_data = {k: v for k, v in cycle_users_data.items() if k not in used_users}
    save_data(cycle_users_data, 'cycle_users.json')

async def leave_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Пользователь {update.message.from_user.id} оставляет отзыв.")
    
    keyboard = [
        [InlineKeyboardButton("💚 - неплохо", callback_data='feedback_1')],
        [InlineKeyboardButton("💚💚 - хорошо", callback_data='feedback_2')],
        [InlineKeyboardButton("💚💚💚 - было круто", callback_data='feedback_3')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text="Расскажи, как прошла ваша встреча?",
        reply_markup=reply_markup
    )

async def feedback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    feedback_responses = {
        'feedback_1': 'Спасибо за отзыв! Очень надеюсь, что в следующий раз будет лучше :)',
        'feedback_2': 'Спасибо за отзыв! Надеюсь, что все прошло хорошо :)',
        'feedback_3': 'Спасибо за отзыв! Рад слышать, до встречи на следующем цикле :)'
    }
    
    feedback_text = feedback_responses.get(query.data)
    
    user_id = context.user_data.get('id', str(uuid.uuid4()))
    feedback_data[user_id] = query.data
    save_data(feedback_data, 'feedback_data.json')
    
    await query.message.reply_text(feedback_text)

async def clear_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_IDS:
        await update.message.reply_text("OOPS! Эта команда доступна только администраторам.")
        return
    global user_data
    user_data = {}
    save_data(user_data, 'user_data.json')
    await update.message.reply_text("База данных успешно очищена!")

async def notify_admins(context, message: str):
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=message)
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение админу {admin_id}: {e}")

async def notify_cycle_user_count(context: ContextTypes.DEFAULT_TYPE):
    cycle_users = load_data('cycle_users.json', {})
    num_users = len(cycle_users)
    message = f"На данный момент в текущем цикле {num_users} пользователей."
    await notify_admins(context, message)


async def check_cycle_users(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Проверка пользователей цикла")
    if len(cycle_users) == 0:
        await notify_admins(context, "Нет пользователей в текущем цикле.")
    else:
        await notify_admins(context, f"В текущем цикле {len(cycle_users)} пользователей.")
    logger.info("Завершена проверка пользователей цикла")

def get_user_count_text(count):
    if count % 10 == 1 and count % 100 != 11:
        return f"{count} пользователь"
    elif 2 <= count % 10 <= 4 and (count % 100 < 10 or count % 100 >= 20):
        return f"{count} пользователя"
    else:
        return f"{count} пользователей"

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Исключение при обработке обновления:", exc_info=context.error)
    try:
        if update.message:
            await update.message.reply_text("Произошла ошибка. Попробуйте снова позже.")
        elif update.callback_query:
            await update.callback_query.message.reply_text("Произошла ошибка. Попробуйте снова позже.")
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение об ошибке: {e}")

async def set_commands(application):
    commands = [
        BotCommand("start", "Начать работу"),
        BotCommand("leave_feedback", "Оставить фидбек")
    ]
    await application.bot.set_my_commands(commands)

USER_DATA_FILE = "user_data.json"

async def send_message_to_chat(context: CallbackContext):
    job = context.job
    chat_id = job.data
    logger.info(f"Отправка сообщения в чат: {chat_id}")
    try:
        await context.bot.send_message(chat_id=chat_id, text="Ваше напоминание!")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")

async def notify_admins_task(context: CallbackContext):
    await notify_cycle_users_command(None, context)

async def run_match_task(context: CallbackContext):
    await match_logic(user_data, context)

async def main():
    global user_data, cycle_users, feedback_data, not_cycle_users

    application = ApplicationBuilder().token("7197628643:AAHqgdZSURQGrkAB6E22MP-cSjgKiFe0xrM").build()
    job_queue = application.job_queue

    user_data = load_data('user_data.json', {})
    cycle_users = load_data('cycle_users.json', {})
    feedback_data = load_data('feedback_data.json', {})
    not_cycle_users = load_data('not_cycle_users.json', {})
    logger.info(f"Загружены cycle users: {cycle_users}")
    logger.info(f"Загружены user data: {user_data}")

    minsk_tz = pytz.timezone('Europe/Minsk')

    # Уведомление администраторам в 9:50
    job_queue.run_daily(notify_admins_task, time=datetime.time(15, 13, 0, tzinfo=minsk_tz), name="notify_admins")

    # Запуск функции /match в 10:00
    job_queue.run_daily(run_match_task, time=datetime.time(20, 48, 0, tzinfo=minsk_tz), name="run_match")

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ASKING_EMAIL: [
                CallbackQueryHandler(button, pattern='^start_registration$'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)
            ],
            ASKING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            ASKING_POSITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_position)],
            CONFIRMING_NAME: [CallbackQueryHandler(confirm_name, pattern='^change_name$|^keep_name$')],
            CONFIRMING_POSITION: [CallbackQueryHandler(confirm_position, pattern='^change_position$|^keep_position$')],
            SHOWING_CARD: [
                CallbackQueryHandler(cycle_handler, pattern='^join_cycle$|^not_join_cycle$'),
                CallbackQueryHandler(button, pattern='^use_existing$|^new_cycle$|^start_registration$')
            ]
        },
        fallbacks=[],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('show_all_users', show_all_users))
    application.add_handler(CommandHandler('match', match))
    application.add_handler(CommandHandler('clear_database', clear_database))
    application.add_handler(CommandHandler('leave_feedback', leave_feedback))
    application.add_handler(CallbackQueryHandler(button_handler, pattern='^yes_meet$|^no_meet$'))
    application.add_handler(CallbackQueryHandler(feedback_handler, pattern='^feedback_1$|^feedback_2$|^feedback_3$'))
    application.add_error_handler(error_handler)

    await application.run_polling()

if __name__ == '__main__':
    nest_asyncio.apply()
    asyncio.run(main())