# Заморозка триксиков
    frozen_tasks[task_id] = {
        'executor_id': user_id,
        'task': task,
        'frozen_at': datetime.now(BUDAPEST_TZ),
        'unfreezes_at': datetime.now(BUDAPEST_TZ) + timedelta(hours=3)
    }
    
    # Обновить последнее взаимодействие
    if user_id in users_db:
        users_db[user_id]['last_interaction'][task['creator_id']] = datetime.now(BUDAPEST_TZ)
    
    # Уведомление создателю
    creator_id = task['creator_id']
    executor = users_db.get(user_id, {})
    
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{task_id}"),
         InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{task_id}")]
    ]
    
    try:
        await context.bot.send_message(
            chat_id=creator_id,
            text=(
                f"🔔 ЗАДАНИЕ ВЫПОЛНЕНО\n\n"
                f"Пользователь: @{executor.get('username', 'unknown')}\n"
                f"Тип: {task['type'].upper()}\n"
                f"Награда: {task['reward']} 🪃\n\n"
                f"⏰ Подтвердите в течение 3 часов\n"
                f"Иначе триксики будут переведены автоматически"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Error notifying creator: {e}")
    
    await query.edit_message_text(
        "✅ Задание отмечено как выполненное!\n\n"
        "⏳ Ожидайте подтверждения от создателя (до 3 часов)\n"
        "Триксики заморожены на это время.",
        reply_markup=get_user_keyboard()
    )
    
    # Автоподтверждение через 3 часа
    context.job_queue.run_once(
        auto_confirm_task,
        when=10800,
        data={'task_id': task_id}
    )


async def confirm_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("✅ Задание подтверждено!")
    
    task_id = query.data.split('_')[1]
    frozen = frozen_tasks.get(task_id)
    
    if not frozen:
        await query.edit_message_text("❌ Задание уже обработано!")
        return
    
    executor_id = frozen['executor_id']
    task = frozen['task']
    reward = task['reward']
    
    # Начисление триксиков
    if executor_id in users_db:
        executor = users_db[executor_id]
        executor['trixiki'] = min(executor['trixiki'] + reward, executor['max_limit'])
        executor['stats']['total_earned'] += reward
        
        # Обновление статистики
        if task['type'] == 'like':
            executor['stats']['likes_given'] += 1
            users_db[task['creator_id']]['stats']['likes_received'] += 1
        elif 'comment' in task['type']:
            executor['stats']['comments_given'] += 1
            users_db[task['creator_id']]['stats']['comments_received'] += 1
        elif task['type'] == 'follow':
            executor['stats']['follows_given'] += 1
            users_db[task['creator_id']]['stats']['follows_received'] += 1
        
        # Проверка достижений
        await check_achievements(executor_id, context)
        
        try:
            await context.bot.send_message(
                chat_id=executor_id,
                text=f"✅ Задание подтверждено!\n\n+{reward} 🪃\n\nТекущий баланс: {executor['trixiki']}/{executor['max_limit']}"
            )
        except Exception as e:
            logger.error(f"Error: {e}")
    
    # Удаление задания
    tasks_db[:] = [t for t in tasks_db if t['id'] != task_id]
    del frozen_tasks[task_id]
    
    await query.edit_message_text("✅ Задание подтверждено и триксики переведены!")


async def reject_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("❌ Задание отклонено")
    
    task_id = query.data.split('_')[1]
    frozen = frozen_tasks.get(task_id)
    
    if not frozen:
        await query.edit_message_text("❌ Задание уже обработано!")
        return
    
    executor = users_db.get(frozen['executor_id'], {})
    creator = users_db.get(frozen['task']['creator_id'], {})
    
    # Отправка в админ-группу
    try:
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=(
                f"⚠️ СПОРНОЕ ЗАДАНИЕ\n\n"
                f"Создатель: @{creator.get('username', 'unknown')}\n"
                f"Исполнитель: @{executor.get('username', 'unknown')}\n"
                f"Тип: {frozen['task']['type']}\n"
                f"Ссылка: {frozen['task']['link']}\n\n"
                f"Создатель отклонил выполнение."
            )
        )
    except Exception as e:
        logger.error(f"Error: {e}")
    
    del frozen_tasks[task_id]
    await query.edit_message_text("❌ Задание отклонено и отправлено на рассмотрение админам.")


async def auto_confirm_task(context: ContextTypes.DEFAULT_TYPE):
    """Автоподтверждение через 3 часа"""
    task_id = context.job.data['task_id']
    
    if task_id not in frozen_tasks:
        return
    
    frozen = frozen_tasks[task_id]
    executor_id = frozen['executor_id']
    reward = frozen['task']['reward']
    
    if executor_id in users_db:
        executor = users_db[executor_id]
        executor['trixiki'] = min(executor['trixiki'] + reward, executor['max_limit'])
        executor['stats']['total_earned'] += reward
        
        try:
            await context.bot.send_message(
                chat_id=executor_id,
                text=f"✅ Задание автоматически подтверждено!\n\n+{reward} 🪃"
            )
        except Exception as e:
            logger.error(f"Error: {e}")
    
    tasks_db[:] = [t for t in tasks_db if t['id'] != task_id]
    del frozen_tasks[task_id]


async def check_achievements(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Проверка достижений"""
    user = users_db.get(user_id)
    if not user:
        return
    
    stats = user['stats']
    achievements = user['achievements']
    new_achievements = []
    
    # Лайки
    for milestone in [100, 200, 300, 500, 1000]:
        ach_name = f"likes_{milestone}"
        if stats['likes_given'] >= milestone and ach_name not in achievements:
            achievements.append(ach_name)
            new_achievements.append(f"🏆 {milestone} лайков поставлено!")
    
    # Комментарии
    for milestone in [50, 100, 200, 500]:
        ach_name = f"comments_{milestone}"
        if stats['comments_given'] >= milestone and ach_name not in achievements:
            achievements.append(ach_name)
            new_achievements.append(f"🏆 {milestone} комментариев написано!")
    
    # Подписки
    for milestone in [20, 50, 100, 200]:
        ach_name = f"follows_{milestone}"
        if stats['follows_given'] >= milestone and ach_name not in achievements:
            achievements.append(ach_name)
            new_achievements.append(f"🏆 {milestone} подписок сделано!")
    
    # Уведомления
    if new_achievements:
        achievement_text = "\n".join(new_achievements)
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 НОВЫЕ ДОСТИЖЕНИЯ!\n\n{achievement_text}"
            )
            
            await context.bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                text=f"🏆 @{user['username']} получил достижения:\n{achievement_text}"
            )
        except Exception as e:
            logger.error(f"Error: {e}")


# ============== CALLBACK HANDLER ==============

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "profile":
        await show_profile(query, context)
    elif data == "trixiki":
        await show_trixiki(query, context)
    elif data == "pool":
        await show_pool_callback(query, context)
    elif data == "actions":
        await create_task_start(update, context)
    elif data == "quest_done":
        await complete_quest(query, context)
    elif data.startswith("task_"):
        await handle_task_creation(update, context)
    elif data.startswith("dotask_"):
        await do_task_callback(update, context)
    elif data.startswith("done_"):
        await task_done_callback(update, context)
    elif data.startswith("confirm_"):
        await confirm_task_callback(update, context)
    elif data.startswith("reject_"):
        await reject_task_callback(update, context)
    elif data == "back_main":
        await query.edit_message_text(
            "Главное меню:",
            reply_markup=get_user_keyboard()
        )
    elif data == "subscribe_check":
        await check_subscription(query, context)
    elif data == "anons_on":
        await toggle_announcements(query, context, True)
    elif data == "anons_off":
        await toggle_announcements(query, context, False)


async def show_profile(query, context):
    user_id = query.from_user.id
    
    if user_id not in users_db:
        await query.edit_message_text("Зарегистрируйтесь: /reg")
        return
    
    user = users_db[user_id]
    stats = user['stats']
    
    profile_text = (
        f"🌀 ПРОФИЛЬ\n\n"
        f"🆔 Номер: {user['number']}\n"
        f"👤 {user['gender']} | {user['age']} лет\n"
        f"📸 Instagram: {user['instagram']}\n"
        f"🧵 Threads: {user['threads']}\n\n"
        f"🪃 Триксики: {user['trixiki']}/{user['max_limit']}\n"
        f"💰 Всего заработано: {stats['total_earned']}\n\n"
        f"📊 СТАТИСТИКА:\n"
        f"❤️ Лайков: {stats['likes_given']}/{stats['likes_received']}\n"
        f"💬 Комментариев: {stats['comments_given']}/{stats['comments_received']}\n"
        f"👥 Подписок: {stats['follows_given']}/{stats['follows_received']}\n\n"
        f"🏆 Достижений: {len(user['achievements'])}"
    )
    
    keyboard = [[InlineKeyboardButton("« Назад", callback_data="back_main")]]
    
    if not user.get('subscribed'):
        keyboard.insert(0, [InlineKeyboardButton(
            "⬆️ Увеличить лимит до 20",
            callback_data="subscribe_check"
        )])
    
    await query.edit_message_text(profile_text, reply_markup=InlineKeyboardMarkup(keyboard))


async def show_trixiki(query, context):
    user_id = query.from_user.id
    
    if user_id not in users_db:
        await query.edit_message_text("Зарегистрируйтесь: /reg")
        return
    
    user = users_db[user_id]
    
    await query.edit_message_text(
        f"🪃 ВАШ БАЛАНС\n\n"
        f"Текущий: {user['trixiki']} 🪃\n"
        f"Максимум: {user['max_limit']} 🪃\n\n"
        f"💡 Используй /daily для бонуса\n"
        f"✨ Выполняй задания для заработка",
        reply_markup=get_user_keyboard()
    )


async def show_pool_callback(query, context):
    user_id = query.from_user.id
    
    if not tasks_db:
        await query.edit_message_text(
            "🧊 Пул заданий пуст!",
            reply_markup=get_user_keyboard()
        )
        return
    
    available_tasks = [t for t in tasks_db if t['creator_id'] != user_id][:5]
    
    if not available_tasks:
        await query.edit_message_text(
            "🧊 Нет доступных заданий",
            reply_markup=get_user_keyboard()
        )
        return
    
    text = "🧊 ДОСТУПНЫЕ ЗАДАНИЯ:\n\n"
    buttons = []
    
    for idx, task in enumerate(available_tasks, 1):
        creator = users_db.get(task['creator_id'], {})
        text += f"{idx}. {task['type'].upper()} | {task['reward']} 🪃\n"
        buttons.append([InlineKeyboardButton(
            f"✅ #{idx}",
            callback_data=f"dotask_{task['id']}"
        )])
    
    buttons.append([InlineKeyboardButton("« Назад", callback_data="back_main")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def complete_quest(query, context):
    user_id = query.from_user.id
    
    if user_id not in users_db:
        return
    
    user = users_db[user_id]
    reward = user['max_limit']
    user['trixiki'] = min(user['trixiki'] + reward, user['max_limit'])
    
    await query.edit_message_text(
        f"✅ Квест выполнен!\n\n"
        f"+{reward} 🪃\n\n"
        f"Баланс: {user['trixiki']}/{user['max_limit']}"
    )


async def check_subscription(query, context):
    user_id = query.from_user.id
    
    keyboard = [
        [InlineKeyboardButton("✅ Подписался", callback_data="sub_confirm")],
        [InlineKeyboardButton("« Назад", callback_data="profile")]
    ]
    
    await query.edit_message_text(
        f"📢 ДЛЯ УВЕЛИЧЕНИЯ ЛИМИТА\n\n"
        f"Подпишитесь на:\n"
        f"📸 Instagram: {INSTAGRAM_ACCOUNT}\n"
        f"🧵 Threads: {THREADS_ACCOUNT}\n\n"
        f"После подписки нажмите кнопку:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def toggle_announcements(query, context, enable: bool):
    user_id = query.from_user.id
    
    if enable:
        if user_id not in announcement_subscribers:
            announcement_subscribers.append(user_id)
        msg = "✅ Анонсы включены!"
    else:
        if user_id in announcement_subscribers:
            announcement_subscribers.remove(user_id)
        msg = "❌ Анонсы отключены"
    
    await query.answer(msg)


# ============== ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ ==============

async def addusdt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in users_db:
        await update.message.reply_text("Зарегистрируйтесь: /reg")
        return
    
    await update.message.reply_text(
        "🔐 USDT TRC-20\n\n"
        "Введите ваш USDT TRC-20 адрес:\n"
        "(Начинается с T...)"
    )
    
    context.user_data['adding_usdt'] = True


async def donate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎯 Цель", callback_data="donate_goal")],
        [InlineKeyboardButton("👥 Донаторы", callback_data="donate_donors")],
        [InlineKeyboardButton("💳 Реквизиты", callback_data="donate_details")],
        [InlineKeyboardButton("📊 Отчеты", callback_data="donate_reports")]
    ]
    
    await update.message.reply_text(
        "💳 ДОНАТЫ\n\n"
        "Поддержите развитие проекта!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        target_id = update.effective_user.id
    else:
        username = context.args[0].replace('@', '')
        target_id = None
        for uid, udata in users_db.items():
            if udata.get('username') == username:
                target_id = uid
                break
        
        if not target_id:
            await update.message.reply_text("❌ Пользователь не найден")
            return
    
    if target_id not in users_db:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    user = users_db[target_id]
    stats = user['stats']
    
    text = (
        f"📊 СТАТИСТИКА @{user.get('username', 'unknown')}\n\n"
        f"❤️ Лайков: {stats['likes_given']} отдано / {stats['likes_received']} получено\n"
        f"💬 Комментариев: {stats['comments_given']} / {stats['comments_received']}\n"
        f"👥 Подписок: {stats['follows_given']} / {stats['follows_received']}\n"
        f"💰 Заработано: {stats['total_earned']} 🪃\n\n"
        f"🏆 Достижений: {len(user['achievements'])}\n"
        f"🪃 Лимит: {user['max_limit']}"
    )
    
    await update.message.reply_text(text)


async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("❤️ Лайки", callback_data="top_likes")],
        [InlineKeyboardButton("💬 Комментарии", callback_data="top_comments")],
        [InlineKeyboardButton("👥 Подписки", callback_data="top_follows")],
        [InlineKeyboardButton("🪃 Лимит", callback_data="top_limit")]
    ]
    
    await update.message.reply_text(
        "🏆 РЕЙТИНГ\n\nВыберите категорию:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Использование: /check @username причина\n\n"
            "Можно отправлять 1 жалобу в час"
        )
        return
    
    # Проверка лимита
    last_report = user_reports.get(user_id)
    if last_report:
        time_passed = (datetime.now(BUDAPEST_TZ) - last_report).total_seconds()
        if time_passed < 3600:
            minutes_left = int((3600 - time_passed) / 60)
            await update.message.reply_text(f"⏰ Следующая жалоба через {minutes_left} минут")
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
        
        user_reports[user_id] = datetime.now(BUDAPEST_TZ)
        await update.message.reply_text("✅ Жалоба отправлена администрации")
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Ошибка отправки")


async def randompool_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in users_db:
        await update.message.reply_text("Зарегистрируйтесь: /reg")
        return
    
    available = [t for t in tasks_db if t['creator_id'] != user_id]
    
    if not available:
        await update.message.reply_text("🧊 Нет доступных заданий")
        return
    
    task = random.choice(available)
    creator = users_db.get(task['creator_id'], {})
    
    text = (
        f"🎲 СЛУЧАЙНОЕ ЗАДАНИЕ\n\n"
        f"Тип: {task['type'].upper()}\n"
        f"От: @{creator.get('username', 'unknown')}\n"
        f"Ссылка: {task['link']}\n"
    )
    
    if 'comment' in task:
        text += f"\nКомментарий:\n{task['comment']}\n"
    
    text += f"\n💰 Награда: {task['reward']} 🪃"
    
    keyboard = [[InlineKeyboardButton("✅ Выполнить", callback_data=f"dotask_{task['id']}")]]
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def onanons_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in announcement_subscribers:
        announcement_subscribers.append(user_id)
    
    await update.message.reply_text("✅ Анонсы включены!\n\nВы будете получать уведомления о новых заданиях")


async def offanons_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in announcement_subscribers:
        announcement_subscribers.remove(user_id)
    
    await update.message.reply_text("❌ Анонсы отключены")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 СПРАВКА TRIXIKI BOT\n\n"
        "🎯 ОСНОВНЫЕ:\n"
        "/start - Начало\n"
        "/reg - Регистрация\n"
        "/daily - Ежедневный бонус\n"
        "/profile - Профиль\n"
        "/trixiki - Баланс\n"
        "/pool - Задания\n"
        "/randompool - Случайное задание\n\n"
        "📊 СТАТИСТИКА:\n"
        "/stats [@user] - Статистика\n"
        "/top - Рейтинг\n\n"
        "💰 ЦЕНЫ:\n"
        "❤️ Like - 3 🪃 (макс 3/день)\n"
        "💬 Comment - 4 🪃 (макс 2/день)\n"
        "💬 Special - 10 🪃\n"
        "👥 Follow - 5 🪃\n\n"
        "🔧 ДОПОЛНИТЕЛЬНО:\n"
        "/addusdt - Добавить USDT адрес\n"
        "/donate - Донаты\n"
        "/check @user - Жалоба (1/час)\n"
        "/onanons - Включить анонсы\n"
        "/offanons - Отключить анонсы\n\n"
        "⚠️ ПРАВИЛА:\n"
        "• Не удалять в течение недели\n"
        "• Один человек = один аккаунт\n"
        "• Фейковые аккаунты блокируются\n"
        "• Взаимодействие раз в 8 часов\n\n"
        f"💬 Чат: https://t.me/c/{str(USER_CHAT_ID)[4:]}/1"
    )
    
    await update.message.reply_text(help_text)


# ============== АДМИН-КОМАНДЫ ==============

async def admin_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                    text=f"🎉 Ваш лимит изменен на {new_limit} триксиков!"
                )
            except Exception as e:
                logger.error(f"Error: {e}")
            return
    
    await update.message.reply_text(f"Пользователь @{username} не найден")


async def admin_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            user_data['trixiki'] = min(user_data['trixiki'] + amount, user_data['max_limit'])
            await update.message.reply_text(
                f"✅ @{username} +{amount} 🪃\nНовый баланс: {user_data['trixiki']}"
            )
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎁 Вы получили +{amount} 🪃!"
                )
            except Exception as e:
                logger.error(f"Error: {e}")
            return
    
    await update.message.reply_text(f"@{username} не найден")


async def admin_localgirls(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                    text="❌ Вам запрещено создавать задания"
                )
            except Exception as e:
                logger.error(f"Error: {e}")
            return
    
    await update.message.reply_text(f"@{username} не найден")


async def giftstart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    daily_users = [uid for uid, u in users_db.items() if u.get('daily_claimed')]
    
    if not daily_users:
        await update.message.reply_text("Нет активных пользователей сегодня")
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
                text="🎁 Поздравляем! Ваш лимит увеличен на +1!"
            )
        except Exception as e:
            logger.error(f"Error: {e}")
    
    await update.message.reply_text(result)


# ============== ОБРАБОТКА СООБЩЕНИЙ ==============

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # Обработка USDT адреса
    if context.user_data.get('adding_usdt'):
        if text.startswith('T') and len(text) == 34:
            users_db[user_id]['usdt_address'] = text
            await update.message.reply_text(
                f"✅ USDT адрес сохранен!\n\n{text}",
                reply_markup=get_user_keyboard()
            )
            context.user_data.clear()
        else:
            await update.message.reply_text("❌ Некорректный адрес USDT TRC-20\nПопробуйте снова:")
        return
    
    # Обработка создания задания
    if 'creating_task' in context.user_data:
        if 'link' in context.user_data['creating_task']:
            await handle_special_comment(update, context)
        else:
            await handle_task_link(update, context)
        return


# ============== ОСНОВНАЯ ФУНКЦИЯ ==============

def main():
    """Запуск бота"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен!")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчик регистрации
    reg_handler = ConversationHandler(
        entry_points=[CommandHandler('reg', reg_start)],
        states={
            REG_INSTAGRAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_instagram)],
            REG_THREADS: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_threads)],
            REG_GENDER: [CallbackQueryHandler(reg_gender, pattern='^gender_')],
            REG_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_age)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Команды пользователя
    application.add_handler(CommandHandler('start', start))
    application.add_handler(reg_handler)
    application.add_handler(CommandHandler('daily', daily_command))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('pool', pool_command))
    application.add_handler(CommandHandler('stats', stats_command))
    application.add_handler(CommandHandler('top', top_command))
    application.add_handler(CommandHandler('check', check_command))
    application.add_handler(CommandHandler('randompool', randompool_command))
    application.add_handler(CommandHandler('addusdt', addusdt_command))
    application.add_handler(CommandHandler('donate', donate_command))
    application.add_handler(CommandHandler('onanons', onanons_command))
    application.add_handler(CommandHandler('offanons', offanons_command))
    
    # Админ команды
    application.add_handler(CommandHandler('limit', admin_limit))
    application.add_handler(CommandHandler('balance', admin_balance))
    application.add_handler(CommandHandler('trixikichange', admin_trixikichange))
    application.add_handler(CommandHandler('trixikiadd', admin_trixikiadd))
    application.add_handler(CommandHandler('localgirls', admin_localgirls))
    application.add_handler(CommandHandler('localboys', admin_localboys))
    application.add_handler(CommandHandler('liketimeon', admin_liketimeon))
    application.add_handler(CommandHandler('liketimeoff', admin_liketimeoff))
    application.add_handler(CommandHandler('giftstart', giftstart_command))
    
    # Callback и текстовые сообщения
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # Джобы
    job_queue = application.job_queue
    
    # Ежедневный сброс в 20:00 Budapest
    budapest_time = datetime.now(BUDAPEST_TZ).replace(hour=20, minute=0, second=0)
    job_queue.run_daily(reset_daily_tasks, time=budapest_time.time())
    
    # Анонсы каждые 20-60 минут
    job_queue.run_repeating(
        send_announcements,
        interval=timedelta(minutes=random.randint(20, 60)),
        first=10
    )
    
    logger.info("🚀 Trixiki Bot запущен!")
    logger.info(f"📊 Админ группа: {ADMIN_GROUP_ID}")
    logger.info(f"💬 Чат пользователей: {USER_CHAT_ID}")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
    
    for user_id, user_data in users_db.items():
        if user_data.get('username') == username:
            user_data['trixiki'] = min(amount, user_data['max_limit'])
            await update.message.reply_text(f"✅ Баланс @{username}: {user_data['trixiki']}")
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"💰 Ваш баланс установлен: {user_data['trixiki']} 🪃"
                )
            except Exception as e:
                logger.error(f"Error: {e}")
            return
    
    await update.message.reply_text(f"@{username} не найден")


