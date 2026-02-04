import logging
import os
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
    [["💰 Расход", "💵 Доход"], ["📊 Статистика", "📜 История"], ["❌ Отмена"]], 
    resize_keyboard=True,
    input_field_placeholder="Выберите действие..."
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

# Обработка выбора из главного меню
async def handle_type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
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
    
    # Обработчик для неизвестных сообщений (должен быть последним)
    application.add_handler(MessageHandler(filters.ALL, unknown_message))
    
    logger.info("Бот запущен...")
    
    # Запускаем бота
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    # Для безопасности используйте переменные окружения:
    # export TELEGRAM_BOT_TOKEN="ваш_токен_здесь"
    # или создайте файл .env с TOKEN=ваш_токен
    
    main()