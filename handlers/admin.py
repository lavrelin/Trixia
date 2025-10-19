"""
Админ-команды
"""
import random
import logging
from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_GROUP_ID
from database import users_db

logger = logging.getLogger(__name__)


# Временное хранилище для админских заданий MyCom
admin_mycom_tasks = {}


async def admin_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /limit"""
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
            await update.message.reply_text(f"❕ Лимит 🪃 @{username}: {new_limit}")
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"👨🏼‍💻 Ваш max limit 🪃Триксиков теперь {new_limit}!"
                )
            except Exception as e:
                logger.error(f"Error: {e}")
            return
    
    await update.message.reply_text(f"@{username} не найден")


async def admin_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /balance"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /balance @username")
        return
    
    username = context.args[0].replace('@', '')
    
    for user_data in users_db.values():
        if user_data.get('username') == username:
            await update.message.reply_text(
                f"💥 @{username}:\n{user_data['trixiki']}/{user_data['max_limit']} 🪃"
            )
            return
    
    await update.message.reply_text(f"@{username} не найден")


async def admin_trixikichange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /trixikichange"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /trixikichange @username число")
        return
    
    username = context.args[0].replace('@', '')
    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Некорректное число")
        return
    
    for user_id, user_data in users_db.items():
        if user_data.get('username') == username:
            user_data['trixiki'] = min(amount, user_data['max_limit'])
            await update.message.reply_text(f"🏦 Баланс @{username}: {user_data['trixiki']}")
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"❕ Баланс установлен: {user_data['trixiki']} 🪃"
                )
            except Exception as e:
                logger.error(f"Error: {e}")
            return
    
    await update.message.reply_text(f"@{username} не найден")


async def admin_trixikiadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /trixikiadd"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /trixikiadd @username число")
        return
    
    username = context.args[0].replace('@', '')
    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Некорректное число")
        return
    
    for user_id, user_data in users_db.items():
        if user_data.get('username') == username:
            user_data['trixiki'] = min(user_data['trixiki'] + amount, user_data['max_limit'])
            await update.message.reply_text(
                f"✅ @{username} +{amount} 🪃\nБаланс: {user_data['trixiki']}"
            )
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"💝 +{amount} 🪃!"
                )
            except Exception as e:
                logger.error(f"Error: {e}")
            return
    
    await update.message.reply_text(f"@{username} не найден")


async def admin_localgirls(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /localgirls"""
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
                logger.error(f"Error: {e}")
    
    await update.message.reply_text(f"📪 Доставлено {count} девушкам")


