"""
Пользовательские команды
"""
import random
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import BUDAPEST_TZ, USER_CHAT_ID, DAILY_BONUS_MIN, DAILY_BONUS_MAX
from database import get_user, get_available_tasks, user_reports, announcement_subscribers, users_db
from utils import get_user_keyboard, format_stats
from quests import DAILY_QUESTS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if user:
        await update.message.reply_text(
            f"С возвращением, {update.effective_user.first_name}! 🎉",
            reply_markup=get_user_keyboard()
        )
    else:
        await update.message.reply_text(
            "👋 Добро пожаловать в Trixiki Bot!\n\n"
            "🎯 Обменивайся активностью в Instagram/Threads\n"
            "🪃 Зарабатывай триксики\n"
            "🏆 Получай достижения\n\n"
            "Используй /reg для регистрации!"
        )


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /daily"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user:
        await update.message.reply_text("Сначала зарегистрируйтесь: /reg")
        return
    
    if user['daily_claimed']:
        await update.message.reply_text(
            "⏰ Вы уже получили ежедневный бонус!\n"
            "Следующий в 00:00 по Будапешту"
        )
        return
    
    base_bonus = random.randint(DAILY_BONUS_MIN, DAILY_BONUS_MAX)
    quest = random.choice(DAILY_QUESTS)
    quest_reward = user['max_limit']
    
    keyboard = [[InlineKeyboardButton("✅ Выполнил квест", callback_data="quest_done")]]
    
    await update.message.reply_text(
        f"🎁 ЕЖЕДНЕВНЫЙ БОНУС\n\n"
        f"Получено: +{base_bonus} 🪃\n\n"
        f"📋 Квест дня:\n{quest}\n\n"
        f"🎯 Награда: {quest_reward} 🪃\n\n"
        f"Выполните квест и нажмите кнопку:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    user['trixiki'] = min(user['trixiki'] + base_bonus, user['max_limit'])
    user['daily_claimed'] = True


async def pool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /pool"""
    user_id = update.effective_user.id
    
    if not get_user(user_id):
        await update.message.reply_text("Сначала зарегистрируйтесь: /reg")
        return
    
    tasks = get_available_tasks(user_id, 10)
    
    if not tasks:
        await update.message.reply_text(
            "🧊 Пул заданий пуст!\n\n"
            "Создайте задание через ❤️ Like/Comment/Follow",
            reply_markup=get_user_keyboard()
        )
        return
    
    text = "🧊 ДОСТУПНЫЕ ЗАДАНИЯ:\n\n"
    buttons = []
    
    for idx, task in enumerate(tasks, 1):
        creator = users_db.get(task['creator_id'], {})
        text += (
            f"{idx}. {task['type'].upper()}\n"
            f"   Награда: {task['reward']} 🪃\n"
            f"   От: @{creator.get('username', 'unknown')}\n\n"
        )
        buttons.append([InlineKeyboardButton(
            f"✅ Выполнить #{idx}",
            callback_data=f"dotask_{task['id']}"
        )])
    
    buttons.append([InlineKeyboardButton("🔄 Обновить", callback_data="pool")])
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats"""
    if len(context.args) == 0:
        target_id = update.effective_user.id
    else:
        username = context.args[0].replace('@', '')
        target_id = None
        for uid, udata in users_db.items():
            if udata.get('username') == username:
                target_id = uid
                break
        
        if not target_id:
            await update.message.reply_text("❌ Пользователь не найден")
            return
    
    user = get_user(target_id)
    if not user:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    text = (
        f"📊 СТАТИСТИКА @{user.get('username', 'unknown')}\n\n"
        f"{format_stats(user['stats'])}\n\n"
        f"🏆 Достижений: {len(user['achievements'])}\n"
        f"🪃 Лимит: {user['max_limit']}"
    )
    
    await update.message.reply_text(text)


async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /top"""
    keyboard = [
        [InlineKeyboardButton("❤️ Лайки", callback_data="top_likes")],
        [InlineKeyboardButton("💬 Комментарии", callback_data="top_comments")],
        [InlineKeyboardButton("👥 Подписки", callback_data="top_follows")],
        [InlineKeyboardButton("🪃 Лимит", callback_data="top_limit")]
    ]
    
    await update.message.reply_text(
        "🏆 РЕЙТИНГ\n\nВыберите категорию:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /check"""
    from config import ADMIN_GROUP_ID
    
    user_id = update.effective_user.id
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Использование: /check @username причина\n\n"
            "Можно отправлять 1 жалобу в час"
        )
        return
    
    # Проверка лимита
    last_report = user_reports.get(user_id)
    if last_report:
        time_passed = (datetime.now(BUDAPEST_TZ) - last_report).total_seconds()
        if time_passed < 3600:
            minutes_left = int((3600 - time_passed) / 60)
            await update.message.reply_text(f"⏰ Следующая жалоба через {minutes_left} минут")
            return
    
    username = context.args[0].replace('@', '')
    reason = ' '.join(context.args[1:])
    reporter = update.effective_user
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=(
                f"⚠️ ЖАЛОБА\n\n"
                f"От: @{reporter.username}\n"
                f"На: @{username}\n"
                f"Причина: {reason}"
            )
        )
        
        user_reports[user_id] = datetime.now(BUDAPEST_TZ)
        await update.message.reply_text("✅ Жалоба отправлена администрации")
    except Exception as e:
        await update.message.reply_text("❌ Ошибка отправки")


