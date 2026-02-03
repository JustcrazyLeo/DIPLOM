import logging
from datetime import datetime
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
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота (замените на свой)
TOKEN = "7835891388:AAFGljb6Z98PCWg6V-9sEaJWQ51SjhSD3p8"

# Константы для ConversationHandler
CATEGORY, AMOUNT, CONFIRM = range(3)

# Клавиатура для выбора типа операции
TYPE_KEYBOARD = ReplyKeyboardMarkup(
    [["Расход", "Доход"], ["Статистика", "История"]], resize_keyboard=True
)

# Клавиатура для выбора категорий расходов
EXPENSE_CATEGORIES = [
    ["Еда", "Транспорт"],
    ["Развлечения", "Покупки"],
    ["Здоровье", "Другое"],
]
EXPENSE_KEYBOARD = ReplyKeyboardMarkup(EXPENSE_CATEGORIES, resize_keyboard=True)

# Клавиатура для выбора категорий доходов
INCOME_CATEGORIES = [["Зарплата", "Подарок"], ["Инвестиции", "Другое"]]
INCOME_KEYBOARD = ReplyKeyboardMarkup(INCOME_CATEGORIES, resize_keyboard=True)

# "База данных" (в памяти, для примера)
user_data_store = {}

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data_store:
        user_data_store[user_id] = []
    
    await update.message.reply_text(
        "💰 *Финансовый помощник*\n\n"
        "Выберите действие:",
        reply_markup=TYPE_KEYBOARD,
        parse_mode="Markdown",
    )

# Обработка выбора "Расход" или "Доход"
async def handle_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data["type"] = text.lower()  # 'расход' или 'доход'
    
    if text == "Расход":
        await update.message.reply_text(
            "Выберите категорию расхода:", reply_markup=EXPENSE_KEYBOARD
        )
        return CATEGORY
    elif text == "Доход":
        await update.message.reply_text(
            "Выберите категорию дохода:", reply_markup=INCOME_KEYBOARD
        )
        return CATEGORY
    elif text == "Статистика":
        return await show_statistics(update, context)
    elif text == "История":
        return await show_history(update, context)
    else:
        await update.message.reply_text("Пожалуйста, используйте кнопки.")
        return ConversationHandler.END

# Получение категории
async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["category"] = update.message.text
    await update.message.reply_text(
        "Введите сумму (только цифры):", reply_markup=ReplyKeyboardRemove()
    )
    return AMOUNT

# Получение суммы
async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError
        context.user_data["amount"] = amount
        await update.message.reply_text(
            f"📝 *Подтвердите запись:*\n\n"
            f"Тип: {context.user_data['type']}\n"
            f"Категория: {context.user_data['category']}\n"
            f"Сумма: {amount:.2f}\n\n"
            f"Верно? (да/нет)",
            parse_mode="Markdown",
        )
        return CONFIRM
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите корректную сумму (число > 0).")
        return AMOUNT

# Подтверждение и сохранение
async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if text == "да":
        record = {
            "type": context.user_data["type"],
            "category": context.user_data["category"],
            "amount": context.user_data["amount"],
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        user_id = update.effective_user.id
        user_data_store[user_id].append(record)
        
        await update.message.reply_text(
            "✅ Запись сохранена!", reply_markup=TYPE_KEYBOARD
        )
    else:
        await update.message.reply_text("❌ Запись отменена.", reply_markup=TYPE_KEYBOARD)
    
    context.user_data.clear()
    return ConversationHandler.END

# Статистика
async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    records = user_data_store.get(user_id, [])
    
    if not records:
        await update.message.reply_text("Записей пока нет.")
        return ConversationHandler.END
    
    today = datetime.now().strftime("%Y-%m-%d")
    total_expense = 0
    total_income = 0
    today_expense = 0
    
    for record in records:
        amount = record["amount"]
        if record["type"] == "расход":
            total_expense += amount
            if record["date"].startswith(today):
                today_expense += amount
        else:
            total_income += amount
    
    balance = total_income - total_expense
    
    stats_text = (
        f"📊 *Статистика*\n\n"
        f"Баланс: *{balance:.2f}*\n"
        f"Доходы: {total_income:.2f}\n"
        f"Расходы: {total_expense:.2f}\n"
        f"Расходы сегодня: {today_expense:.2f}\n"
        f"Всего записей: {len(records)}"
    )
    
    await update.message.reply_text(stats_text, parse_mode="Markdown")
    return ConversationHandler.END

# История операций
async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    records = user_data_store.get(user_id, [])
    
    if not records:
        await update.message.reply_text("История пуста.")
        return ConversationHandler.END
    
    history_text = "📜 *Последние 10 операций:*\n\n"
    for record in records[-10:]:
        icon = "📈" if record["type"] == "доход" else "📉"
        history_text += (
            f"{icon} {record['date']}\n"
            f"{record['category']}: *{record['amount']:.2f}*\n\n"
        )
    
    await update.message.reply_text(history_text, parse_mode="Markdown")
    return ConversationHandler.END

# Отмена
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Действие отменено.", reply_markup=TYPE_KEYBOARD)
    context.user_data.clear()
    return ConversationHandler.END

# Основная функция
def main():
    # Создаем Application с правильным контекстом
    application = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_type)],
        states={
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    
    print("Бот запущен...")
    # Упрощенный запуск без allowed_updates
    application.run_polling()

if __name__ == "__main__":
    main()