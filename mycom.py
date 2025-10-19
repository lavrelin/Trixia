"""
Система конкурса MyCom для Trixiki Bot
Конкурс комментариев с живыми раундами
"""

import random
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)

# Импорт из основного файла
from bot import users_db, mycom_contest, BUDAPEST_TZ, ADMIN_GROUP_ID, USER_CHAT_ID

# База данных конкурса
mycom_participants = {}  # user_id: {'posts': [], 'comments': {}, 'score': 0}
mycom_banned = []
mycom_history = []


async def mycom_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Что такое конкурс 💨MyCom? Показать информацию"""
    user_id = update.effective_user.id
    
    if user_id not in users_db:
        await update.message.reply_text("👨🏼‍💻 Необходимо зарегистрироваться: /reg")
        return
    
    if not mycom_contest['active'] and not mycom_contest['registration']:
        text = (
    "💨 КОНКУРС MYCOM\n\n"
    "Что это❓\n"
    "Это конкурс активности, где каждый участник указывает какие свои посты, как нужно комментировать и пишет к ним текст для коммента.\n"
    "Другие участники делают то же самое — комментируют твои посты, а ты — их.\n\n"
    "☑️ Цель — собрать больше подтверждённых и актуальных комментариев.\n\n"
    "🔖 Правила: ставим ❤️ на комментируемый пост\n"
    "• Приготовь 2–4 ссылки на свои публикации которые нужно прокоментировать\n"
    "• Напиши три комментария для каждой\n"
    "• Подтверждай полученные комментарии\n"
    "• Всё происходит вручную — реально, на выбранных платформах.\n\n"
    "⚠️ Удаление комментариев раньше недели = бан\n\n"
    "💥 Продолжительность: 2 часа\n"
    "🏆 Победители получают награды!\n\n"
    "🔴 Статус: Ожидание следующего конкурса"
)
    elif mycom_contest['registration']:
        text = (
            "💨 MYCOM\n\n"
            "📖 Регистрация открыта!\n\n"
            "❕Команда /mycomjoin для участия!\n"
            f"☄️ Начало: {get_time_left(mycom_contest['start_time'])}"
        )
    else:  # active
        text = (
            "❕ КОНКУРС MYCOM\n\n"
            "💨 MyCom активен!\n\n"
            f"🧑‍🧑‍🧒‍🧒 Участников: {len(mycom_participants)}\n"
            f"⌚️ Осталось: {get_time_left(mycom_contest.get('end_time'))}\n\n"
            "Команда /mycomstatus для проверки прогресса"
        )
    
    await update.message.reply_text(text)


def get_time_left(target_time):
    """Получить оставшееся время"""
    if not target_time:
        return "неизвестно"
    
    now = datetime.now(BUDAPEST_TZ)
    delta = target_time - now
    
    if delta.total_seconds() <= 0:
        return "время истекло"
    
    minutes = int(delta.total_seconds() / 60)
    return f"{minutes} мин"


async def mycom_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """💥 Присоединиться"""
    user_id = update.effective_user.id
    
    if user_id not in users_db:
        await update.message.reply_text("Сначала зарегистрируйтесь: /reg")
        return
    
    if user_id in mycom_banned:
        await update.message.reply_text(
            "👺 Вы заблокированы в конкурсе MyCom👹"
        )
        return
    
    if not mycom_contest['registration']:
        await update.message.reply_text(
            "🔒 Регистрация закрыта! Ожидайте следующего конкурса."
        )
        return
    
    if user_id in mycom_participants:
        await update.message.reply_text("Вы уже зарегистрированы!")
        return
    
    default_limit = 2
    mycom_participants[user_id] = {
        'posts': [],
        'comments': {},
        'score': 0,
        'post_limit': default_limit,
        'last_action': datetime.now(BUDAPEST_TZ),
        'active': True
    }
    
    await update.message.reply_text(
        f"🟩 Успешная регистрация\n\n"
        f"⛓️ Отправьте ссылки на свои публикации (до {default_limit}):\n\n"
        f"Формат:\n"
        f"пост1 https://instagram.com/p/...\n"
        f"пост2 https://threads.net/...\n\n"
        f"После отправки используйте /editmycom для добавления комментариев"
    )


async def mycom_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверить свой прогресс"""
    user_id = update.effective_user.id
    
    if user_id not in mycom_participants:
        await update.message.reply_text("🤷🏼‍♂️ Вы не участвуете в конкурсе!")
        return
    
    participant = mycom_participants[user_id]
    
    text = (
        f"🔥 ВАШ ПРОГРЕСС\n\n"
        f"▪️ Баллов: {participant['score']}\n"
        f"◽️ Постов добавлено: {len(participant['posts'])}/{participant['post_limit']}\n"
        f"🪄 Комментариев подготовлено: {sum(len(c) for c in participant['comments'].values())}\n"
        f"💚 Статус: {'Активен' if participant['active'] else 'Неактивен'}"
    )
    
    await update.message.reply_text(text)