async def admin_trixikiadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        returnimport os
import logging
import random
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pytz
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8365633345:AAE2VnePSyEiTn0vtEynwd3r5rBOBBuTteE')
ADMIN_GROUP_ID = int(os.environ.get('ADMIN_GROUP_ID', -4843909295))
USER_CHAT_ID = int(os.environ.get('USER_CHAT_ID', -1003088023508))
INSTAGRAM_ACCOUNT = os.environ.get('INSTAGRAM_ACCOUNT', '@budapesttrix')
THREADS_ACCOUNT = os.environ.get('THREADS_ACCOUNT', '@budapesttrix')
BUDAPEST_TZ = pytz.timezone('Europe/Budapest')

# Состояния для ConversationHandler
(REG_INSTAGRAM, REG_THREADS, REG_GENDER, REG_AGE,
 ADD_USDT, CREATE_TASK_TYPE, CREATE_TASK_LINKS,
 CREATE_TASK_COMMENT, CREATE_SPECIAL_COMMENT,
 ADMIN_TASK_DESC, DONATE_SETUP) = range(11)

# База данных
users_db: Dict = {}
tasks_db: List = []
frozen_tasks: Dict = {}
admin_tasks: List = []
donations: Dict = {
    'goal': 'Развитие проекта',
    'amount': '0 USDT',
    'description': 'Поддержите развитие Trixiki Bot!',
    'donors': [],
    'reports': []
}
user_reports: Dict = {}  # user_id: last_report_time
announcement_subscribers: List = []

