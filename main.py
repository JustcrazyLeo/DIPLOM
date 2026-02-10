import logging
import os
import csv
import io
from telegram import InputFile
from datetime import timedelta
from datetime import datetime
from typing import Dict, List
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота из переменных окружения (БЕЗОПАСНОСТЬ!)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Константы для ConversationHandler
TYPE_SELECTION, CATEGORY, AMOUNT, CONFIRM = range(4)

# Клавиатура для выбора типа операции
TYPE_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["💰 Расход", "💵 Доход"],
        ["📊 Статистика", "📜 История"],
        ["🎯 Цели", "🔄 Подписки"],
        ["📤 Экспорт", "❌ Отмена"]
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие..."
)

QUICK_CATEGORIES_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🍔 Еда 150", "🚗 Такси 300"],
        ["☕ Кофе 250", "🛒 Продукты 1000"],
        ["🎬 Кино 500", "⬅️ Отмена"]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

# Клавиатура для выбора категорий расходов
EXPENSE_CATEGORIES = [
    ["🍔 Еда", "🚗 Транспорт"],
    ["🎮 Развлечения", "🛒 Покупки"],
    ["🏥 Здоровье", "📝 Другое"],
    ["⬅️ Назад"]
]
EXPENSE_KEYBOARD = ReplyKeyboardMarkup(EXPENSE_CATEGORIES, resize_keyboard=True)

# Клавиатура для выбора категорий доходов
INCOME_CATEGORIES = [
    ["💼 Зарплата", "🎁 Подарок"], 
    ["📈 Инвестиции", "📝 Другое"],
    ["⬅️ Назад"]
]
INCOME_KEYBOARD = ReplyKeyboardMarkup(INCOME_CATEGORIES, resize_keyboard=True)

# Клавиатура для подтверждения
CONFIRM_KEYBOARD = ReplyKeyboardMarkup(
    [["✅ Да", "❌ Нет"]], 
    resize_keyboard=True,
    one_time_keyboard=True
)

# "База данных" (в памяти, для примера - в реальном проекте используйте БД)
user_data_store: Dict[int, List[Dict]] = {}

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data_store:
        user_data_store[user_id] = []
    
    await update.message.reply_text(
        "👋 *Добро пожаловать в Финансовый помощник!*\n\n"
        "Я помогу вам отслеживать доходы и расходы.\n"
        "Выберите действие:",
        reply_markup=TYPE_KEYBOARD,
        parse_mode="Markdown",
    )
    return TYPE_SELECTION