async def mycom_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рейтинг текущего конкурса"""
    if not mycom_contest['active']:
        await update.message.reply_text("Конкурс не активен!")
        return
    
    sorted_participants = sorted(
        mycom_participants.items(),
        key=lambda x: x[1]['score'],
        reverse=True
    )[:10]
    
    text = "🏆 MyCom top users\n\n"
    
    for idx, (user_id, data) in enumerate(sorted_participants, 1):
        user = users_db.get(user_id, {})
        username = user.get('username', 'unknown')
        
        medal = ""
        if idx == 1:
            medal = "🥇"
        elif idx == 2:
            medal = "🥈"
        elif idx == 3:
            medal = "🥉"
        
        text += f"{medal}{idx}. @{username} - {data['score']} баллов\n"
    
    await update.message.reply_text(text)


async def edit_mycom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактировать комментарии для поста"""
    user_id = update.effective_user.id
    
    if user_id not in mycom_participants:
        await update.message.reply_text("Вы не участвуете в конкурсе!")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text(
            "Команда: /editmycom пост1\n\n"
            "Затем отправьте до 3 комментариев построчно"
        )
        return
    
    post_key = context.args[0]
    participant = mycom_participants[user_id]
    
    if post_key not in [f"пост{i+1}" for i in range(len(participant['posts']))]:
        await update.message.reply_text("Некорректный номер поста!")
        return
    
    context.user_data['editing_post'] = post_key
    
    await update.message.reply_text(
        f"🖋️ Редактирование комментариев для {post_key}\n\n"
        f"Отправьте до 3 комментариев (каждый с новой строки):\n\n"
        f"🤔 FAKECom Пример:\n"
        f"У тебя невероятно красивые глаза 🤩\n"
        f"Фотки супер, это ты в каком городе?\n"
        f"В следующий раз возьми меня с собой😄"
    )


async def handle_mycom_post_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ссылок на посты"""
    user_id = update.effective_user.id
    
    if user_id not in mycom_participants:
        return
    
    participant = mycom_participants[user_id]
    message_text = update.message.text
    
    # Парсинг ссылок
    lines = message_text.strip().split('\n')
    
    for line in lines:
        if line.startswith('пост'):
            parts = line.split(' ', 1)
            if len(parts) == 2:
                post_num = parts[0]
                url = parts[1].strip()
                
                if len(participant['posts']) < participant['post_limit']:
                    participant['posts'].append({
                        'key': post_num,
                        'url': url
                    })
                    participant['comments'][post_num] = []
    
    await update.message.reply_text(
        f"🌃 Посты добавлены: {len(participant['posts'])}/{participant['post_limit']}\n\n"
        f"✒️ Используйте команду /editmycom пост1 для добавления комментариев"
    )


async def handle_mycom_comments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка комментариев для поста"""
    user_id = update.effective_user.id
    
    if 'editing_post' not in context.user_data:
        return
    
    if user_id not in mycom_participants:
        return
    
    post_key = context.user_data['editing_post']
    comments = update.message.text.strip().split('\n')[:3]
    
    mycom_participants[user_id]['comments'][post_key] = comments
    
    await update.message.reply_text(
        f"💾 Комментарии сохранены для {post_key}!\n\n"
        f"💻 Добавлено: {len(comments)} комментариев"
    )
    
    del context.user_data['editing_post']


async def start_mycom_task_distribution(context: ContextTypes.DEFAULT_TYPE):
    """Начало раздачи заданий в конкурсе"""
    mycom_contest['active'] = True
    mycom_contest['registration'] = False
    
    # Уведомление участников
    for user_id in mycom_participants.keys():
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="💨 MyCom запущен!🫣\n\nОжидайте первое задание☑️"
            )
            
            # Отправить первое задание
            await send_mycom_task(user_id, context)
            
        except Exception as e:
            logger.error(f"Error starting contest for user {user_id}: {e}")