# Квесты (50 штук)
DAILY_QUESTS = [
    "Поставь лайк на 3 поста в Instagram",
    "Напиши 2 комментария под постами",
    "Подпишись на 1 новый аккаунт",
    "Поделись историей в Instagram",
    "Сохрани 5 постов в закладки",
    "Просмотри 10 сторис",
    "Отметь друга в комментарии",
    "Используй 3 хэштега в посте",
    "Ответь на 2 сторис",
    "Отправь сообщение 3 подписчикам",
    "Добавь пост в коллекцию",
    "Используй фильтр в сторис",
    "Отметь локацию в посте",
    "Сделай репост в сторис",
    "Ответь на 3 комментария",
    "Используй опрос в сторис",
    "Добавь музыку в сторис",
    "Поставь реакцию на 5 сторис",
    "Прокомментируй с вопросом",
    "Поддержи малый бизнес",
    "Используй тренд",
    "Сделай бумеранг",
    "Обратный отсчет в сторис",
    "Отметь бренд",
    "Напиши мотивацию",
    "Поделись рецептом",
    "Стикер с вопросом",
    "Карусельный пост",
    "Добавь GIF",
    "Комментарий с эмодзи",
    "Викторина в сторис",
    "Лайк конкуренту",
    "Подпишись на микроблогера",
    "Слайдер стикер",
    "Длинный комментарий 50+ слов",
    "Коллаборация в сторис",
    "Таймер в рилс",
    "Субтитры к рилс",
    "Лайк старому посту (год+)",
    "Прокомментируй иностранный пост",
    "Стикер с донатами",
    "Инфографика в посте",
    "Поддержи благотворительность",
    "Тренд-аудио в рилс",
    "Совет в комментарии",
    "Поделись воспоминанием",
    "Стикер с ссылкой",
    "Закулисный контент",
    "До/после пост",
    "Поддержи местный бизнес"
]

