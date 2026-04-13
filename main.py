import json
import os
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
)
from telegram.constants import ChatType
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = os.getenv("TOKEN")
OWNER_ID = 8406441503

DATA_FILE = Path("data.json")
BADWORDS_FILE = Path("badwords.txt")
BACKUP_FILE = Path("backup_data.json")

LINK_RE = re.compile(r"(https?://\S+|www\.\S+|t\.me/\S+)", re.IGNORECASE)

DEFAULT_GROUP = {
    "title": "",
    "welcome_enabled": True,
    "welcome_text": (
        "✨ أهلاً {name}\n"
        "🌹 نورت {group}\n\n"
        "📜 القوانين: /rules\n"
        "🆔 آيديك: {user_id}\n"
        "💎 نتمنى لك تجربة ممتعة ومميزة معنا"
    ),
    "welcome_photo": "",
    "rules_text": (
        "📜 قوانين القروب:\n"
        "1) احترام الجميع\n"
        "2) ممنوع السب\n"
        "3) ممنوع الإعلانات والروابط\n"
        "4) الالتزام بموضوع القروب\n"
        "5) قرارات الإدارة ملزمة"
    ),
    "note_text": "📌 لا توجد رسالة مثبتة حاليًا.",
    "auto_replies": {
        "السلام عليكم": "وعليكم السلام ورحمة الله وبركاته 🌹",
    },
    "anti_links": False,
    "anti_badwords": False,
    "auto_pin_note": False,
    "warnings": {},
    "mute_after": 3,
    "ban_after": 5,
    "vip_mode": True,
}

owner_states: dict[int, dict[str, Any]] = {}


def load_badwords() -> list[str]:
    if not BADWORDS_FILE.exists():
        return []
    with open(BADWORDS_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def save_badwords(words: list[str]) -> None:
    with open(BADWORDS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(words))


BADWORDS = load_badwords()


def load_data() -> dict[str, Any]:
    if not DATA_FILE.exists():
        return {"groups": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "groups" not in data or not isinstance(data["groups"], dict):
            data["groups"] = {}
        for gid, cfg in list(data["groups"].items()):
            merged = DEFAULT_GROUP.copy()
            if isinstance(cfg, dict):
                merged.update(cfg)
            if not isinstance(merged.get("auto_replies"), dict):
                merged["auto_replies"] = {}
            if not isinstance(merged.get("warnings"), dict):
                merged["warnings"] = {}
            data["groups"][gid] = merged
        return data
    except Exception:
        return {"groups": {}}


def save_data() -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(DATA, f, ensure_ascii=False, indent=2)


DATA = load_data()


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def ensure_group(chat_id: int, title: str = "") -> dict[str, Any]:
    gid = str(chat_id)
    if gid not in DATA["groups"]:
        DATA["groups"][gid] = DEFAULT_GROUP.copy()
        DATA["groups"][gid]["auto_replies"] = DEFAULT_GROUP["auto_replies"].copy()
        DATA["groups"][gid]["warnings"] = {}
    if title:
        DATA["groups"][gid]["title"] = title
    return DATA["groups"][gid]


def get_group(chat_id: int) -> dict[str, Any] | None:
    return DATA["groups"].get(str(chat_id))


def user_state(user_id: int) -> dict[str, Any]:
    if user_id not in owner_states:
        owner_states[user_id] = {"selected_group": None, "waiting": None, "temp_key": None}
    return owner_states[user_id]


def selected_group_id(user_id: int) -> str | None:
    state = user_state(user_id)
    gid = state.get("selected_group")
    if gid and gid in DATA["groups"]:
        return gid
    if DATA["groups"]:
        gid = next(iter(DATA["groups"].keys()))
        state["selected_group"] = gid
        return gid
    return None


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_user or not update.effective_chat:
        return False
    if is_owner(update.effective_user.id):
        return True
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


async def is_target_admin(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    if is_owner(user_id):
        return True
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


def contains_link(text: str) -> bool:
    return bool(LINK_RE.search(text))


def main_menu(user_id: int) -> InlineKeyboardMarkup:
    gid = selected_group_id(user_id)
    top = "⚠️ اختر قروب" if not gid else "📌 القروب المحدد"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(top, callback_data="groups")],
        [InlineKeyboardButton("🎉 الترحيب", callback_data="welcome_menu"),
         InlineKeyboardButton("📜 القوانين", callback_data="rules_menu")],
        [InlineKeyboardButton("🤖 الردود", callback_data="replies_menu"),
         InlineKeyboardButton("🛡️ الحماية", callback_data="protect_menu")],
        [InlineKeyboardButton("⚠️ الإنذارات", callback_data="warns_menu"),
         InlineKeyboardButton("📌 التثبيت", callback_data="pin_menu")],
        [InlineKeyboardButton("🖼️ الوسائط", callback_data="media_menu"),
         InlineKeyboardButton("📊 الإعدادات", callback_data="show_settings")],
        [InlineKeyboardButton("🛠️ أوامر المشرفين", callback_data="admins_menu"),
         InlineKeyboardButton("💾 النسخ الاحتياطي", callback_data="backup_menu")],
        [InlineKeyboardButton("📜 الأوامر", callback_data="commands_menu")],
    ])


