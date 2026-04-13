import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TOKEN")
OWNER_ID = 8406441503

group_settings = {
    "group_id": None,
    "welcome_enabled": True,
    "welcome_text": "ياهلا وسهلا فيك، نورت القروب 🌹",
    "rules_text": "قوانين القروب:\n- احترام الجميع\n- ممنوع السب\n- ممنوع الإعلانات",
    "replies": {
        "السلام عليكم": "وعليكم السلام ورحمة الله 🌹"
    }
}

user_states = {}

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

def main_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🔗 ربط القروب", callback_data="link_group")],
        [InlineKeyboardButton("🎉 الترحيب", callback_data="welcome_menu")],
        [InlineKeyboardButton("📜 القوانين", callback_data="rules_menu")],
        [InlineKeyboardButton("🤖 الردود التلقائية", callback_data="replies_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

def back_menu(target: str = "main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ رجوع", callback_data=target)]
    ])

def welcome_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("تشغيل/إيقاف الترحيب", callback_data="toggle_welcome")],
        [InlineKeyboardButton("تغيير رسالة الترحيب", callback_data="set_welcome")],
        [InlineKeyboardButton("عرض رسالة الترحيب", callback_data="show_welcome")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="main")],
    ]
    return InlineKeyboardMarkup(keyboard)

def rules_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("تغيير القوانين", callback_data="set_rules")],
        [InlineKeyboardButton("عرض القوانين", callback_data="show_rules")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="main")],
    ]
    return InlineKeyboardMarkup(keyboard)

def replies_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("إضافة رد", callback_data="add_reply")],
        [InlineKeyboardButton("عرض الردود", callback_data="show_replies")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="main")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_owner(user.id):
        await update.message.reply_text("هذا البوت مخصص للإدارة فقط.")
        return

    await update.message.reply_text(
        "أهلًا بك في لوحة تحكم البوت 👑",
        reply_markup=main_menu()
    )

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    await query.answer()

    user = query.from_user
    if not is_owner(user.id):
        await query.edit_message_text("هذا البوت مخصص للإدارة فقط.")
        return

    data = query.data

    if data == "main":
        await query.edit_message_text(
            "أهلًا بك في لوحة تحكم البوت 👑",
            reply_markup=main_menu()
        )

    elif data == "link_group":
        await query.edit_message_text(
            "أرسل الآن آيدي القروب.\n\nمثال:\n-1001234567890",
            reply_markup=back_menu("main")
        )
        user_states[user.id] = "waiting_group_id"

    elif data == "welcome_menu":
        status = "مفعل ✅" if group_settings["welcome_enabled"] else "معطل ❌"
        await query.edit_message_text(
            f"قسم الترحيب\nالحالة: {status}",
            reply_markup=welcome_keyboard()
        )

    elif data == "toggle_welcome":
        group_settings["welcome_enabled"] = not group_settings["welcome_enabled"]
        status = "مفعل ✅" if group_settings["welcome_enabled"] else "معطل ❌"
        await query.edit_message_text(
            f"قسم الترحيب\nالحالة: {status}",
            reply_markup=welcome_keyboard()
        )

    elif data == "set_welcome":
        user_states[user.id] = "waiting_welcome_text"
        await query.edit_message_text(
            "أرسل رسالة الترحيب الجديدة الآن.",
            reply_markup=back_menu("welcome_menu")
        )

    elif data == "show_welcome":
        await query.edit_message_text(
            f"رسالة الترحيب الحالية:\n\n{group_settings['welcome_text']}",
            reply_markup=back_menu("welcome_menu")
        )

    elif data == "rules_menu":
        await query.edit_message_text(
            "قسم القوانين",
            reply_markup=rules_keyboard()
        )

    elif data == "set_rules":
        user_states[user.id] = "waiting_rules_text"
        await query.edit_message_text(
            "أرسل نص القوانين الجديد الآن.",
            reply_markup=back_menu("rules_menu")
        )

    elif data == "show_rules":
        await query.edit_message_text(
            f"القوانين الحالية:\n\n{group_settings['rules_text']}",
            reply_markup=back_menu("rules_menu")
        )

    elif data == "replies_menu":
        await query.edit_message_text(
            "قسم الردود التلقائية",
            reply_markup=replies_keyboard()
        )

    elif data == "add_reply":
        user_states[user.id] = "waiting_reply_trigger"
        await query.edit_message_text(
            "أرسل الكلمة التي تريد للبوت أن يرد عليها.",
            reply_markup=back_menu("replies_menu")
        )

    elif data == "show_replies":
        if not group_settings["replies"]:
            text = "لا توجد ردود تلقائية."
        else:
            items = []
            for k, v in group_settings["replies"].items():
                items.append(f"الكلمة: {k}\nالرد: {v}")
            text = "\n\n".join(items)

        await query.edit_message_text(
            text,
            reply_markup=back_menu("replies_menu")
        )

async def handle_private_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_owner(user.id):
        return

    if not update.message or not update.message.text:
        return

    state = user_states.get(user.id)
    text = update.message.text.strip()

    if state == "waiting_group_id":
        if not text.startswith("-100"):
            await update.message.reply_text("الآيدي غير صحيح. لازم يبدأ بـ -100")
            return

        group_settings["group_id"] = text
        user_states.pop(user.id, None)
        await update.message.reply_text(
            f"تم حفظ آيدي القروب:\n{text}",
            reply_markup=main_menu()
        )

    elif state == "waiting_welcome_text":
        group_settings["welcome_text"] = text
        user_states.pop(user.id, None)
        await update.message.reply_text(
            "تم تحديث رسالة الترحيب ✅",
            reply_markup=main_menu()
        )

    elif state == "waiting_rules_text":
        group_settings["rules_text"] = text
        user_states.pop(user.id, None)
        await update.message.reply_text(
            "تم تحديث القوانين ✅",
            reply_markup=main_menu()
        )

    elif state == "waiting_reply_trigger":
        context.user_data["new_trigger"] = text
        user_states[user.id] = "waiting_reply_response"
        await update.message.reply_text("أرسل الآن الرد الذي تريده لهذه الكلمة.")

    elif state == "waiting_reply_response":
        trigger = context.user_data.get("new_trigger")
        if trigger:
            group_settings["replies"][trigger] = text

        context.user_data.pop("new_trigger", None)
        user_states.pop(user.id, None)
        await update.message.reply_text(
            "تمت إضافة الرد التلقائي ✅",
            reply_markup=main_menu()
        )

async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    if group_settings["group_id"]:
        current_chat_id = str(update.effective_chat.id)
        if current_chat_id != str(group_settings["group_id"]):
            return

    text = update.message.text.strip()

    for trigger, reply in group_settings["replies"].items():
        if trigger in text:
            await update.message.reply_text(reply)
            break

async def welcome_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not group_settings["welcome_enabled"]:
        return

    if not update.message or not update.message.new_chat_members:
        return

    if group_settings["group_id"]:
        current_chat_id = str(update.effective_chat.id)
        if current_chat_id != str(group_settings["group_id"]):
            return

    for member in update.message.new_chat_members:
        name = member.first_name if member.first_name else "يا هلا"
        text = group_settings["welcome_text"].replace("{name}", name)
        await update.message.reply_text(text)

def main():
    if not TOKEN:
        raise ValueError("TOKEN غير موجود. حطه في المتغيرات.")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
            handle_private_text
        )
    )
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.StatusUpdate.NEW_CHAT_MEMBERS,
            welcome_new_members
        )
    )
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND,
            handle_group_messages
        )
    )

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()