async def quick_expense_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню быстрых расходов"""
    await update.message.reply_text(
        "⚡ *Выберите быстрый расход:*",
        reply_markup=QUICK_CATEGORIES_KEYBOARD,
        parse_mode="Markdown"
    )
    return TYPE_SELECTION

# Обработка быстрых расходов
# Обработка быстрых расходов
async def handle_quick_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if "Отмена" in text:
        await update.message.reply_text(
            "Быстрая запись отменена",
            reply_markup=TYPE_KEYBOARD
        )
        return TYPE_SELECTION
    
    try:
        # Парсим текст вида "🍔 Еда 150"
        parts = text.split()
        emoji = parts[0]
        category = parts[1]
        amount = float(parts[2])
        
        user_id = update.effective_user.id
        record = {
            "type": "расход",
            "category": category,
            "amount": amount,
            "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "timestamp": datetime.now().isoformat()
        }
        
        if user_id not in user_data_store:
            user_data_store[user_id] = []
        user_data_store[user_id].append(record)
        
        await update.message.reply_text(
            f"✅ *{emoji} {category} за {amount}₽ сохранен!*\n"
            f"💳 Баланс автоматически обновлен.",
            reply_markup=TYPE_KEYBOARD,
            parse_mode="Markdown"
        )
        
        # Показываем обновленную статистику
        await show_quick_stats(update, user_id)
        
    except Exception as e:
        logger.error(f"Ошибка быстрой записи: {e}")
        await update.message.reply_text(
            "❌ Ошибка записи",
            reply_markup=TYPE_KEYBOARD
        )
    
    return TYPE_SELECTION

# Быстрая статистика после записи
async def show_quick_stats(update: Update, user_id: int):
    """Показывает краткую статистику после записи"""
    records = user_data_store.get(user_id, [])
    
    if not records:
        return
        return
    
    # Статистика за сегодня
    today = datetime.now().strftime("%d.%m.%Y")
    today_expenses = sum(
        r["amount"] for r in records 
        if r["type"] == "расход" and r["date"].startswith(today)
    )
    
    # Статистика за неделю
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%d.%m.%Y")
    week_expenses = sum(
        r["amount"] for r in records 
        if r["type"] == "расход" and r["date"][:10] >= week_ago
    )
    
    await update.message.reply_text(
        f"📊 *Краткая статистика:*\n\n"
        f"💸 Расходы сегодня: {today_expenses:,.0f}₽\n"
        f"📅 Расходы за неделю: {week_expenses:,.0f}₽\n\n"
        f"💡 Совет: старайтесь не превышать 1000₽ в день",
        parse_mode="Markdown"
    )

# Команда /export - экспорт данных в CSV
async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    records = user_data_store.get(user_id, [])
    
    if not records:
        await update.message.reply_text(
            "📭 Нет данных для экспорта.",
            reply_markup=TYPE_KEYBOARD
        )
        return TYPE_SELECTION
    
    # Создаем CSV в памяти
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Заголовки
    writer.writerow(['Дата', 'Тип', 'Категория', 'Сумма'])
    
    # Данные
    for record in records:
        writer.writerow([
            record['date'],
            record['type'],
            record['category'],
            f"{record['amount']:.2f}"
        ])
    
    # Создаем файл
    output.seek(0)
    csv_file = io.BytesIO(output.getvalue().encode('utf-8'))
    
    # Отправляем файл
    await update.message.reply_document(
        document=InputFile(csv_file, filename=f'finance_{user_id}_{datetime.now().strftime("%Y%m%d")}.csv'),
        caption=f"📊 Экспорт ваших финансовых данных\n"
                f"Всего записей: {len(records)}",
        reply_markup=TYPE_KEYBOARD
    )
    
    return TYPE_SELECTION

# Добавим в константы
MONTHS_RU = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
             'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']

# Клавиатура для месячной статистики
MONTHS_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["📊 Этот месяц", "📊 Прошлый месяц"],
        ["📊 По месяцам", "⬅️ Назад"]
    ],
    resize_keyboard=True
)

# Обработка месячной статистики
async def monthly_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    records = user_data_store.get(user_id, [])
    
    if not records:
        await update.message.reply_text(
            "📭 Нет данных для статистики.",
            reply_markup=TYPE_KEYBOARD
        )
        return TYPE_SELECTION
    
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    # Собираем данные по месяцам
    monthly_data = {}
    for record in records:
        record_date = datetime.strptime(record['date'], "%d.%m.%Y %H:%M")
        month_key = f"{record_date.year}-{record_date.month}"
        
        if month_key not in monthly_data:
            monthly_data[month_key] = {'доход': 0, 'расход': 0}
        
        monthly_data[month_key][record['type']] += record['amount']
    
    # Формируем статистику
    stats_text = "📅 *Статистика по месяцам:*\n\n"
    
    for month_key in sorted(monthly_data.keys(), reverse=True)[:6]:  # Последние 6 месяцев
        year, month = map(int, month_key.split('-'))
        data = monthly_data[month_key]
        
        balance = data['доход'] - data['расход']
        month_name = MONTHS_RU[month-1]
        
        stats_text += (
            f"*{month_name} {year}*\n"
            f"📈 Доходы: {data['доход']:,.2f}\n"
            f"📉 Расходы: {data['расход']:,.2f}\n"
            f"💼 Баланс: {balance:,.2f}\n\n"
        ).replace(',', ' ')
    
    await update.message.reply_text(
        stats_text,
        reply_markup=TYPE_KEYBOARD,
        parse_mode="Markdown"
    )
    return TYPE_SELECTION

# Добавим в глобальные переменные
user_goals: Dict[int, Dict] = {}

# Команда для удаления последней записи
async def undo_last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет последнюю запись"""
    user_id = update.effective_user.id
    records = user_data_store.get(user_id, [])
    
    if not records:
        await update.message.reply_text("📭 Нет записей для удаления")
        return
    
    last_record = records.pop()
    
    await update.message.reply_text(
        f"↩️ *Последняя запись удалена:*\n\n"
        f"🗑️ {last_record['type'].capitalize()}\n"
        f"🏷️ {last_record['category']}\n"
        f"💰 {last_record['amount']:,.2f}₽\n"
        f"📅 {last_record['date']}",
        parse_mode="Markdown",
        reply_markup=TYPE_KEYBOARD
    )