def groups_menu() -> InlineKeyboardMarkup:
    rows = []
    for gid, cfg in DATA["groups"].items():
        title = cfg.get("title") or gid
        rows.append([InlineKeyboardButton(f"📌 {title}", callback_data=f"select_group:{gid}")])
    rows.append([InlineKeyboardButton("⬅️ العودة", callback_data="main")])
    return InlineKeyboardMarkup(rows)


def back(target: str = "main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ العودة", callback_data=target)]])


def welcome_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("تشغيل/إيقاف الترحيب", callback_data="toggle_welcome")],
        [InlineKeyboardButton("تغيير رسالة الترحيب", callback_data="set_welcome")],
        [InlineKeyboardButton("عرض رسالة الترحيب", callback_data="show_welcome")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="main")],
    ])


def rules_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("تغيير القوانين", callback_data="set_rules")],
        [InlineKeyboardButton("عرض القوانين", callback_data="show_rules")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="main")],
    ])


def replies_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("إضافة رد", callback_data="add_reply")],
        [InlineKeyboardButton("حذف رد", callback_data="delete_reply")],
        [InlineKeyboardButton("عرض الردود", callback_data="show_replies")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="main")],
    ])


def protect_menu(gid: str) -> InlineKeyboardMarkup:
    cfg = DATA["groups"][gid]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🚫 الروابط {'✅' if cfg['anti_links'] else '❌'}", callback_data="toggle_links")],
        [InlineKeyboardButton(f"🤬 الكلمات {'✅' if cfg['anti_badwords'] else '❌'}", callback_data="toggle_badwords")],
        [InlineKeyboardButton("➕ إضافة كلمة ممنوعة", callback_data="add_badword")],
        [InlineKeyboardButton("➖ حذف كلمة ممنوعة", callback_data="delete_badword")],
        [InlineKeyboardButton("📄 عرض الكلمات", callback_data="show_badwords")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="main")],
    ])


def warns_menu(gid: str) -> InlineKeyboardMarkup:
    cfg = DATA["groups"][gid]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔇 الكتم بعد {cfg['mute_after']}", callback_data="set_mute_after")],
        [InlineKeyboardButton(f"⛔ الطرد بعد {cfg['ban_after']}", callback_data="set_ban_after")],
        [InlineKeyboardButton("📄 عرض التحذيرات", callback_data="show_warns_panel")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="main")],
    ])


