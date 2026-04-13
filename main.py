import json
import os
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
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
DATA_FILE = Path("settings.json")

LINK_RE = re.compile(r"(https?://\S+|www\.\S+|t\.me/\S+|telegram\.me/\S+)", re.IGNORECASE)

DEFAULT_GROUP = {
    "title": "",
    "welcome_enabled": True,
    "welcome_text": (
        "🌹 أهلاً {name}\n"
        "👑 نورت {group}\n\n"
        "📜 القوانين: /rules\n"
        "🆔 آيديك: {user_id}\n"
        "✨ نتمنى لك وقت ممتع معنا"
    ),
    "rules_text": (
        "📜 قوانين القروب:\n"
        "1) احترام الجميع\n"
        "2) ممنوع السب\n"
        "3) ممنوع الروابط والإعلانات\n"
        "4) الالتزام بموضوع القروب"
    ),
    "auto_replies": {
        "السلام عليكم": "وعليكم السلام ورحمة الله 🌹",
    },
    "anti_links": False,
    "anti_badwords": False,
    "badwords": ["سب", "شتيمة"],
    "warnings": {},
    "mute_after": 3,
    "ban_after": 5,
    "settings_note": "لا يوجد",
}

DEFAULT_DATA = {
    "groups": {}
}

owner_session: dict[int, dict[str, Any]] = {}


def load_data() -> dict[str, Any]:
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "groups" not in data or not isinstance(data["groups"], dict):
                data["groups"] = {}
            for gid, cfg in list(data["groups"].items()):
                merged = deepcopy(DEFAULT_GROUP)
                merged.update(cfg if isinstance(cfg, dict) else {})
                if not isinstance(merged.get("auto_replies"), dict):
                    merged["auto_replies"] = {}
                if not isinstance(merged.get("badwords"), list):
                    merged["badwords"] = []
                if not isinstance(merged.get("warnings"), dict):
                    merged["warnings"] = {}
                data["groups"][gid] = merged
            return data
        except Exception:
            return deepcopy(DEFAULT_DATA)
    return deepcopy(DEFAULT_DATA)


def save_data() -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(DATA, f, ensure_ascii=False, indent=2)


DATA = load_data()


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def ensure_group(chat_id: int, title: str = "") -> dict[str, Any]:
    gid = str(chat_id)
    if gid not in DATA["groups"]:
        DATA["groups"][gid] = deepcopy(DEFAULT_GROUP)
    if title:
        DATA["groups"][gid]["title"] = title
    return DATA["groups"][gid]


def get_group(chat_id: int) -> dict[str, Any] | None:
    return DATA["groups"].get(str(chat_id))


def owner_state(user_id: int) -> dict[str, Any]:
    if user_id not in owner_session:
        owner_session[user_id] = {"selected_group": None, "waiting": None}
    return owner_session[user_id]


def selected_group_id(user_id: int) -> str | None:
    st = owner_state(user_id)
    gid = st.get("selected_group")
    if gid and gid in DATA["groups"]:
        return gid
    if DATA["groups"]:
        first_gid = next(iter(DATA["groups"].keys()))
        st["selected_group"] = first_gid
        return first_gid
    return None


def current_group_text(user_id: int) -> str:
    gid = selected_group_id(user_id)
    if not gid:
        return "غير محدد"
    title = DATA["groups"][gid].get("title") or gid
    return f"{title}\n{gid}"


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_user or not update.effective_chat:
        return False
    if is_owner(update.effective_user.id):
        return True
    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id,
            update.effective_user.id,
        )
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