# Команда /goal для установки целей
async def set_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    
    if not args or len(args) < 2:
        await update.message.reply_text(
            "🎯 *Установка финансовой цели*\n\n"
            "Использование: /goal [название] [сумма]\n"
            "Пример: /goal Новая_машина 500000\n"
            "Пример: /goal Отпуск 100000\n\n"
            "Просмотреть цели: /goals\n"
            "Удалить цель: /goal_remove [id]",
            parse_mode="Markdown"
        )
        return
    
    try:
        user_id = update.effective_user.id
        goal_name = args[0]
        goal_amount = float(args[1])
        
        if user_id not in user_goals:
            user_goals[user_id] = {}
        
        goal_id = len(user_goals[user_id]) + 1
        user_goals[user_id][goal_id] = {
            'name': goal_name,
            'target': goal_amount,
            'saved': 0,
            'created': datetime.now().strftime("%d.%m.%Y")
        }
        
        await update.message.reply_text(
            f"🎯 *Цель установлена!*\n\n"
            f"ID: {goal_id}\n"
            f"Название: {goal_name}\n"
            f"Цель: {goal_amount:,.2f}\n"
            f"Дата создания: {datetime.now().strftime('%d.%m.%Y')}",
            parse_mode="Markdown"
        )
        
    except ValueError:
        await update.message.reply_text("❌ Неверная сумма!")

# Просмотр целей
async def show_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in user_goals or not user_goals[user_id]:
        await update.message.reply_text("🎯 У вас еще нет финансовых целей.")
        return
    
    goals_text = "🎯 *Ваши финансовые цели:*\n\n"
    
    for goal_id, goal in user_goals[user_id].items():
        progress = (goal['saved'] / goal['target']) * 100 if goal['target'] > 0 else 0
        progress_bar = "🟢" * int(progress / 10) + "⚪" * (10 - int(progress / 10))
        
        goals_text += (
            f"*ID {goal_id}: {goal['name']}*\n"
            f"Накоплено: {goal['saved']:,.2f} / {goal['target']:,.2f}\n"
            f"Прогресс: {progress:.1f}%\n"
            f"{progress_bar}\n"
            f"Создана: {goal['created']}\n\n"
        ).replace(',', ' ')
    
    await update.message.reply_text(goals_text, parse_mode="Markdown")

