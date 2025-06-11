import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)

# ملف البيانات
DATA_FILE = "users.json"
ORDERS_FILE = "orders.json"
try:
    with open(DATA_FILE, "r") as f:
        users_data = json.load(f)
except FileNotFoundError:
    users_data = {}

try:
    with open(ORDERS_FILE, "r") as f:
        order_logs = json.load(f)
except FileNotFoundError:
    order_logs = []

def save_users():
    with open(DATA_FILE, "w") as f:
        json.dump(users_data, f)

def save_orders():
    with open(ORDERS_FILE, "w") as f:
        json.dump(order_logs, f)

ADMIN_IDS = [6266125760]  # معرفات الإدمن
ADMIN_CHAT_ID = 6266125760  # معرف حساب الإدارة

# حالات المحادثة
TRANSFER_ID, TRANSFER_AMOUNT, ENTER_PUBG_ID = range(3)

# أمر البدء
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[
        InlineKeyboardButton("معلومات حسابي", callback_data="account_info"),
        InlineKeyboardButton("PUBG UC", callback_data="pubg_uc")
    ]]
    await update.message.reply_text("مرحبًا! اختر خيارًا:", reply_markup=InlineKeyboardMarkup(keyboard))

# عرض معلومات الحساب
async def account_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = str(query.from_user.id)
    if user_id not in users_data:
        users_data[user_id] = {"username": query.from_user.username, "points": 0}
        save_users()
    points = users_data[user_id]["points"]
    keyboard = [[InlineKeyboardButton("شحن حسابي", callback_data="recharge")]]
    await query.answer()
    await context.bot.send_message(chat_id=query.message.chat_id, text=f"رصيدك الحالي: {points} نقطة", reply_markup=InlineKeyboardMarkup(keyboard))

# خيارات UC
async def pubg_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("60 UC", callback_data="buy_60"), InlineKeyboardButton("325 UC", callback_data="buy_325")],
        [InlineKeyboardButton("660 UC", callback_data="buy_660"), InlineKeyboardButton("1800 UC", callback_data="buy_1800")]
    ]
    await query.answer()
    await context.bot.send_message(chat_id=query.message.chat_id, text="اختر كمية UC:", reply_markup=InlineKeyboardMarkup(keyboard))

# الأسعار
price_map = {"60": 9000, "325": 45000, "660": 88000, "1800": 220000}

# عرض السعر وزر الشراء
async def show_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    _, uc_amount = query.data.split("_")
    price = price_map.get(uc_amount, 0)
    context.user_data['pending_uc'] = uc_amount
    keyboard = [[InlineKeyboardButton("شراء", callback_data=f"start_purchase")]]
    await query.answer()
    await context.bot.send_message(chat_id=query.message.chat_id, text=f"{uc_amount} UC بسعر {price} نقطة", reply_markup=InlineKeyboardMarkup(keyboard))

# بدء الشراء (طلب ID)
async def start_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await context.bot.send_message(chat_id=query.message.chat_id, text="يرجى إدخال الـ ID الخاص بك في PUBG Mobile:")
    return ENTER_PUBG_ID

# إتمام الشراء بعد استلام ID
async def receive_pubg_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pubg_id = update.message.text.strip()
    user_id = str(update.effective_user.id)
    uc_amount = context.user_data.get('pending_uc')
    price = price_map.get(uc_amount, 0)
    user = users_data.get(user_id, {"points": 0})
    points = user["points"]

    if points >= price:
        context.user_data['pending_id'] = pubg_id
        context.user_data['pending_price'] = price
        await update.message.reply_text("تم إرسال طلبك للإدارة وسيتم تنفيذه بعد المراجعة.")
        username = update.effective_user.username or "بدون اسم مستخدم"
        keyboard = [[
            InlineKeyboardButton("✅ تأكيد الطلب", callback_data=f"confirm_{user_id}_{uc_amount}_{pubg_id}"),
            InlineKeyboardButton("❌ إلغاء الطلب", callback_data=f"cancel_{user_id}_{uc_amount}_{pubg_id}")
        ]]
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"✅ طلب شراء جديد:\nالمستخدم: @{username}\nمعرفه: {user_id}\nالحزمة: {uc_amount} UC\nالسعر: {price} نقطة\nPUBG ID: {pubg_id}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text("عذراً، لا تملك نقاطًا كافية.")
    return ConversationHandler.END