def main_menu(user_id: int) -> InlineKeyboardMarkup:
    gid = selected_group_id(user_id)
    top = "⚠️ ما فيه قروب مربوط" if not gid else "📌 القروب المحدد"
    keyboard = [
        [InlineKeyboardButton(top, callback_data="groups")],
        [InlineKeyboardButton("🎉 الترحيب", callback_data="welcome_menu"),
         InlineKeyboardButton("📜 القوانين", callback_data="rules_menu")],
        [InlineKeyboardButton("🤖 الردود التلقائية", callback_data="replies_menu"),
         InlineKeyboardButton("🛡️ الحماية", callback_data="protect_menu")],
        [InlineKeyboardButton("⚠️ الإنذارات", callback_data="warns_menu"),
         InlineKeyboardButton("🔗 رابط المجموعة", callback_data="groups")],
        [InlineKeyboardButton("📊 عرض الإعدادات", callback_data="show_settings"),
         InlineKeyboardButton("🆔 /id", callback_data="show_id_help")],
        [InlineKeyboardButton("➕ مميزات إضافية", callback_data="extras_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def back_button(target: str = "main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ العودة", callback_data=target)]])


def groups_menu() -> InlineKeyboardMarkup:
    rows = []
    for gid, cfg in DATA["groups"].items():
        title = cfg.get("title") or gid
        rows.append([InlineKeyboardButton(f"📌 {title}", callback_data=f"selgrp:{gid}")])
    rows.append([InlineKeyboardButton("⬅️ العودة", callback_data="main")])
    return InlineKeyboardMarkup(rows)


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
        [InlineKeyboardButton("حذف رد", callback_data="del_reply")],
        [InlineKeyboardButton("عرض الردود", callback_data="show_replies")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="main")],
    ])


def protect_menu(gid: str) -> InlineKeyboardMarkup:
    cfg = DATA["groups"][gid]
    link_s = "✅" if cfg["anti_links"] else "❌"
    bad_s = "✅" if cfg["anti_badwords"] else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🚫 منع الروابط {link_s}", callback_data="toggle_links")],
        [InlineKeyboardButton(f"🤬 منع الكلمات {bad_s}", callback_data="toggle_badwords")],
        [InlineKeyboardButton("➕ إضافة كلمة ممنوعة", callback_data="add_badword")],
        [InlineKeyboardButton("➖ حذف كلمة ممنوعة", callback_data="del_badword")],
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


def extras_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ أوامر القروب", callback_data="show_group_commands")],
        [InlineKeyboardButton("💡 طريقة ربط القروب", callback_data="show_bind_help")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="main")],
    ])


def settings_summary(gid: str) -> str:
    cfg = DATA["groups"][gid]
    replies_count = len(cfg["auto_replies"])
    bad_count = len(cfg["badwords"])
    warns_count = len(cfg["warnings"])
    return (
        "⚙️ إعدادات القروب\n\n"
        f"📌 الاسم: {cfg.get('title') or gid}\n"
        f"🆔 الآيدي: {gid}\n"
        f"🎉 الترحيب: {'مفعل ✅' if cfg['welcome_enabled'] else 'معطل ❌'}\n"
        f"🤖 الردود: {replies_count}\n"
        f"🚫 منع الروابط: {'مفعل ✅' if cfg['anti_links'] else 'معطل ❌'}\n"
        f"🤬 منع الكلمات: {'مفعل ✅' if cfg['anti_badwords'] else 'معطل ❌'}\n"
        f"📝 الكلمات الممنوعة: {bad_count}\n"
        f"⚠️ عدد سجلات التحذيرات: {warns_count}\n"
        f"🔇 الكتم بعد: {cfg['mute_after']}\n"
        f"⛔ الطرد بعد: {cfg['ban_after']}\n"
        f"📎 ملاحظة: {cfg.get('settings_note', 'لا يوجد')}"
    )


def welcome_text_for_user(cfg: dict[str, Any], member_name: str, group_name: str, user_id: int) -> str:
    return (
        cfg["welcome_text"]
        .replace("{name}", member_name)
        .replace("{group}", group_name)
        .replace("{user_id}", str(user_id))
    )


def contains_link(text: str) -> bool:
    return bool(LINK_RE.search(text))


async def warn_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    reason: str,
) -> None:
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
            await context.bot.ban_chat_member(chat_id=chat_id, user_id=update.effective_user.id)
            punishment = "⛔ تم طرده من القروب."
        elif count >= int(cfg["mute_after"]):
            until = datetime.now(timezone.utc) + timedelta(minutes=30)
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=update.effective_user.id,
                permissions=ChatPermissions(
                    can_send_messages=False,
                    can_send_audios=False,
                    can_send_documents=False,
                    can_send_photos=False,
                    can_send_videos=False,
                    can_send_video_notes=False,
                    can_send_voice_notes=False,
                    can_send_polls=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False,
                    can_change_info=False,
                    can_invite_users=False,
                    can_pin_messages=False,
                    can_manage_topics=False,
                ),
                until_date=until,
            )
            punishment = "🔇 تم كتمه 30 دقيقة."
    except Exception:
        pass

    await update.effective_chat.send_message(
        f"⚠️ {update.effective_user.first_name} أخذ تحذير رقم {count}\n"
        f"السبب: {reason}\n"
        f"{punishment}"
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
        f"📌 القروب المحدد الآن:\n{current_group_text(user.id)}\n\n"
        "من هنا تقدر تضبط:\n"
        "• ربط القروبات\n"
        "• الترحيب VIP\n"
        "• القوانين\n"
        "• الردود التلقائية\n"
        "• الحماية\n"
        "• الإنذارات"
    )
    await update.message.reply_text(text, reply_markup=main_menu(user.id))


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    text = (
        f"🆔 آيديك: {user.id}\n"
        f"👤 اسمك: {user.first_name}\n"
        f"💬 آيدي الدردشة: {chat.id}\n"
        f"📌 النوع: {chat.type}"
    )
    await update.message.reply_text(text)


