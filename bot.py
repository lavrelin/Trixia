import os
import logging
import random
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_GROUP_ID = int(os.environ.get('ADMIN_GROUP_ID', -4843909295))
USER_CHAT_ID = int(os.environ.get('USER_CHAT_ID', -1003088023508))
BUDAPEST_TZ = pytz.timezone('Europe/Budapest')

# Состояния для ConversationHandler
(REG_INSTAGRAM, REG_THREADS, REG_GENDER, REG_AGE,
 ADD_USDT, CREATE_TASK_TYPE, CREATE_TASK_LINKS,
 CREATE_TASK_COMMENT, EDIT_MYCOM, MYCOM_POSTS,
 MYCOM_COMMENTS, RAID_DESCRIPTION) = range(12)

# База данных (в продакшене использовать PostgreSQL)
users_db: Dict = {}
tasks_db: List = []
frozen_tasks: Dict = {}
admin_tasks: List = []
mycom_contest: Dict = {
    'active': False,
    'registration': False,
    'participants': {},
    'start_time': None,
    'duration': 120
}
mycom_participants = {}
mycom_banned = []
mycom_history = []

raid_data: Dict = {
    'status': 'inactive',
    'description': '',
    'participants': [],
    'start_time': None,
    'duration': 0,
    'winners_history': []
}

# Квесты для daily (50 заданий)
DAILY_QUESTS = [
    "Поставь лайк на 3 поста в Instagram",
    "Напиши 2 комментария под постами",
    "Подпишись на 1 новый аккаунт",
    "Поделись историей в Instagram",
    "Сохрани 5 постов в закладки",
    "Просмотри 10 сторис",
    "Отметь друга в комментарии",
    "Используй 3 хэштега в посте",
    "Ответь на 2 сторис",
    "Отправь сообщение 3 подписчикам",
    "Добавь пост в сохраненные коллекции",
    "Используй фильтр в сторис",
    "Отметь локацию в посте",
    "Сделай репост в сторис",
    "Ответь на 3 комментария под своим постом",
    "Используй опрос в сторис",
    "Добавь музыку в сторис",
    "Поставь реакцию на 5 сторис",
    "Прокомментируй пост с вопросом",
    "Поддержи малый бизнес лайком",
    "Найди новый тренд и используй его",
    "Сделай бумеранг сторис",
    "Используй стикер с обратным отсчетом",
    "Отметь бренд в посте",
    "Напиши мотивирующий комментарий",
    "Поделись рецептом в сторис",
    "Используй стикер с вопросом",
    "Сделай карусельный пост",
    "Добавь GIF в сторис",
    "Прокомментируй с эмодзи",
    "Используй стикер с викториной",
    "Поставь лайк конкуренту",
    "Найди и подпишись на микроблогера",
    "Используй слайдер стикер",
    "Напиши длинный комментарий (50+ слов)",
    "Сделай коллаборацию в сторис",
    "Используй таймер в рилс",
    "Добавь субтитры к рилс",
    "Поставь лайк на старый пост (год+)",
    "Прокомментируй иностранный пост",
    "Используй стикер с донатами",
    "Сделай инфографику в посте",
    "Поддержи благотворительность",
    "Используй тренд-аудио в рилс",
    "Напиши совет в комментарии",
    "Поделись воспоминанием",
    "Используй стикер с ссылкой",
    "Сделай закулисный контент",
    "Отметь до/после",
    "Поддержи местный бизнес"
]


def get_user_keyboard():
    """Основная клавиатура пользователя"""
    keyboard = [
        [InlineKeyboardButton("🧊 Pool", callback_data="pool"),
         InlineKeyboardButton("🪃 Trixiki", callback_data="trixiki")],
        [InlineKeyboardButton("❤️ Like/Comment/Follow", callback_data="actions")],
        [InlineKeyboardButton("🌀 Profile", callback_data="profile")]
    ]
    return InlineKeyboardMarkup(keyboard)


def generate_user_number(gender: str) -> int:
    """Генерация уникального номера пользователя"""
    while True:
        if gender.upper() == 'Ж':
            number = random.randrange(1, 10000, 2)
        else:
            number = random.randrange(2, 10000, 2)
        
        if not any(u.get('number') == number for u in users_db.values()):
            return number


