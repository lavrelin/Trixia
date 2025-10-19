"""
Обработчики заданий
"""
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging

from config import TASK_COSTS, DAILY_LIMITS, BUDAPEST_TZ, TASK_FREEZE_TIME, ADMIN_GROUP_ID
from database import (get_user, add_task, remove_task, get_task, freeze_task,
                     unfreeze_task, get_frozen_task, users_db, tasks_db, announcement_subscribers)
from utils import is_content_safe, can_interact, generate_task_id, get_user_keyboard

logger = logging.getLogger(__name__)


async def handle_task_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало создания задания"""
    query = update.callback_query
    user_id = query.from_user.id
    user = get_user(user_id)
    
    task_type = query.data.split('_')[1]
    cost = TASK_COSTS[task_type]
    limit_key = 'likes' if task_type == 'like' else 'comments' if task_type in ['comment', 'special'] else 'follows'
    
    if user['trixiki'] < cost:
        await query.edit_message_text(
            f"🪫 Недостаточно триксиков!\n"
            f"Нужно: {cost} 🪃\nЕсть: {user['trixiki']} 🪃",
            reply_markup=get_user_keyboard()
        )
        return
    
    if user['daily_tasks_created'][limit_key] >= DAILY_LIMITS[task_type]:
        await query.edit_message_text(
            f"🔐 Дневной лимит достигнут!\n"
            f"Создано: {user['daily_tasks_created'][limit_key]}/{DAILY_LIMITS[task_type]}",
            reply_markup=get_user_keyboard()
        )
        return
    
    context.user_data['creating_task'] = {
        'type': task_type,
        'cost': cost,
        'limit_key': limit_key
    }
    
    if task_type == 'like':
        msg = "🔗 Отправьте ссылку на пост 🟧Instagram 🧵Threads"
    elif task_type == 'comment':
        msg = "🔗 Отправьте ссылку на пост для ✍️комментария"
    elif task_type == 'special':
        msg = "🔗 Шаг 1/2: Отправьте ссылку на пост"
    else:  # follow
        msg = "🔗 Отправьте ссылку на профиль для подписки"
    
    await query.edit_message_text(msg)


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # USDT адрес
    if context.user_data.get('adding_usdt'):
        if text.startswith('T') and len(text) == 34:
            user = get_user(user_id)
            if user:
                user['usdt_address'] = text
            await update.message.reply_text(
                f"$USDT адрес сохранен!\n\n{text}",
                reply_markup=get_user_keyboard()
            )
            context.user_data.clear()
        else:
            await update.message.reply_text("‼️ Некорректный адрес USDT TRC-20")
        return
    
    # Создание задания
    if 'creating_task' in context.user_data:
        if 'link' in context.user_data['creating_task']:
            await handle_special_comment(update, context)
        else:
            await handle_task_link(update, context)


async def handle_task_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ссылки задания"""
    user_id = update.effective_user.id
    link = update.message.text.strip()
    
    if not (link.startswith('https://instagram.com') or link.startswith('https://threads.net')):
        await update.message.reply_text("😡 Некорректная ссылка!")
        return
    
    if not is_content_safe(link):
        await update.message.reply_text("🚔 Ссылка содержит запрещенный контент!")
        return
    
    task_data = context.user_data['creating_task']
    user = get_user(user_id)
    
    if task_data['type'] == 'special':
        context.user_data['creating_task']['link'] = link
        await update.message.reply_text(
            "🔗 Шаг 2/2: Напишите ✍️комментарий\n\n"
            "Этот текст будет скопирован на ваш пост"
        )
        return
    
    # Создание задания
    task_id = generate_task_id(user_id)
    
    task = {
        'id': task_id,
        'creator_id': user_id,
        'type': task_data['type'],
        'link': link,
        'reward': task_data['cost'],
        'created_at': datetime.now(BUDAPEST_TZ).isoformat()
    }
    
    add_task(task)
    user['trixiki'] -= task_data['cost']
    user['daily_tasks_created'][task_data['limit_key']] += 1
    
    await update.message.reply_text(
        f"🔰 Задание создано\n\n"
        f"Тип: {task_data['type'].upper()}\n"
        f"Списано: {task_data['cost']} 🪃\n"
        f"Баланс: {user['trixiki']}/{user['max_limit']} 🪃",
        reply_markup=get_user_keyboard()
    )
    
    context.user_data.clear()