async def cmd_bindgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text("استخدم هذا الأمر داخل القروب.")
        return

    if not await is_admin(update, context):
        await update.message.reply_text("هذا الأمر للمشرف أو المالك فقط.")
        return

    cfg = ensure_group(update.effective_chat.id, update.effective_chat.title or "")
    save_data()
    await update.message.reply_text(
        f"✅ تم ربط القروب بنجاح\n"
        f"الاسم: {cfg['title']}\n"
        f"الآيدي: {update.effective_chat.id}"
    )


async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = get_group(update.effective_chat.id)
    if not cfg:
        await update.message.reply_text("هذا القروب غير مربوط بعد. استخدم /bindgroup")
        return
    await update.message.reply_text(cfg["rules_text"])


async def cmd_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = get_group(update.effective_chat.id)
    if not cfg:
        await update.message.reply_text("هذا القروب غير مربوط بعد. استخدم /bindgroup")
        return
    name = update.effective_user.first_name if update.effective_user else "يا هلا"
    await update.message.reply_text(
        welcome_text_for_user(cfg, name, update.effective_chat.title or "القروب", update.effective_user.id)
    )


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("هذا الأمر للمشرفين فقط.")
        return
    cfg = get_group(update.effective_chat.id)
    if not cfg:
        await update.message.reply_text("هذا القروب غير مربوط بعد. استخدم /bindgroup")
        return
    await update.message.reply_text(settings_summary(str(update.effective_chat.id)))


async def cmd_warns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = get_group(update.effective_chat.id)
    if not cfg:
        await update.message.reply_text("هذا القروب غير مربوط بعد.")
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
        await update.message.reply_text("هذا القروب غير مربوط بعد.")
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

    punishment = ""
    try:
        if count >= int(cfg["ban_after"]):
            await context.bot.ban_chat_member(update.effective_chat.id, target.id)
            punishment = "⛔ تم طرده."
        elif count >= int(cfg["mute_after"]):
            until = datetime.now(timezone.utc) + timedelta(minutes=30)
            await context.bot.restrict_chat_member(
                chat_id=update.effective_chat.id,
                user_id=target.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until,
            )
            punishment = "🔇 تم كتمه 30 دقيقة."
    except Exception:
        pass

    await update.message.reply_text(
        f"⚠️ {target.first_name} أخذ تحذير رقم {count}\n{punishment}"
    )


async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("هذا الأمر للمشرفين فقط.")
        return
    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("رد على رسالة الشخص ثم استخدم /mute")
        return
    target = update.message.reply_to_message.from_user
    if await is_target_admin(context, update.effective_chat.id, target.id):
        await update.message.reply_text("لا يمكن كتم مشرف.")
        return
    try:
        until = datetime.now(timezone.utc) + timedelta(minutes=30)
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until,
        )
        await update.message.reply_text(f"🔇 تم كتم {target.first_name} لمدة 30 دقيقة.")
    except Exception:
        await update.message.reply_text("تعذر كتم العضو.")


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
            chat_id=update.effective_chat.id,
            user_id=target.id,
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
    if await is_target_admin(context, update.effective_chat.id, target.id):
        await update.message.reply_text("لا يمكن طرد مشرف.")
        return
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await update.message.reply_text(f"⛔ تم طرد {target.first_name}.")
    except Exception:
        await update.message.reply_text("تعذر طرد العضو.")


