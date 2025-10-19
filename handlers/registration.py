"""
Обработчики регистрации
"""
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from config import BUDAPEST_TZ, START_TRIXIKI, INSTAGRAM_ACCOUNT, THREADS_ACCOUNT
from database import create_user, get_user
from utils import generate_user_number, get_user_keyboard

# Состояния
REG_INSTAGRAM, REG_THREADS, REG_GENDER, REG_AGE = range(4)


async def reg_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало регистрации"""
    user_id = update.effective_user.id
    
    if get_user(user_id):
        await update.message.reply_text("Вы уже зарегистрированы! ✅")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📝 РЕГИСТРАЦИЯ\n\n"
        "Шаг 1/4: Введите ваш Instagram аккаунт\n"
        "Формат: @username"
    )
    return REG_INSTAGRAM


async def reg_instagram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение Instagram"""
    instagram = update.message.text.strip()
    if not instagram.startswith('@'):
        await update.message.reply_text("❌ Формат: @username\nПопробуйте снова:")
        return REG_INSTAGRAM
    
    context.user_data['instagram'] = instagram
    await update.message.reply_text(
        "Шаг 2/4: Введите ваш Threads аккаунт\n"
        "Формат: @username"
    )
    return REG_THREADS


async def reg_threads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение Threads"""
    threads = update.message.text.strip()
    if not threads.startswith('@'):
        await update.message.reply_text("❌ Формат: @username\nПопробуйте снова:")
        return REG_THREADS
    
    context.user_data['threads'] = threads
    
    keyboard = [
        [InlineKeyboardButton("👨 Мужской", callback_data="gender_m"),
         InlineKeyboardButton("👩 Женский", callback_data="gender_f")]
    ]
    await update.message.reply_text(
        "Шаг 3/4: Выберите ваш пол:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return REG_GENDER


async def reg_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение пола"""
    query = update.callback_query
    await query.answer()
    
    gender = 'М' if query.data == 'gender_m' else 'Ж'
    context.user_data['gender'] = gender
    
    await query.edit_message_text(
        "Шаг 4/4: Введите ваш возраст\n"
        "Формат: число (13-100)"
    )
    return REG_AGE


async def reg_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение регистрации"""
    try:
        age = int(update.message.text.strip())
        if age < 13 or age > 100:
            await update.message.reply_text("❌ Возраст: 13-100\nПопробуйте снова:")
            return REG_AGE
        
        user_id = update.effective_user.id
        user_number = generate_user_number(context.user_data['gender'])
        
        user_data = {
            'number': user_number,
            'username': update.effective_user.username,
            'instagram': context.user_data['instagram'],
            'threads': context.user_data['threads'],
            'gender': context.user_data['gender'],
            'age': age,
            'trixiki': START_TRIXIKI,
            'max_limit': START_TRIXIKI,
            'daily_claimed': False,
            'usdt_address': None,
            'subscribed': False,
            'banned': False,
            'can_create_tasks': True,
            'daily_tasks_created': {'likes': 0, 'comments': 0, 'follows': 0},
            'stats': {
                'likes_given': 0,
                'likes_received': 0,
                'comments_given': 0,
                'comments_received': 0,
                'follows_given': 0,
                'follows_received': 0,
                'total_earned': 0
            },
            'achievements': [],
            'created_at': datetime.now(BUDAPEST_TZ).isoformat(),
            'last_interaction': {}
        }
        
        create_user(user_id, user_data)
        
        await update.message.reply_text(
            f"✅ Регистрация завершена!\n\n"
            f"🆔 Номер: {user_number}\n"
            f"👤 {context.user_data['gender']} | {age} лет\n"
            f"📸 Instagram: {context.user_data['instagram']}\n"
            f"🧵 Threads: {context.user_data['threads']}\n"
            f"🪃 Баланс: {START_TRIXIKI} триксиков\n\n"
            f"🔥 Подпишись на {INSTAGRAM_ACCOUNT} и {THREADS_ACCOUNT}\n"
            f"чтобы увеличить лимит до 20!\n\n"
            f"Используй /daily для ежедневного бонуса!",
            reply_markup=get_user_keyboard()
        )
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ Введите число (возраст):")
        return REG_AGE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена регистрации"""
    await update.message.reply_text("❌ Регистрация отменена", reply_markup=get_user_keyboard())
    context.user_data.clear()
    return ConversationHandler.END