# Добавление денег к цели
async def add_to_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    
    if not args or len(args) < 2:
        await update.message.reply_text(
            "💵 *Пополнить цель*\n\n"
            "Использование: /goal_add [id] [сумма]\n"
            "Пример: /goal_add 1 5000"
        )
        return
    
    try:
        user_id = update.effective_user.id
        goal_id = int(args[0])
        amount = float(args[1])
        
        if user_id not in user_goals or goal_id not in user_goals[user_id]:
            await update.message.reply_text("❌ Цель не найдена!")
            return
        
        user_goals[user_id][goal_id]['saved'] += amount
        
        goal = user_goals[user_id][goal_id]
        progress = (goal['saved'] / goal['target']) * 100
        
        await update.message.reply_text(
            f"✅ *Средства добавлены!*\n\n"
            f"Цель: {goal['name']}\n"
            f"Добавлено: {amount:,.2f}\n"
            f"Всего накоплено: {goal['saved']:,.2f}\n"
            f"Прогресс: {progress:.1f}%",
            parse_mode="Markdown"
        )
        
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Неверные параметры!")

# Глобальная переменная для регулярных платежей
user_subscriptions: Dict[int, List] = {}

# Команда для добавления регулярного платежа
async def add_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    
    if not args or len(args) < 3:
        await update.message.reply_text(
            "🔄 *Добавить регулярный платеж*\n\n"
            "Использование: /subscribe [название] [сумма] [день месяца]\n"
            "Пример: /subscribe Netflix 599 15\n"
            "Пример: /subscribe Интернет 890 1\n\n"
            "Мои подписки: /subscriptions",
            parse_mode="Markdown"
        )
        return
    
    try:
        user_id = update.effective_user.id
        name = args[0]
        amount = float(args[1])
        day = int(args[2])
        
        if not 1 <= day <= 31:
            await update.message.reply_text("❌ День должен быть от 1 до 31!")
            return
        
        if user_id not in user_subscriptions:
            user_subscriptions[user_id] = []
        
        subscription = {
            'name': name,
            'amount': amount,
            'day': day,
            'added': datetime.now().strftime("%d.%m.%Y")
        }
        
        user_subscriptions[user_id].append(subscription)
        
        await update.message.reply_text(
            f"✅ *Регулярный платеж добавлен!*\n\n"
            f"Название: {name}\n"
            f"Сумма: {amount:,.2f}\n"
            f"Списание каждый: {day} число\n"
            f"Добавлено: {datetime.now().strftime('%d.%m.%Y')}",
            parse_mode="Markdown"
        )
        
    except ValueError:
        await update.message.reply_text("❌ Неверные параметры!")

# Проверка регулярных платежей (можно запускать по расписанию)
async def check_subscriptions(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now()
    
    if today.day == 1:  # Проверяем 1 числа каждого месяца
        for user_id, subscriptions in user_subscriptions.items():
            total = sum(sub['amount'] for sub in subscriptions)
            
            if total > 0:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"📅 *Напоминание о регулярных платежах*\n\n"
                        f"В этом месяце к оплате:\n"
                        f"Общая сумма: {total:,.2f}\n\n"
                        f"Не забудьте внести эти платежи!",
                    parse_mode="Markdown"
                )

# Обработка выбора из главного меню
async def handle_type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    # Добавьте в начало функции перед другими проверками:
    if "Быстрый расход" in text:
        return await quick_expense_menu(update, context)
    user_id = update.effective_user.id
    
    # Очищаем временные данные при новом запуске
    context.user_data.clear()
    
    if "Расход" in text:
        context.user_data["type"] = "расход"
        await update.message.reply_text(
            "📉 *Вы выбрали: Расход*\n"
            "Выберите категорию:",
            reply_markup=EXPENSE_KEYBOARD,
            parse_mode="Markdown"
        )
        return CATEGORY
        
    elif "Доход" in text:
        context.user_data["type"] = "доход"
        await update.message.reply_text(
            "📈 *Вы выбрали: Доход*\n"
            "Выберите категорию:",
            reply_markup=INCOME_KEYBOARD,
            parse_mode="Markdown"
        )
        return CATEGORY
        
    elif "Статистика" in text:
        return await show_statistics(update, context)
        
    elif "История" in text:
        return await show_history(update, context)
        
    elif "Отмена" in text or text.lower() == "отмена":
        return await cancel(update, context)
        
    else:
        await update.message.reply_text(
            "Пожалуйста, используйте кнопки ниже:",
            reply_markup=TYPE_KEYBOARD
        )
        return TYPE_SELECTION

