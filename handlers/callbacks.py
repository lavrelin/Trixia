"""
Обработчики callback кнопок
"""
from telegram import Update
from telegram.ext import ContextTypes

from database import get_user
from utils import get_user_keyboard, format_stats


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Маршрутизация callback запросов"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "profile":
        await show_profile(query, context)
    elif data == "trixiki":
        await show_trixiki(query, context)
    elif data == "pool":
        await show_pool(query, context)
    elif data == "actions":
        await show_actions(query, context)
    elif data == "quest_done":
        await complete_quest(query, context)
    elif data.startswith("task_"):
        from handlers.tasks import handle_task_creation
        await handle_task_creation(update, context)
    elif data.startswith("dotask_"):
        from handlers.tasks import show_task_details
        await show_task_details(query, context)
    elif data.startswith("done_"):
        from handlers.tasks import mark_task_done
        await mark_task_done(query, context)
    elif data.startswith("confirm_"):
        from handlers.tasks import confirm_task
        await confirm_task(query, context)
    elif data.startswith("reject_"):
        from handlers.tasks import reject_task
        await reject_task(query, context)
    elif data.startswith("top_"):
        await show_top(query, context)
    elif data == "back_main":
        await query.edit_message_text(
            "Главное меню:",
            reply_markup=get_user_keyboard()
        )


async def show_profile(query, context):
    """Показать профиль"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if not user:
        await query.edit_message_text("Зарегистрируйтесь: /reg")
        return
    
    profile_text = (
        f"🌀 ПРОФИЛЬ\n\n"
        f"🆔 Номер: {user['number']}\n"
        f"🎭 {user['gender']} | {user['age']} лет\n"
        f"🟧 Instagram: {user['instagram']}\n"
        f"🧵 Threads: {user['threads']}\n\n"
        f"🪃 Триксики: {user['trixiki']}/{user['max_limit']}\n"
        f"💰 Заработано: {user['stats']['total_earned']}\n\n"
        f"📈 СТАТИСТИКА:\n"
        f"{format_stats(user['stats'])}\n\n"
        f"🏆 Достижений: {len(user['achievements'])}"
    )
    
    keyboard = [[InlineKeyboardButton("« Назад", callback_data="back_main")]]
    
    await query.edit_message_text(
        profile_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_trixiki(query, context):
    """Показать баланс"""
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if not user:
        await query.edit_message_text("Зарегистрируйтесь: /reg")
        return
    
    await query.edit_message_text(
        f"🪃 ВАШ БАЛАНС\n\n"
        f"🏧 Текущий: {user['trixiki']} 🪃\n"
        f"🏦 Макс лимит: {user['max_limit']} 🪃\n\n"
        f"💡 Используй /daily для бонуса\n"
        f"✨ Выполняй задания для заработка",
        reply_markup=get_user_keyboard()
    )


async def show_pool(query, context):
    """Показать пул заданий"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from database import get_available_tasks, users_db
    
    user_id = query.from_user.id
    tasks = get_available_tasks(user_id, 5)
    
    if not tasks:
        await query.edit_message_text(
            "🪫 Пул заданий пуст!",
            reply_markup=get_user_keyboard()
        )
        return
    
    text = "🔋 ДОСТУПНЫЕ ЗАДАНИЯ:\n\n"
    buttons = []
    
    for idx, task in enumerate(tasks, 1):
        creator = users_db.get(task['creator_id'], {})
        text += f"{idx}. {task['type'].upper()} | {task['reward']} 🪃\n"
        buttons.append([InlineKeyboardButton(
            f"✅ #{idx}",
            callback_data=f"dotask_{task['id']}"
        )])
    
    buttons.append([InlineKeyboardButton("« Назад", callback_data="back_main")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def show_actions(query, context):
    """Показать меню действий"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if not user or not user.get('can_create_tasks'):
        await query.edit_message_text("📛 У вас нет доступа к созданию заданий")
        return
    
    keyboard = [
        [InlineKeyboardButton("❤️ Like (3🪃)", callback_data="task_like"),
         InlineKeyboardButton("✍️ Comment (4🪃)", callback_data="task_comment")],
        [InlineKeyboardButton("💻 Special (10🪃)", callback_data="task_special"),
         InlineKeyboardButton("💚 Follow (5🪃)", callback_data="task_follow")],
        [InlineKeyboardButton("« Назад", callback_data="back_main")]
    ]
    
    await query.edit_message_text(
        f"☑️ СОЗДАТЬ ЗАДАНИЕ\n\n"
        f"🏦 Баланс: {user['trixiki']}/{user['max_limit']} 🪃\n\n"
        f"📲 Сегодня создано:\n"
        f"❤️ Лайков: {user['daily_tasks_created']['likes']}/3\n"
        f"✍️ Комментариев: {user['daily_tasks_created']['comments']}/2\n\n"
        f"↔️ Выберите тип:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def complete_quest(query, context):
    """Завершить квест"""
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if not user:
        return
    
    reward = user['max_limit']
    user['trixiki'] = min(user['trixiki'] + reward, user['max_limit'])
    
    await query.edit_message_text(
        f"🧩 Квест выполнен!\n\n"
        f"+{reward} 🪃\n\n"
        f"🏦 Баланс: {user['trixiki']}/{user['max_limit']}"
    )


async def show_top(query, context):
    """Показать топ"""
    from database import users_db
    
    category = query.data.split('_')[1]
    
    if category == 'likes':
        sorted_users = sorted(
            users_db.items(),
            key=lambda x: x[1]['stats']['likes_given'],
            reverse=True
        )[:5]
        title = "❤️ ТОП ПО ЛАЙКАМ"
        stat_key = 'likes_given'
    elif category == 'comments':
        sorted_users = sorted(
            users_db.items(),
            key=lambda x: x[1]['stats']['comments_given'],
            reverse=True
        )[:5]
        title = "✍️ ТОП ПО КОММЕНТАРИЯМ"
        stat_key = 'comments_given'
    elif category == 'follows':
        sorted_users = sorted(
            users_db.items(),
            key=lambda x: x[1]['stats']['follows_given'],
            reverse=True
        )[:5]
        title = "💚 ТОП ПО ПОДПИСКАМ"
        stat_key = 'follows_given'
    else:  # limit
        sorted_users = sorted(
            users_db.items(),
            key=lambda x: x[1]['max_limit'],
            reverse=True
        )[:5]
        title = "🪃 ТОП ПО ЛИМИТУ"
        stat_key = 'max_limit'
    
    text = f"{title}\n\n"
    for idx, (user_id, user_data) in enumerate(sorted_users, 1):
        if stat_key == 'max_limit':
            value = user_data[stat_key]
        else:
            value = user_data['stats'][stat_key]
        text += f"{idx}. @{user_data.get('username', 'unknown')} - {value}\n"
    
    await query.edit_message_text(text)