def pin_menu(gid: str) -> InlineKeyboardMarkup:
    cfg = DATA["groups"][gid]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 تغيير النص المثبت", callback_data="set_note")],
        [InlineKeyboardButton("📌 تثبيت النص الآن", callback_data="pin_note_now")],
        [InlineKeyboardButton(f"📍 التثبيت التلقائي {'✅' if cfg['auto_pin_note'] else '❌'}", callback_data="toggle_auto_pin")],
        [InlineKeyboardButton("👁️ عرض النص", callback_data="show_note")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="main")],
    ])


def media_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🖼️ تعيين صورة ترحيب", callback_data="set_welcome_photo")],
        [InlineKeyboardButton("🗑️ حذف صورة الترحيب", callback_data="clear_welcome_photo")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="main")],
    ])


def admins_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📘 عرض أوامر المشرفين", callback_data="show_admin_commands")],
        [InlineKeyboardButton("📘 عرض أوامر القروب", callback_data="show_group_commands")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="main")],
    ])


def backup_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💾 إنشاء نسخة احتياطية", callback_data="make_backup")],
        [InlineKeyboardButton("♻️ استرجاع النسخة الاحتياطية", callback_data="restore_backup")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="main")],
    ])


def settings_summary(gid: str) -> str:
    cfg = DATA["groups"][gid]
    return (
        "⚙️ إعدادات القروب\n\n"
        f"📌 الاسم: {cfg.get('title') or gid}\n"
        f"🆔 الآيدي: {gid}\n"
        f"🎉 الترحيب: {'مفعل ✅' if cfg['welcome_enabled'] else 'معطل ❌'}\n"
        f"🖼️ صورة الترحيب: {'موجودة ✅' if cfg['welcome_photo'] else 'غير موجودة ❌'}\n"
        f"🤖 الردود: {len(cfg['auto_replies'])}\n"
        f"🚫 منع الروابط: {'مفعل ✅' if cfg['anti_links'] else 'معطل ❌'}\n"
        f"🤬 منع الكلمات: {'مفعل ✅' if cfg['anti_badwords'] else 'معطل ❌'}\n"
        f"📝 الكلمات الممنوعة: {len(BADWORDS)}\n"
        f"⚠️ عدد التحذيرات: {len(cfg['warnings'])}\n"
        f"🔇 الكتم بعد: {cfg['mute_after']}\n"
        f"⛔ الطرد بعد: {cfg['ban_after']}\n"
        f"📌 التثبيت التلقائي: {'مفعل ✅' if cfg['auto_pin_note'] else 'معطل ❌'}"
    )


def format_welcome(cfg: dict[str, Any], name: str, group_title: str, user_id: int) -> str:
    return (
        cfg["welcome_text"]
        .replace("{name}", name)
        .replace("{group}", group_title)
        .replace("{user_id}", str(user_id))
    )


async def pin_note_now(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str) -> None:
    try:
        msg = await context.bot.send_message(chat_id, text)
        await context.bot.pin_chat_message(chat_id, msg.message_id, disable_notification=True)
    except Exception:
        pass


def make_backup() -> None:
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(DATA, f, ensure_ascii=False, indent=2)


def restore_backup() -> bool:
    global DATA
    if not BACKUP_FILE.exists():
        return False
    try:
        with open(BACKUP_FILE, "r", encoding="utf-8") as f:
            DATA = json.load(f)
        save_data()
        return True
    except Exception:
        return False


