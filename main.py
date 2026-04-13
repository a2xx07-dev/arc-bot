import json
import os
import re
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType
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
SETTINGS_FILE = Path("settings.json")

DEFAULT_SETTINGS = {
    "group_id": None,
    "welcome_enabled": True,
    "welcome_text": "🌹 يا هلا {name}، نورت القروب",
    "rules_text": "📜 قوانين القروب:\n- احترام الجميع\n- ممنوع السب\n- ممنوع الإعلانات",
    "replies": {
        "السلام عليكم": "وعليكم السلام ورحمة الله 🌹"
    },
    "anti_links": False,
    "anti_badwords": False,
    "badwords": ["سب", "شتيمة"],
    "warnings": {}
}

user_states = {}


def load_settings():
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = DEFAULT_SETTINGS.copy()
            merged.update(data)
            if "replies" not in merged or not isinstance(merged["replies"], dict):
                merged["replies"] = DEFAULT_SETTINGS["replies"].copy()
            if "warnings" not in merged or not isinstance(merged["warnings"], dict):
                merged["warnings"] = {}
            if "badwords" not in merged or not isinstance(merged["badwords"], list):
                merged["badwords"] = DEFAULT_SETTINGS["badwords"].copy()
            return merged
        except Exception:
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()


def save_settings():
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(group_settings, f, ensure_ascii=False, indent=2)


group_settings = load_settings()


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


async def is_user_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_user or not update.effective_chat:
        return False
    if is_owner(update.effective_user.id):
        return True
    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id, update.effective_user.id
        )
        return member.status in ("administrator", "creator")
    except Exception:
        return False


def main_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🔗 ربط القروب", callback_data="link_group")],
        [InlineKeyboardButton("🎉 الترحيب", callback_data="welcome_menu")],
        [InlineKeyboardButton("📜 القوانين", callback_data="rules_menu")],
        [InlineKeyboardButton("🤖 الردود التلقائية", callback_data="replies_menu")],
        [InlineKeyboardButton("🛡️ الحماية", callback_data="protection_menu")],
        [InlineKeyboardButton("⚙️ عرض الإعدادات", callback_data="show_settings")],
    ]
    return InlineKeyboardMarkup(keyboard)


def back_menu(target: str = "main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ رجوع", callback_data=target)]]
    )


def welcome_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("تشغيل/إيقاف الترحيب", callback_data="toggle_welcome")],
        [InlineKeyboardButton("تغيير رسالة الترحيب", callback_data="set_welcome")],
        [InlineKeyboardButton("عرض رسالة الترحيب", callback_data="show_welcome")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="main")],
    ])


def rules_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("تغيير القوانين", callback_data="set_rules")],
        [InlineKeyboardButton("عرض القوانين", callback_data="show_rules")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="main")],
    ])


def replies_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("إضافة رد", callback_data="add_reply")],
        [InlineKeyboardButton("حذف رد", callback_data="delete_reply")],
        [InlineKeyboardButton("عرض الردود", callback_data="show_replies")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="main")],
    ])


def protection_menu_keyboard() -> InlineKeyboardMarkup:
    anti_links_status = "✅" if group_settings["anti_links"] else "❌"
    anti_badwords_status = "✅" if group_settings["anti_badwords"] else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"منع الروابط {anti_links_status}", callback_data="toggle_links")],
        [InlineKeyboardButton(f"منع السب {anti_badwords_status}", callback_data="toggle_badwords")],
        [InlineKeyboardButton("إضافة كلمة ممنوعة", callback_data="add_badword")],
        [InlineKeyboardButton("عرض الكلمات الممنوعة", callback_data="show_badwords")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="main")],
    ])