async def handle_special_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка специального комментария"""
    user_id = update.effective_user.id
    comment = update.message.text.strip()
    
    if not is_content_safe(comment):
        await update.message.reply_text("👮‍♂️ Комментарий содержит запрещенный контент‼️")
        return
    
    if len(comment) > 500:
        await update.message.reply_text("〰️Длинный❗️Limit 500 символов")
        return
    
    task_data = context.user_data['creating_task']
    user = get_user(user_id)
    task_id = generate_task_id(user_id)
    
    task = {
        'id': task_id,
        'creator_id': user_id,
        'type': 'special_comment',
        'link': task_data['link'],
        'comment': comment,
        'reward': task_data['cost'],
        'created_at': datetime.now(BUDAPEST_TZ).isoformat()
    }
    
    add_task(task)
    user['trixiki'] -= task_data['cost']
    user['daily_tasks_created'][task_data['limit_key']] += 1
    
    await update.message.reply_text(
        f"📗 Special Comment создан!\n\n"
        f"Списано: {task_data['cost']} 🪃\n"
        f"Баланс: {user['trixiki']}/{user['max_limit']} 🪃",
        reply_markup=get_user_keyboard()
    )
    
    context.user_data.clear()


async def show_task_details(query, context):
    """Показать детали задания"""
    task_id = query.data.split('_')[1]
    user_id = query.from_user.id
    
    task = get_task(task_id)
    
    if not task:
        await query.edit_message_text("❗️ Задание не найдено!")
        return
    
    if task['creator_id'] == user_id:
        await query.edit_message_text("😡 Вы не можете выполнить свое задание!")
        return
    
    if not can_interact(user_id, task['creator_id']):
        await query.edit_message_text(
            "🚗 Вы недавно взаимодействовали с этим пользователем!\n"
            "Coldown 8 часов."
        )
        return
    
    text = f"❕ ЗАДАНИЕ #{task_id}\n\n"
    text += f"Тип: {task['type'].upper()}\n"
    text += f"Ссылка: {task['link']}\n"
    
    if 'comment' in task:
        text += f"\nКомментарий:\n{task['comment']}\n"
    
    text += f"\n💳 Награда: {task['reward']} 🪃\n\n"
    text += "Выполните задание и нажмите кнопку:"
    
    keyboard = [
        [InlineKeyboardButton("☑️ Выполнено", callback_data=f"done_{task_id}")],
        [InlineKeyboardButton("« Назад", callback_data="pool")]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def mark_task_done(query, context):
    """Отметить задание как выполненное"""
    task_id = query.data.split('_')[1]
    user_id = query.from_user.id
    
    task = get_task(task_id)
    
    if not task:
        await query.edit_message_text("😡 Задание не найдено!")
        return
    
    # Заморозка
    freeze_task(task_id, {
        'executor_id': user_id,
        'task': task,
        'frozen_at': datetime.now(BUDAPEST_TZ),
        'unfreezes_at': datetime.now(BUDAPEST_TZ) + timedelta(seconds=TASK_FREEZE_TIME)
    })
    
    # Обновить взаимодействие
    user = get_user(user_id)
    if user:
        user['last_interaction'][task['creator_id']] = datetime.now(BUDAPEST_TZ)
    
    # Уведомление создателю
    executor = get_user(user_id)
    keyboard = [
        [InlineKeyboardButton("🔰 Подтверждаю", callback_data=f"confirm_{task_id}"),
         InlineKeyboardButton("♦️ Отклоняю", callback_data=f"reject_{task_id}")]
    ]
    
    try:
        await context.bot.send_message(
            chat_id=task['creator_id'],
            text=(
                f"🔰 ЗАДАНИЕ ВЫПОЛНЕНО\n\n"
                f"🧬 Пользователь: @{executor.get('username', 'unknown')}\n"
                f"🌌 Тип: {task['type'].upper()}\n"
                f"💝 Награда: {task['reward']} 🪃\n\n"
                f"🟩 В течении 3 часов нужно подтвердить"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Error: {e}")
    
    await query.edit_message_text(
        "💙 Задание отмечено!\n\n"
        "💤 Ожидайте подтверждения (до 3 часов)",
        reply_markup=get_user_keyboard()
    )
    
    # Автоподтверждение через 3 часа
    context.job_queue.run_once(
        auto_confirm,
        when=TASK_FREEZE_TIME,
        data={'task_id': task_id}
    )


async def confirm_task(query, context):
    """Подтвердить задание"""
    task_id = query.data.split('_')[1]
    frozen = get_frozen_task(task_id)
    
    if not frozen:
        await query.edit_message_text("❌ Задание уже обработано!")
        return
    
    executor_id = frozen['executor_id']
    task = frozen['task']
    reward = task['reward']
    
    # Начисление
    executor = get_user(executor_id)
    if executor:
        executor['trixiki'] = min(executor['trixiki'] + reward, executor['max_limit'])
        executor['stats']['total_earned'] += reward
        
        # Статистика
        if task['type'] == 'like':
            executor['stats']['likes_given'] += 1
            users_db[task['creator_id']]['stats']['likes_received'] += 1
        elif 'comment' in task['type']:
            executor['stats']['comments_given'] += 1
            users_db[task['creator_id']]['stats']['comments_received'] += 1
        elif task['type'] == 'follow':
            executor['stats']['follows_given'] += 1
            users_db[task['creator_id']]['stats']['follows_received'] += 1
        
        # Достижения
        await check_achievements(executor_id, context)
        
        try:
            await context.bot.send_message(
                chat_id=executor_id,
                text=f"💚Подтверждено\n\n+{reward} 🪃"
            )
        except Exception as e:
            logger.error(f"Error: {e}")
    
    remove_task(task_id)
    unfreeze_task(task_id)
    
    await query.edit_message_text("Задание 💚Подтверждено!")


async def reject_task(query, context):
    """Отклонить задание"""
    task_id = query.data.split('_')[1]
    frozen = get_frozen_task(task_id)
    
    if not frozen:
        await query.edit_message_text("🫡 Задание уже обработано!")
        return
    
    executor = get_user(frozen['executor_id'])
    creator = get_user(frozen['task']['creator_id'])
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=(
                f"⚠️ СПОРНОЕ ЗАДАНИЕ\n\n"
                f"🥵 Создатель: @{creator.get('username', 'unknown')}\n"
                f"🫣 Исполнитель: @{executor.get('username', 'unknown')}\n"
                f"🔬 Тип: {frozen['task']['type']}\n"
                f"⛓️ Ссылка: {frozen['task']['link']}"
            )
        )
    except Exception as e:
        logger.error(f"Error: {e}")
    
    unfreeze_task(task_id)
    await query.edit_message_text("🚗 Отклонено и отправлено админам")


async def auto_confirm(context):
    """Автоподтверждение"""
    task_id = context.job.data['task_id']
    frozen = get_frozen_task(task_id)
    
    if not frozen:
        return
    
    executor_id = frozen['executor_id']
    reward = frozen['task']['reward']
    
    executor = get_user(executor_id)
    if executor:
        executor['trixiki'] = min(executor['trixiki'] + reward, executor['max_limit'])
        executor['stats']['total_earned'] += reward
        
        try:
            await context.bot.send_message(
                chat_id=executor_id,
                text=f"✅ Автоподтверждение!\n\n+{reward} 🪃"
            )
        except Exception as e:
            logger.error(f"Error: {e}")
    
    remove_task(task_id)
    unfreeze_task(task_id)


async def check_achievements(user_id: int, context):
    """Проверка достижений"""
    from config import ACHIEVEMENTS
    
    user = get_user(user_id)
    if not user:
        return
    
    stats = user['stats']
    achievements = user['achievements']
    new_achievements = []
    
    # Лайки
    for milestone in ACHIEVEMENTS['likes']:
        ach_name = f"likes_{milestone}"
        if stats['likes_given'] >= milestone and ach_name not in achievements:
            achievements.append(ach_name)
            new_achievements.append(f"🏆 {milestone} лайков!")
    
    # Комментарии
    for milestone in ACHIEVEMENTS['comments']:
        ach_name = f"comments_{milestone}"
        if stats['comments_given'] >= milestone and ach_name not in achievements:
            achievements.append(ach_name)
            new_achievements.append(f"🏆 {milestone} комментариев!")
    
    # Подписки
    for milestone in ACHIEVEMENTS['follows']:
        ach_name = f"follows_{milestone}"
        if stats['follows_given'] >= milestone and ach_name not in achievements:
            achievements.append(ach_name)
            new_achievements.append(f"🏆 {milestone} подписок!")
    
    # Уведомления
    if new_achievements:
        achievement_text = "\n".join(new_achievements)
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🔈 НОВЫЕ ДОСТИЖЕНИЯ!\n\n{achievement_text}"
            )
            
            await context.bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                text=f"🏆 @{user['username']} получил:\n{achievement_text}"
            )
        except Exception as e:
            logger.error(f"Error: {e}")


async def send_task_announcements(context):
    """Рассылка анонсов"""
    if not tasks_db or not announcement_subscribers:
        return
    
    recent_tasks = tasks_db[-5:]
    
    text = "💙 НОВЫЕ ЗАДАНИЯ:\n\n"
    for idx, task in enumerate(recent_tasks, 1):
        creator = users_db.get(task['creator_id'], {})
        text += f"{idx}. {task['type'].upper()} | {task['reward']} 🪃\n"
    
    text += "\nИспользуй /pool!"
    
    for user_id in announcement_subscribers:
        try:
            await context.bot.send_message(chat_id=user_id, text=text)
        except Exception as e:
            logger.error(f"Error: {e}")
