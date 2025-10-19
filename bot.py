"""
Главный файл бота
"""
import logging
from datetime import datetime, timedelta
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from telegram import Update
from telegram.ext import ContextTypes

# Импорты модулей
from config import BOT_TOKEN, BUDAPEST_TZ, ADMIN_GROUP_ID
from database import clear_daily_data, users_db
from handlers import registration, commands, callbacks, admin, tasks

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
(REG_INSTAGRAM, REG_THREADS, REG_GENDER, REG_AGE) = range(4)


async def reset_daily(context):
    """Ежедневный сброс в 20:00"""
    logger.info(f"Daily reset at {datetime.now(BUDAPEST_TZ)}")
    clear_daily_data()
    
    for user_id in users_db.keys():
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🌙 Новый день! Триксики сброшены.\nИспользуй /daily!"
            )
        except Exception as e:
            logger.error(f"Error notifying user {user_id}: {e}")


async def send_announcements(context):
    """Рассылка анонсов"""
    await tasks.send_task_announcements(context)


async def text_message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Маршрутизация текстовых сообщений"""
    # Сначала проверяем админские MyCom задания
    if await admin.handle_mycom_admin_input(update, context):
        return
    
    # Затем обычная обработка заданий
    await tasks.handle_text_message(update, context)


def main():
    """Запуск бота"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен!")
        return
    
    # Создание приложения с отключенным job_queue
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчик регистрации
    reg_handler = ConversationHandler(
        entry_points=[CommandHandler('reg', registration.reg_start)],
        states={
            REG_INSTAGRAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, registration.reg_instagram)],
            REG_THREADS: [MessageHandler(filters.TEXT & ~filters.COMMAND, registration.reg_threads)],
            REG_GENDER: [CallbackQueryHandler(registration.reg_gender, pattern='^gender_')],
            REG_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, registration.reg_age)],
        },
        fallbacks=[CommandHandler('cancel', registration.cancel)]
    )
    
    # Команды пользователя
    application.add_handler(CommandHandler('start', commands.start))
    application.add_handler(reg_handler)
    application.add_handler(CommandHandler('daily', commands.daily))
    application.add_handler(CommandHandler('help', commands.help_command))
    application.add_handler(CommandHandler('pool', commands.pool))
    application.add_handler(CommandHandler('stats', commands.stats))
    application.add_handler(CommandHandler('top', commands.top))
    application.add_handler(CommandHandler('check', commands.check))
    application.add_handler(CommandHandler('randompool', commands.randompool))
    application.add_handler(CommandHandler('addusdt', commands.addusdt))
    application.add_handler(CommandHandler('donate', commands.donate))
    application.add_handler(CommandHandler('onanons', commands.onanons))
    application.add_handler(CommandHandler('offanons', commands.offanons))
    
    # Админ команды
    application.add_handler(CommandHandler('limit', admin.admin_limit))
    application.add_handler(CommandHandler('balance', admin.admin_balance))
    application.add_handler(CommandHandler('trixikichange', admin.admin_trixikichange))
    application.add_handler(CommandHandler('trixikiadd', admin.admin_trixikiadd))
    application.add_handler(CommandHandler('localgirls', admin.admin_localgirls))
    application.add_handler(CommandHandler('localboys', admin.admin_localboys))
    application.add_handler(CommandHandler('liketimeon', admin.admin_liketimeon))
    application.add_handler(CommandHandler('liketimeoff', admin.admin_liketimeoff))
    application.add_handler(CommandHandler('giftstart', admin.giftstart))
    application.add_handler(CommandHandler('mycomadminadd', admin.mycomadminadd))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(callbacks.callback_router))
    
    # Текстовые сообщения
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        text_message_router
    ))
    
    # Временное отключение job queue для обхода ошибки
    logger.warning("JobQueue временно отключен из-за ошибки weak reference")
    
    # Альтернатива: ручной запуск задач через asyncio
    # Вместо job queue можно использовать отдельные asyncio задачи
    
    logger.info("🚀 Trixiki Bot запущен!")
    logger.info(f"📊 Админ группа: {ADMIN_GROUP_ID}")
    
    # Запуск polling
    application.run_polling(
        allowed_updates=['message', 'callback_query'],
        close_loop=False
    )


if __name__ == '__main__':
    main()