# Обработка кнопки "Назад"
async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Возвращаемся в главное меню:",
        reply_markup=TYPE_KEYBOARD
    )
    return TYPE_SELECTION

# Получение категории
async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    # Обработка кнопки "Назад"
    if "Назад" in text:
        return await handle_back(update, context)
    
    # Убираем эмодзи для чистого хранения
    clean_category = text.split(' ', 1)[-1] if ' ' in text else text
    context.user_data["category"] = clean_category
    
    await update.message.reply_text(
        f"Категория: *{clean_category}*\n\n"
        "💵 Введите сумму (только цифры):\n"
        "Например: 1500 или 99.99",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    return AMOUNT

# Получение суммы
async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Заменяем запятую на точку для корректного преобразования
        amount_str = update.message.text.replace(',', '.').strip()
        amount = float(amount_str)
        
        if amount <= 0:
            await update.message.reply_text(
                "❌ Сумма должна быть больше нуля!\n"
                "Попробуйте еще раз:"
            )
            return AMOUNT
            
        if amount > 1000000000:  # Лимит 1 миллиард
            await update.message.reply_text(
                "❌ Сумма слишком большая!\n"
                "Попробуйте еще раз:"
            )
            return AMOUNT
            
        context.user_data["amount"] = amount
        
        # Форматируем сумму с разделителями тысяч
        formatted_amount = f"{amount:,.2f}".replace(',', ' ').replace('.', ',')
        
        operation_type = context.user_data.get("type", "")
        category = context.user_data.get("category", "")
        
        await update.message.reply_text(
            f"📝 *Подтвердите запись:*\n\n"
            f"📌 Тип: {operation_type.capitalize()}\n"
            f"🏷️ Категория: {category}\n"
            f"💰 Сумма: {formatted_amount}\n\n"
            f"Всё верно?",
            reply_markup=CONFIRM_KEYBOARD,
            parse_mode="Markdown"
        )
        return CONFIRM
        
    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введите корректную сумму!\n"
            "Используйте только цифры и точку/запятую.\n"
            "Пример: 1500 или 99.99\n\n"
            "Попробуйте еще раз:"
        )
        return AMOUNT

# Подтверждение и сохранение
async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    
    if "да" in text or "✅" in text:
        user_id = update.effective_user.id
        
        # Создаем запись
        record = {
            "type": context.user_data.get("type", ""),
            "category": context.user_data.get("category", ""),
            "amount": context.user_data.get("amount", 0),
            "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "timestamp": datetime.now().isoformat()
        }
        
        # Сохраняем в хранилище
        if user_id not in user_data_store:
            user_data_store[user_id] = []
        user_data_store[user_id].append(record)
        
        # Форматируем сумму для сообщения
        amount = record["amount"]
        formatted_amount = f"{amount:,.2f}".replace(',', ' ').replace('.', ',')
        
        await update.message.reply_text(
            f"✅ *Запись успешно сохранена!*\n\n"
            f"📌 {record['type'].capitalize()}\n"
            f"🏷️ {record['category']}\n"
            f"💰 {formatted_amount}\n"
            f"📅 {record['date']}",
            reply_markup=TYPE_KEYBOARD,
            parse_mode="Markdown"
        )
        
    else:
        await update.message.reply_text(
            "❌ Запись отменена.",
            reply_markup=TYPE_KEYBOARD
        )
    
    # Очищаем временные данные
    context.user_data.clear()
    return TYPE_SELECTION