async def admin_localboys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /localboys"""
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
                logger.error(f"Error: {e}")
    
    await update.message.reply_text(f"📬 Доставлено {count} парням")


async def admin_liketimeon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /liketimeon"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /liketimeon @username")
        return
    
    username = context.args[0].replace('@', '')
    
    for user_id, user_data in users_db.items():
        if user_data.get('username') == username:
            user_data['can_create_tasks'] = True
            await update.message.reply_text(f"🟢 @{username} может создавать задания")
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="💚 Вам разрешено создавать задания!"
                )
            except Exception as e:
                logger.error(f"Error: {e}")
            return
    
    await update.message.reply_text(f"@{username} не найден")


async def admin_liketimeoff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /liketimeoff"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /liketimeoff @username")
        return
    
    username = context.args[0].replace('@', '')
    
    for user_id, user_data in users_db.items():
        if user_data.get('username') == username:
            user_data['can_create_tasks'] = False
            await update.message.reply_text(f"📛 @{username} не может создавать задания")
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="📛 Создание заданий запрещено"
                )
            except Exception as e:
                logger.error(f"Error: {e}")
            return
    
    await update.message.reply_text(f"@{username} не найден")


async def giftstart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /giftstart"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    daily_users = [uid for uid, u in users_db.items() if u.get('daily_claimed')]
    
    if not daily_users:
        await update.message.reply_text("Нет активных пользователей")
        return
    
    winners_count = random.randint(1, 3)
    winners = random.sample(daily_users, min(winners_count, len(daily_users)))
    
    result = "❤️ Награды:\n\n"
    
    for winner_id in winners:
        user = users_db[winner_id]
        user['max_limit'] = min(user['max_limit'] + 1, 50)
        result += f"@{user.get('username', 'unknown')} +1 лимит\n"
        
        try:
            await context.bot.send_message(
                chat_id=winner_id,
                text="⚙️ Ваш лимит Триксиков увеличен на +1!"
            )
        except Exception as e:
            logger.error(f"Error: {e}")
    
    await update.message.reply_text(result)


async def mycomadminadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔐 СКРЫТАЯ КОМАНДА: Админ добавляет задания в MyCom"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    admin_id = update.effective_user.id
    
    await update.message.reply_text(
        "🔐 АДМИН ЗАДАНИЯ MYCOM\n\n"
        "Отправьте ссылки на посты (1-4 штуки):\n\n"
        "Формат:\n"
        "пост1 https://instagram.com/p/...\n"
        "пост2 https://threads.net/...\n"
        "пост3 https://instagram.com/p/...\n"
        "пост4 https://threads.net/..."
    )
    
    context.user_data['mycom_admin_adding'] = {
        'admin_id': admin_id,
        'posts': [],
        'comments': {},
        'stage': 'posts'
    }


async def handle_mycom_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода админа для MyCom заданий"""
    if 'mycom_admin_adding' not in context.user_data:
        return False
    
    admin_data = context.user_data['mycom_admin_adding']
    text = update.message.text
    
    if admin_data['stage'] == 'posts':
        # Парсинг постов
        lines = text.strip().split('\n')
        for line in lines:
            if line.startswith('пост'):
                parts = line.split(' ', 1)
                if len(parts) == 2:
                    post_key = parts[0]
                    url = parts[1].strip()
                    admin_data['posts'].append({
                        'key': post_key,
                        'url': url
                    })
                    admin_data['comments'][post_key] = []
        
        if not admin_data['posts']:
            await update.message.reply_text("❌ Не найдено постов. Попробуйте снова.")
            return True
        
        # Переход к комментариям
        admin_data['stage'] = 'comments'
        admin_data['current_post_index'] = 0
        current_post = admin_data['posts'][0]
        
        await update.message.reply_text(
            f"✅ Добавлено {len(admin_data['posts'])} постов\n\n"
            f"Теперь добавьте 3 комментария для {current_post['key']}:\n"
            f"(Каждый с новой строки)"
        )
        return True
    
    elif admin_data['stage'] == 'comments':
        # Добавление комментариев
        current_index = admin_data['current_post_index']
        current_post = admin_data['posts'][current_index]
        comments = text.strip().split('\n')[:3]
        
        admin_data['comments'][current_post['key']] = comments
        
        # Переход к следующему посту
        admin_data['current_post_index'] += 1
        
        if admin_data['current_post_index'] < len(admin_data['posts']):
            next_post = admin_data['posts'][admin_data['current_post_index']]
            await update.message.reply_text(
                f"✅ Комментарии для {current_post['key']} сохранены\n\n"
                f"Теперь 3 комментария для {next_post['key']}:"
            )
            return True
        else:
            # Все комментарии добавлены - сохраняем задания
            await save_admin_mycom_tasks(admin_data, update, context)
            context.user_data.clear()
            return True
    
    return False


async def save_admin_mycom_tasks(admin_data, update, context):
    """Сохранить админские задания в MyCom"""
    # Сохраняем в глобальное хранилище
    task_id = f"admin_{int(__import__('time').time())}"
    admin_mycom_tasks[task_id] = {
        'posts': admin_data['posts'],
        'comments': admin_data['comments'],
        'admin_id': admin_data['admin_id']
    }
    
    result = f"✅ АДМИНСКИЕ ЗАДАНИЯ ДОБАВЛЕНЫ\n\n"
    result += f"📝 Постов: {len(admin_data['posts'])}\n"
    result += f"💬 Комментариев: {sum(len(c) for c in admin_data['comments'].values())}\n\n"
    result += "Задания будут распределяться участникам MyCom автоматически!"
    
    await update.message.reply_text(result)
    
    logger.info(f"Admin MyCom tasks added: {task_id}")


# Экспортируем функцию для использования в handlers/tasks.py
def get_admin_mycom_tasks():
    """Получить админские задания MyCom"""
    return admin_mycom_tasks



