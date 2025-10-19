"""
Расширенные обработчики для Trixiki Bot
Включает: пул заданий, админ-команды, рейды, конкурсы MyCom
"""

import random
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)

# Импорт из основного файла
from bot import (
    users_db, tasks_db, frozen_tasks, admin_tasks,
    mycom_contest, raid_data, BUDAPEST_TZ, ADMIN_GROUP_ID
)


# ============== ПУЛ ЗАДАНИЙ ==============

async def pool_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать пул доступных заданий"""
    user_id = update.effective_user.id
    
    if user_id not in users_db:
        await update.message.reply_text("Сначала зарегистрируйтесь: /reg")
        return
    
    if not tasks_db:
        await update.message.reply_text(
            "🧊 Пул заданий пуст!\n\nСоздайте первое задание через кнопку ❤️ Like/Comment/Follow"
        )
        return
    
    # Показываем последние 10 заданий
    available_tasks = [t for t in tasks_db if t['creator_id'] != user_id][:10]
    
    if not available_tasks:
        await update.message.reply_text("Нет доступных заданий для вас.")
        return
    
    text = "🧊 ДОСТУПНЫЕ ЗАДАНИЯ:\n\n"
    for idx, task in enumerate(available_tasks, 1):
        creator = users_db.get(task['creator_id'], {})
        text += (
            f"{idx}. {task['type'].upper()}\n"
            f"   От: @{creator.get('username', 'unknown')}\n"
            f"   Награда: {task['reward']} 🪃\n"
            f"   ID: {task['id']}\n\n"
        )
    
    text += "Используйте /dotask <ID> для выполнения"
    await update.message.reply_text(text)


async def create_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало создания задания"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user = users_db.get(user_id)
    
    if not user:
        await query.edit_message_text("Ошибка: пользователь не найден")
        return
    
    keyboard = [
        [InlineKeyboardButton("❤️ Like (3🪃)", callback_data="create_like"),
         InlineKeyboardButton("💬 Comment (4🪃)", callback_data="create_comment")],
        [InlineKeyboardButton("💬 Special Comment (10🪃)", callback_data="create_special"),
         InlineKeyboardButton("👥 Follow (5🪃)", callback_data="create_follow")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ]
    
    await query.edit_message_text(
        f"Выберите тип задания:\n\n"
        f"Ваш баланс: {user['trixiki']} 🪃",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def do_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выполнение задания"""
    user_id = update.effective_user.id
    
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /dotask <ID>")
        return
    
    task_id = context.args[0]
    task = next((t for t in tasks_db if t['id'] == task_id), None)
    
    if not task:
        await update.message.reply_text("Задание не найдено!")
        return
    
    if task['creator_id'] == user_id:
        await update.message.reply_text("Вы не можете выполнить свое собственное задание!")
        return
    
    # Заморозка триксиков
    frozen_tasks[task_id] = {
        'executor_id': user_id,
        'task': task,
        'frozen_at': datetime.now(BUDAPEST_TZ),
        'unfreezes_at': datetime.now(BUDAPEST_TZ) + timedelta(hours=3)
    }
    
    # Уведомление создателю
    creator_id = task['creator_id']
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{task_id}"),
         InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{task_id}")]
    ]
    
    try:
        await context.bot.send_message(
            chat_id=creator_id,
            text=(
                f"🔔 Задание выполнено!\n\n"
                f"Пользователь @{users_db[user_id]['username']} "
                f"выполнил ваше задание: {task['type']}\n\n"
                f"Подтвердите выполнение в течение 3 часов:"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Error notifying creator: {e}")
    
    await update.message.reply_text(
        "✅ Задание отмечено как выполненное!\n"
        "Ожидайте подтверждения от создателя (до 3 часов)."
    )
    
    # Автоматическое подтверждение через 3 часа
    context.job_queue.run_once(
        auto_confirm_task,
        when=10800,  # 3 часа
        data={'task_id': task_id}
    )


async def confirm_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение выполнения задания"""
    query = update.callback_query
    await query.answer()
    
    task_id = query.data.split('_')[1]
    frozen = frozen_tasks.get(task_id)
    
    if not frozen:
        await query.edit_message_text("Задание уже обработано!")
        return
    
    executor_id = frozen['executor_id']
    task = frozen['task']
    reward = task['reward']
    
    # Начисление триксиков
    if executor_id in users_db:
        users_db[executor_id]['trixiki'] = min(
            users_db[executor_id]['trixiki'] + reward,
            users_db[executor_id]['max_limit']
        )
        
        # Обновление статистики
        task_type = task['type']
        if task_type == 'like':
            users_db[executor_id]['stats']['likes_given'] += 1
            users_db[task['creator_id']]['stats']['likes_received'] += 1
        elif 'comment' in task_type:
            users_db[executor_id]['stats']['comments_given'] += 1
            users_db[task['creator_id']]['stats']['comments_received'] += 1
        elif task_type == 'follow':
            users_db[executor_id]['stats']['follows_given'] += 1
            users_db[task['creator_id']]['stats']['follows_received'] += 1
        
        # Проверка достижений
        await check_achievements(executor_id, context)
        
        try:
            await context.bot.send_message(
                chat_id=executor_id,
                text=f"✅ Задание подтверждено! +{reward} 🪃"
            )
        except Exception as e:
            logger.error(f"Error notifying executor: {e}")
    
    # Удаление задания
    tasks_db[:] = [t for t in tasks_db if t['id'] != task_id]
    del frozen_tasks[task_id]
    
    await query.edit_message_text("✅ Задание подтверждено!")


async def reject_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отклонение выполнения задания"""
    query = update.callback_query
    await query.answer()
    
    task_id = query.data.split('_')[1]
    frozen = frozen_tasks.get(task_id)
    
    if not frozen:
        await query.edit_message_text("Задание уже обработано!")
        return
    
    # Отправка в админ-группу
    executor = users_db.get(frozen['executor_id'], {})
    creator = users_db.get(frozen['task']['creator_id'], {})
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=(
                f"⚠️ СПОРНОЕ ЗАДАНИЕ\n\n"
                f"Создатель: @{creator.get('username', 'unknown')}\n"
                f"Исполнитель: @{executor.get('username', 'unknown')}\n"
                f"Тип: {frozen['task']['type']}\n\n"
                f"Создатель отклонил выполнение задания."
            )
        )
    except Exception as e:
        logger.error(f"Error sending to admin group: {e}")
    
    del frozen_tasks[task_id]
    await query.edit_message_text("❌ Задание отклонено и отправлено на рассмотрение админам.")


async def auto_confirm_task(context: ContextTypes.DEFAULT_TYPE):
    """Автоматическое подтверждение через 3 часа"""
    task_id = context.job.data['task_id']
    
    if task_id in frozen_tasks:
        frozen = frozen_tasks[task_id]
        executor_id = frozen['executor_id']
        reward = frozen['task']['reward']
        
        if executor_id in users_db:
            users_db[executor_id]['trixiki'] = min(
                users_db[executor_id]['trixiki'] + reward,
                users_db[executor_id]['max_limit']
            )
            
            try:
                await context.bot.send_message(
                    chat_id=executor_id,
                    text=f"✅ Задание автоматически подтверждено! +{reward} 🪃"
                )
            except Exception as e:
                logger.error(f"Error notifying executor: {e}")
        
        tasks_db[:] = [t for t in tasks_db if t['id'] != task_id]
        del frozen_tasks[task_id]


async def check_achievements(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Проверка достижений пользователя"""
    user = users_db.get(user_id)
    if not user:
        return
    
    stats = user['stats']
    achievements = user['achievements']
    new_achievements = []
    
    # Достижения за лайки
    like_milestones = [100, 200, 300, 500, 1000]
    for milestone in like_milestones:
        achievement_name = f"likes_given_{milestone}"
        if stats['likes_given'] >= milestone and achievement_name not in achievements:
            achievements.append(achievement_name)
            new_achievements.append(f"🏆 {milestone} лайков поставлено!")
    
    # Достижения за комментарии
    comment_milestones = [50, 100, 200, 500]
    for milestone in comment_milestones:
        achievement_name = f"comments_{milestone}"
        if stats['comments_given'] >= milestone and achievement_name not in achievements:
            achievements.append(achievement_name)
            new_achievements.append(f"🏆 {milestone} комментариев написано!")
    
    # Достижения за подписки
    follow_milestones = [20, 50, 100, 200]
    for milestone in follow_milestones:
        achievement_name = f"follows_{milestone}"
        if stats['follows_given'] >= milestone and achievement_name not in achievements:
            achievements.append(achievement_name)
            new_achievements.append(f"🏆 {milestone} подписок сделано!")
    
    # Уведомление пользователя и админов
    if new_achievements:
        achievement_text = "\n".join(new_achievements)
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 НОВЫЕ ДОСТИЖЕНИЯ!\n\n{achievement_text}"
            )
            
            await context.bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                text=f"🏆 @{user['username']} получил новые достижения:\n{achievement_text}"
            )
        except Exception as e:
            logger.error(f"Error sending achievement notification: {e}")


# ============== АДМИН-КОМАНДЫ ==============

async def admin_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменить лимит триксиков пользователя"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /limit @username 1-50")
        return
    
    username = context.args[0].replace('@', '')
    try:
        new_limit = int(context.args[1])
        if new_limit < 1 or new_limit > 50:
            await update.message.reply_text("Лимит должен быть от 1 до 50")
            return
    except ValueError:
        await update.message.reply_text("Некорректное значение лимита")
        return
    
    # Поиск пользователя
    user_id = None
    for uid, user_data in users_db.items():
        if user_data.get('username') == username:
            user_id = uid
            break
    
    if not user_id:
        await update.message.reply_text(f"Пользователь @{username} не найден")
        return
    
    users_db[user_id]['max_limit'] = new_limit
    
    await update.message.reply_text(
        f"✅ Лимит @{username} изменен на {new_limit} триксиков"
    )
    
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎉 Ваш максимальный лимит триксиков изменен на {new_limit}!"
        )
    except Exception as e:
        logger.error(f"Error notifying user: {e}")


async def admin_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверить баланс пользователя"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /balance @username")
        return
    
    username = context.args[0].replace('@', '')
    
    for user_id, user_data in users_db.items():
        if user_data.get('username') == username:
            await update.message.reply_text(
                f"💰 Баланс @{username}:\n"
                f"🪃 {user_data['trixiki']}/{user_data['max_limit']} триксиков"
            )
            return
    
    await update.message.reply_text(f"Пользователь @{username} не найден")


async def admin_trixiki_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить точное количество триксиков"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /trixikichange @username количество")
        return
    
    username = context.args[0].replace('@', '')
    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Некорректное количество")
        return
    
    for user_id, user_data in users_db.items():
        if user_data.get('username') == username:
            user_data['trixiki'] = min(amount, user_data['max_limit'])
            await update.message.reply_text(
                f"✅ Баланс @{username} установлен на {user_data['trixiki']} триксиков"
            )
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"💰 Ваш баланс изменен на {user_data['trixiki']} триксиков"
                )
            except Exception as e:
                logger.error(f"Error notifying user: {e}")
            return
    
    await update.message.reply_text(f"Пользователь @{username} не найден")


async def admin_trixiki_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить триксики пользователю"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /trixikiadd @username количество")
        return
    
    username = context.args[0].replace('@', '')
    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Некорректное количество")
        return
    
    for user_id, user_data in users_db.items():
        if user_data.get('username') == username:
            user_data['trixiki'] = min(
                user_data['trixiki'] + amount,
                user_data['max_limit']
            )
            await update.message.reply_text(
                f"✅ @{username} получил +{amount} триксиков\n"
                f"Новый баланс: {user_data['trixiki']}/{user_data['max_limit']}"
            )
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎁 Вы получили +{amount} триксиков!"
                )
            except Exception as e:
                logger.error(f"Error notifying user: {e}")
            return
    
    await update.message.reply_text(f"Пользователь @{username} не найден")


async def admin_localgirls(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить сообщение всем девушкам"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    message = ' '.join(context.args)
    if not message:
        await update.message.reply_text("Использование: /localgirls <сообщение>")
        return
    
    count = 0
    for user_id, user_data in users_db.items():
        if user_data.get('gender') == 'Ж':
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"💌 Сообщение от администрации:\n\n{message}"
                )
                count += 1
            except Exception as e:
                logger.error(f"Error sending to {user_id}: {e}")
    
    await update.message.reply_text(f"✅ Сообщение отправлено {count} девушкам")


async def admin_localboys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить сообщение всем парням"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    message = ' '.join(context.args)
    if not message:
        await update.message.reply_text("Использование: /localboys <сообщение>")
        return
    
    count = 0
    for user_id, user_data in users_db.items():
        if user_data.get('gender') == 'М':
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"💌 Сообщение от администрации:\n\n{message}"
                )
                count += 1
            except Exception as e:
                logger.error(f"Error sending to {user_id}: {e}")
    
    await update.message.reply_text(f"✅ Сообщение отправлено {count} парням")


# ============== СИСТЕМА РЕЙДОВ ==============

async def raid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать информацию о рейде"""
    user_id = update.effective_user.id
    
    if user_id not in users_db:
        await update.message.reply_text("Сначала зарегистрируйтесь: /reg")
        return
    
    status = raid_data['status']
    
    if status == 'inactive':
        text = (
            "🔴 Raid - not active\n\n"
            "Описание появится когда рейд будет запущен.\n\n"
            "Используйте /lastraid для просмотра результатов"
        )
    elif status == 'processing':
        start_time = raid_data.get('start_time')
        if start_time:
            time_left = (start_time - datetime.now(BUDAPEST_TZ)).total_seconds() / 60
            text = (
                f"🟡 Raid - processing\n\n"
                f"⏰ До начала рейда: {int(time_left)} минут\n\n"
                f"Описание будет доступно после старта."
            )
        else:
            text = "🟡 Raid - processing\n\nОжидайте анонса..."
    else:  # active
        text = (
            f"🟢 Raid - active\n\n"
            f"📋 {raid_data['description']}\n\n"
            f"👥 Участников: {len(raid_data['participants'])}\n\n"
            f"Используйте /joinraid для участия!"
        )
    
    await update.message.reply_text(text)


async def raid_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Присоединиться к рейду"""
    user_id = update.effective_user.id
    
    if user_id not in users_db:
        await update.message.reply_text("Сначала зарегистрируйтесь: /reg")
        return
    
    if raid_data['status'] != 'active':
        await update.message.reply_text("❌ Рейд не активен!")
        return
    
    if user_id in raid_data['participants']:
        await update.message.reply_text("Вы уже участвуете в рейде!")
        return
    
    raid_data['participants'].append(user_id)
    
    await update.message.reply_text(
        f"✅ Вы присоединились к рейду!\n\n"
        f"📋 Задание:\n{raid_data['description']}\n\n"
        f"👥 Всего участников: {len(raid_data['participants'])}"
    )


async def raid_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список участников рейда"""
    male_count = sum(1 for uid in raid_data['participants'] 
                     if users_db.get(uid, {}).get('gender') == 'М')
    female_count = sum(1 for uid in raid_data['participants'] 
                       if users_db.get(uid, {}).get('gender') == 'Ж')
    total = len(raid_data['participants'])
    
    await update.message.reply_text(
        f"👥 УЧАСТНИКИ РЕЙДА:\n\n"
        f"👨 Парни: {male_count}\n"
        f"👩 Девушки: {female_count}\n"
        f"📊 Всего: {total}"
    )


async def admin_raid_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запустить рейд (админ)"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    delay_minutes = random.randint(33, 99)
    start_time = datetime.now(BUDAPEST_TZ) + timedelta(minutes=delay_minutes)
    
    raid_data['status'] = 'processing'
    raid_data['start_time'] = start_time
    raid_data['participants'] = []
    
    await update.message.reply_text(
        f"🟡 Рейд запущен!\n\n"
        f"⏰ Начало через {delay_minutes} минут\n"
        f"🕐 Старт в {start_time.strftime('%H:%M')}"
    )
    
    # Запланировать активацию
    context.job_queue.run_once(
        activate_raid,
        when=delay_minutes * 60,
        data={}
    )


async def activate_raid(context: ContextTypes.DEFAULT_TYPE):
    """Активация рейда"""
    raid_data['status'] = 'active'
    
    # Уведомление всех пользователей
    for user_id in users_db.keys():
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"🟢 РЕЙД АКТИВИРОВАН!\n\n"
                    f"📋 {raid_data['description']}\n\n"
                    f"Используйте /joinraid для участия!"
                )
            )
        except Exception as e:
            logger.error(f"Error notifying user {user_id}: {e}")