def settings_text() -> str:
    gid = group_settings["group_id"] or "غير مربوط"
    welcome_status = "مفعل ✅" if group_settings["welcome_enabled"] else "معطل ❌"
    links_status = "مفعل ✅" if group_settings["anti_links"] else "معطل ❌"
    badwords_status = "مفعل ✅" if group_settings["anti_badwords"] else "معطل ❌"
    replies_count = len(group_settings["replies"])
    badwords_count = len(group_settings["badwords"])
    return (
        "⚙️ إعدادات البوت\n\n"
        f"🔗 آيدي القروب: {gid}\n"
        f"🎉 الترحيب: {welcome_status}\n"
        f"🤖 عدد الردود: {replies_count}\n"
        f"🚫 منع الروابط: {links_status}\n"
        f"🤬 منع السب: {badwords_status}\n"
        f"📝 الكلمات الممنوعة: {badwords_count}"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.message.reply_text("⚠️ استخدم البوت في الخاص فقط\n\n@ArcZone_SaudiBot")
        return

    user = update.effective_user
    if not user or not is_owner(user.id):
        await update.message.reply_text("هذا البوت مخصص للإدارة فقط.")
        return

    text = (
        "👑 أهلاً بك في لوحة تحكم البوت\n\n"
        "من هنا تقدر تضبط:\n"
        "• ربط القروب\n"
        "• الترحيب\n"
        "• القوانين\n"
        "• الردود التلقائية\n"
        "• الحماية"
    )
    await update.message.reply_text(text, reply_markup=main_menu())


async def bindgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text("استخدم هذا الأمر داخل القروب.")
        return

    if not await is_user_admin(update, context):
        await update.message.reply_text("هذا الأمر للمشرف أو المالك فقط.")
        return

    group_settings["group_id"] = str(update.effective_chat.id)
    save_settings()
    await update.message.reply_text(f"✅ تم ربط هذا القروب بنجاح\n{update.effective_chat.id}")


async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(group_settings["rules_text"])


async def welcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(group_settings["welcome_text"].replace("{name}", "يا هلا"))


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_admin(update, context):
        await update.message.reply_text("هذا الأمر للمشرف أو المالك فقط.")
        return
    await update.message.reply_text(settings_text())


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
        await query.edit_message_text("👑 أهلاً بك في لوحة تحكم البوت", reply_markup=main_menu())

    elif data == "show_settings":
        await query.edit_message_text(settings_text(), reply_markup=back_menu("main"))

    elif data == "link_group":
        await query.edit_message_text(
            "🔗 لربط القروب:\n\n"
            "1) أضف البوت للقروب\n"
            "2) خله مشرف\n"
            "3) اكتب داخل القروب:\n/bindgroup\n\n"
            "أو أرسل آيدي القروب هنا يدويًا.",
            reply_markup=back_menu("main"),
        )
        user_states[user.id] = "waiting_group_id"

    elif data == "welcome_menu":
        status = "مفعل ✅" if group_settings["welcome_enabled"] else "معطل ❌"
        await query.edit_message_text(
            f"🎉 قسم الترحيب\nالحالة: {status}",
            reply_markup=welcome_menu_keyboard(),
        )

    elif data == "toggle_welcome":
        group_settings["welcome_enabled"] = not group_settings["welcome_enabled"]
        save_settings()
        status = "مفعل ✅" if group_settings["welcome_enabled"] else "معطل ❌"
        await query.edit_message_text(
            f"🎉 قسم الترحيب\nالحالة: {status}",
            reply_markup=welcome_menu_keyboard(),
        )

    elif data == "set_welcome":
        user_states[user.id] = "waiting_welcome_text"
        await query.edit_message_text(
            "أرسل رسالة الترحيب الجديدة الآن.\n\nتقدر تستخدم {name} لاسم العضو.",
            reply_markup=back_menu("welcome_menu"),
        )

    elif data == "show_welcome":
        await query.edit_message_text(
            f"رسالة الترحيب الحالية:\n\n{group_settings['welcome_text']}",
            reply_markup=back_menu("welcome_menu"),
        )

    elif data == "rules_menu":
        await query.edit_message_text("📜 قسم القوانين", reply_markup=rules_menu_keyboard())

    elif data == "set_rules":
        user_states[user.id] = "waiting_rules_text"
        await query.edit_message_text(
            "أرسل نص القوانين الجديد الآن.",
            reply_markup=back_menu("rules_menu"),
        )

    elif data == "show_rules":
        await query.edit_message_text(
            f"القوانين الحالية:\n\n{group_settings['rules_text']}",
            reply_markup=back_menu("rules_menu"),
        )

    elif data == "replies_menu":
        await query.edit_message_text("🤖 قسم الردود التلقائية", reply_markup=replies_menu_keyboard())

    elif data == "add_reply":
        user_states[user.id] = "waiting_reply_trigger"
        await query.edit_message_text(
            "أرسل الكلمة التي تريد للبوت أن يرد عليها.",
            reply_markup=back_menu("replies_menu"),
        )

    elif data == "delete_reply":
        user_states[user.id] = "waiting_delete_reply"
        await query.edit_message_text(
            "أرسل الكلمة التي تريد حذف ردها.",
            reply_markup=back_menu("replies_menu"),
        )

    elif data == "show_replies":
        if not group_settings["replies"]:
            text = "لا توجد ردود تلقائية."
        else:
            text = "\n\n".join(
                [f"الكلمة: {k}\nالرد: {v}" for k, v in group_settings["replies"].items()]
            )
        await query.edit_message_text(text, reply_markup=back_menu("replies_menu"))

    elif data == "protection_menu":
        await query.edit_message_text("🛡️ قسم الحماية", reply_markup=protection_menu_keyboard())

    elif data == "toggle_links":
        group_settings["anti_links"] = not group_settings["anti_links"]
        save_settings()
        await query.edit_message_text("🛡️ قسم الحماية", reply_markup=protection_menu_keyboard())

    elif data == "toggle_badwords":
        group_settings["anti_badwords"] = not group_settings["anti_badwords"]
        save_settings()
        await query.edit_message_text("🛡️ قسم الحماية", reply_markup=protection_menu_keyboard())

    elif data == "add_badword":
        user_states[user.id] = "waiting_badword"
        await query.edit_message_text(
            "أرسل الكلمة الممنوعة الجديدة.",
            reply_markup=back_menu("protection_menu"),
        )

    elif data == "show_badwords":
        text = "\n".join(group_settings["badwords"]) if group_settings["badwords"] else "لا توجد كلمات ممنوعة."
        await query.edit_message_text(text, reply_markup=back_menu("protection_menu"))


async def handle_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_owner(user.id):
        return
    if not update.message or not update.message.text:
        return

    state = user_states.get(user.id)
    text = update.message.text.strip()

    if state == "waiting_group_id":
        group_settings["group_id"] = text
        user_states.pop(user.id, None)
        save_settings()
        await update.message.reply_text("✅ تم حفظ آيدي القروب", reply_markup=main_menu())

    elif state == "waiting_welcome_text":
        group_settings["welcome_text"] = text
        user_states.pop(user.id, None)
        save_settings()
        await update.message.reply_text("✅ تم تحديث رسالة الترحيب", reply_markup=main_menu())

    elif state == "waiting_rules_text":
        group_settings["rules_text"] = text
        user_states.pop(user.id, None)
        save_settings()
        await update.message.reply_text("✅ تم تحديث القوانين", reply_markup=main_menu())

    elif state == "waiting_reply_trigger":
        context.user_data["trigger"] = text
        user_states[user.id] = "waiting_reply_response"
        await update.message.reply_text("أرسل الآن الرد.")

    elif state == "waiting_reply_response":
        trigger = context.user_data.get("trigger")
        if trigger:
            group_settings["replies"][trigger] = text
            save_settings()
        context.user_data.pop("trigger", None)
        user_states.pop(user.id, None)
        await update.message.reply_text("✅ تمت إضافة الرد", reply_markup=main_menu())

    elif state == "waiting_delete_reply":
        if text in group_settings["replies"]:
            del group_settings["replies"][text]
            save_settings()
            msg = "✅ تم حذف الرد"
        else:
            msg = "❌ هذه الكلمة غير موجودة"
        user_states.pop(user.id, None)
        await update.message.reply_text(msg, reply_markup=main_menu())

    elif state == "waiting_badword":
        if text not in group_settings["badwords"]:
            group_settings["badwords"].append(text)
            save_settings()
        user_states.pop(user.id, None)
        await update.message.reply_text("✅ تمت إضافة الكلمة الممنوعة", reply_markup=main_menu())


def contains_link(text: str) -> bool:
    pattern = r"(https?://\S+|www\.\S+|t\.me/\S+)"
    return bool(re.search(pattern, text, re.IGNORECASE))


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    if group_settings["group_id"]:
        current_chat_id = str(update.effective_chat.id)
        if current_chat_id != str(group_settings["group_id"]):
            return

    text = update.message.text.strip()
    user = update.effective_user

    if group_settings["anti_links"] and contains_link(text):
        try:
            await update.message.delete()
            await update.effective_chat.send_message("🚫 الروابط ممنوعة.")
        except Exception:
            pass
        return

    if group_settings["anti_badwords"]:
        lowered = text.lower()
        for badword in group_settings["badwords"]:
            if badword.lower() in lowered:
                try:
                    await update.message.delete()
                except Exception:
                    pass

                uid = str(user.id)
                count = group_settings["warnings"].get(uid, 0) + 1
                group_settings["warnings"][uid] = count
                save_settings()

                await update.effective_chat.send_message(
                    f"⚠️ {user.first_name} تحذير رقم {count} بسبب كلمة ممنوعة."
                )
                return

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
        name = member.first_name or "يا هلا"
        text = group_settings["welcome_text"].replace("{name}", name)
        await update.message.reply_text(text)


def main():
    if not TOKEN:
        raise ValueError("TOKEN غير موجود. حطه في Variables.")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bindgroup", bindgroup))
    app.add_handler(CommandHandler("rules", rules_command))
    app.add_handler(CommandHandler("welcome", welcome_command))
    app.add_handler(CommandHandler("settings", settings_command))

    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, handle_private))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_members))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND, handle_group_message))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()