# Запрещенные слова/паттерны
FORBIDDEN_PATTERNS = [
    r'casino', r'porn', r'xxx', r'sex', r'viagra',
    r'casino', r'ставки', r'казино', r'18\+', r'секс'
]


def get_user_keyboard():
    """Основная клавиатура"""
    keyboard = [
        [InlineKeyboardButton("🧊 Pool", callback_data="pool"),
         InlineKeyboardButton("🪃 Trixiki", callback_data="trixiki")],
        [InlineKeyboardButton("❤️ Like/Comment/Follow", callback_data="actions")],
        [InlineKeyboardButton("🌀 Profile", callback_data="profile")]
    ]
    return InlineKeyboardMarkup(keyboard)


def generate_user_number(gender: str) -> int:
    """Генерация уникального номера"""
    while True:
        if gender.upper() == 'Ж':
            number = random.randrange(1, 10000, 2)
        else:
            number = random.randrange(2, 10000, 2)
        
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


async def reset_daily_tasks(context: ContextTypes.DEFAULT_TYPE):
    """Ежедневный сброс в 20:00"""
    logger.info(f"Daily reset at {datetime.now(BUDAPEST_TZ)}")
    
    tasks_db.clear()
    for user_id, user_data in users_db.items():
        user_data['daily_claimed'] = False
        user_data['trixiki'] = 0
        user_data['daily_tasks_created'] = {'likes': 0, 'comments': 0, 'follows': 0}
    
    for user_id in users_db.keys():
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🌙 Новый день начался! Триксики сброшены.\nИспользуй /daily для бонуса!"
            )
        except Exception as e:
            logger.error(f"Error notifying user {user_id}: {e}")