async def admin_raid_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить длительность рейда"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /raidtime <минуты>")
        return
    
    try:
        duration = int(context.args[0])
        raid_data['duration'] = duration
        
        await update.message.reply_text(f"✅ Длительность рейда: {duration} минут")
        
        # Запланировать окончание
        context.job_queue.run_once(
            end_raid,
            when=duration * 60,
            data={}
        )
    except ValueError:
        await update.message.reply_text("Некорректное значение")


async def end_raid(context: ContextTypes.DEFAULT_TYPE):
    """Окончание рейда"""
    participants = raid_data['participants']
    
    # Выбор победителей (М и Ж)
    males = [uid for uid in participants if users_db.get(uid, {}).get('gender') == 'М']
    females = [uid for uid in participants if users_db.get(uid, {}).get('gender') == 'Ж']
    
    winners = {}
    if males:
        winners['male'] = random.choice(males)
    if females:
        winners['female'] = random.choice(females)
    
    # Уведомление участников
    for user_id in participants:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🏁 Рейд завершен! Ожидайте результатов..."
            )
        except Exception as e:
            logger.error(f"Error notifying participant {user_id}: {e}")
    
    # Сброс
    raid_data['status'] = 'inactive'
    raid_data['participants'] = []
    
    # Отправка результатов в админ-группу
    result_text = "🏆 РЕЗУЛЬТАТЫ РЕЙДА:\n\n"
    for gender_key, winner_id in winners.items():
        winner = users_db.get(winner_id, {})
        result_text += f"{'👨' if gender_key == 'male' else '👩'} @{winner.get('username', 'unknown')}\n"
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=result_text
        )
    except Exception as e:
        logger.error(f"Error sending raid results: {e}")