async def admin_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /limit"""
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
                    text=f"🎉 Ваш лимит изменен на {new_limit}!"
                )
            except Exception as e:
                logger.error(f"Error: {e}")
            return
    
    await update.message.reply_text(f"@{username} не найден")


async def admin_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /balance"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /balance @username")
        return
    
    username = context.args[0].replace('@', '')
    
    for user_data in users_db.values():
        if user_data.get('username') == username:
            await update.message.reply_text(
                f"💰 @{username}:\n{user_data['trixiki']}/{user_data['max_limit']} 🪃"
            )
            return
    
    await update.message.reply_text(f"@{username} не найден")


async def admin_trixikichange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /trixikichange"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /trixikichange @username число")
        return
    
    username = context.args[0].replace('@', '')
    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Некорректное число")
        return
    
    for user_id, user_data in users_db.items():
        if user_data.get('username') == username:
            user_data['trixiki'] = min(amount, user_data['max_limit'])
            await update.message.reply_text(f"✅ Баланс @{username}: {user_data['trixiki']}")
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"💰 Баланс установлен: {user_data['trixiki']} 🪃"
                )
            except Exception as e:
                logger.error(f"Error: {e}")
            return
    
    await update.message.reply_text(f"@{username} не найден")


async def admin_trixikiadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /trixikiadd"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /trixikiadd @username число")
        return
    
    username = context.args[0].replace('@', '')
    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Некорректное число")
        return
    
    for user_id, user_data in users_db.items():
        if user_data.get('username') == username:
            user_data['trixiki'] = min(user_data['trixiki'] + amount, user_data['max_limit'])
            await update.message.reply_text(
                f"✅ @{username} +{amount} 🪃\nБаланс: {user_data['trixiki']}"
            )
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎁 +{amount} 🪃!"
                )
            except Exception as e:
                logger.error(f"Error: {e}")
            return
    
    await update.message.reply_text(f"@{username} не найден")


async def admin_localgirls(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /localgirls"""
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
                logger.error(f"Error: {e}")
    
    await update.message.reply_text(f"✅ Отправлено {count} девушкам")


async def admin_localboys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /localboys"""
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
                logger.error(f"Error: {e}")
    
    await update.message.reply_text(f"✅ Отправлено {count} парням")


async def admin_liketimeon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /liketimeon"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /liketimeon @username")
        return
    
    username = context.args[0].replace('@', '')
    
    for user_id, user_data in users_db.items():
        if user_data.get('username') == username:
            user_data['can_create_tasks'] = True
            await update.message.reply_text(f"✅ @{username} может создавать задания")
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="✅ Вам разрешено создавать задания!"
                )
            except Exception as e:
                logger.error(f"Error: {e}")
            return
    
    await update.message.reply_text(f"@{username} не найден")


async def admin_liketimeoff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /liketimeoff"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /liketimeoff @username")
        return
    
    username = context.args[0].replace('@', '')
    
    for user_id, user_data in users_db.items():
        if user_data.get('username') == username:
            user_data['can_create_tasks'] = False
            await update.message.reply_text(f"❌ @{username} не может создавать задания")
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ Создание заданий запрещено"
                )
            except Exception as e:
                logger.error(f"Error: {e}")
            return
    
    await update.message.reply_text(f"@{username} не найден")


async def giftstart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /giftstart"""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    daily_users = [uid for uid, u in users_db.items() if u.get('daily_claimed')]
    
    if not daily_users:
        await update.message.reply_text("Нет активных пользователей")
        return
    
    winners_count = random.randint(1, 3)
    winners = random.sample(daily_users, min(winners_count, len(daily_users)))
    
    result = "🎁 ПОДАРКИ:\n\n"
    
    for winner_id in winners:
        user = users_db[winner_id]
        user['max_limit'] = min(user['max_limit'] + 1, 50)
        result += f"@{user.get('username', 'unknown')} +1 лимит\n"
        
        try:
            await context.bot.send_message(
                chat_id=winner_id,
                text="🎁 Ваш лимит увеличен на +1!"
            )
        except Exception as e:
            logger.error(f"Error: {e}")
    
    await update.message.reply_text(result)