async def send_announcements(context: ContextTypes.DEFAULT_TYPE):
    """Рассылка анонсов каждые 20-60 минут"""
    if not tasks_db or not announcement_subscribers:
        return
    
    recent_tasks = tasks_db[-5:]
    
    text = "📢 НОВЫЕ ЗАДАНИЯ:\n\n"
    for idx, task in enumerate(recent_tasks, 1):
        creator = users_db.get(task['creator_id'], {})
        text += f"{idx}. {task['type'].upper()} | {task['reward']} 🪃\n"
    
    text += "\nИспользуй /pool для просмотра!"
    
    for user_id in announcement_subscribers:
        try:
            await context.bot.send_message(chat_id=user_id, text=text)
        except Exception as e:
            logger.error(f"Error sending announcement to {user_id}: {e}")


# ============== РЕГИСТРАЦИЯ ==============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in users_db:
        await update.message.reply_text(
            f"С возвращением, {update.effective_user.first_name}! 🎉",
            reply_markup=get_user_keyboard()
        )
    else:
        await update.message.reply_text(
            "👋 Добро пожаловать в Trixiki Bot!\n\n"
            "🎯 Обменивайся активностью в Instagram/Threads\n"
            "🪃 Зарабатывай триксики\n"
            "🏆 Получай достижения\n\n"
            "Используй /reg для регистрации!"
        )