async def send_mycom_task(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Отправить задание участнику"""
    if user_id not in mycom_participants:
        return
    
    participant = mycom_participants[user_id]
    
    # Найти случайного участника
    other_participants = [
        uid for uid in mycom_participants.keys()
        if uid != user_id and mycom_participants[uid]['posts']
    ]
    
    if not other_participants:
        return
    
    target_user_id = random.choice(other_participants)
    target_participant = mycom_participants[target_user_id]
    
    # Выбрать случайный пост
    if not target_participant['posts']:
        return
    
    post = random.choice(target_participant['posts'])
    post_key = post['key']
    
    # Выбрать случайный комментарий
    comments = target_participant['comments'].get(post_key, [])
    if not comments:
        comment = "Прокомментируйте🙊"
    else:
        comment = random.choice(comments)
    
    keyboard = [
        [InlineKeyboardButton("✅ Отправлено", callback_data=f"mycom_done_{target_user_id}_{post_key}"),
         InlineKeyboardButton("🔁 Следующий", callback_data="mycom_next")],
        [InlineKeyboardButton("🚨 Жалоба", callback_data=f"mycom_report_{target_user_id}")]
    ]
    
    target_user = users_db.get(target_user_id, {})
    
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"❕ НОВОЕ ЗАДАНИЕ\n\n"
                f"🙋‍♀️ Пользователь: @{target_user.get('username', 'unknown')}\n"
                f"⛓️ Пост: {post['url']}\n\n"
                f"🧑‍🏫 Комментарий:\n{comment}\n\n"
                f"Оставьте этот комментарий под постом и нажмите 'Отправлено'"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # Обновить время последнего действия
        participant['last_action'] = datetime.now(BUDAPEST_TZ)
        
    except Exception as e:
        logger.error(f"Error sending task to {user_id}: {e}")


async def mycom_task_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выполненного задания"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data_parts = query.data.split('_')
    
    if len(data_parts) < 4:
        return
    
    target_user_id = int(data_parts[2])
    post_key = data_parts[3]
    
    # Отправить уведомление владельцу поста
    keyboard = [
        [InlineKeyboardButton("🔔 Подтвердить", callback_data=f"mycom_confirm_{user_id}"),
         InlineKeyboardButton("🔕 Отклонить", callback_data=f"mycom_reject_{user_id}")]
    ]
    
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=(
                f"📣 Уведомление от @{users_db[user_id]['username']} "
                f"🖋️ прокоментировал ваш пост ({post_key}).\n\n"
                f"🔎 Проверьте и подтвердите :"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        await query.edit_message_text(
            "✅ Задание отмечено как выполненное!\n"
            "▪️ Ожидайте подтверждения (до 10 минут)."
        )
        
        # Автоподтверждение через 10 минут
        context.job_queue.run_once(
            auto_confirm_mycom,
            when=600,
            data={'executor_id': user_id, 'target_id': target_user_id}
        )
        
    except Exception as e:
        logger.error(f"Error notifying target user: {e}")


async def mycom_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение комментария"""
    query = update.callback_query
    await query.answer()
    
    executor_id = int(query.data.split('_')[2])
    
    if executor_id in mycom_participants:
        mycom_participants[executor_id]['score'] += 1
        
        try:
            await context.bot.send_message(
                chat_id=executor_id,
                text="✅ MyComментарий подтвержден! +1 балл 🔥"
            )
            
            # Отправить следующее задание
            await send_mycom_task(executor_id, context)
            
        except Exception as e:
            logger.error(f"Error confirming task: {e}")
    
    await query.edit_message_text("✅ MyComментарий подтвержден❕")


async def mycom_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отклонение комментария"""
    query = update.callback_query
    await query.answer()
    
    executor_id = int(query.data.split('_')[2])
    target_id = update.effective_user.id
    
    # Отправка в админ-группу
    try:
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=(
                f"⚠️ СПОРНЫЙ КОММЕНТАРИЙ MYCOM\n\n"
                f"Исполнитель: @{users_db.get(executor_id, {}).get('username', 'unknown')}\n"
                f"Владелец поста: @{users_db.get(target_id, {}).get('username', 'unknown')}\n\n"
                f"Владелец отклонил комментарий."
            )
        )
    except Exception as e:
        logger.error(f"Error sending to admin group: {e}")
    
    await query.edit_message_text("🚔 MyComментарий отклонен и отправлен на рассмотрение.")


async def mycom_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запросить следующее задание"""
    query = update.callback_query
    await query.answer("😴 Ожидайте 10 минут")
    
    user_id = update.effective_user.id
    
    # Запланировать следующее задание через 10 минут
    context.job_queue.run_once(
        lambda ctx: send_mycom_task(user_id, ctx),
        when=600
    )
    
    await query.edit_message_text(
        "🚅 Следующее задание придет через 10 минут.\n\n"
        "🚝 Приступайте к выполнения других заданий!"
    )

async def mycom_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Жалоба на 🤬"""
    query = update.callback_query
    await query.answer()
    
    target_user_id = int(query.data.split('_')[2])
    reporter_id = update.effective_user.id
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=(
                f"🚨 ЖАЛОБА В MYCOM\n\n"
                f"🤬 От: @{users_db.get(reporter_id, {}).get('username', 'unknown')}\n"
                f"🫣 На: @{users_db.get(target_user_id, {}).get('username', 'unknown')}\n\n"
                f"🧑🏽‍⚖️ Расследование."
            )
        )
        
        await query.edit_message_text("🥵 Жалоба проверяется")
        
    except Exception as e:
        logger.error(f"Error sending report: {e}")


async def auto_confirm_mycom(context: ContextTypes.DEFAULT_TYPE):
    """Автоматическое подтверждение через 10 минут"""
    executor_id = context.job.data['executor_id']
    
    if executor_id in mycom_participants:
        mycom_participants[executor_id]['score'] += 1
        
        try:
            await context.bot.send_message(
                chat_id=executor_id,
                text="☑️ Комментарий автоматически подтвержден❕ +1 балл 🔥"
            )
            
            await send_mycom_task(executor_id, context)
            
        except Exception as e:
            logger.error(f"Error auto-confirming: {e}")


async def check_mycom_inactivity(context: ContextTypes.DEFAULT_TYPE):
    """🚓 Проверка неактивных участников"""
    if not mycom_contest['active']:
        return
    
    now = datetime.now(BUDAPEST_TZ)
    inactive_threshold = timedelta(minutes=10)
    
    for user_id, participant in list(mycom_participants.items()):
        if not participant['active']:
            continue
        
        time_since_last = now - participant['last_action']
        
        if time_since_last > inactive_threshold:
            participant['active'] = False
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="💤 Вас исключили из конкурса за АФК (10 минут)."
                )
            except Exception as e:
                logger.error(f"Error notifying inactive user {user_id}: {e}")


async def end_mycom_contest(context: ContextTypes.DEFAULT_TYPE):
    """🙋‍♀️ Завершение MyCom"""
    mycom_contest['active'] = False
    
    # Сортировка победителей
    sorted_participants = sorted(
        mycom_participants.items(),
        key=lambda x: x[1]['score'],
        reverse=True
    )[:3]
    
    # Составление сообщения с результатами
    result_text = "💨 MYCOM ЗАВЕРШЁН!\n\n"
    
    for idx, (user_id, data) in enumerate(sorted_participants, 1):
        user = users_db.get(user_id, {})
        username = user.get('username', 'unknown')
        
        medal = ["🥇", "🥈", "🥉"][idx-1] if idx <= 3 else f"{idx}."
        result_text += f"{medal} @{username} ({data['score']} подтверждений)\n"
    
    # Отправка в чат и участникам
    try:
        await context.bot.send_message(
            chat_id=USER_CHAT_ID,
            text=result_text
        )
    except Exception as e:
        logger.error(f"Error sending results to chat: {e}")
    
    for user_id in mycom_participants.keys():
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=result_text
            )
        except Exception as e:
            logger.error(f"Error notifying participant {user_id}: {e}")
    
    # Сохранить в историю
    mycom_history.append({
        'date': datetime.now(BUDAPEST_TZ),
        'winners': sorted_participants
    })
    
    # Очистка
    mycom_participants.clear()


# ============== АДМИН-КОМАНДЫ MYCOM ==============

async def admin_mycom_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запустить конкурс MyCom"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    # Случайное время старта (12:00 - 22:00)
    hour = random.randint(12, 22)
    minute = random.randint(0, 59)
    
    today = datetime.now(BUDAPEST_TZ).replace(hour=hour, minute=minute, second=0)
    
    if today < datetime.now(BUDAPEST_TZ):
        today += timedelta(days=1)
    
    # За час до старта - регистрация
    registration_time = today - timedelta(hours=1)
    
    mycom_contest['start_time'] = today
    mycom_contest['end_time'] = today + timedelta(minutes=120)
    mycom_contest['registration'] = False
    
    await update.message.reply_text(
        f"💨 Новый конкурс MyCom запланирован❕\n\n"
        f"🤍 Когда?: {today.strftime('%d.%m.%Y')}\n"
        f"🕐 Регистрация: {registration_time.strftime('%H:%M')}\n"
        f"🕐 Начало: {today.strftime('%H:%M')}\n"
        f"⏱ Длительность: Два часа"
    )
    
    # Запланировать открытие регистрации
    delay_to_registration = (registration_time - datetime.now(BUDAPEST_TZ)).total_seconds()
    if delay_to_registration > 0:
        context.job_queue.run_once(
            open_mycom_registration,
            when=delay_to_registration,
            data={'start_time': today}
        )
    
    # Запланировать старт
    delay_to_start = (today - datetime.now(BUDAPEST_TZ)).total_seconds()
    if delay_to_start > 0:
        context.job_queue.run_once(
            start_mycom_task_distribution,
            when=delay_to_start,
            data={}
        )
    
    # Запланировать окончание
    delay_to_end = (mycom_contest['end_time'] - datetime.now(BUDAPEST_TZ)).total_seconds()
    if delay_to_end > 0:
        context.job_queue.run_once(
            end_mycom_contest,
            when=delay_to_end,
            data={}
        )


async def open_mycom_registration(context: ContextTypes.DEFAULT_TYPE):
    """Открыть регистрацию на конкурс"""
    mycom_contest['registration'] = True
    
    start_time = context.job.data['start_time']
    
    # Анонс в чате
    try:
        await context.bot.send_message(
            chat_id=USER_CHAT_ID,
            text=(
                f"📣 РЕГИСТРАЦИЯ НА MYCOM ОТКРЫТА!\n\n"
                f"🕐 Старт конкурса: {start_time.strftime('%H:%M')}\n"
                f"⏱ Длительность: 120 минут\n\n"
                f"🖋️ Команда /mycomjoin для участия!\n\n"
                f"⚠️ За удаление комментариев раньше семи дней - бан 📛"
            )
        )
    except Exception as e:
        logger.error(f"Error announcing registration: {e}")
    
    # Уведомление всех пользователей
    for user_id in users_db.keys():
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🔔 Регистрация на MyCom запущена!\n\nИспользуйте /mycomjoin"
            )
        except Exception as e:
            logger.error(f"Error notifying user {user_id}: {e}")


async def admin_mycom_postlimit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """⚙️ Изменить лимит на добавление постов для юзера"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("▪️Команда: /mycompostlimit @username 1-4")
        return
    
    username = context.args[0].replace('@', '')
    try:
        new_limit = int(context.args[1])
        if new_limit < 1 or new_limit > 4:
            await update.message.reply_text("Лимит от 1 до 4")
            return
    except ValueError:
        await update.message.reply_text("🤬 Внимательней..")
        return
    
    # Найти пользователя
    for user_id, user_data in users_db.items():
        if user_data.get('username') == username:
            if user_id in mycom_participants:
                mycom_participants[user_id]['post_limit'] = new_limit
                
                await update.message.reply_text(
                    f"⚙️ Пост Limit для @{username}: {new_limit}"
                )
                
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"💌 Лимит для добавление постов 💨MyCom теперь {new_limit}"
                    )
                except Exception as e:
                    logger.error(f"Error notifying user: {e}")
                
                return
            else:
                await update.message.reply_text(f"@{username} 🚩 Не участвует")
                return
    
    await update.message.reply_text(f"🔮 Персонаж @{username} потерян и не найден 🥵")