# Статистика
async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    records = user_data_store.get(user_id, [])
    
    if not records:
        await update.message.reply_text(
            "📭 Записей пока нет.\n"
            "Начните добавлять доходы и расходы!",
            reply_markup=TYPE_KEYBOARD
        )
        return TYPE_SELECTION
    
    # Сегодняшняя дата
    today = datetime.now().strftime("%d.%m.%Y")
    
    total_expense = 0
    total_income = 0
    today_expense = 0
    today_income = 0
    
    # Анализ по категориям
    expense_categories = {}
    income_categories = {}
    
    for record in records:
        amount = record["amount"]
        
        if record["type"] == "расход":
            total_expense += amount
            if record["date"].startswith(today):
                today_expense += amount
            
            # Собираем по категориям расходов
            cat = record["category"]
            expense_categories[cat] = expense_categories.get(cat, 0) + amount
            
        else:  # доход
            total_income += amount
            if record["date"].startswith(today):
                today_income += amount
            
            # Собираем по категориям доходов
            cat = record["category"]
            income_categories[cat] = income_categories.get(cat, 0) + amount
    
    balance = total_income - total_expense
    
    # Форматирование сумм
    def format_amount(num):
        return f"{num:,.2f}".replace(',', ' ').replace('.', ',')
    
    # Топ категорий расходов
    top_expenses = ""
    if expense_categories:
        sorted_expenses = sorted(expense_categories.items(), key=lambda x: x[1], reverse=True)[:3]
        top_expenses = "\n📉 *Топ расходов:*\n"
        for i, (cat, amount) in enumerate(sorted_expenses, 1):
            percentage = (amount / total_expense * 100) if total_expense > 0 else 0
            top_expenses += f"{i}. {cat}: {format_amount(amount)} ({percentage:.1f}%)\n"
    
    # Создаем текст статистики
    stats_text = (
        f"📊 *Ваша статистика*\n\n"
        f"💼 Баланс: *{format_amount(balance)}*\n"
        f"📈 Доходы: {format_amount(total_income)}\n"
        f"📉 Расходы: {format_amount(total_expense)}\n\n"
        f"📅 *За сегодня ({today}):*\n"
        f"📈 Доходы: {format_amount(today_income)}\n"
        f"📉 Расходы: {format_amount(today_expense)}\n\n"
        f"📝 Всего записей: {len(records)}\n"
    )
    
    if top_expenses:
        stats_text += top_expenses
    
    await update.message.reply_text(
        stats_text,
        reply_markup=TYPE_KEYBOARD,
        parse_mode="Markdown"
    )
    return TYPE_SELECTION

# История операций
async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    records = user_data_store.get(user_id, [])
    
    if not records:
        await update.message.reply_text(
            "📭 История пуста.\n"
            "Начните добавлять записи!",
            reply_markup=TYPE_KEYBOARD
        )
        return TYPE_SELECTION
    
    # Показываем последние 15 записей
    recent_records = records[-15:]
    history_text = "📜 *Последние операции:*\n\n"
    
    for record in reversed(recent_records):
        icon = "📈" if record["type"] == "доход" else "📉"
        color = "🟢" if record["type"] == "доход" else "🔴"
        
        formatted_amount = f"{record['amount']:,.2f}".replace(',', ' ').replace('.', ',')
        
        history_text += (
            f"{color} {icon} *{record['date']}*\n"
            f"   {record['category']}: {formatted_amount}\n\n"
        )
    
    await update.message.reply_text(
        history_text,
        reply_markup=TYPE_KEYBOARD,
        parse_mode="Markdown"
    )
    return TYPE_SELECTION

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 *Финансовый помощник - справка*\n\n"
        "*Доступные команды:*\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать эту справку\n"
        "/cancel - Отменить текущее действие\n\n"
        "*Как пользоваться:*\n"
        "1. Выберите 'Расход' или 'Доход'\n"
        "2. Выберите категорию\n"
        "3. Введите сумму\n"
        "4. Подтвердите запись\n\n"
        "*Дополнительно:*\n"
        "• Статистика - обзор финансов\n"
        "• История - последние операции"
    )
    
    await update.message.reply_text(
        help_text,
        reply_markup=TYPE_KEYBOARD,
        parse_mode="Markdown"
    )
