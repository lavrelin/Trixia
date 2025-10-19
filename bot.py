# В bot.py добавьте:
import os
from sqlalchemy import create_engine

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    engine = create_engine(DATABASE_URL)
    # Используйте engine для работы с БД