async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE, reason: str) -> None:
    if not update.effective_user or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    uid = str(update.effective_user.id)
    cfg = ensure_group(chat_id, update.effective_chat.title or "")

    count = int(cfg["warnings"].get(uid, 0)) + 1
    cfg["warnings"][uid] = count
    save_data()

    punishment = ""
    try:
        if count >= int(cfg["ban_after"]):
            await context.bot.ban_chat_member(chat_id, update.effective_user.id)
            punishment = "⛔ تم طرده."
        elif count >= int(cfg["mute_after"]):
            until = datetime.now(timezone.utc) + timedelta(minutes=30)
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=update.effective_user.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until,
            )
            punishment = "🔇 تم كتمه 30 دقيقة."
    except Exception:
        pass

    await update.effective_chat.send_message(
        f"⚠️ {update.effective_user.first_name} أخذ تحذير رقم {count}\nالسبب: {reason}\n{punishment}"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.message.reply_text("⚠️ استخدم البوت في الخاص فقط\n\n@ArcZone_SaudiBot")
        return

    user = update.effective_user
    if not user or not is_owner(user.id):
        await update.message.reply_text("هذا البوت مخصص للإدارة فقط.")
        return

    await update.message.reply_text("👑 أهلاً بك في لوحة تحكم البوت الكاملة", reply_markup=main_menu(user.id))


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return
    await update.message.reply_text(
        f"🆔 آيديك: {user.id}\n👤 اسمك: {user.first_name}\n💬 آيدي الدردشة: {chat.id}\n📌 النوع: {chat.type}"
    )


async def cmd_bindgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text("استخدم هذا الأمر داخل القروب.")
        return
    if not await is_admin(update, context):
        await update.message.reply_text("هذا الأمر للمشرفين فقط.")
        return
    cfg = ensure_group(update.effective_chat.id, update.effective_chat.title or "")
    save_data()
    await update.message.reply_text(f"✅ تم ربط القروب\nالاسم: {cfg['title']}\nالآيدي: {update.effective_chat.id}")


async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = get_group(update.effective_chat.id)
    if not cfg:
        await update.message.reply_text("هذا القروب غير مربوط. استخدم /bindgroup")
        return
    await update.message.reply_text(cfg["rules_text"])


async def cmd_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = get_group(update.effective_chat.id)
    if not cfg:
        await update.message.reply_text("هذا القروب غير مربوط. استخدم /bindgroup")
        return
    text = format_welcome(cfg, update.effective_user.first_name, update.effective_chat.title or "القروب", update.effective_user.id)
    if cfg["welcome_photo"]:
        try:
            await update.message.reply_photo(cfg["welcome_photo"], caption=text)
            return
        except Exception:
            pass
    await update.message.reply_text(text)


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("هذا الأمر للمشرفين فقط.")
        return
    cfg = get_group(update.effective_chat.id)
    if not cfg:
        await update.message.reply_text("هذا القروب غير مربوط.")
        return
    await update.message.reply_text(settings_summary(str(update.effective_chat.id)))


async def cmd_warns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = get_group(update.effective_chat.id)
    if not cfg:
        await update.message.reply_text("هذا القروب غير مربوط.")
        return
    target = update.message.reply_to_message.from_user if update.message.reply_to_message and update.message.reply_to_message.from_user else update.effective_user
    count = int(cfg["warnings"].get(str(target.id), 0))
    await update.message.reply_text(f"⚠️ عدد تحذيرات {target.first_name}: {count}")


async def cmd_clearwarns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("هذا الأمر للمشرفين فقط.")
        return
    cfg = get_group(update.effective_chat.id)
    if not cfg:
        await update.message.reply_text("هذا القروب غير مربوط.")
        return
    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("رد على رسالة الشخص ثم استخدم /clearwarns")
        return
    target = update.message.reply_to_message.from_user
    cfg["warnings"][str(target.id)] = 0
    save_data()
    await update.message.reply_text(f"✅ تم تصفير تحذيرات {target.first_name}")


async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("هذا الأمر للمشرفين فقط.")
        return
    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("رد على رسالة الشخص ثم استخدم /warn")
        return
    target = update.message.reply_to_message.from_user
    if await is_target_admin(context, update.effective_chat.id, target.id):
        await update.message.reply_text("لا يمكن إنذار مشرف.")
        return
    cfg = ensure_group(update.effective_chat.id, update.effective_chat.title or "")
    uid = str(target.id)
    count = int(cfg["warnings"].get(uid, 0)) + 1
    cfg["warnings"][uid] = count
    save_data()
    await update.message.reply_text(f"⚠️ تم إنذار {target.first_name}. عدد التحذيرات: {count}")


async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("هذا الأمر للمشرفين فقط.")
        return
    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("رد على رسالة الشخص ثم استخدم /mute")
        return
    target = update.message.reply_to_message.from_user
    try:
        until = datetime.now(timezone.utc) + timedelta(minutes=30)
        await context.bot.restrict_chat_member(update.effective_chat.id, target.id, permissions=ChatPermissions(can_send_messages=False), until_date=until)
        await update.message.reply_text(f"🔇 تم كتم {target.first_name} 30 دقيقة.")
    except Exception:
        await update.message.reply_text("تعذر الكتم.")


async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("هذا الأمر للمشرفين فقط.")
        return
    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("رد على رسالة الشخص ثم استخدم /unmute")
        return
    target = update.message.reply_to_message.from_user
    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            target.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            ),
        )
        await update.message.reply_text(f"✅ تم فك كتم {target.first_name}.")
    except Exception:
        await update.message.reply_text("تعذر فك الكتم.")