async def randompool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /randompool"""
    user_id = update.effective_user.id
    
    if not get_user(user_id):
        await update.message.reply_text("Зарегистрируйтесь: /reg")
        return
    
    tasks = get_available_tasks(user_id, 999)
    
    if not tasks:
        await update.message.reply_text("🧊 Нет доступных заданий")
        return
    
    task = random.choice(tasks)
    creator = users_db.get(task['creator_id'], {})
    
    text = (
        f"🎲 СЛУЧАЙНОЕ ЗАДАНИЕ\n\n"
        f"Тип: {task['type'].upper()}\n"
        f"От: @{creator.get('username', 'unknown')}\n"
        f"Ссылка: {task['link']}\n"
    )
    
    if 'comment' in task:
        text += f"\nКомментарий:\n{task['comment']}\n"
    
    text += f"\n💰 Награда: {task['reward']} 🪃"
    
    keyboard = [[InlineKeyboardButton("✅ Выполнить", callback_data=f"dotask_{task['id']}")]]
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def addusdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /addusdt"""
    user_id = update.effective_user.id
    
    if not get_user(user_id):
        await update.message.reply_text("Зарегистрируйтесь: /reg")
        return
    
    await update.message.reply_text(
        "🔐 USDT TRC-20\n\n"
        "Введите ваш USDT TRC-20 адрес:\n"
        "(Начинается с T...)"
    )
    
    context.user_data['adding_usdt'] = True


async def donate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /donate"""
    from database import donations
    
    keyboard = [
        [InlineKeyboardButton("🎯 Цель", callback_data="donate_goal")],
        [InlineKeyboardButton("👥 Донаторы", callback_data="donate_donors")],
        [InlineKeyboardButton("💳 Реквизиты", callback_data="donate_details")],
        [InlineKeyboardButton("📊 Отчеты", callback_data="donate_reports")]
    ]
    
    await update.message.reply_text(
        f"💳 ДОНАТЫ\n\n"
        f"Цель: {donations['goal']}\n"
        f"Собрано: {donations['amount']}\n\n"
        f"Поддержите развитие проекта!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def onanons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /onanons"""
    user_id = update.effective_user.id
    
    if user_id not in announcement_subscribers:
        announcement_subscribers.append(user_id)
    
    await update.message.reply_text(
        "✅ Анонсы включены!\n\n"
        "Вы будете получать уведомления о новых заданиях"
    )


async def offanons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /offanons"""
    user_id = update.effective_user.id
    
    if user_id in announcement_subscribers:
        announcement_subscribers.remove(user_id)
    
    await update.message.reply_text("❌ Анонсы отключены")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = (
        "📖 СПРАВКА TRIXIKI BOT\n\n"
        "🎯 ОСНОВНЫЕ:\n"
        "/start - Начало\n"
        "/reg - Регистрация\n"
        "/daily - Ежедневный бонус\n"
        "/profile - Профиль\n"
        "/trixiki - Баланс\n"
        "/pool - Задания\n"
        "/randompool - Случайное задание\n\n"
        "📊 СТАТИСТИКА:\n"
        "/stats [@user] - Статистика\n"
        "/top - Рейтинг\n\n"
        "💰 ЦЕНЫ:\n"
        "❤️ Like - 3 🪃 (макс 3/день)\n"
        "💬 Comment - 4 🪃 (макс 2/день)\n"
        "💬 Special - 10 🪃\n"
        "👥 Follow - 5 🪃\n\n"
        "🔧 ДОПОЛНИТЕЛЬНО:\n"
        "/addusdt - Добавить USDT адрес\n"
        "/donate - Донаты\n"
        "/check @user - Жалоба (1/час)\n"
        "/onanons - Включить анонсы\n"
        "/offanons - Отключить анонсы\n\n"
        "⚠️ ПРАВИЛА:\n"
        "• Не удалять в течение недели\n"
        "• Один человек = один аккаунт\n"
        "• Фейковые аккаунты блокируются\n"
        "• Взаимодействие раз в 8 часов\n\n"
        f"💬 Чат: https://t.me/c/{str(USER_CHAT_ID)[4:]}/1"
    )
    
    await update.message.reply_text(help_text)
