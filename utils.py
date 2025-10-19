"""
Вспомогательные функции
"""
import random
import re
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import FORBIDDEN_PATTERNS, BUDAPEST_TZ
from database import users_db


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
            number = random.randrange(1, 10000, 2)  # нечетные
        else:
            number = random.randrange(2, 10000, 2)  # четные
        
        if not any(u.get('number') == number for u in users_db.values()):
            return number


def is_content_safe(text: str) -> bool:
    """Проверка на запрещенный контент"""
    text_lower = text.lower()
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, text_lower):
            return False
    return True


def can_interact(user1_id: int, user2_id: int) -> bool:
    """Проверка возможности взаимодействия (раз в 8 часов)"""
    user1 = users_db.get(user1_id)
    if not user1:
        return True
    
    last_interaction = user1.get('last_interaction', {}).get(user2_id)
    if not last_interaction:
        return True
    
    time_passed = (datetime.now(BUDAPEST_TZ) - last_interaction).total_seconds()
    return time_passed >= 28800  # 8 часов


def format_stats(stats: dict) -> str:
    """Форматирование статистики"""
    return (
        f"❤️ Лайков: {stats['likes_given']}/{stats['likes_received']}\n"
        f"💬 Комментариев: {stats['comments_given']}/{stats['comments_received']}\n"
        f"👥 Подписок: {stats['follows_given']}/{stats['follows_received']}\n"
        f"💰 Заработано: {stats['total_earned']} 🪃"
    )


def get_task_type_emoji(task_type: str) -> str:
    """Эмодзи для типа задания"""
    emojis = {
        'like': '❤️',
        'comment': '💬',
        'special': '💬',
        'follow': '👥'
    }
    return emojis.get(task_type, '📋')


def generate_task_id(user_id: int) -> str:
    """Генерация ID задания"""
    return f"{user_id}_{int(datetime.now().timestamp())}"
