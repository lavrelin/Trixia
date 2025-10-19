"""
Конфигурация бота
"""
import os
import pytz

# Токен бота
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8365633345:AAE2VnePSyEiTn0vtEynwd3r5rBOBBuTteE')

# ID групп
ADMIN_GROUP_ID = int(os.environ.get('ADMIN_GROUP_ID', -4843909295))
USER_CHAT_ID = int(os.environ.get('USER_CHAT_ID', -1003088023508))

# Социальные сети
INSTAGRAM_ACCOUNT = os.environ.get('INSTAGRAM_ACCOUNT', '@budapesttrix')
THREADS_ACCOUNT = os.environ.get('THREADS_ACCOUNT', '@budapesttrix')

# Часовой пояс
BUDAPEST_TZ = pytz.timezone('Europe/Budapest')

# Стоимость заданий
TASK_COSTS = {
    'like': 3,
    'comment': 4,
    'special': 10,
    'follow': 5
}

# Дневные лимиты
DAILY_LIMITS = {
    'like': 3,
    'comment': 2,
    'special': 2,
    'follow': 999
}

# Триксики
START_TRIXIKI = 15
MAX_TRIXIKI = 50
DAILY_BONUS_MIN = 3
DAILY_BONUS_MAX = 9

# Таймеры (в секундах)
TASK_FREEZE_TIME = 10800  # 3 часа
INTERACTION_COOLDOWN = 28800  # 8 часов
REPORT_COOLDOWN = 3600  # 1 час

# Достижения
ACHIEVEMENTS = {
    'likes': [100, 200, 300, 500, 1000],
    'comments': [50, 100, 200, 500],
    'follows': [20, 50, 100, 200]
}

# Запрещенные слова
FORBIDDEN_PATTERNS = [
    r'casino', r'porn', r'xxx', r'sex', r'viagra',
    r'ставки', r'казино', r'18\+', r'секс'
]