# ============== ТОП ПОЛЬЗОВАТЕЛЕЙ ==============

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать топ пользователей"""
    keyboard = [
        [InlineKeyboardButton("❤️ Лайки", callback_data="top_likes"),
         InlineKeyboardButton("💬 Комментарии", callback_data="top_comments")],
        [InlineKeyboardButton("👥 Подписки", callback_data="top_follows"),
         InlineKeyboardButton("🪃 Лимит", callback_data="top_limit")]
    ]
    
    await update.message.reply_text(
        "🏆 РЕЙТИНГ\n\nВыберите категорию:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать топ по категории"""
    query = update.callback_query
    await query.answer()
    
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
        title = "💬 ТОП ПО КОММЕНТАРИЯМ"
        stat_key = 'comments_given'
    elif category == 'follows':
        sorted_users = sorted(
            users_db.items(),
            key=lambda x: x[1]['stats']['follows_given'],
            reverse=True
        )[:5]
        title = "👥 ТОП ПО ПОДПИСКАМ"
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
        value = user_data['stats'].get(stat_key) if stat_key in ['likes_given', 'comments_given', 'follows_given'] else user_data.get(stat_key)
        text += f"{idx}. @{user_data.get('username', 'unknown')} - {value}\n"
    
    await query.edit_message_text(text)