async def admin_mycom_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Забанить 🤬 в 💨MyCom"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("Юзай: /mycomban @username")
        return
    
    username = context.args[0].replace('@', '')
    
    for user_id, user_data in users_db.items():
        if user_data.get('username') == username:
            if user_id not in mycom_banned:
                mycom_banned.append(user_id)
                
                # Удалить из участников если участвует
                if user_id in mycom_participants:
                    del mycom_participants[user_id]
                
                await update.message.reply_text(f"🚗 @{username} забанен для 💨MyCom")
                
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="🚩 Вы заблокированы в конкурсе 💨MyCom‼️"
                    )
                except Exception as e:
                    logger.error(f"Error notifying user: {e}")
                
                return
            else:
                await update.message.reply_text(f"@{username} уже забанен")
                return
    
    await update.message.reply_text(f"Уважаемый @{username} не найден")


async def admin_mycom_banlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """💨MyCom посмотреть БанЛист"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if not mycom_banned:
        await update.message.reply_text("🫗 Пока что пусто")
        return
    
    text = "🚫 Забанены в 💨MyCom:\n\n"
    
    for user_id in mycom_banned:
        user = users_db.get(user_id, {})
        username = user.get('username', 'unknown')
        text += f"• @{username}\n"
    
    await update.message.reply_text(text)