async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("هذا الأمر للمشرفين فقط.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("استخدم /unban user_id")
        return
    try:
        user_id = int(args[0])
        await context.bot.unban_chat_member(update.effective_chat.id, user_id, only_if_banned=True)
        await update.message.reply_text("✅ تم فك الحظر.")
    except Exception:
        await update.message.reply_text("تعذر فك الحظر. تأكد من user_id.")


async def cmd_setnote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("هذا الأمر للمشرفين فقط.")
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("استخدم /setnote نص الملاحظة")
        return
    cfg = ensure_group(update.effective_chat.id, update.effective_chat.title or "")
    cfg["settings_note"] = text
    save_data()
    await update.message.reply_text("✅ تم حفظ الملاحظة.")


async def cmd_clean(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("هذا الأمر للمشرفين فقط.")
        return
    try:
        if update.message.reply_to_message:
            await update.message.reply_to_message.delete()
        await update.message.delete()
    except Exception:
        await update.message.reply_text("تعذر حذف الرسالة. خل البوت مشرف وبصلاحية حذف الرسائل.")


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user = query.from_user
    if not is_owner(user.id):
        await query.edit_message_text("هذا البوت مخصص للإدارة فقط.")
        return

    st = owner_state(user.id)
    gid = selected_group_id(user.id)
    data = query.data

    if data == "main":
        text = (
            "👑 أهلاً بك في لوحة تحكم البوت\n\n"
            f"📌 القروب المحدد الآن:\n{current_group_text(user.id)}"
        )
        await query.edit_message_text(text, reply_markup=main_menu(user.id))

    elif data == "groups":
        if not DATA["groups"]:
            await query.edit_message_text(
                "لا يوجد أي قروب مربوط.\n\n"
                "أضف البوت للقروب، خله مشرف، ثم اكتب داخل القروب:\n/bindgroup",
                reply_markup=back_button("main"),
            )
            return
        await query.edit_message_text("اختر القروب الذي تريد تعديله:", reply_markup=groups_menu())

    elif data.startswith("selgrp:"):
        gid = data.split(":", 1)[1]
        st["selected_group"] = gid
        title = DATA["groups"][gid].get("title") or gid
        await query.edit_message_text(
            f"✅ تم اختيار القروب:\n{title}\n{gid}",
            reply_markup=back_button("main"),
        )

    elif not gid:
        await query.edit_message_text(
            "لا يوجد قروب محدد. اختر قروب أولاً.",
            reply_markup=back_button("main"),
        )

    elif data == "welcome_menu":
        status = "مفعل ✅" if DATA["groups"][gid]["welcome_enabled"] else "معطل ❌"
        await query.edit_message_text(
            f"🎉 قسم الترحيب\nالحالة: {status}",
            reply_markup=welcome_menu(),
        )

    elif data == "toggle_welcome":
        DATA["groups"][gid]["welcome_enabled"] = not DATA["groups"][gid]["welcome_enabled"]
        save_data()
        status = "مفعل ✅" if DATA["groups"][gid]["welcome_enabled"] else "معطل ❌"
        await query.edit_message_text(
            f"🎉 قسم الترحيب\nالحالة: {status}",
            reply_markup=welcome_menu(),
        )

    elif data == "set_welcome":
        st["waiting"] = "set_welcome"
        await query.edit_message_text(
            "أرسل رسالة الترحيب الجديدة.\n\n"
            "تقدر تستخدم:\n"
            "{name} اسم العضو\n"
            "{group} اسم القروب\n"
            "{user_id} آيدي العضو",
            reply_markup=back_button("main"),
        )

    elif data == "show_welcome":
        await query.edit_message_text(
            DATA["groups"][gid]["welcome_text"],
            reply_markup=back_button("welcome_menu"),
        )

    elif data == "rules_menu":
        await query.edit_message_text("📜 قسم القوانين", reply_markup=rules_menu())

    elif data == "set_rules":
        st["waiting"] = "set_rules"
        await query.edit_message_text("أرسل القوانين الجديدة الآن.", reply_markup=back_button("main"))

    elif data == "show_rules":
        await query.edit_message_text(
            DATA["groups"][gid]["rules_text"],
            reply_markup=back_button("rules_menu"),
        )

    elif data == "replies_menu":
        await query.edit_message_text("🤖 قسم الردود التلقائية", reply_markup=replies_menu())

    elif data == "add_reply":
        st["waiting"] = "add_reply_key"
        await query.edit_message_text("أرسل الكلمة التي تريد الرد عليها.", reply_markup=back_button("main"))

    elif data == "del_reply":
        st["waiting"] = "del_reply_key"
        await query.edit_message_text("أرسل الكلمة التي تريد حذف ردها.", reply_markup=back_button("main"))

    elif data == "show_replies":
        replies = DATA["groups"][gid]["auto_replies"]
        text = "لا توجد ردود." if not replies else "\n\n".join(
            [f"الكلمة: {k}\nالرد: {v}" for k, v in replies.items()]
        )
        await query.edit_message_text(text, reply_markup=back_button("replies_menu"))

    elif data == "protect_menu":
        await query.edit_message_text("🛡️ قسم الحماية", reply_markup=protect_menu(gid))

    elif data == "toggle_links":
        DATA["groups"][gid]["anti_links"] = not DATA["groups"][gid]["anti_links"]
        save_data()
        await query.edit_message_text("🛡️ قسم الحماية", reply_markup=protect_menu(gid))

    elif data == "toggle_badwords":
        DATA["groups"][gid]["anti_badwords"] = not DATA["groups"][gid]["anti_badwords"]
        save_data()
        await query.edit_message_text("🛡️ قسم الحماية", reply_markup=protect_menu(gid))

    elif data == "add_badword":
        st["waiting"] = "add_badword"
        await query.edit_message_text("أرسل الكلمة الممنوعة الجديدة.", reply_markup=back_button("main"))

    elif data == "del_badword":
        st["waiting"] = "del_badword"
        await query.edit_message_text("أرسل الكلمة الممنوعة التي تريد حذفها.", reply_markup=back_button("main"))

    elif data == "show_badwords":
        words = DATA["groups"][gid]["badwords"]
        text = "لا توجد كلمات ممنوعة." if not words else "\n".join(words)
        await query.edit_message_text(text, reply_markup=back_button("protect_menu"))

    elif data == "warns_menu":
        await query.edit_message_text("⚠️ قسم الإنذارات", reply_markup=warns_menu(gid))

    elif data == "set_mute_after":
        st["waiting"] = "set_mute_after"
        await query.edit_message_text("أرسل رقم الكتم بعد كم إنذار.", reply_markup=back_button("main"))

    elif data == "set_ban_after":
        st["waiting"] = "set_ban_after"
        await query.edit_message_text("أرسل رقم الطرد بعد كم إنذار.", reply_markup=back_button("main"))

    elif data == "show_warns_panel":
        warns = DATA["groups"][gid]["warnings"]
        if not warns:
            text = "لا توجد تحذيرات مسجلة."
        else:
            text = "\n".join([f"{uid}: {count}" for uid, count in warns.items()])
        await query.edit_message_text(text, reply_markup=back_button("warns_menu"))

    elif data == "show_settings":
        await query.edit_message_text(settings_summary(gid), reply_markup=back_button("main"))

    elif data == "show_id_help":
        await query.edit_message_text(
            "الأمر /id يشتغل داخل القروب أو الخاص ويعطيك الآيدي.",
            reply_markup=back_button("main"),
        )

    elif data == "show_group_commands":
        text = (
            "📘 أوامر القروب:\n\n"
            "/bindgroup - ربط القروب\n"
            "/id - معرفة الآيدي\n"
            "/rules - عرض القوانين\n"
            "/welcome - عرض رسالة الترحيب\n"
            "/settings - عرض إعدادات القروب\n"
            "/warns - عرض التحذيرات\n"
            "/clearwarns - تصفير التحذيرات\n"
            "/warn - إنذار يدوي\n"
            "/mute - كتم بالرد\n"
            "/unmute - فك كتم بالرد\n"
            "/ban - طرد بالرد\n"
            "/unban user_id - فك حظر\n"
            "/setnote نص - ملاحظة للقروب\n"
            "/clean - حذف الرسالة بالرد"
        )
        await query.edit_message_text(text, reply_markup=back_button("extras_menu"))

    elif data == "show_bind_help":
        text = (
            "🔗 طريقة ربط القروب:\n\n"
            "1) أضف البوت للقروب\n"
            "2) خله مشرف\n"
            "3) اكتب داخل القروب:\n/bindgroup"
        )
        await query.edit_message_text(text, reply_markup=back_button("extras_menu"))

    elif data == "extras_menu":
        await query.edit_message_text("➕ المميزات الإضافية", reply_markup=extras_menu())


async def handle_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    user = update.effective_user
    if not user or not is_owner(user.id):
        return
    if not update.message or not update.message.text:
        return

    st = owner_state(user.id)
    gid = selected_group_id(user.id)
    waiting = st.get("waiting")
    text = update.message.text.strip()

    if waiting == "set_welcome" and gid:
        DATA["groups"][gid]["welcome_text"] = text
        save_data()
        st["waiting"] = None
        await update.message.reply_text("✅ تم تحديث رسالة الترحيب", reply_markup=main_menu(user.id))

    elif waiting == "set_rules" and gid:
        DATA["groups"][gid]["rules_text"] = text
        save_data()
        st["waiting"] = None
        await update.message.reply_text("✅ تم تحديث القوانين", reply_markup=main_menu(user.id))

    elif waiting == "add_reply_key" and gid:
        st["reply_key"] = text
        st["waiting"] = "add_reply_value"
        await update.message.reply_text("أرسل الرد الآن.")

    elif waiting == "add_reply_value" and gid:
        key = st.get("reply_key")
        if key:
            DATA["groups"][gid]["auto_replies"][key] = text
            save_data()
        st["reply_key"] = None
        st["waiting"] = None
        await update.message.reply_text("✅ تمت إضافة الرد", reply_markup=main_menu(user.id))

    elif waiting == "del_reply_key" and gid:
        if text in DATA["groups"][gid]["auto_replies"]:
            del DATA["groups"][gid]["auto_replies"][text]
            save_data()
            msg = "✅ تم حذف الرد"
        else:
            msg = "❌ هذه الكلمة غير موجودة"
        st["waiting"] = None
        await update.message.reply_text(msg, reply_markup=main_menu(user.id))

    elif waiting == "add_badword" and gid:
        if text not in DATA["groups"][gid]["badwords"]:
            DATA["groups"][gid]["badwords"].append(text)
            save_data()
        st["waiting"] = None
        await update.message.reply_text("✅ تمت إضافة الكلمة الممنوعة", reply_markup=main_menu(user.id))

    elif waiting == "del_badword" and gid:
        if text in DATA["groups"][gid]["badwords"]:
            DATA["groups"][gid]["badwords"].remove(text)
            save_data()
            msg = "✅ تم حذف الكلمة"
        else:
            msg = "❌ الكلمة غير موجودة"
        st["waiting"] = None
        await update.message.reply_text(msg, reply_markup=main_menu(user.id))

    elif waiting == "set_mute_after" and gid:
        if text.isdigit():
            DATA["groups"][gid]["mute_after"] = int(text)
            save_data()
            msg = "✅ تم تحديث عدد إنذارات الكتم"
        else:
            msg = "❌ أرسل رقم فقط"
        st["waiting"] = None
        await update.message.reply_text(msg, reply_markup=main_menu(user.id))

    elif waiting == "set_ban_after" and gid:
        if text.isdigit():
            DATA["groups"][gid]["ban_after"] = int(text)
            save_data()
            msg = "✅ تم تحديث عدد إنذارات الطرد"
        else:
            msg = "❌ أرسل رقم فقط"
        st["waiting"] = None
        await update.message.reply_text(msg, reply_markup=main_menu(user.id))


async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return

    cfg = get_group(update.effective_chat.id)
    if not cfg or not cfg["welcome_enabled"]:
        return

    group_name = update.effective_chat.title or "القروب"
    for member in update.message.new_chat_members:
        name = member.first_name or "يا هلا"
        text = welcome_text_for_user(cfg, name, group_name, member.id)
        await update.message.reply_text(text)


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

    if await is_target_admin(context, update.effective_chat.id, user.id):
        pass
    else:
        if cfg["anti_links"] and contains_link(text):
            try:
                await update.message.delete()
            except Exception:
                pass
            await warn_user(update, context, "إرسال رابط")
            return

        if cfg["anti_badwords"]:
            lowered = text.lower()
            for badword in cfg["badwords"]:
                if badword.lower() in lowered:
                    try:
                        await update.message.delete()
                    except Exception:
                        pass
                    await warn_user(update, context, "كلمة ممنوعة")
                    return

    for trigger, reply in cfg["auto_replies"].items():
        if trigger and trigger.lower() in text.lower():
            await update.message.reply_text(reply)
            break


def main():
    if not TOKEN:
        raise ValueError("TOKEN غير موجود. حطه في Variables باسم TOKEN")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bindgroup", cmd_bindgroup))
    app.add_handler(CommandHandler("id", cmd_id))
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