# Быстрые команды
async def quick_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    
    if not args:
        await update.message.reply_text(
            "⚡ *Быстрый расход*\n\n"
            "Использование: /ex [сумма] [категория]\n"
            "Пример: /ex 350 еда\n"
            "Пример: /ex 1500 транспорт",
            parse_mode="Markdown"
        )
        return
    
    try:
        user_id = update.effective_user.id
        amount = float(args[0])
        category = args[1] if len(args) > 1 else "Другое"
        
        # Сохраняем запись
        record = {
            "type": "расход",
            "category": category,
            "amount": amount,
            "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "timestamp": datetime.now().isoformat()
        }
        
        if user_id not in user_data_store:
            user_data_store[user_id] = []
        user_data_store[user_id].append(record)
        
        await update.message.reply_text(
            f"✅ *Быстрая запись сохранена!*\n\n"
            f"📉 Расход: {category}\n"
            f"💰 {amount:,.2f}",
            parse_mode="Markdown"
        )
        
    except ValueError:
        await update.message.reply_text("❌ Неверная сумма!")
# Отмена
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "✅ Текущее действие отменено.\n"
        "Выберите новое действие:",
        reply_markup=TYPE_KEYBOARD
    )
    return TYPE_SELECTION

# Обработка неизвестных сообщений
async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤔 Я не понимаю эту команду.\n"
        "Используйте кнопки или команды:\n"
        "/start - начать\n"
        "/help - помощь",
        reply_markup=TYPE_KEYBOARD
    )



async def setup_commands(application: Application):
    """Настройка команд меню бота"""
    commands = [
        ("start", "Запустить бота"),
        ("help", "Помощь"),
        ("quick", "Быстрый расход"),
        ("stats", "Статистика"),
        ("history", "История"),
        ("export", "Экспорт данных"),
        ("undo", "Отменить последнюю запись"),
        ("goals", "Мои цели"),
        ("subscriptions", "Мои подписки")
    ]
    
    await application.bot.set_my_commands(commands)

# Основная функция
def main():
    # Проверка токена
    if TOKEN == "ВАШ_ТОКЕН_ЗДЕСЬ":
        logger.error("Токен бота не установлен! Укажите TELEGRAM_BOT_TOKEN в переменных окружения.")
        return
    
    # Создаем Application
    application = Application.builder().token(TOKEN).build()
    
    # ConversationHandler для добавления записей
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_type_selection)
        ],
        states={
            TYPE_SELECTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_type_selection)
                
            ],
            CATEGORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category)
            ],
            AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount)
            ],
            CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirm)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
            CommandHandler("help", help_command)
        ],
    )
    
    # Регистрируем обработчики
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("export", export_data))
    application.add_handler(CommandHandler("goal", set_goal))
    application.add_handler(CommandHandler("goals", show_goals))
    application.add_handler(CommandHandler("goal_add", add_to_goal))
    application.add_handler(CommandHandler("subscribe", add_subscription))
    
    
    # Добавим JobQueue для проверки подписок
    job_queue = application.job_queue
    if job_queue:
        # Проверка каждое 1 число месяца в 10:00
        job_queue.run_monthly(
            check_subscriptions,
            when=datetime.time(hour=10, minute=0),
            day=1
        )
    # Обработчик для неизвестных сообщений (должен быть последним)
    application.add_handler(MessageHandler(filters.ALL, unknown_message))
    # В main() после создания application добавьте:
    application.add_handler(CommandHandler("quick", quick_expense_menu))
    application.add_handler(CommandHandler("undo", undo_last))
    logger.info("Бот запущен...")
    
    
    # Запускаем бота
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    # Для безопасности используйте переменные окружения:
    # export TELEGRAM_BOT_TOKEN="ваш_токен_здесь"
    # или создайте файл .env с TOKEN=ваш_токен
    
    main()