async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("هذا الأمر للمشرفين فقط.")
        return
    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("رد على رسالة الشخص ثم استخدم /ban")
        return
    target = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await update.message.reply_text(f"⛔ تم طرد {target.first_name}.")
    except Exception:
        await update.message.reply_text("تعذر الطرد.")


async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("هذا الأمر للمشرفين فقط.")
        return
    if not context.args:
        await update.message.reply_text("استخدم /unban user_id")
        return
    try:
        user_id = int(context.args[0])
        await context.bot.unban_chat_member(update.effective_chat.id, user_id, only_if_banned=True)
        await update.message.reply_text("✅ تم فك الحظر.")
    except Exception:
        await update.message.reply_text("تعذر فك الحظر.")


async def cmd_setnote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("هذا الأمر للمشرفين فقط.")
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("استخدم /setnote نص الملاحظة")
        return
    cfg = ensure_group(update.effective_chat.id, update.effective_chat.title or "")
    cfg["note_text"] = text
    save_data()
    await update.message.reply_text("✅ تم حفظ النص المثبت.")


async def cmd_clean(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("هذا الأمر للمشرفين فقط.")
        return
    try:
        if update.message.reply_to_message:
            await update.message.reply_to_message.delete()
        await update.message.delete()
    except Exception:
        await update.message.reply_text("تعذر حذف الرسالة.")


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user = query.from_user
    if not is_owner(user.id):
        await query.edit_message_text("هذا البوت مخصص للإدارة فقط.")
        return

    st = user_state(user.id)
    gid = selected_group_id(user.id)
    data = query.data

    if data == "main":
        await query.edit_message_text("👑 أهلاً بك في لوحة تحكم البوت الكاملة", reply_markup=main_menu(user.id))
        return

    if data == "groups":
        if not DATA["groups"]:
            await query.edit_message_text("لا يوجد قروبات مربوطة بعد.\nأضف البوت للقروب ثم اكتب /bindgroup", reply_markup=back("main"))
            return
        await query.edit_message_text("اختر القروب:", reply_markup=groups_menu())
        return

    if data.startswith("select_group:"):
        st["selected_group"] = data.split(":", 1)[1]
        await query.edit_message_text("✅ تم اختيار القروب.", reply_markup=back("main"))
        return

    if not gid:
        await query.edit_message_text("اختر قروب أولاً.", reply_markup=back("main"))
        return

    cfg = DATA["groups"][gid]

    if data == "welcome_menu":
        await query.edit_message_text("🎉 قسم الترحيب", reply_markup=welcome_menu())
    elif data == "toggle_welcome":
        cfg["welcome_enabled"] = not cfg["welcome_enabled"]
        save_data()
        await query.edit_message_text("✅ تم تحديث حالة الترحيب", reply_markup=welcome_menu())
    elif data == "set_welcome":
        st["waiting"] = "set_welcome"
        await query.edit_message_text("أرسل رسالة الترحيب الجديدة.", reply_markup=back("main"))
    elif data == "show_welcome":
        await query.edit_message_text(cfg["welcome_text"], reply_markup=back("welcome_menu"))

    elif data == "rules_menu":
        await query.edit_message_text("📜 قسم القوانين", reply_markup=rules_menu())
    elif data == "set_rules":
        st["waiting"] = "set_rules"
        await query.edit_message_text("أرسل القوانين الجديدة.", reply_markup=back("main"))
    elif data == "show_rules":
        await query.edit_message_text(cfg["rules_text"], reply_markup=back("rules_menu"))

    elif data == "replies_menu":
        await query.edit_message_text("🤖 قسم الردود", reply_markup=replies_menu())
    elif data == "add_reply":
        st["waiting"] = "add_reply_key"
        await query.edit_message_text("أرسل الكلمة.", reply_markup=back("main"))
    elif data == "delete_reply":
        st["waiting"] = "delete_reply_key"
        await query.edit_message_text("أرسل الكلمة لحذف ردها.", reply_markup=back("main"))
    elif data == "show_replies":
        text = "لا توجد ردود." if not cfg["auto_replies"] else "\n\n".join([f"{k} ➜ {v}" for k, v in cfg["auto_replies"].items()])
        await query.edit_message_text(text, reply_markup=back("replies_menu"))

    elif data == "protect_menu":
        await query.edit_message_text("🛡️ قسم الحماية", reply_markup=protect_menu(gid))
    elif data == "toggle_links":
        cfg["anti_links"] = not cfg["anti_links"]
        save_data()
        await query.edit_message_text("✅ تم تحديث منع الروابط", reply_markup=protect_menu(gid))
    elif data == "toggle_badwords":
        cfg["anti_badwords"] = not cfg["anti_badwords"]
        save_data()
        await query.edit_message_text("✅ تم تحديث منع الكلمات", reply_markup=protect_menu(gid))
    elif data == "add_badword":
        st["waiting"] = "add_badword"
        await query.edit_message_text("أرسل الكلمة الممنوعة.", reply_markup=back("main"))
    elif data == "delete_badword":
        st["waiting"] = "delete_badword"
        await query.edit_message_text("أرسل الكلمة المراد حذفها.", reply_markup=back("main"))
    elif data == "show_badwords":
        await query.edit_message_text("لا توجد كلمات." if not BADWORDS else "\n".join(BADWORDS), reply_markup=back("protect_menu"))

    elif data == "warns_menu":
        await query.edit_message_text("⚠️ قسم الإنذارات", reply_markup=warns_menu(gid))
    elif data == "set_mute_after":
        st["waiting"] = "set_mute_after"
        await query.edit_message_text("أرسل رقم الكتم بعد كم إنذار.", reply_markup=back("main"))
    elif data == "set_ban_after":
        st["waiting"] = "set_ban_after"
        await query.edit_message_text("أرسل رقم الطرد بعد كم إنذار.", reply_markup=back("main"))
    elif data == "show_warns_panel":
        text = "لا توجد تحذيرات." if not cfg["warnings"] else "\n".join([f"{u}: {c}" for u, c in cfg["warnings"].items()])
        await query.edit_message_text(text, reply_markup=back("warns_menu"))

    elif data == "pin_menu":
        await query.edit_message_text("📌 قسم التثبيت", reply_markup=pin_menu(gid))
    elif data == "set_note":
        st["waiting"] = "set_note"
        await query.edit_message_text("أرسل النص المثبت الجديد.", reply_markup=back("main"))
    elif data == "show_note":
        await query.edit_message_text(cfg["note_text"], reply_markup=back("pin_menu"))
    elif data == "toggle_auto_pin":
        cfg["auto_pin_note"] = not cfg["auto_pin_note"]
        save_data()
        await query.edit_message_text("✅ تم تحديث التثبيت التلقائي", reply_markup=pin_menu(gid))
    elif data == "pin_note_now":
        await pin_note_now(context, int(gid), cfg["note_text"])
        await query.edit_message_text("✅ تمت محاولة تثبيت الرسالة.", reply_markup=pin_menu(gid))

    elif data == "media_menu":
        await query.edit_message_text("🖼️ قسم الوسائط", reply_markup=media_menu())
    elif data == "set_welcome_photo":
        st["waiting"] = "set_welcome_photo"
        await query.edit_message_text("أرسل رابط الصورة أو file_id.", reply_markup=back("main"))
    elif data == "clear_welcome_photo":
        cfg["welcome_photo"] = ""
        save_data()
        await query.edit_message_text("✅ تم حذف صورة الترحيب.", reply_markup=media_menu())

    elif data == "show_settings":
        await query.edit_message_text(settings_summary(gid), reply_markup=back("main"))

    elif data == "admins_menu":
        await query.edit_message_text("🛠️ قسم أوامر المشرفين", reply_markup=admins_menu())
    elif data == "show_admin_commands":
        await query.edit_message_text(
            "🛠️ أوامر المشرفين:\n\n"
            "/warn - تحذير عضو بالرد\n"
            "/warns - عرض التحذيرات\n"
            "/clearwarns - تصفير التحذيرات\n"
            "/mute - كتم عضو بالرد\n"
            "/unmute - فك الكتم بالرد\n"
            "/ban - حظر عضو بالرد\n"
            "/unban user_id - فك الحظر\n"
            "/setnote نص - تغيير الملاحظة المثبتة\n"
            "/clean - حذف الرسالة بالرد",
            reply_markup=back("admins_menu"),
        )
    elif data == "show_group_commands":
        await query.edit_message_text(
            "📘 أوامر القروب:\n\n"
            "/bindgroup - ربط القروب\n"
            "/id - عرض الآيدي\n"
            "/rules - عرض القوانين\n"
            "/welcome - عرض رسالة الترحيب\n"
            "/settings - عرض إعدادات القروب",
            reply_markup=back("admins_menu"),
        )

    elif data == "backup_menu":
        await query.edit_message_text("💾 قسم النسخ الاحتياطي", reply_markup=backup_menu())
    elif data == "make_backup":
        make_backup()
        await query.edit_message_text("✅ تم إنشاء نسخة احتياطية.", reply_markup=backup_menu())
    elif data == "restore_backup":
        ok = restore_backup()
        await query.edit_message_text("✅ تم استرجاع النسخة." if ok else "❌ لا توجد نسخة احتياطية.", reply_markup=backup_menu())

    elif data == "commands_menu":
        await query.edit_message_text(
            "📜 أوامر البوت:\n\n"
            "👤 أوامر عامة:\n"
            "/id - عرض الآيدي\n"
            "/rules - عرض القوانين\n"
            "/welcome - عرض رسالة الترحيب\n"
            "/settings - عرض إعدادات القروب\n\n"
            "🛡️ أوامر المشرفين:\n"
            "/warn - تحذير عضو بالرد\n"
            "/warns - عرض تحذيرات عضو\n"
            "/clearwarns - تصفير التحذيرات\n"
            "/mute - كتم عضو بالرد\n"
            "/unmute - فك الكتم بالرد\n"
            "/ban - حظر عضو بالرد\n"
            "/unban user_id - فك الحظر\n"
            "/setnote نص - تغيير الملاحظة المثبتة\n"
            "/clean - حذف الرسالة بالرد\n"
            "/bindgroup - ربط القروب\n",
            reply_markup=back("main"),
        )


async def handle_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    user = update.effective_user
    if not user or not is_owner(user.id):
        return
    if not update.message or not update.message.text:
        return

    st = user_state(user.id)
    gid = selected_group_id(user.id)
    if not gid:
        return

    cfg = DATA["groups"][gid]
    waiting = st.get("waiting")
    text = update.message.text.strip()

    if waiting == "set_welcome":
        cfg["welcome_text"] = text
    elif waiting == "set_rules":
        cfg["rules_text"] = text
    elif waiting == "add_reply_key":
        st["temp_key"] = text
        st["waiting"] = "add_reply_value"
        await update.message.reply_text("أرسل الرد الآن.")
        return
    elif waiting == "add_reply_value":
        if st.get("temp_key"):
            cfg["auto_replies"][st["temp_key"]] = text
            st["temp_key"] = None
    elif waiting == "delete_reply_key":
        cfg["auto_replies"].pop(text, None)
    elif waiting == "add_badword":
        if text not in BADWORDS:
            BADWORDS.append(text)
            save_badwords(BADWORDS)
    elif waiting == "delete_badword":
        if text in BADWORDS:
            BADWORDS.remove(text)
            save_badwords(BADWORDS)
    elif waiting == "set_mute_after":
        if text.isdigit():
            cfg["mute_after"] = int(text)
    elif waiting == "set_ban_after":
        if text.isdigit():
            cfg["ban_after"] = int(text)
    elif waiting == "set_note":
        cfg["note_text"] = text
    elif waiting == "set_welcome_photo":
        cfg["welcome_photo"] = text

    st["waiting"] = None
    save_data()
    await update.message.reply_text("✅ تم الحفظ.", reply_markup=main_menu(user.id))


async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return
    cfg = get_group(update.effective_chat.id)
    if not cfg or not cfg["welcome_enabled"]:
        return

    group_name = update.effective_chat.title or "القروب"
    for member in update.message.new_chat_members:
        text = format_welcome(cfg, member.first_name or "يا هلا", group_name, member.id)
        if cfg["welcome_photo"]:
            try:
                await update.message.reply_photo(cfg["welcome_photo"], caption=text)
            except Exception:
                await update.message.reply_text(text)
        else:
            await update.message.reply_text(text)

    if cfg["auto_pin_note"] and cfg["note_text"]:
        await pin_note_now(context, update.effective_chat.id, cfg["note_text"])


async def handle_group_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    cfg = get_group(update.effective_chat.id)
    if not cfg:
        return

    user = update.effective_user
    text = update.message.text.strip()

    if not await is_target_admin(context, update.effective_chat.id, user.id):
        if cfg["anti_links"] and contains_link(text):
            try:
                await update.message.delete()
            except Exception:
                pass
            await warn_user(update, context, "إرسال رابط")
            return

        if cfg["anti_badwords"]:
            lowered = text.lower()
            for word in BADWORDS:
                if word.lower() in lowered:
                    try:
                        await update.message.delete()
                    except Exception:
                        pass
                    await warn_user(update, context, "كلمة ممنوعة")
                    return

    for key, reply in cfg["auto_replies"].items():
        if key and key.lower() in text.lower():
            await update.message.reply_text(reply)
            break


def main():
    if not TOKEN:
        raise ValueError("TOKEN غير موجود. حطه في Variables باسم TOKEN")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("bindgroup", cmd_bindgroup))
    app.add_handler(CommandHandler("rules", cmd_rules))
    app.add_handler(CommandHandler("welcome", cmd_welcome))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("warns", cmd_warns))
    app.add_handler(CommandHandler("clearwarns", cmd_clearwarns))
    app.add_handler(CommandHandler("warn", cmd_warn))
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("unmute", cmd_unmute))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("setnote", cmd_setnote))
    app.add_handler(CommandHandler("clean", cmd_clean))

    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, handle_private))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND, handle_group_text))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()