# تأكيد الطلب من الإدمن
async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("غير مصرح.", show_alert=True)
        return
    _, user_id, uc_amount, pubg_id = query.data.split("_", 3)
    user_id = str(user_id)
    price = price_map.get(uc_amount, 0)

    if user_id not in users_data or users_data[user_id]['points'] < price:
        await query.answer("المستخدم لا يملك رصيد كافي أو غير موجود.", show_alert=True)
        return

    users_data[user_id]['points'] -= price
    save_users()
    order_logs.append({"user_id": user_id, "uc": uc_amount, "pubg_id": pubg_id, "status": "تم التنفيذ"})
    save_orders()

    await context.bot.send_message(chat_id=int(user_id), text=f"✅ تم تنفيذ طلبك لشحن {uc_amount} UC إلى ID: {pubg_id}.")
    await query.edit_message_text(f"✅ تم تنفيذ طلب @{users_data[user_id].get('username', 'مستخدم')} بنجاح.")

# إلغاء الطلب من الإدمن
async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("غير مصرح.", show_alert=True)
        return
    _, user_id, uc_amount, pubg_id = query.data.split("_", 3)
    order_logs.append({"user_id": user_id, "uc": uc_amount, "pubg_id": pubg_id, "status": "تم الإلغاء"})
    save_orders()

    await context.bot.send_message(chat_id=int(user_id), text=f"❌ تم إلغاء طلبك لشحن {uc_amount} UC.")
    await query.edit_message_text("❌ تم إلغاء الطلب من قبل الإدارة.")

# بدء شحن الحساب
async def recharge_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await context.bot.send_message(chat_id=update.effective_chat.id, text="أرسل رقم عملية التحويل:")
    return TRANSFER_ID

# استلام رقم العملية
async def get_transfer_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    transfer_id = update.message.text.strip()
    if not transfer_id:
        await update.message.reply_text("الرجاء إدخال رقم العملية.")
        return TRANSFER_ID
    context.user_data['transfer_id'] = transfer_id
    await update.message.reply_text("أرسل المبلغ:")
    return TRANSFER_AMOUNT

# استلام المبلغ
async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    amount = update.message.text.strip()
    if not amount.isdigit():
        await update.message.reply_text("الرجاء إدخال مبلغ صحيح بالأرقام.")
        return TRANSFER_AMOUNT
    transfer_id = context.user_data['transfer_id']
    username = update.effective_user.username or "بدون اسم مستخدم"
    user_id = update.effective_user.id
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=f"طلب شحن جديد:\nالمستخدم: @{username}\nمعرفه: {user_id}\nرقم العملية: {transfer_id}\nالمبلغ: {amount}"
    )
    await update.message.reply_text("تم إرسال طلب الشحن. ستضيف الإدارة النقاط يدويًا لاحقًا.")
    return ConversationHandler.END

# إضافة نقاط (للإدمن)
async def add_points(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_id = update.effective_user.id
    if admin_id not in ADMIN_IDS:
        await update.message.reply_text("ليس لديك صلاحية لاستخدام هذا الأمر.")
        return
    if len(context.args) != 2:
        await update.message.reply_text("الرجاء استخدام الصيغة: /addpoints <user_id> <points>")
        return
    try:
        user_id, pts = context.args
        user_id = str(int(user_id))
        pts = int(pts)
    except ValueError:
        await update.message.reply_text("يرجى إدخال معرف ورقم نقاط صحيحين.")
        return
    if user_id not in users_data:
        users_data[user_id] = {"username": None, "points": 0}
    users_data[user_id]["points"] += pts
    save_users()
    await update.message.reply_text(f"تم إضافة {pts} نقطةً للمستخدم {user_id}.")

# تشغيل التطبيق
if __name__ == "__main__":
    app = ApplicationBuilder().token("7721684765:AAHGXmkyuPag_OpLxb0UphfOyG55Dc2QfEA").build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(account_info, pattern="^account_info$"))
    app.add_handler(CallbackQueryHandler(pubg_options, pattern="^pubg_uc$"))
    app.add_handler(CallbackQueryHandler(show_price, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(start_purchase, pattern="^start_purchase$"))
    app.add_handler(CallbackQueryHandler(confirm_order, pattern="^confirm_"))
    app.add_handler(CallbackQueryHandler(cancel_order, pattern="^cancel_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_pubg_id))

    recharge_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(recharge_start, pattern="^recharge$")],
        states={
            TRANSFER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_transfer_id)],
            TRANSFER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
        },
        fallbacks=[]
    )
    app.add_handler(recharge_conv)
    app.add_handler(CommandHandler("addpoints", add_points))
    app.run_polling()