async def reg_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in users_db:
        await update.message.reply_text("Вы уже зарегистрированы! ✅")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📝 РЕГИСТРАЦИЯ\n\n"
        "Шаг 1/4: Введите ваш Instagram аккаунт\n"
        "Формат: @username"
    )
    return REG_INSTAGRAM


async def reg_instagram(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    try:
        age = int(update.message.text.strip())
        if age < 13 or age > 100:
            await update.message.reply_text("❌ Возраст: 13-100\nПопробуйте снова:")
            return REG_AGE
        
        user_id = update.effective_user.id
        user_number = generate_user_number(context.user_data['gender'])
        
        users_db[user_id] = {
            'number': user_number,
            'username': update.effective_user.username,
            'instagram': context.user_data['instagram'],
            'threads': context.user_data['threads'],
            'gender': context.user_data['gender'],
            'age': age,
            'trixiki': 15,
            'max_limit': 15,
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
        
        await update.message.reply_text(
            f"✅ Регистрация завершена!\n\n"
            f"🆔 Номер: {user_number}\n"
            f"👤 {context.user_data['gender']} | {age} лет\n"
            f"📸 Instagram: {context.user_data['instagram']}\n"
            f"🧵 Threads: {context.user_data['threads']}\n"
            f"🪃 Баланс: 15 триксиков\n\n"
            f"💡 Подпишись на {INSTAGRAM_ACCOUNT} и {THREADS_ACCOUNT}\n"
            f"чтобы увеличить лимит до 20 триксиков!\n\n"
            f"Используй /daily для ежедневного бонуса!",
            reply_markup=get_user_keyboard()
        )
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ Введите число (возраст):")
        return REG_AGE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено", reply_markup=get_user_keyboard())
    context.user_data.clear()
    return ConversationHandler.END


# ============== ЕЖЕДНЕВНЫЕ БОНУСЫ ==============

async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in users_db:
        await update.message.reply_text("Сначала зарегистрируйтесь: /reg")
        return
    
    user = users_db[user_id]
    
    if user['daily_claimed']:
        await update.message.reply_text("⏰ Вы уже получили ежедневный бонус!\nСледующий в 00:00 по Будапешту")
        return
    
    base_bonus = random.randint(3, 9)
    quest = random.choice(DAILY_QUESTS)
    quest_reward = user['max_limit']
    
    keyboard = [[InlineKeyboardButton("✅ Выполнил квест", callback_data="quest_done")]]
    
    await update.message.reply_text(
        f"🎁 ЕЖЕДНЕВНЫЙ БОНУС\n\n"
        f"Получено: +{base_bonus} 🪃\n\n"
        f"📋 Квест дня:\n{quest}\n\n"
        f"🎯 Награда: {quest_reward} 🪃\n\n"
        f"Выполните квест и нажмите кнопку:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    user['trixiki'] = min(user['trixiki'] + base_bonus, user['max_limit'])
    user['daily_claimed'] = True


# ============== СОЗДАНИЕ ЗАДАНИЙ ==============

async def create_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user = users_db.get(user_id)
    
    if not user or not user.get('can_create_tasks'):
        await query.edit_message_text("❌ У вас нет доступа к созданию заданий")
        return
    
    keyboard = [
        [InlineKeyboardButton("❤️ Like (3🪃)", callback_data="task_like"),
         InlineKeyboardButton("💬 Comment (4🪃)", callback_data="task_comment")],
        [InlineKeyboardButton("💬 Special (10🪃)", callback_data="task_special"),
         InlineKeyboardButton("👥 Follow (5🪃)", callback_data="task_follow")],
        [InlineKeyboardButton("« Назад", callback_data="back_main")]
    ]
    
    await query.edit_message_text(
        f"❤️ СОЗДАТЬ ЗАДАНИЕ\n\n"
        f"Баланс: {user['trixiki']}/{user['max_limit']} 🪃\n\n"
        f"Сегодня создано:\n"
        f"❤️ Лайков: {user['daily_tasks_created']['likes']}/3\n"
        f"💬 Комментариев: {user['daily_tasks_created']['comments']}/2\n\n"
        f"Выберите тип:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_task_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user = users_db[user_id]
    task_type = query.data.split('_')[1]
    
    costs = {'like': 3, 'comment': 4, 'special': 10, 'follow': 5}
    limits = {'like': 3, 'comment': 2, 'special': 2, 'follow': 999}
    
    cost = costs[task_type]
    limit_key = 'likes' if task_type == 'like' else 'comments' if task_type in ['comment', 'special'] else 'follows'
    
    if user['trixiki'] < cost:
        await query.edit_message_text(
            f"❌ Недостаточно триксиков!\n"
            f"Нужно: {cost} 🪃\nЕсть: {user['trixiki']} 🪃",
            reply_markup=get_user_keyboard()
        )
        return
    
    if user['daily_tasks_created'][limit_key] >= limits[task_type]:
        await query.edit_message_text(
            f"❌ Дневной лимит достигнут!\n"
            f"Создано: {user['daily_tasks_created'][limit_key]}/{limits[task_type]}",
            reply_markup=get_user_keyboard()
        )
        return
    
    context.user_data['creating_task'] = {
        'type': task_type,
        'cost': cost,
        'limit_key': limit_key
    }
    
    if task_type == 'like':
        await query.edit_message_text(
            "📝 Отправьте ссылку на пост Instagram/Threads\n\n"
            "Формат: https://instagram.com/p/xxx или https://threads.net/..."
        )
    elif task_type == 'comment':
        await query.edit_message_text(
            "📝 Отправьте ссылку на пост для комментария\n\n"
            "Формат: https://instagram.com/p/xxx"
        )
    elif task_type == 'special':
        await query.edit_message_text(
            "📝 Шаг 1/2: Отправьте ссылку на пост\n\n"
            "Затем напишите комментарий который хотите получить"
        )
    else:  # follow
        await query.edit_message_text(
            "📝 Отправьте ссылку на профиль для подписки\n\n"
            "Формат: https://instagram.com/username"
        )


async def handle_task_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if 'creating_task' not in context.user_data:
        return
    
    link = update.message.text.strip()
    
    if not (link.startswith('https://instagram.com') or link.startswith('https://threads.net')):
        await update.message.reply_text("❌ Некорректная ссылка! Используйте ссылки Instagram или Threads")
        return
    
    if not is_content_safe(link):
        await update.message.reply_text("❌ Ссылка содержит запрещенный контент!")
        return
    
    task_data = context.user_data['creating_task']
    user = users_db[user_id]
    
    if task_data['type'] == 'special':
        context.user_data['creating_task']['link'] = link
        await update.message.reply_text(
            "📝 Шаг 2/2: Теперь напишите комментарий\n\n"
            "Этот текст будут копировать другие пользователи"
        )
        return
    
    # Создание задания
    task_id = f"{user_id}_{int(datetime.now().timestamp())}"
    
    task = {
        'id': task_id,
        'creator_id': user_id,
        'type': task_data['type'],
        'link': link,
        'reward': task_data['cost'],
        'created_at': datetime.now(BUDAPEST_TZ).isoformat()
    }
    
    tasks_db.append(task)
    user['trixiki'] -= task_data['cost']
    user['daily_tasks_created'][task_data['limit_key']] += 1
    
    await update.message.reply_text(
        f"✅ Задание создано!\n\n"
        f"Тип: {task_data['type'].upper()}\n"
        f"Списано: {task_data['cost']} 🪃\n"
        f"Баланс: {user['trixiki']}/{user['max_limit']} 🪃\n\n"
        f"Задание добавлено в пул!",
        reply_markup=get_user_keyboard()
    )
    
    context.user_data.clear()


async def handle_special_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if 'creating_task' not in context.user_data or 'link' not in context.user_data['creating_task']:
        return
    
    comment = update.message.text.strip()
    
    if not is_content_safe(comment):
        await update.message.reply_text("❌ Комментарий содержит запрещенный контент!")
        return
    
    if len(comment) > 500:
        await update.message.reply_text("❌ Комментарий слишком длинный (макс 500 символов)")
        return
    
    task_data = context.user_data['creating_task']
    user = users_db[user_id]
    
    task_id = f"{user_id}_{int(datetime.now().timestamp())}"
    
    task = {
        'id': task_id,
        'creator_id': user_id,
        'type': 'special_comment',
        'link': task_data['link'],
        'comment': comment,
        'reward': task_data['cost'],
        'created_at': datetime.now(BUDAPEST_TZ).isoformat()
    }
    
    tasks_db.append(task)
    user['trixiki'] -= task_data['cost']
    user['daily_tasks_created'][task_data['limit_key']] += 1
    
    await update.message.reply_text(
        f"✅ Special Comment создан!\n\n"
        f"Комментарий: {comment[:50]}...\n"
        f"Списано: {task_data['cost']} 🪃\n"
        f"Баланс: {user['trixiki']}/{user['max_limit']} 🪃",
        reply_markup=get_user_keyboard()
    )
    
    context.user_data.clear()


# ============== ПУЛ ЗАДАНИЙ ==============

async def pool_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in users_db:
        await update.message.reply_text("Сначала зарегистрируйтесь: /reg")
        return
    
    if not tasks_db:
        await update.message.reply_text(
            "🧊 Пул заданий пуст!\n\n"
            "Создайте первое задание через ❤️ Like/Comment/Follow",
            reply_markup=get_user_keyboard()
        )
        return
    
    available_tasks = [t for t in tasks_db if t['creator_id'] != user_id][:10]
    
    if not available_tasks:
        await update.message.reply_text(
            "🧊 Нет доступных заданий для вас",
            reply_markup=get_user_keyboard()
        )
        return
    
    text = "🧊 ДОСТУПНЫЕ ЗАДАНИЯ:\n\n"
    buttons = []
    
    for idx, task in enumerate(available_tasks, 1):
        creator = users_db.get(task['creator_id'], {})
        text += (
            f"{idx}. {task['type'].upper()}\n"
            f"   Награда: {task['reward']} 🪃\n"
            f"   От: @{creator.get('username', 'unknown')}\n\n"
        )
        buttons.append([InlineKeyboardButton(
            f"✅ Выполнить #{idx}",
            callback_data=f"dotask_{task['id']}"
        )])
    
    buttons.append([InlineKeyboardButton("🔄 Обновить", callback_data="pool")])
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def do_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    task_id = query.data.split('_')[1]
    
    task = next((t for t in tasks_db if t['id'] == task_id), None)
    
    if not task:
        await query.edit_message_text("❌ Задание не найдено или уже выполнено!")
        return
    
    if task['creator_id'] == user_id:
        await query.edit_message_text("❌ Вы не можете выполнить свое задание!")
        return
    
    if not can_interact(user_id, task['creator_id']):
        await query.edit_message_text(
            "❌ Вы недавно взаимодействовали с этим пользователем!\n"
            "Подождите 8 часов."
        )
        return
    
    # Показать детали задания
    task_info = f"📋 ЗАДАНИЕ #{task_id}\n\n"
    task_info += f"Тип: {task['type'].upper()}\n"
    task_info += f"Ссылка: {task['link']}\n"
    
    if 'comment' in task:
        task_info += f"\nКомментарий:\n{task['comment']}\n"
    
    task_info += f"\n💰 Награда: {task['reward']} 🪃\n\n"
    task_info += "Выполните задание и нажмите кнопку:"
    
    keyboard = [
        [InlineKeyboardButton("✅ Выполнено", callback_data=f"done_{task_id}")],
        [InlineKeyboardButton("« Назад к пулу", callback_data="pool")]
    ]
    
    await query.edit_message_text(task_info, reply_markup=InlineKeyboardMarkup(keyboard))


async def task_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ Ожидайте подтверждения...")
    
    user_id = update.effective_user.id
    task_id = query.data.split('_')[1]
    
    task = next((t for t in tasks_db if t['id'] == task_id), None)
    
    if not task:
        await query.edit_message_text("❌ Задание не найдено!")
        return
    
    # Заморозка триксиков
    frozen_tasks[task_id] = {
