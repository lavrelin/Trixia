"""
База данных (в памяти)
"""
from typing import Dict, List

# Пользователи
users_db: Dict = {}

# Задания
tasks_db: List = []

# Замороженные задания
frozen_tasks: Dict = {}

# Админские задания
admin_tasks: List = []

# Донаты
donations: Dict = {
    'goal': 'Развитие проекта',
    'amount': '0 USDT',
    'description': 'Поддержите развитие Trixiki Bot!',
    'donors': [],
    'reports': []
}

# Жалобы пользователей (user_id: last_report_time)
user_reports: Dict = {}

# Подписчики анонсов
announcement_subscribers: List = []


def get_user(user_id: int) -> dict:
    """Получить пользователя"""
    return users_db.get(user_id)


def create_user(user_id: int, data: dict):
    """Создать пользователя"""
    users_db[user_id] = data


def update_user(user_id: int, updates: dict):
    """Обновить данные пользователя"""
    if user_id in users_db:
        users_db[user_id].update(updates)


def get_all_users() -> Dict:
    """Получить всех пользователей"""
    return users_db


def add_task(task: dict):
    """Добавить задание"""
    tasks_db.append(task)


def remove_task(task_id: str):
    """Удалить задание"""
    global tasks_db
    tasks_db = [t for t in tasks_db if t['id'] != task_id]


def get_task(task_id: str) -> dict:
    """Получить задание по ID"""
    return next((t for t in tasks_db if t['id'] == task_id), None)


def get_available_tasks(user_id: int, limit: int = 10) -> List:
    """Получить доступные задания для пользователя"""
    return [t for t in tasks_db if t['creator_id'] != user_id][:limit]


def freeze_task(task_id: str, data: dict):
    """Заморозить задание"""
    frozen_tasks[task_id] = data


def unfreeze_task(task_id: str):
    """Разморозить задание"""
    if task_id in frozen_tasks:
        del frozen_tasks[task_id]


def get_frozen_task(task_id: str) -> dict:
    """Получить замороженное задание"""
    return frozen_tasks.get(task_id)


def clear_daily_data():
    """Очистка ежедневных данных"""
    tasks_db.clear()
    for user in users_db.values():
        user['daily_claimed'] = False
        user['trixiki'] = 0
        user['daily_tasks_created'] = {'likes': 0, 'comments': 0, 'follows': 0}