# ============== ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ ==============

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика пользователя"""
    if len(context.args) < 1:
        user_id = update.effective_user.id
    else:
        username = context.args[0].replace('@', '')
        user_id = None
        for uid, user_data in users_db.items():
            if user_data.get('username') == username:
                user_id = uid
                break
        
        if not user_id:
            await update.message.reply_text("Пользователь не найден")
            return
    
    if user_id not in users_db:
        await update.message.reply_text("Пользователь не найден")
        return
    
    user = users_db[user_id]
    stats = user['stats']
    
    text = (
        f"📊 СТАТИСТИКА @{user.get('username', 'unknown')}\n\n"
        f"❤️ Лайков: {stats['likes_given']} / {stats['likes_received']}\n"
        f"💬 Комментариев: {stats['comments_given']} / {stats['comments_received']}\n"
        f"👥 Подписок: {stats['follows_given']} / {stats['follows_received']}\n\n"
        f"🏆 Достижений: {len(user['achievements'])}\n"
        f"🪃 Лимит: {user['max_limit']}"
    )
    
    await update.message.reply_text(text)


async def check_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Жалоба на пользователя"""
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /check @username <причина>")
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
        await update.message.reply_text("✅ Жалоба отправлена администрации")
    except Exception as e:
        logger.error(f"Error sending complaint: {e}")
        await update.message.reply_text("❌ Ошибка отправки жалобы")