async def reset_daily_tasks(context: ContextTypes.DEFAULT_TYPE):
    """Ежедневный сброс в 20:00"""
    budapest_time = datetime.now(BUDAPEST_TZ)
    logger.info(f"Daily reset at {budapest_time}")
    
    tasks_db.clear()
    for user_id, user_data in users_db.items():
        user_data['daily_claimed'] = False
        user_data['trixiki'] = 0
    
    for user_id in users_db.keys():
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🌙 Новый день! Триксики сброшены.\nИспользуй /daily!"
            )
        except Exception as e:
            logger.error(f"Error notifying user {user_id}: {e}")


# ============== ОСНОВНЫЕ КОМАНДЫ ==============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Стартовое сообщение"""
    user_id = update.effective_user.id
    
    if user_id in users_db:
        await update.message.reply_text(
            f"С возвращением, {update.effective_user.first_name}! 🎉",
            reply_markup=get_user_keyboard()
        )
    else:
        await update.message.reply_text(
            "👋 Добро пожаловать в Trixiki Bot!\n\n"
            "Бот для обмена активностью в Instagram/Threads.\n"
            "Используй /reg для регистрации."
        )


async def reg_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало регистрации"""
    user_id = update.effective_user.id
    
    if user_id in users_db:
        await update.message.reply_text("Вы уже зарегистрированы! ✅")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📝 Регистрация\n\nВведите ваш Instagram аккаунт (@username):"
    )
    return REG_INSTAGRAM


async def reg_instagram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['instagram'] = update.message.text.strip()
    await update.message.reply_text("Теперь введите ваш Threads аккаунт:")
    return REG_THREADS


async def reg_threads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['threads'] = update.message.text.strip()
    
    keyboard = [
        [InlineKeyboardButton("Мужской", callback_data="gender_m"),
         InlineKeyboardButton("Женский", callback_data="gender_f")]
    ]
    await update.message.reply_text(
        "Выберите ваш пол:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return REG_GENDER


async def reg_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    gender = 'М' if query.data == 'gender_m' else 'Ж'
    context.user_data['gender'] = gender
    
    await query.edit_message_text("Введите ваш возраст:")
    return REG_AGE


async def reg_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text.strip())
        if age < 13 or age > 100:
            await update.message.reply_text("Некорректный возраст. Попробуйте снова:")
            return REG_AGE
        
        user_id = update.effective_user.id
        user_number = generate_user_number(context.user_data['gender'])
        
        users_db[user_id] = {
            'number': user_number,
            'username': update.effective_user.username,
            'instagram': context.user_data['instagram'],
            'threads': context.user_data['threads'],
            'gender': context.user_data['gender'],
            'age': age,
            'trixiki': 15,
            'max_limit': 15,
            'daily_claimed': False,
            'usdt_address': None,
            'subscribed': False,
            'banned': False,
            'can_create_tasks': True,
            'stats': {
                'likes_given': 0,
                'likes_received': 0,
                'comments_given': 0,
                'comments_received': 0,
                'follows_given': 0,
                'follows_received': 0
            },
            'achievements': [],
            'created_at': datetime.now(BUDAPEST_TZ).isoformat(),
            'last_interaction': {}
        }
        
        await update.message.reply_text(
            f"✅ Регистрация завершена!\n\n"
            f"🆔 Ваш номер: {user_number}\n"
            f"📸 Instagram: {context.user_data['instagram']}\n"
            f"🧵 Threads: {context.user_data['threads']}\n"
            f"🪃 Стартовый баланс: 15 триксиков\n\n"
            f"Используйте /daily для ежедневного бонуса!",
            reply_markup=get_user_keyboard()
        )
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("Введите корректный возраст (число):")
        return REG_AGE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Операция отменена.", reply_markup=get_user_keyboard())
    return ConversationHandler.END


async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ежедневный бонус и квест"""
    user_id = update.effective_user.id
    
    if user_id not in users_db:
        await update.message.reply_text("Сначала зарегистрируйтесь: /reg")
        return
    
    user = users_db[user_id]
    
    if user['daily_claimed']:
        await update.message.reply_text("Вы уже получили свой ежедневный бонус! ⏰")
        return
    
    base_bonus = random.randint(3, 9)
    quest = random.choice(DAILY_QUESTS)
    quest_reward = user['max_limit']
    
    keyboard = [[InlineKeyboardButton("✅ Выполнил квест", callback_data="daily_quest_done")]]
    
    await update.message.reply_text(
        f"🎁 Ежедневный бонус: +{base_bonus} триксиков!\n\n"
        f"📋 Ваш квест дня:\n{quest}\n\n"
        f"🎯 Награда за квест: {quest_reward} триксиков\n\n"
        f"Нажмите кнопку после выполнения:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    user['trixiki'] = min(user['trixiki'] + base_bonus, user['max_limit'])
    user['daily_claimed'] = True


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик inline кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if query.data == "profile":
        await show_profile(update, context)
    elif query.data == "trixiki":
        await show_trixiki(update, context)
    elif query.data == "pool":
        await show_pool(update, context)
    elif query.data == "actions":
        await show_actions_menu(update, context)
    elif query.data == "daily_quest_done":
        await complete_daily_quest(update, context)


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query if update.callback_query else None
    user_id = update.effective_user.id
    
    if user_id not in users_db:
        message = "Сначала зарегистрируйтесь: /reg"
        if query:
            await query.edit_message_text(message)
        else:
            await update.message.reply_text(message)
        return
    
    user = users_db[user_id]
    stats = user['stats']
    
    profile_text = (
        f"🌀 ПРОФИЛЬ\n\n"
        f"🆔 Номер: {user['number']}\n"
        f"👤 {user['gender']} | {user['age']} лет\n"
        f"📸 Instagram: {user['instagram']}\n"
        f"🧵 Threads: {user['threads']}\n\n"
        f"🪃 Триксики: {user['trixiki']}/{user['max_limit']}\n\n"
        f"📊 СТАТИСТИКА:\n"
        f"❤️ Лайков: {stats['likes_given']}/{stats['likes_received']}\n"
        f"💬 Комментариев: {stats['comments_given']}/{stats['comments_received']}\n"
        f"👥 Подписок: {stats['follows_given']}/{stats['follows_received']}\n"
    )
    
    if user['achievements']:
        profile_text += f"\n🏆 Достижений: {len(user['achievements'])}"
    
    if query:
        await query.edit_message_text(profile_text, reply_markup=get_user_keyboard())
    else:
        await update.message.reply_text(profile_text, reply_markup=get_user_keyboard())


async def show_trixiki(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    
    if user_id not in users_db:
        await query.edit_message_text("Зарегистрируйтесь: /reg")
        return
    
    user = users_db[user_id]
    await query.edit_message_text(
        f"🪃 ВАШ БАЛАНС\n\n"
        f"Триксики: {user['trixiki']}/{user['max_limit']}\n\n"
        f"💡 Используйте триксики для создания заданий\n"
        f"✨ Выполняйте задания других для заработка",
        reply_markup=get_user_keyboard()
    )


async def show_pool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not tasks_db:
        await query.edit_message_text(
            "🧊 Пул заданий пуст!\n\nСоздайте задание через ❤️ Like/Comment/Follow",
            reply_markup=get_user_keyboard()
        )
        return
    
    available_tasks = [t for t in tasks_db if t['creator_id'] != user_id][:5]
    
    if not available_tasks:
        await query.edit_message_text(
            "Нет доступных заданий для вас.",
            reply_markup=get_user_keyboard()
        )
        return
    
    text = "🧊 ДОСТУПНЫЕ ЗАДАНИЯ:\n\n"
    for idx, task in enumerate(available_tasks, 1):
        creator = users_db.get(task['creator_id'], {})
        text += (
            f"{idx}. {task['type'].upper()} | {task['reward']} 🪃\n"
            f"   От: @{creator.get('username', 'unknown')}\n\n"
        )
    
    text += "Используйте /dotask <номер> для выполнения"
    await query.edit_message_text(text, reply_markup=get_user_keyboard())


async def show_actions_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    
    if user_id not in users_db:
        await query.edit_message_text("Зарегистрируйтесь: /reg")
        return
    
    user = users_db[user_id]
    
    keyboard = [
        [InlineKeyboardButton("❤️ Like (3🪃)", callback_data="create_like"),
         InlineKeyboardButton("💬 Comment (4🪃)", callback_data="create_comment")],
        [InlineKeyboardButton("💬 Special (10🪃)", callback_data="create_special"),
         InlineKeyboardButton("👥 Follow (5🪃)", callback_data="create_follow")],
        [InlineKeyboardButton("« Назад", callback_data="back_main")]
    ]
    
    await query.edit_message_text(
        f"❤️ СОЗДАТЬ ЗАДАНИЕ\n\n"
        f"Ваш баланс: {user['trixiki']} 🪃\n\n"
        f"Выберите тип задания:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def complete_daily_quest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    
    if user_id not in users_db:
        return
    
    user = users_db[user_id]
    reward = user['max_limit']
    user['trixiki'] = min(user['trixiki'] + reward, user['max_limit'])
    
    await query.edit_message_text(
        f"✅ Квест выполнен! +{reward} 🪃\n\n"
        f"Текущий баланс: {user['trixiki']}/{user['max_limit']}"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 СПРАВКА TRIXIKI BOT\n\n"
        "🎯 ОСНОВНЫЕ:\n"
        "/start - Начало\n"
        "/reg - Регистрация\n"
        "/daily - Ежедневный бонус\n"
        "/profile - Профиль\n"
        "/trixiki - Баланс\n"
        "/pool - Задания\n"
        "/help - Справка\n\n"
        "📊 СТАТИСТИКА:\n"
        "/stats [@user] - Статистика\n"
        "/top - Топ игроков\n\n"
        "🎮 ИГРОВЫЕ:\n"
        "/raid - Рейды\n"
        "/mycom - Конкурс\n"
        "/quest - Квесты\n\n"
        "💰 ЦЕНЫ:\n"
        "❤️ Like - 3 🪃\n"
        "💬 Comment - 4 🪃\n"
        "💬 Special - 10 🪃\n"
        "👥 Follow - 5 🪃\n\n"
        "⚠️ ПРАВИЛА:\n"
        "• Не удалять в течение недели\n"
        "• Один человек = один аккаунт\n"
        "• /check @user - жалоба"
    )
    await update.message.reply_text(help_text)


# ============== АДМИН-КОМАНДЫ ==============

async def admin_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /limit @username 1-50")
        return
    
    username = context.args[0].replace('@', '')
    try:
        new_limit = int(context.args[1])
        if new_limit < 1 or new_limit > 50:
            await update.message.reply_text("Лимит: 1-50")
            return
    except ValueError:
        await update.message.reply_text("Некорректное значение")
        return
    
    for user_id, user_data in users_db.items():
        if user_data.get('username') == username:
            user_data['max_limit'] = new_limit
            await update.message.reply_text(f"✅ Лимит @{username}: {new_limit}")
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎉 Ваш лимит изменен на {new_limit} триксиков!"
                )
            except Exception as e:
                logger.error(f"Error: {e}")
            return
    
    await update.message.reply_text(f"Пользователь @{username} не найден")


async def admin_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /balance @username")
        return
    
    username = context.args[0].replace('@', '')
    
    for user_data in users_db.values():
        if user_data.get('username') == username:
            await update.message.reply_text(
                f"💰 @{username}: {user_data['trixiki']}/{user_data['max_limit']} 🪃"
            )
            return
    
    await update.message.reply_text(f"@{username} не найден")


async def giftstart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Случайные подарки активным пользователям"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    daily_users = [uid for uid, u in users_db.items() if u.get('daily_claimed')]
    
    if not daily_users:
        await update.message.reply_text("Нет активных пользователей сегодня")
        return
    
    winners_count = random.randint(1, 3)
    winners = random.sample(daily_users, min(winners_count, len(daily_users)))
    
    result = "🎁 ПОДАРКИ:\n\n"
    
    for winner_id in winners:
        user = users_db[winner_id]
        user['max_limit'] = min(user['max_limit'] + 1, 50)
        result += f"@{user.get('username', 'unknown')} +1 к лимиту\n"
        
        try:
            await context.bot.send_message(
                chat_id=winner_id,
                text="🎁 Поздравляем! Ваш лимит увеличен на +1!"
            )
        except Exception as e:
            logger.error(f"Error: {e}")
    
    await update.message.reply_text(result)


# ============== ОСНОВНАЯ ФУНКЦИЯ ==============

def main():
    """Запуск бота"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен!")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчик регистрации
    reg_handler = ConversationHandler(
        entry_points=[CommandHandler('reg', reg_start)],
        states={
            REG_INSTAGRAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_instagram)],
            REG_THREADS: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_threads)],
            REG_GENDER: [CallbackQueryHandler(reg_gender, pattern='^gender_')],
            REG_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_age)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Регистрация команд
    application.add_handler(CommandHandler('start', start))
    application.add_handler(reg_handler)
    application.add_handler(CommandHandler('daily', daily_command))
    application.add_handler(CommandHandler('help', help_command))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Админ команды
    application.add_handler(CommandHandler('limit', admin_limit))
    application.add_handler(CommandHandler('balance', admin_balance))
    application.add_handler(CommandHandler('giftstart', giftstart_command))
    
    # Ежедневный сброс в 20:00 Budapest
    job_queue = application.job_queue
    budapest_time = datetime.now(BUDAPEST_TZ).replace(hour=20, minute=0, second=0)
    job_queue.run_daily(reset_daily_tasks, time=budapest_time.time())
    
    logger.info("🚀 Trixiki Bot запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
import os
import logging
import random
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_GROUP_ID = -4843909295
USER_CHAT_ID = -1003088023508
BUDAPEST_TZ = pytz.timezone('Europe/Budapest')

# Состояния для ConversationHandler
(REG_INSTAGRAM, REG_THREADS, REG_GENDER, REG_AGE,
 ADD_USDT, CREATE_TASK_TYPE, CREATE_TASK_LINKS,
 CREATE_TASK_COMMENT, EDIT_MYCOM, MYCOM_POSTS,
 MYCOM_COMMENTS, RAID_DESCRIPTION) = range(12)

# База данных (в продакшене использовать PostgreSQL)
users_db: Dict = {}
tasks_db: List = []
frozen_tasks: Dict = {}
admin_tasks: List = []
mycom_contest: Dict = {
    'active': False,
    'registration': False,
    'participants': {},
    'start_time': None,
    'duration': 120
}
raid_data: Dict = {
    'status': 'inactive',  # inactive, processing, active
    'description': '',
    'participants': [],
    'start_time': None,
    'duration': 0
}

# Квесты для daily
DAILY_QUESTS = [
    "Поставь лайк на 3 поста в Instagram",
    "Напиши 2 комментария под постами",
    "Подпишись на 1 новый аккаунт",
    "Поделись историей в Instagram",
    "Сохрани 5 постов в закладки",
    "Просмотри 10 сторис",
    "Отметь друга в комментарии",
    "Используй 3 хэштега в посте",
    "Ответь на 2 сторис",
    "Отправь сообщение 3 подписчикам"
    # ... добавить еще 40 квестов
]


# Вспомогательные функции
def get_user_keyboard():
    """Основная клавиатура пользователя"""
    keyboard = [
        [InlineKeyboardButton("🧊 Pool", callback_data="pool"),
         InlineKeyboardButton("🪃 Trixiki", callback_data="trixiki")],
        [InlineKeyboardButton("❤️ Like/Comment/Follow", callback_data="actions")],
        [InlineKeyboardButton("🌀 Profile", callback_data="profile"),
         InlineKeyboardButton("💬 Chat", url=f"https://t.me/c/{str(USER_CHAT_ID)[4:]}/1")]
    ]
    return InlineKeyboardMarkup(keyboard)


def generate_user_number(gender: str) -> int:
    """Генерация уникального номера пользователя"""
    while True:
        if gender.upper() == 'Ж':
            number = random.randrange(1, 10000, 2)  # нечетные
        else:
            number = random.randrange(2, 10000, 2)  # четные
        
        if not any(u.get('number') == number for u in users_db.values()):
            return number


async def reset_daily_tasks(context: ContextTypes.DEFAULT_TYPE):
    """Ежедневный сброс в 20:00 по Будапешту"""
    budapest_time = datetime.now(BUDAPEST_TZ)
    logger.info(f"Daily reset at {budapest_time}")
    
    # Очистка заданий и сброс триксиков
    tasks_db.clear()
    for user_id, user_data in users_db.items():
        user_data['daily_claimed'] = False
        user_data['trixiki'] = 0
    
    # Уведомление пользователей
    for user_id in users_db.keys():
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🌙 Новый день начался! Триксики сброшены.\n"
                     "Используй /daily для получения бонуса!"
            )
        except Exception as e:
            logger.error(f"Error notifying user {user_id}: {e}")


# Команды бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Стартовое сообщение"""
    user_id = update.effective_user.id
    
    if user_id in users_db:
        await update.message.reply_text(
            f"С возвращением, {update.effective_user.first_name}! 🎉",
            reply_markup=get_user_keyboard()
        )
    else:
        await update.message.reply_text(
            "👋 Добро пожаловать в Trixiki Bot!\n\n"
            "Это бот для обмена активностью в Instagram и Threads.\n"
            "Используй команду /reg для регистрации."
        )


async def reg_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало регистрации"""
    user_id = update.effective_user.id
    
    if user_id in users_db:
        await update.message.reply_text("Вы уже зарегистрированы! ✅")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📝 Регистрация\n\n"
        "Введите ваш Instagram аккаунт (например: @username):"
    )
    return REG_INSTAGRAM


async def reg_instagram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение Instagram"""
    context.user_data['instagram'] = update.message.text.strip()
    await update.message.reply_text("Теперь введите ваш Threads аккаунт:")
    return REG_THREADS


async def reg_threads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение Threads"""
    context.user_data['threads'] = update.message.text.strip()
    
    keyboard = [
        [InlineKeyboardButton("Мужской", callback_data="gender_m"),
         InlineKeyboardButton("Женский", callback_data="gender_f")]
    ]
    await update.message.reply_text(
        "Выберите ваш пол:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return REG_GENDER


async def reg_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение пола"""
    query = update.callback_query
    await query.answer()
    
    gender = 'М' if query.data == 'gender_m' else 'Ж'
    context.user_data['gender'] = gender
    
    await query.edit_message_text("Введите ваш возраст:")
    return REG_AGE


async def reg_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение регистрации"""
    try:
        age = int(update.message.text.strip())
        if age < 13 or age > 100:
            await update.message.reply_text("Некорректный возраст. Попробуйте снова:")
            return REG_AGE
        
        user_id = update.effective_user.id
        user_number = generate_user_number(context.user_data['gender'])
        
        users_db[user_id] = {
            'number': user_number,
            'username': update.effective_user.username,
            'instagram': context.user_data['instagram'],
            'threads': context.user_data['threads'],
            'gender': context.user_data['gender'],
            'age': age,
            'trixiki': 15,
            'max_limit': 15,
            'daily_claimed': False,
            'usdt_address': None,
            'subscribed': False,
            'banned': False,
            'stats': {
                'likes_given': 0,
                'likes_received': 0,
                'comments_given': 0,
                'comments_received': 0,
                'follows_given': 0,
                'follows_received': 0
            },
            'achievements': [],
            'created_at': datetime.now(BUDAPEST_TZ).isoformat()
        }
        
        await update.message.reply_text(
            f"✅ Регистрация завершена!\n\n"
            f"🆔 Ваш номер: {user_number}\n"
            f"📸 Instagram: {context.user_data['instagram']}\n"
            f"🧵 Threads: {context.user_data['threads']}\n"
            f"🪃 Стартовый баланс: 15 триксиков\n\n"
            f"Используйте /daily для получения ежедневного бонуса!",
            reply_markup=get_user_keyboard()
        )
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите корректный возраст (число):")
        return REG_AGE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущей операции"""
    await update.message.reply_text(
        "Операция отменена.",
        reply_markup=get_user_keyboard()
    )
    return ConversationHandler.END


async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ежедневный бонус и квест"""
    user_id = update.effective_user.id
    
    if user_id not in users_db:
        await update.message.reply_text("Сначала зарегистрируйтесь: /reg")
        return
    
    user = users_db[user_id]
    
    if user['daily_claimed']:
        await update.message.reply_text("Вы уже получили свой ежедневный бонус! ⏰")
        return
    
    # Базовый бонус
    base_bonus = random.randint(3, 9)
    
    # Квест
    quest = random.choice(DAILY_QUESTS)
    quest_reward = user['max_limit']
    
    keyboard = [
        [InlineKeyboardButton("✅ Выполнил квест", callback_data="daily_quest_done")]
    ]
    
    await update.message.reply_text(
        f"🎁 Ежедневный бонус: +{base_bonus} триксиков!\n\n"
        f"📋 Ваш квест дня:\n{quest}\n\n"
        f"🎯 Награда за квест: {quest_reward} триксиков\n\n"
        f"Нажмите кнопку после выполнения:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    user['trixiki'] = min(user['trixiki'] + base_bonus, user['max_limit'])
    user['daily_claimed'] = True


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ профиля"""
    user_id = update.effective_user.id
    
    if user_id not in users_db:
        await update.message.reply_text("Сначала зарегистрируйтесь: /reg")
        return
    
    user = users_db[user_id]
    stats = user['stats']
    
    profile_text = (
        f"🌀 ПРОФИЛЬ\n\n"
        f"🆔 Номер: {user['number']}\n"
        f"👤 Пол: {user['gender']} | Возраст: {user['age']}\n"
        f"📸 Instagram: {user['instagram']}\n"
        f"🧵 Threads: {user['threads']}\n\n"
        f"🪃 Триксики: {user['trixiki']}/{user['max_limit']}\n\n"
        f"📊 СТАТИСТИКА:\n"
        f"❤️ Лайков отдано: {stats['likes_given']}\n"
        f"❤️ Лайков получено: {stats['likes_received']}\n"
        f"💬 Комментариев: {stats['comments_given']}/{stats['comments_received']}\n"
        f"👥 Подписок: {stats['follows_given']}/{stats['follows_received']}\n"
    )
    
    if user['achievements']:
        profile_text += f"\n🏆 Достижения: {len(user['achievements'])}"
    
    await update.message.reply_text(profile_text, reply_markup=get_user_keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка"""
    help_text = (
        "📖 СПРАВКА TRIXIKI BOT\n\n"
        "🎯 ОСНОВНЫЕ КОМАНДЫ:\n"
        "/reg - Регистрация\n"
        "/daily - Ежедневный бонус\n"
        "/profile - Ваш профиль\n"
        "/trixiki - Баланс\n"
        "/pool - Задания\n\n"
        "❤️ ДЕЙСТВИЯ:\n"
        "• Like - 3 триксика (макс 3 поста)\n"
        "• Comment - 4 триксика (макс 2)\n"
        "• Special Comment - 10 триксиков\n"
        "• Follow - 5 триксиков\n\n"
        "📋 ДОПОЛНИТЕЛЬНО:\n"
        "/stats @username - Статистика\n"
        "/check @username - Жалоба\n"
        "/top - Топ пользователей\n"
        "/quest - Активные квесты\n"
        "/raid - Рейд система\n"
        "/mycom - Конкурс комментариев\n\n"
        "⚠️ ПРАВИЛА:\n"
        "❌ Запрещено в течение недели:\n"
        "- Отменять подписки\n"
        "- Удалять лайки\n"
        "- Удалять комментарии\n\n"
        "Фейковые аккаунты блокируются!"
    )
    
    await update.message.reply_text(help_text)


# Основная функция
def main():
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчик регистрации
    reg_handler = ConversationHandler(
        entry_points=[CommandHandler('reg', reg_start)],
        states={
            REG_INSTAGRAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_instagram)],
            REG_THREADS: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_threads)],
            REG_GENDER: [CallbackQueryHandler(reg_gender, pattern='^gender_')],
            REG_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_age)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler('start', start))
    application.add_handler(reg_handler)
    application.add_handler(CommandHandler('daily', daily_command))
    application.add_handler(CommandHandler('profile', profile_command))
    application.add_handler(CommandHandler('help', help_command))
    
    # Настройка ежедневного сброса (20:00 Budapest)
    job_queue = application.job_queue
    budapest_time = datetime.now(BUDAPEST_TZ).replace(hour=20, minute=0, second=0)
    job_queue.run_daily(reset_daily_tasks, time=budapest_time.time())
    
    # Запуск бота
    logger.info("Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
