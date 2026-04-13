from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import os

# التوكن من Railway
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

def main_menu():
    keyboard = [
        [InlineKeyboardButton("🔗 ربط القروب", callback_data="link_group")],
        [InlineKeyboardButton("🎉 الترحيب", callback_data="welcome_menu")],
        [InlineKeyboardButton("📜 القوانين", callback_data="rules_menu")],
        [InlineKeyboardButton("🤖 الردود التلقائية", callback_data="replies_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

def back_menu(target="main"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ رجوع", callback_data=target)]
    ])

# ===================== START =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 🚫 منع التشغيل في القروب
    if update.effective_chat.type != "private":
        await update.message.reply_text("❌ استخدم /start في خاص البوت.")
        return

    user = update.effective_user

    if not is_owner(user.id):
        await update.message.reply_text("هذا البوت مخصص للإدارة فقط.")
        return

    await update.message.reply_text(
        "أهلًا بك في لوحة تحكم البوت 👑",
        reply_markup=main_menu()
    )

# ===================== BUTTON =====================

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
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
            "أرسل آيدي القروب:\n\n-1001234567890",
            reply_markup=back_menu("main")
        )
        user_states[user.id] = "waiting_group_id"

    elif data == "welcome_menu":
        status = "مفعل ✅" if group_settings["welcome_enabled"] else "معطل ❌"
        keyboard = [
            [InlineKeyboardButton("تشغيل/إيقاف", callback_data="toggle_welcome")],
            [InlineKeyboardButton("تغيير الرسالة", callback_data="set_welcome")],
            [InlineKeyboardButton("عرض الرسالة", callback_data="show_welcome")],
            [InlineKeyboardButton("⬅️ رجوع", callback_data="main")],
        ]
        await query.edit_message_text(
            f"قسم الترحيب\nالحالة: {status}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "toggle_welcome":
        group_settings["welcome_enabled"] = not group_settings["welcome_enabled"]
        await on_button(update, context)

    elif data == "set_welcome":
        user_states[user.id] = "waiting_welcome_text"
        await query.edit_message_text(
            "أرسل رسالة الترحيب الجديدة.",
            reply_markup=back_menu("welcome_menu")
        )

    elif data == "show_welcome":
        await query.edit_message_text(
            group_settings["welcome_text"],
            reply_markup=back_menu("welcome_menu")
        )

    elif data == "rules_menu":
        keyboard = [
            [InlineKeyboardButton("تغيير القوانين", callback_data="set_rules")],
            [InlineKeyboardButton("عرض القوانين", callback_data="show_rules")],
            [InlineKeyboardButton("⬅️ رجوع", callback_data="main")],
        ]
        await query.edit_message_text(
            "قسم القوانين",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "set_rules":
        user_states[user.id] = "waiting_rules_text"
        await query.edit_message_text(
            "أرسل القوانين الجديدة.",
            reply_markup=back_menu("rules_menu")
        )

    elif data == "show_rules":
        await query.edit_message_text(
            group_settings["rules_text"],
            reply_markup=back_menu("rules_menu")
        )

    elif data == "replies_menu":
        keyboard = [
            [InlineKeyboardButton("إضافة رد", callback_data="add_reply")],
            [InlineKeyboardButton("عرض الردود", callback_data="show_replies")],
            [InlineKeyboardButton("⬅️ رجوع", callback_data="main")],
        ]
        await query.edit_message_text(
            "قسم الردود",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "add_reply":
        user_states[user.id] = "waiting_reply_trigger"
        await query.edit_message_text(
            "أرسل الكلمة.",
            reply_markup=back_menu("replies_menu")
        )

    elif data == "show_replies":
        text = "\n\n".join(
            [f"{k} ➜ {v}" for k, v in group_settings["replies"].items()]
        ) or "مافي ردود"
        await query.edit_message_text(text, reply_markup=back_menu("replies_menu"))

# ===================== PRIVATE =====================

async def handle_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_owner(user.id):
        return

    state = user_states.get(user.id)
    text = update.message.text

    if state == "waiting_group_id":
        group_settings["group_id"] = text
        user_states.pop(user.id)
        await update.message.reply_text("تم ربط القروب ✅", reply_markup=main_menu())

    elif state == "waiting_welcome_text":
        group_settings["welcome_text"] = text
        user_states.pop(user.id)
        await update.message.reply_text("تم التحديث ✅", reply_markup=main_menu())

    elif state == "waiting_rules_text":
        group_settings["rules_text"] = text
        user_states.pop(user.id)
        await update.message.reply_text("تم التحديث ✅", reply_markup=main_menu())

    elif state == "waiting_reply_trigger":
        context.user_data["trigger"] = text
        user_states[user.id] = "waiting_reply_response"
        await update.message.reply_text("أرسل الرد")

    elif state == "waiting_reply_response":
        trigger = context.user_data.get("trigger")
        group_settings["replies"][trigger] = text
        user_states.pop(user.id)
        await update.message.reply_text("تمت الإضافة ✅", reply_markup=main_menu())

# ===================== GROUP =====================

async def group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text

    for k, v in group_settings["replies"].items():
        if k in text:
            await update.message.reply_text(v)
            break

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not group_settings["welcome_enabled"]:
        return

    if update.message and update.message.new_chat_members:
        await update.message.reply_text(group_settings["welcome_text"])

# ===================== MAIN =====================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_button))

    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT, handle_private))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT, group_messages))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()