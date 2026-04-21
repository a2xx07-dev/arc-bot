
import json
import os
import re
from copy import deepcopy
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
    InputFile,
)
from telegram.constants import ChatType
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    ChatMemberHandler,
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
        "🔥 حياك {name} في {group} 🔥\n\n"
        "🎮 Arc Zone - ارك زون\n"
        "🚀 هنا المكان اللي يفرق بين العادي والمحترف\n\n"
        "📌 وش نقدم لك:\n"
        "• السكوربين\n"
        "• قطع Lie Ying Por\n"
        "• ثبات الأيم\n"
        "• مخططات القطع\n"
        "• تشغيل وتعريف القطع\n\n"
        "📜 قبل تبدأ اقرأ القوانين من الزر تحت\n\n"
        "👑 شد حيلك وخل بصمتك تبان"
    ),
    "welcome_photo": "",
    "media_below_text": True,
    "welcome_buttons": [],
    "rules_text": (
        "📜 قوانين القروب:\n"
        "1) احترام الجميع\n"
        "2) ممنوع السب والشتم\n"
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
    "anti_spam": False,
    "anti_flood": False,
    "anti_caps": False,
    "captcha_enabled": False,
    "admin_report": False,
    "anti_nsfw": False,
    "night_mode": False,
    "tag_alert": False,
    "approval_mode": False,
    "delete_system_messages": False,
    "topics_enabled": False,
    "stealth_users": False,
    "discussion_group": "",
    "custom_commands_enabled": False,
    "animated_stickers": True,
    "long_messages": False,
    "channels_manager": False,
    "log_channel": "",
    "permissions_locked": False,
    "lang": "ar",
    "group_link": "",
    "auto_pin_note": False,
    "warnings": {},
    "mute_after": 3,
    "ban_after": 5,
    "vip_mode": True,
    "commands_intro_text": (
        "أوامر المجموعة\n\n"
        "📌 أوامر سكوربين\nكل ما يخص سكوربين العادي والبرو\n\n"
        "📌 أوامر اللمس\nكل ما يخص قطع اللمس ودمج الأزرار\n\n"
        "📌 أوامر النقل\nكل ما يخص النقل والشاشات الخارجية والوصلات\n\n"
        "📌 أوامر الخدمات\nأوامر الخدمات التي يوفرها متجرنا\n\n"
        "✍️ اكتب اسم الأمر واضغط Enter ويطلع لك المطلوب مباشرة"
    ),
    "command_categories": {
        "سكوربين": {"description": "كل ما يخص سكوربين العادي والبرو", "commands": {}},
        "اللمس": {"description": "كل ما يخص قطع اللمس مثل لي يونق القديمة وقطعة دمج الأزرار", "commands": {}},
        "النقل": {"description": "كل ما يخص النقل والشاشات الخارجية والوصلات", "commands": {}},
        "الخدمات": {"description": "أوامر الخدمات التي يوفرها متجرنا", "commands": {}},
    },
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
            merged = deepcopy(DEFAULT_GROUP)
            if isinstance(cfg, dict):
                merged.update(cfg)
            if not isinstance(merged.get("auto_replies"), dict):
                merged["auto_replies"] = {}
            if not isinstance(merged.get("warnings"), dict):
                merged["warnings"] = {}
            if not isinstance(merged.get("welcome_buttons"), list):
                merged["welcome_buttons"] = []
            if "media_below_text" not in merged:
                merged["media_below_text"] = True
            if not isinstance(merged.get("command_categories"), dict):
                merged["command_categories"] = deepcopy(DEFAULT_GROUP["command_categories"])
            else:
                for cat_name, cat_cfg in deepcopy(DEFAULT_GROUP["command_categories"]).items():
                    current = merged["command_categories"].get(cat_name)
                    if not isinstance(current, dict):
                        merged["command_categories"][cat_name] = deepcopy(cat_cfg)
                        continue
                    if not isinstance(current.get("description"), str):
                        current["description"] = cat_cfg["description"]
                    if not isinstance(current.get("commands"), dict):
                        current["commands"] = {}
                for cat_name, cat_cfg in list(merged["command_categories"].items()):
                    if not isinstance(cat_cfg, dict):
                        merged["command_categories"][cat_name] = {"description": "", "commands": {}}
                        continue
                    if not isinstance(cat_cfg.get("description"), str):
                        cat_cfg["description"] = ""
                    if not isinstance(cat_cfg.get("commands"), dict):
                        cat_cfg["commands"] = {}
            if not isinstance(merged.get("commands_intro_text"), str):
                merged["commands_intro_text"] = DEFAULT_GROUP["commands_intro_text"]
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
        DATA["groups"][gid] = deepcopy(DEFAULT_GROUP)
    if title:
        DATA["groups"][gid]["title"] = title
    return DATA["groups"][gid]


def get_group(chat_id: int) -> dict[str, Any] | None:
    return DATA["groups"].get(str(chat_id))


def get_or_create_group(chat_id: int, title: str = "") -> dict[str, Any]:
    cfg = get_group(chat_id)
    if cfg is None:
        cfg = ensure_group(chat_id, title)
        save_data()
    elif title and cfg.get("title") != title:
        cfg["title"] = title
        save_data()
    return cfg


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


def is_probable_url(text: str) -> bool:
    value = text.strip()
    return bool(re.match(r"^(https?://|www\.|t\.me/)", value, re.IGNORECASE))


def split_command_content(content: str) -> tuple[str, str | None]:
    value = str(content).strip()
    match = LINK_RE.search(value)
    if not match:
        return value, None
    url = match.group(0).strip()
    body = (value[:match.start()] + value[match.end():]).strip()
    if url.lower().startswith("www."):
        url = "https://" + url
    return body, url


def on_off_text(value: bool) -> str:
    return "✅" if value else "❌"


def bool_label(name: str, value: bool) -> str:
    return f"{name} {on_off_text(value)}"


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
        f"🤬 الكلمات الممنوعة: {'مفعل ✅' if cfg['anti_badwords'] else 'معطل ❌'}\n"
        f"📨 مانع الرسائل المزعجة: {'مفعل ✅' if cfg['anti_spam'] else 'معطل ❌'}\n"
        f"🕒 مانع التكرار: {'مفعل ✅' if cfg['anti_flood'] else 'معطل ❌'}\n"
        f"🕉 الحروف البذيئة: {'مفعل ✅' if cfg['anti_caps'] else 'معطل ❌'}\n"
        f"🧠 Captcha: {'مفعل ✅' if cfg['captcha_enabled'] else 'معطل ❌'}\n"
        f"🚨 تقرير @admin: {'مفعل ✅' if cfg['admin_report'] else 'معطل ❌'}\n"
        f"🔞 الإباحية: {'مفعل ✅' if cfg['anti_nsfw'] else 'معطل ❌'}\n"
        f"🌙 الوضع الليلي: {'مفعل ✅' if cfg['night_mode'] else 'معطل ❌'}\n"
        f"🔔 تنبيه Tag: {'مفعل ✅' if cfg['tag_alert'] else 'معطل ❌'}\n"
        f"📮 وضع الموافقة: {'مفعل ✅' if cfg['approval_mode'] else 'معطل ❌'}\n"
        f"🗑 حذف الرسائل: {'مفعل ✅' if cfg['delete_system_messages'] else 'معطل ❌'}\n"
        f"📂 الموضوع: {'مفعل ✅' if cfg['topics_enabled'] else 'معطل ❌'}\n"
        f"👻 المستخدمون المتخفون: {'مفعل ✅' if cfg['stealth_users'] else 'معطل ❌'}\n"
        f"🎭 الملصقات السحرية: {'مسموح ✅' if cfg['animated_stickers'] else 'مقفلة ❌'}\n"
        f"📏 الرسائل الطويلة: {'مفعل ✅' if cfg['long_messages'] else 'معطل ❌'}\n"
        f"📢 إدارة القنوات: {'مفعل ✅' if cfg['channels_manager'] else 'معطل ❌'}\n"
        f"🔍 قناة السجل: {cfg['log_channel'] or 'غير محددة'}\n"
        f"✒️ أذونات المجموعة: {'مقفلة ✅' if cfg['permissions_locked'] else 'مفتوحة ❌'}\n"
        f"🔗 رابط المجموعة: {cfg['group_link'] or 'غير محدد'}\n"
        f"⚠️ عدد التحذيرات: {len(cfg['warnings'])}\n"
        f"🔇 الكتم بعد: {cfg['mute_after']}\n"
        f"⛔ الطرد بعد: {cfg['ban_after']}\n"
        f"📌 التثبيت التلقائي: {'مفعل ✅' if cfg['auto_pin_note'] else 'معطل ❌'}\n"
        f"🌐 اللغة: {cfg['lang']}"
    )


def format_welcome(cfg: dict[str, Any], name: str, group_title: str, user_id: int) -> str:
    return (
        cfg["welcome_text"]
        .replace("{name}", name)
        .replace("{group}", group_title)
        .replace("{user_id}", str(user_id))
    )


def build_welcome_keyboard(cfg: dict[str, Any]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton("📜 عرض القوانين", callback_data="show_rules_btn")]
    ]
    for item in cfg.get("welcome_buttons", []):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        url = str(item.get("url", "")).strip()
        if text and url:
            rows.append([InlineKeyboardButton(text, url=url)])
    return InlineKeyboardMarkup(rows)


def back(target: str = "settings_menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◀️ العودة", callback_data=target),
            InlineKeyboardButton("✅ إغلاق", callback_data="main"),
            InlineKeyboardButton("🇸🇦 Lang", callback_data="toggle_lang"),
        ]
    ])


def groups_menu() -> InlineKeyboardMarkup:
    rows = []
    for gid, cfg in DATA["groups"].items():
        title = cfg.get("title") or gid
        rows.append([InlineKeyboardButton(f"📌 {title}", callback_data=f"select_group:{gid}")])
    rows.append([InlineKeyboardButton("⬅️ العودة", callback_data="main")])
    return InlineKeyboardMarkup(rows)


def main_menu(user_id: int) -> InlineKeyboardMarkup:
    gid = selected_group_id(user_id)
    title = DATA["groups"].get(gid, {}).get("title", "غير محدد") if gid else "غير محدد"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings_menu")],
        [InlineKeyboardButton(f"📌 المجموعة: {title}", callback_data="groups")],
        [InlineKeyboardButton("👑 لوحة VIP", callback_data="vip_hub")],
    ])


def settings_menu(user_id: int) -> InlineKeyboardMarkup:
    gid = selected_group_id(user_id)
    cfg = DATA["groups"][gid]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 القوانين", callback_data="rules_menu"),
         InlineKeyboardButton(bool_label("📨 مانع الرسائل المزعجة", cfg["anti_spam"]), callback_data="toggle_anti_spam")],
        [InlineKeyboardButton("💬 الترحيب", callback_data="welcome_menu"),
         InlineKeyboardButton(bool_label("🕒 مانع الرسائل المكررة", cfg["anti_flood"]), callback_data="toggle_anti_flood")],
        [InlineKeyboardButton("👋 وداعاً", callback_data="farewell_menu"),
         InlineKeyboardButton(bool_label("🕉 الحروف البذيئة", cfg["anti_caps"]), callback_data="toggle_anti_caps")],
        [InlineKeyboardButton(bool_label("🧠 التحقق Captcha", cfg["captcha_enabled"]), callback_data="toggle_captcha"),
         InlineKeyboardButton("🎤 القيود", callback_data="restrictions_menu")],
        [InlineKeyboardButton(bool_label("🆘 تقرير @admin", cfg["admin_report"]), callback_data="toggle_admin_report"),
         InlineKeyboardButton("🔐 حظر", callback_data="ban_menu")],
        [InlineKeyboardButton("📸 الوسائط", callback_data="media_menu"),
         InlineKeyboardButton(bool_label("🔞 إباحية", cfg["anti_nsfw"]), callback_data="toggle_anti_nsfw")],
        [InlineKeyboardButton("❗ الإنذارات", callback_data="warns_menu"),
         InlineKeyboardButton(bool_label("🌙 الوضع الليلي", cfg["night_mode"]), callback_data="toggle_night_mode")],
        [InlineKeyboardButton(bool_label("🔔 Tag تنبيه", cfg["tag_alert"]), callback_data="toggle_tag_alert"),
         InlineKeyboardButton("🔗 رابط المجموعة", callback_data="set_group_link")],
        [InlineKeyboardButton(bool_label("📮 وضع الموافقة", cfg["approval_mode"]), callback_data="toggle_approval_mode")],
        [InlineKeyboardButton(bool_label("🗑 حذف الرسائل", cfg["delete_system_messages"]), callback_data="toggle_delete_system_messages")],
        [InlineKeyboardButton("▶️ أخرى", callback_data="more_menu"),
         InlineKeyboardButton("✅ إغلاق", callback_data="main"),
         InlineKeyboardButton("🇸🇦 Lang", callback_data="toggle_lang")],
    ])


def more_menu(user_id: int) -> InlineKeyboardMarkup:
    gid = selected_group_id(user_id)
    cfg = DATA["groups"][gid]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(bool_label("🗂 الموضوع", cfg["topics_enabled"]), callback_data="toggle_topics_enabled")],
        [InlineKeyboardButton("🔤 الكلمات المحظورة", callback_data="badwords_menu")],
        [InlineKeyboardButton(bool_label("🕒 تكرار الرسائل", cfg["anti_flood"]), callback_data="toggle_anti_flood")],
        [InlineKeyboardButton("👥 إدارة الأعضاء", callback_data="members_menu")],
        [InlineKeyboardButton(bool_label("🧙 المستخدمون المتخفون", cfg["stealth_users"]), callback_data="toggle_stealth_users")],
        [InlineKeyboardButton("📣 مجموعة المناقشة", callback_data="set_discussion_group")],
        [InlineKeyboardButton(bool_label("📱 الأوامر الشخصية", cfg["custom_commands_enabled"]), callback_data="toggle_custom_commands_enabled")],
        [InlineKeyboardButton(bool_label("🎭 ملصقات سحرية وصور متحركة", cfg["animated_stickers"]), callback_data="toggle_animated_stickers")],
        [InlineKeyboardButton(bool_label("📏 الرسائل الطويلة", cfg["long_messages"]), callback_data="toggle_long_messages")],
        [InlineKeyboardButton(bool_label("📢 إدارة القنوات", cfg["channels_manager"]), callback_data="toggle_channels_manager")],
        [InlineKeyboardButton("🔍 قناة سجل المجموعة", callback_data="set_log_channel"),
         InlineKeyboardButton(bool_label("✒️ أذونات", cfg["permissions_locked"]), callback_data="toggle_permissions_locked")],
        [InlineKeyboardButton("◀️ العودة", callback_data="settings_menu"),
         InlineKeyboardButton("✅ إغلاق", callback_data="main"),
         InlineKeyboardButton("🇸🇦 Lang", callback_data="toggle_lang")],
    ])


def welcome_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("تشغيل/إيقاف الترحيب", callback_data="toggle_welcome")],
        [InlineKeyboardButton("تغيير رسالة الترحيب", callback_data="set_welcome")],
        [InlineKeyboardButton("عرض رسالة الترحيب", callback_data="show_welcome")],
        [InlineKeyboardButton("تعيين صورة الترحيب", callback_data="set_welcome_photo")],
        [InlineKeyboardButton("🖼️ تبديل مكان الوسائط", callback_data="toggle_media_position")],
        [InlineKeyboardButton("🔗 تعيين زر رابط", callback_data="set_buttons")],
        [InlineKeyboardButton("🗑️ حذف أزرار الروابط", callback_data="clear_welcome_buttons")],
        [InlineKeyboardButton("👁️ معاينة الترحيب", callback_data="preview_welcome")],
        [InlineKeyboardButton("حذف صورة الترحيب", callback_data="clear_welcome_photo")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="settings_menu")],
    ])


def rules_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("تغيير القوانين", callback_data="set_rules")],
        [InlineKeyboardButton("عرض القوانين", callback_data="show_rules")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="settings_menu")],
    ])


def replies_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("إضافة رد", callback_data="add_reply")],
        [InlineKeyboardButton("حذف رد", callback_data="delete_reply")],
        [InlineKeyboardButton("عرض الردود", callback_data="show_replies")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="vip_hub")],
    ])


def protect_menu(gid: str) -> InlineKeyboardMarkup:
    cfg = DATA["groups"][gid]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(bool_label("🚫 الروابط", cfg["anti_links"]), callback_data="toggle_links")],
        [InlineKeyboardButton(bool_label("🤬 الكلمات", cfg["anti_badwords"]), callback_data="toggle_badwords")],
        [InlineKeyboardButton("➕ إضافة كلمة ممنوعة", callback_data="add_badword")],
        [InlineKeyboardButton("➖ حذف كلمة ممنوعة", callback_data="delete_badword")],
        [InlineKeyboardButton("📄 عرض الكلمات", callback_data="show_badwords")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="vip_hub")],
    ])


def warns_menu(gid: str) -> InlineKeyboardMarkup:
    cfg = DATA["groups"][gid]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔇 الكتم بعد {cfg['mute_after']}", callback_data="set_mute_after")],
        [InlineKeyboardButton(f"⛔ الطرد بعد {cfg['ban_after']}", callback_data="set_ban_after")],
        [InlineKeyboardButton("📄 عرض التحذيرات", callback_data="show_warns_panel")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="settings_menu")],
    ])


def pin_menu(gid: str) -> InlineKeyboardMarkup:
    cfg = DATA["groups"][gid]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 تغيير النص المثبت", callback_data="set_note")],
        [InlineKeyboardButton("📌 تثبيت النص الآن", callback_data="pin_note_now")],
        [InlineKeyboardButton(bool_label("📍 التثبيت التلقائي", cfg["auto_pin_note"]), callback_data="toggle_auto_pin")],
        [InlineKeyboardButton("👁️ عرض النص", callback_data="show_note")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="vip_hub")],
    ])


def media_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🖼️ تعيين صورة ترحيب", callback_data="set_welcome_photo")],
        [InlineKeyboardButton("🗑️ حذف صورة الترحيب", callback_data="clear_welcome_photo")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="settings_menu")],
    ])


def admins_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📘 عرض أوامر المشرفين", callback_data="show_admin_commands")],
        [InlineKeyboardButton("📘 عرض أوامر القروب", callback_data="show_group_commands")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="vip_hub")],
    ])


def backup_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💾 إنشاء نسخة احتياطية", callback_data="make_backup")],
        [InlineKeyboardButton("📤 إرسال النسخة الاحتياطية", callback_data="send_backup_file")],
        [InlineKeyboardButton("♻️ استرجاع النسخة الاحتياطية", callback_data="restore_backup")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="vip_hub")],
    ])


def vip_hub() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 الردود", callback_data="replies_menu"),
         InlineKeyboardButton("🛡️ الحماية", callback_data="protect_menu")],
        [InlineKeyboardButton("🛠️ أوامر المشرفين", callback_data="admins_menu"),
         InlineKeyboardButton("💾 النسخ الاحتياطي", callback_data="backup_menu")],
        [InlineKeyboardButton("🧾 أوامر المجموعة", callback_data="commands_menu"),
         InlineKeyboardButton("📌 التثبيت", callback_data="pin_menu")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="main")],
    ])




def commands_menu(gid: str) -> InlineKeyboardMarkup:
    cfg = DATA["groups"][gid]
    rows = [
        [InlineKeyboardButton("📖 رسالة قسم الأوامر", callback_data="show_commands_intro")],
        [InlineKeyboardButton("📝 تعديل رسالة القسم", callback_data="set_commands_intro")],
        [InlineKeyboardButton("📋 عرض الأقسام والأوامر", callback_data="show_commands_catalog")],
        [InlineKeyboardButton("🗂️ إضافة قسم", callback_data="add_category")],
        [InlineKeyboardButton("📝 تغيير اسم قسم", callback_data="rename_category")],
        [InlineKeyboardButton("🗑️ حذف قسم", callback_data="delete_category")],
        [InlineKeyboardButton("➕ إضافة أمر", callback_data="add_exact_command")],
        [InlineKeyboardButton("🗑️ حذف أمر", callback_data="delete_exact_command")],
    ]
    for cat_name in cfg.get("command_categories", {}).keys():
        rows.append([InlineKeyboardButton(f"📌 أوامر {cat_name}", callback_data=f"commands_category:{cat_name}")])
    rows.append([InlineKeyboardButton("⬅️ العودة", callback_data="vip_hub")])
    return InlineKeyboardMarkup(rows)


def command_category_menu(gid: str, cat_name: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("📝 تعديل اسم القسم", callback_data=f"rename_category_in:{cat_name}")],
        [InlineKeyboardButton("📝 تعديل وصف القسم", callback_data=f"set_category_desc:{cat_name}")],
        [InlineKeyboardButton("📋 عرض أوامر القسم", callback_data=f"show_category_commands:{cat_name}")],
        [InlineKeyboardButton("➕ إضافة أمر لهذا القسم", callback_data=f"add_command_in:{cat_name}")],
        [InlineKeyboardButton("🗑️ حذف أمر من هذا القسم", callback_data=f"delete_command_in:{cat_name}")],
        [InlineKeyboardButton("🗑️ حذف هذا القسم", callback_data=f"delete_category_in:{cat_name}")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="commands_menu")],
    ]
    return InlineKeyboardMarkup(rows)


def build_public_categories_keyboard(cfg: dict[str, Any]) -> InlineKeyboardMarkup | None:
    rows: list[list[InlineKeyboardButton]] = []
    current_row: list[InlineKeyboardButton] = []
    for cat_name, cat_cfg in cfg.get("command_categories", {}).items():
        cmds = cat_cfg.get("commands", {})
        if not cmds:
            continue
        current_row.append(InlineKeyboardButton(f"📂 {cat_name}", callback_data=f"public_cat:{cat_name}"))
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    if not rows:
        return None
    return InlineKeyboardMarkup(rows)


def build_public_commands_keyboard(cfg: dict[str, Any], cat_name: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    current_row: list[InlineKeyboardButton] = []
    cat_cfg = cfg.get("command_categories", {}).get(cat_name, {})
    for cmd_name in cat_cfg.get("commands", {}).keys():
        current_row.append(InlineKeyboardButton(str(cmd_name), callback_data=f"public_cmd:{cat_name}:{cmd_name}"))
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    rows.append([InlineKeyboardButton("⬅️ رجوع للأقسام", callback_data="public_back_categories")])
    return InlineKeyboardMarkup(rows)


def build_public_commands_intro_text(cfg: dict[str, Any]) -> str:
    return (
        f"{cfg.get('commands_intro_text', 'أوامر المجموعة')}\n\n"
        "👇 اضغط على القسم المناسب لك"
    )


def build_commands_overview_text(cfg: dict[str, Any]) -> str:
    lines = [cfg.get("commands_intro_text", "أوامر المجموعة"), ""]
    for cat_name, cat_cfg in cfg.get("command_categories", {}).items():
        desc = str(cat_cfg.get("description", "")).strip()
        lines.append(f"📌 أوامر {cat_name}")
        if desc:
            lines.append(desc)
        cmds = cat_cfg.get("commands", {})
        if cmds:
            for cmd_name in cmds.keys():
                lines.append(f"• {cmd_name}")
        else:
            lines.append("لا يوجد أوامر حالياً")
        lines.append("")
    return "\n".join(lines).strip()


def build_single_category_text(cfg: dict[str, Any], cat_name: str) -> str:
    cat_cfg = cfg.get("command_categories", {}).get(cat_name, {})
    desc = str(cat_cfg.get("description", "")).strip()
    cmds = cat_cfg.get("commands", {})
    lines = [f"📌 أوامر {cat_name}"]
    if desc:
        lines.append(desc)
    lines.append("")
    if cmds:
        for cmd_name in cmds.keys():
            lines.append(f"• {cmd_name}")
    else:
        lines.append("لا يوجد أوامر حالياً")
    return "\n".join(lines).strip()




def build_public_commands_categories_keyboard(cfg: dict[str, Any]) -> InlineKeyboardMarkup:
    rows = []
    for cat_name, cat_cfg in cfg.get("command_categories", {}).items():
        if cat_cfg.get("commands"):
            rows.append([InlineKeyboardButton(f"📂 {cat_name}", callback_data=f"public_cat:{cat_name}")])
    if rows:
        rows.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="public_commands_home")])
    return InlineKeyboardMarkup(rows) if rows else InlineKeyboardMarkup([])


def build_public_commands_items_keyboard(cfg: dict[str, Any], cat_name: str) -> InlineKeyboardMarkup:
    rows = []
    cat_cfg = cfg.get("command_categories", {}).get(cat_name, {})
    for cmd_name in cat_cfg.get("commands", {}).keys():
        rows.append([InlineKeyboardButton(f"🔹 {cmd_name}", callback_data=f"public_cmd:{cat_name}:{cmd_name}")])
    rows.append([
        InlineKeyboardButton("⬅️ رجوع", callback_data="public_commands_back"),
        InlineKeyboardButton("🏠 الرئيسية", callback_data="public_commands_home"),
    ])
    return InlineKeyboardMarkup(rows)

def find_exact_command(cfg: dict[str, Any], text: str) -> str | None:
    needle = text.strip().casefold()
    for cat_cfg in cfg.get("command_categories", {}).values():
        for cmd_name, cmd_reply in cat_cfg.get("commands", {}).items():
            if cmd_name.strip().casefold() == needle:
                return cmd_reply
    return None



ARABIC_TO_ENGLISH_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def normalize_digits(value: str) -> str:
    return value.translate(ARABIC_TO_ENGLISH_DIGITS)


def build_commands_numbers_text(cfg: dict[str, Any]) -> str:
    lines = [cfg.get("commands_intro_text", "أوامر المجموعة"), "", "📋 قائمة الأوامر بالأرقام:"]
    idx = 1
    for cat_name, cat_cfg in cfg.get("command_categories", {}).items():
        desc = str(cat_cfg.get("description", "")).strip()
        cmds = cat_cfg.get("commands", {})
        if not cmds:
            continue
        lines.append("")
        lines.append(f"📌 أوامر {cat_name}")
        if desc:
            lines.append(desc)
        for cmd_name in cmds.keys():
            lines.append(f"{idx}- {cmd_name}")
            idx += 1
    if idx == 1:
        lines.append("لا يوجد أوامر حالياً")
    else:
        lines.append("")
        lines.append("✍️ اكتب رقم الأمر فقط وسيظهر لك الرد مباشرة")
    return "\n".join(lines).strip()


def get_command_reply_by_number(cfg: dict[str, Any], text: str) -> str | None:
    normalized = normalize_digits(text.strip())
    if not normalized.isdigit():
        return None
    wanted = int(normalized)
    idx = 1
    for cat_cfg in cfg.get("command_categories", {}).values():
        for _cmd_name, cmd_reply in cat_cfg.get("commands", {}).items():
            if idx == wanted:
                return cmd_reply
            idx += 1
    return None


async def handle_admin_text_command(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    if not update.message or not update.effective_chat or not update.effective_user:
        return False
    if not await is_target_admin(context, update.effective_chat.id, update.effective_user.id):
        return False

    normalized = normalize_digits(text.strip())
    compact = normalized.replace("_", " ").strip()
    base = compact.split(maxsplit=1)[0].strip().lower() if compact else ""
    reply_msg = update.message.reply_to_message

    if compact in {"ايدي", "آيدي"}:
        await cmd_id(update, context)
        return True

    if base in {"تحذير", "انذار", "إنذار"}:
        if not reply_msg or not reply_msg.from_user:
            await update.message.reply_text("رد على رسالة العضو ثم اكتب: تحذير")
            return True
        target = reply_msg.from_user
        if await is_target_admin(context, update.effective_chat.id, target.id):
            await update.message.reply_text("لا يمكن إنذار مشرف.")
            return True
        cfg = ensure_group(update.effective_chat.id, update.effective_chat.title or "")
        uid = str(target.id)
        count = int(cfg["warnings"].get(uid, 0)) + 1
        cfg["warnings"][uid] = count
        save_data()
        await update.message.reply_text(f"⚠️ تم إنذار {target.first_name}. عدد التحذيرات: {count}")
        return True

    if compact in {"مسح التحذيرات", "تصفير التحذيرات"}:
        if not reply_msg or not reply_msg.from_user:
            await update.message.reply_text("رد على رسالة العضو ثم اكتب: مسح التحذيرات")
            return True
        target = reply_msg.from_user
        cfg = get_or_create_group(update.effective_chat.id, update.effective_chat.title or "")
        cfg["warnings"][str(target.id)] = 0
        save_data()
        await update.message.reply_text(f"✅ تم تصفير تحذيرات {target.first_name}")
        return True

    if base in {"كتم", "ميوت"}:
        if not reply_msg or not reply_msg.from_user:
            await update.message.reply_text("رد على رسالة العضو ثم اكتب: كتم")
            return True
        target = reply_msg.from_user
        if await is_target_admin(context, update.effective_chat.id, target.id):
            await update.message.reply_text("لا يمكن كتم مشرف.")
            return True
        try:
            until = datetime.now(timezone.utc) + timedelta(minutes=30)
            await context.bot.restrict_chat_member(
                update.effective_chat.id,
                target.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until,
            )
            await update.message.reply_text(f"🔇 تم كتم {target.first_name} 30 دقيقة.")
        except Exception:
            await update.message.reply_text("تعذر الكتم.")
        return True

    if compact in {"فك الكتم", "الغاء الكتم", "إلغاء الكتم"}:
        if not reply_msg or not reply_msg.from_user:
            await update.message.reply_text("رد على رسالة العضو ثم اكتب: فك الكتم")
            return True
        target = reply_msg.from_user
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
        return True

    if base in {"طرد", "حظر", "تبنيد", "بان"}:
        if not reply_msg or not reply_msg.from_user:
            await update.message.reply_text("رد على رسالة العضو ثم اكتب: حظر")
            return True
        target = reply_msg.from_user
        if await is_target_admin(context, update.effective_chat.id, target.id):
            await update.message.reply_text("لا يمكن حظر مشرف.")
            return True
        try:
            await context.bot.ban_chat_member(update.effective_chat.id, target.id)
            await update.message.reply_text(f"⛔ تم حظر {target.first_name}.")
        except Exception:
            await update.message.reply_text("تعذر الحظر.")
        return True

    if compact.startswith("فك الحظر") or compact.startswith("الغاء الحظر") or compact.startswith("إلغاء الحظر"):
        parts = compact.split(maxsplit=2)
        if len(parts) < 3 or not parts[2].strip().isdigit():
            await update.message.reply_text("اكتب هكذا: فك الحظر 123456789")
            return True
        try:
            user_id = int(parts[2].strip())
            await context.bot.unban_chat_member(update.effective_chat.id, user_id, only_if_banned=True)
            await update.message.reply_text("✅ تم فك الحظر.")
        except Exception:
            await update.message.reply_text("تعذر فك الحظر.")
        return True

    return False

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

    await update.message.reply_text(
        "👑 أهلاً بك في لوحة تحكم Arc Zone VIP\n\nاختر القسم اللي تبيه:",
        reply_markup=main_menu(user.id),
    )


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
    cfg = get_or_create_group(update.effective_chat.id, update.effective_chat.title or "")

    await update.message.reply_text(cfg["rules_text"])

    if cfg["welcome_photo"]:
        try:
            await update.message.reply_photo(cfg["welcome_photo"])
        except Exception:
            pass


async def cmd_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = get_or_create_group(update.effective_chat.id, update.effective_chat.title or "")

    text = format_welcome(
        cfg,
        update.effective_user.first_name,
        update.effective_chat.title or "القروب",
        update.effective_user.id,
    )
    keyboard = build_welcome_keyboard(cfg)

    if cfg["welcome_photo"]:
        try:
            if len(text) > 1024:
                text = text[:1000] + "..."
            if cfg.get("media_below_text", True):
                await update.message.reply_text(text, reply_markup=keyboard)
                await update.message.reply_photo(photo=cfg["welcome_photo"])
            else:
                await update.message.reply_photo(
                    photo=cfg["welcome_photo"],
                    caption=text,
                    reply_markup=keyboard,
                )
            return
        except Exception as e:
            print(f"/welcome photo error: {e}")

    await update.message.reply_text(text, reply_markup=keyboard)


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("هذا الأمر للمشرفين فقط.")
        return
    cfg = get_or_create_group(update.effective_chat.id, update.effective_chat.title or "")
    await update.message.reply_text(settings_summary(str(update.effective_chat.id)))


async def cmd_warns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = get_or_create_group(update.effective_chat.id, update.effective_chat.title or "")
    target = update.message.reply_to_message.from_user if update.message.reply_to_message and update.message.reply_to_message.from_user else update.effective_user
    count = int(cfg["warnings"].get(str(target.id), 0))
    await update.message.reply_text(f"⚠️ عدد تحذيرات {target.first_name}: {count}")


async def cmd_clearwarns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("هذا الأمر للمشرفين فقط.")
        return
    cfg = get_or_create_group(update.effective_chat.id, update.effective_chat.title or "")
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


async def send_backup_document(target_message, context: ContextTypes.DEFAULT_TYPE):
    make_backup()
    with open(BACKUP_FILE, "rb") as f:
        await target_message.reply_document(
            document=InputFile(f, filename="arc_zone_backup.json"),
            caption="💾 نسخة احتياطية جاهزة"
        )


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user = query.from_user
    data = query.data or ""

    if data.startswith("public_"):
        chat = query.message.chat if query.message else None
        if not chat or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return
        cfg = get_or_create_group(chat.id, chat.title or "")

        if data == "public_back_categories":
            keyboard = build_public_categories_keyboard(cfg)
            if keyboard is None:
                await query.edit_message_text("لا يوجد أوامر متاحة حالياً.")
                return
            await query.edit_message_text(build_public_commands_intro_text(cfg), reply_markup=keyboard)
            return

        if data.startswith("public_cat:"):
            cat_name = data.split(":", 1)[1]
            if cat_name not in cfg.get("command_categories", {}):
                await query.answer("هذا القسم غير موجود", show_alert=True)
                return
            text_msg = build_single_category_text(cfg, cat_name)
            await query.edit_message_text(text_msg + "\n\n👇 اختر الأمر المناسب لك", reply_markup=build_public_commands_keyboard(cfg, cat_name))
            return

        if data == "public_close":
            try:
                await query.message.delete()
            except Exception:
                try:
                    await query.edit_message_reply_markup(reply_markup=None)
                except Exception:
                    pass
            return

        if data.startswith("public_cmd:"):
            parts = data.split(":", 2)
            if len(parts) < 3:
                return
            cat_name, cmd_name = parts[1], parts[2]
            cmd_reply = cfg.get("command_categories", {}).get(cat_name, {}).get("commands", {}).get(cmd_name)
            if cmd_reply is None:
                await query.answer("هذا الأمر غير موجود", show_alert=True)
                return

            body, url = split_command_content(str(cmd_reply))
            if not body:
                body = (
                    f"🚀 {cmd_name}\n\n"
                    "آخر نسخة جاهزة الآن\n"
                    "اضغط على زر التحميل تحت 👇"
                )

            rows = []
            if url:
                rows.append([InlineKeyboardButton("⬇️ تحميل الآن", url=url)])
            rows.append([
                InlineKeyboardButton("⬅️ رجوع", callback_data=f"public_cat:{cat_name}"),
                InlineKeyboardButton("🏠 الرئيسية", callback_data="public_back_categories"),
            ])
            rows.append([InlineKeyboardButton("❌ إغلاق", callback_data="public_close")])

            await query.edit_message_text(
                body,
                reply_markup=InlineKeyboardMarkup(rows),
                disable_web_page_preview=True,
            )
            return

    if not is_owner(user.id):
        try:
            await query.answer("هذه اللوحة للإدارة فقط.", show_alert=True)
        except Exception:
            pass
        return

    st = user_state(user.id)
    gid = selected_group_id(user.id)

    if data == "main":
        await query.edit_message_text("👑 أهلاً بك في لوحة تحكم البوت الكاملة", reply_markup=main_menu(user.id))
        return

    if data == "settings_menu":
        if not gid:
            await query.edit_message_text("اختر قروب أولاً.", reply_markup=back("main"))
            return
        title = DATA["groups"][gid].get("title") or gid
        await query.edit_message_text(
            f"الإعدادات\nللمجموعة: {title}\nاختر الإعدادات التي تريد تعديلها",
            reply_markup=settings_menu(user.id)
        )
        return

    if data == "more_menu":
        if not gid:
            await query.edit_message_text("اختر قروب أولاً.", reply_markup=back("main"))
            return
        title = DATA["groups"][gid].get("title") or gid
        await query.edit_message_text(
            f"الإعدادات\nللمجموعة: {title}\nإعدادات إضافية متقدمة",
            reply_markup=more_menu(user.id)
        )
        return

    if data == "vip_hub":
        await query.edit_message_text("👑 لوحة VIP المتقدمة", reply_markup=vip_hub())
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

    if data == "toggle_lang":
        if gid:
            cfg = DATA["groups"][gid]
            cfg["lang"] = "en" if cfg["lang"] == "ar" else "ar"
            save_data()
        await query.edit_message_text("✅ تم تغيير اللغة.", reply_markup=back("settings_menu"))
        return

    if not gid:
        await query.edit_message_text("اختر قروب أولاً.", reply_markup=back("main"))
        return

    cfg = DATA["groups"][gid]

    if data == "toggle_media_position":
        cfg["media_below_text"] = not cfg.get("media_below_text", True)
        save_data()
        mode = "النص فوق الصورة ✅" if cfg["media_below_text"] else "النص تحت الصورة ✅"
        await query.edit_message_text(f"✅ تم تحديث طريقة عرض الترحيب\n{mode}", reply_markup=welcome_menu())
        return

    if data == "clear_welcome_buttons":
        cfg["welcome_buttons"] = []
        save_data()
        await query.edit_message_text("✅ تم حذف أزرار الروابط.", reply_markup=welcome_menu())
        return

    if data == "preview_welcome":
        preview_name = user.first_name or "أحمد"
        preview_text = format_welcome(cfg, preview_name, cfg.get("title") or "ARC ZONE", user.id)
        keyboard = build_welcome_keyboard(cfg)

        if cfg.get("welcome_photo"):
            try:
                if cfg.get("media_below_text", True):
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text=preview_text,
                        reply_markup=keyboard,
                    )
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=cfg["welcome_photo"],
                    )
                else:
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=cfg["welcome_photo"],
                        caption=preview_text[:1024],
                        reply_markup=keyboard,
                    )
            except Exception as e:
                await context.bot.send_message(query.message.chat_id, f"تعذر إرسال المعاينة بالصورة: {e}")
        else:
            await context.bot.send_message(query.message.chat_id, preview_text, reply_markup=keyboard)

        await query.edit_message_text("✅ تم إرسال المعاينة.", reply_markup=welcome_menu())
        return


    if data == "commands_menu":
        await query.edit_message_text("🧾 قسم أوامر المجموعة", reply_markup=commands_menu(gid))
        return

    if data == "show_commands_intro":
        await query.edit_message_text(cfg.get("commands_intro_text", "أوامر المجموعة"), reply_markup=back("commands_menu"))
        return

    if data == "show_commands_catalog":
        await query.edit_message_text(build_commands_overview_text(cfg), reply_markup=back("commands_menu"))
        return
    if data == "add_category":
        st["waiting"] = "add_category_name"
        await query.edit_message_text("أرسل اسم القسم الجديد.", reply_markup=back("commands_menu"))
        return

    if data == "rename_category":
        st["waiting"] = "rename_category_old_name"
        await query.edit_message_text("أرسل اسم القسم الذي تريد تغيير اسمه.", reply_markup=back("commands_menu"))
        return

    if data == "delete_category":
        st["waiting"] = "delete_category_name"
        await query.edit_message_text("أرسل اسم القسم الذي تريد حذفه.", reply_markup=back("commands_menu"))
        return


    if data.startswith("commands_category:"):
        cat_name = data.split(":", 1)[1]
        await query.edit_message_text(build_single_category_text(cfg, cat_name), reply_markup=command_category_menu(gid, cat_name))
        return

    if data.startswith("show_category_commands:"):
        cat_name = data.split(":", 1)[1]
        await query.edit_message_text(build_single_category_text(cfg, cat_name), reply_markup=command_category_menu(gid, cat_name))
        return

    if data.startswith("rename_category_in:"):
        cat_name = data.split(":", 1)[1]
        st["waiting"] = "rename_category_new_name"
        st["temp_key"] = cat_name
        await query.edit_message_text(f"أرسل الاسم الجديد لقسم {cat_name}.", reply_markup=back("commands_menu"))
        return

    if data.startswith("delete_category_in:"):
        cat_name = data.split(":", 1)[1]
        if cat_name in cfg.get("command_categories", {}):
            del cfg["command_categories"][cat_name]
            save_data()
        await query.edit_message_text("✅ تم حذف القسم.", reply_markup=commands_menu(gid))
        return

    if data.startswith("set_category_desc:"):
        cat_name = data.split(":", 1)[1]
        st["waiting"] = "set_category_desc"
        st["temp_key"] = cat_name
        await query.edit_message_text(f"أرسل وصف قسم {cat_name}.", reply_markup=back("commands_menu"))
        return

    if data.startswith("add_command_in:"):
        cat_name = data.split(":", 1)[1]
        st["waiting"] = "add_exact_command_name"
        st["temp_category"] = cat_name
        await query.edit_message_text(f"أرسل اسم الأمر الجديد داخل قسم {cat_name}.", reply_markup=back("commands_menu"))
        return

    if data.startswith("delete_command_in:"):
        cat_name = data.split(":", 1)[1]
        st["waiting"] = "delete_exact_command_name"
        st["temp_category"] = cat_name
        await query.edit_message_text(f"أرسل اسم الأمر الذي تريد حذفه من قسم {cat_name}.", reply_markup=back("commands_menu"))
        return

    toggle_map = {
        "toggle_anti_spam": "anti_spam",
        "toggle_anti_flood": "anti_flood",
        "toggle_anti_caps": "anti_caps",
        "toggle_captcha": "captcha_enabled",
        "toggle_admin_report": "admin_report",
        "toggle_anti_nsfw": "anti_nsfw",
        "toggle_night_mode": "night_mode",
        "toggle_tag_alert": "tag_alert",
        "toggle_approval_mode": "approval_mode",
        "toggle_delete_system_messages": "delete_system_messages",
        "toggle_topics_enabled": "topics_enabled",
        "toggle_stealth_users": "stealth_users",
        "toggle_custom_commands_enabled": "custom_commands_enabled",
        "toggle_animated_stickers": "animated_stickers",
        "toggle_long_messages": "long_messages",
        "toggle_channels_manager": "channels_manager",
        "toggle_permissions_locked": "permissions_locked",
        "toggle_links": "anti_links",
        "toggle_badwords": "anti_badwords",
        "toggle_welcome": "welcome_enabled",
        "toggle_auto_pin": "auto_pin_note",
    }

    if data in toggle_map:
        key = toggle_map[data]
        cfg[key] = not cfg[key]
        save_data()
        if data.startswith("toggle_") and data not in {"toggle_links", "toggle_badwords"}:
            await query.edit_message_text("✅ تم تحديث الإعداد.", reply_markup=settings_menu(user.id) if data not in {"toggle_auto_pin"} else pin_menu(gid))
        else:
            await query.edit_message_text("✅ تم تحديث الإعداد.", reply_markup=protect_menu(gid) if data in {"toggle_links", "toggle_badwords"} else settings_menu(user.id))
        return

    waiting_map = {
        "set_welcome": ("set_welcome", "أرسل رسالة الترحيب الجديدة."),
        "set_rules": ("set_rules", "أرسل القوانين الجديدة."),
        "add_reply": ("add_reply_key", "أرسل الكلمة."),
        "delete_reply": ("delete_reply_key", "أرسل الكلمة لحذف ردها."),
        "add_badword": ("add_badword", "أرسل الكلمة الممنوعة."),
        "delete_badword": ("delete_badword", "أرسل الكلمة المراد حذفها."),
        "set_mute_after": ("set_mute_after", "أرسل رقم الكتم بعد كم إنذار."),
        "set_ban_after": ("set_ban_after", "أرسل رقم الطرد بعد كم إنذار."),
        "set_note": ("set_note", "أرسل النص المثبت الجديد."),
        "set_welcome_photo": ("set_welcome_photo", "أرسل رابط الصورة أو file_id أو أرسل صورة في الخاص."),
        "set_buttons": ("set_buttons", "أرسل الزر بهذا الشكل:\nاسم الزر | الرابط\nوتقدر ترسل أكثر من زر، كل زر في سطر."),
        "set_commands_intro": ("set_commands_intro", "أرسل رسالة قسم الأوامر الجديدة."),
        "add_exact_command": ("add_exact_command_name", "أرسل اسم الأمر الجديد."),
        "delete_exact_command": ("delete_exact_command_name", "أرسل اسم الأمر الذي تريد حذفه."),
        "set_group_link": ("set_group_link", "أرسل رابط المجموعة."),
        "set_log_channel": ("set_log_channel", "أرسل يوزر قناة السجل أو ID."),
        "set_discussion_group": ("set_discussion_group", "أرسل رابط أو آيدي مجموعة المناقشة."),
    }
    if data in waiting_map:
        st["waiting"], text = waiting_map[data]
        await query.edit_message_text(text, reply_markup=back("main"))
        return

    if data == "show_welcome":
        mode_text = "النص فوق الصورة ✅" if cfg.get("media_below_text", True) else "النص تحت الصورة ✅"
        buttons_count = len(cfg.get("welcome_buttons", []))
        await query.edit_message_text(
            f"{cfg['welcome_text']}\n\n🖼️ وضع الوسائط: {mode_text}\n🔗 عدد الأزرار: {buttons_count}",
            reply_markup=back("welcome_menu")
        )
    elif data == "welcome_menu":
        await query.edit_message_text("🎉 قسم الترحيب", reply_markup=welcome_menu())
    elif data == "rules_menu":
        await query.edit_message_text("📜 قسم القوانين", reply_markup=rules_menu())
    elif data == "show_rules_btn":
        await query.message.reply_text(cfg["rules_text"])

        if cfg["welcome_photo"]:
            try:
                await query.message.reply_photo(cfg["welcome_photo"])
            except Exception:
                pass
    elif data == "show_rules":
        await query.edit_message_text(cfg["rules_text"], reply_markup=back("rules_menu"))
    elif data == "replies_menu":
        await query.edit_message_text("🤖 قسم الردود", reply_markup=replies_menu())
    elif data == "show_replies":
        text = "لا توجد ردود." if not cfg["auto_replies"] else "\n\n".join([f"{k} ➜ {v}" for k, v in cfg["auto_replies"].items()])
        await query.edit_message_text(text, reply_markup=back("replies_menu"))
    elif data == "protect_menu":
        await query.edit_message_text("🛡️ قسم الحماية", reply_markup=protect_menu(gid))
    elif data == "badwords_menu":
        await query.edit_message_text("🔤 قسم الكلمات المحظورة", reply_markup=protect_menu(gid))
    elif data == "warns_menu":
        await query.edit_message_text("⚠️ قسم الإنذارات", reply_markup=warns_menu(gid))
    elif data == "show_warns_panel":
        text = "لا توجد تحذيرات." if not cfg["warnings"] else "\n".join([f"{u}: {c}" for u, c in cfg["warnings"].items()])
        await query.edit_message_text(text, reply_markup=back("warns_menu"))
    elif data == "pin_menu":
        await query.edit_message_text("📌 قسم التثبيت", reply_markup=pin_menu(gid))
    elif data == "show_note":
        await query.edit_message_text(cfg["note_text"], reply_markup=back("pin_menu"))
    elif data == "pin_note_now":
        await pin_note_now(context, int(gid), cfg["note_text"])
        await query.edit_message_text("✅ تمت محاولة تثبيت الرسالة.", reply_markup=pin_menu(gid))
    elif data == "media_menu":
        await query.edit_message_text("🖼️ قسم الوسائط", reply_markup=media_menu())
    elif data == "clear_welcome_photo":
        cfg["welcome_photo"] = ""
        save_data()
        await query.edit_message_text("✅ تم حذف صورة الترحيب.", reply_markup=media_menu())
    elif data == "show_settings":
        await query.edit_message_text(settings_summary(gid), reply_markup=back("settings_menu"))
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
    elif data == "send_backup_file":
        await send_backup_document(query.message, context)
        await query.edit_message_text("✅ تم إرسال ملف النسخة الاحتياطية.", reply_markup=backup_menu())
    elif data == "restore_backup":
        ok = restore_backup()
        await query.edit_message_text("✅ تم استرجاع النسخة." if ok else "❌ لا توجد نسخة احتياطية.", reply_markup=backup_menu())
    elif data == "commands_menu":
        await query.edit_message_text("🧾 قسم أوامر المجموعة", reply_markup=commands_menu(gid))
    elif data == "farewell_menu":
        await query.edit_message_text("👋 قسم الوداع جاهز كواجهة حالياً. إذا تبي أربطه برسالة خروج لاحقاً أقدر.", reply_markup=back("settings_menu"))
    elif data == "restrictions_menu":
        await query.edit_message_text("🎤 قسم القيود مرتبط حالياً بأوامر /mute /unmute /ban /unban", reply_markup=back("settings_menu"))
    elif data == "ban_menu":
        await query.edit_message_text("🔐 قسم الحظر مرتبط حالياً بأوامر /ban و /unban", reply_markup=back("settings_menu"))
    elif data == "members_menu":
        await query.edit_message_text("👥 إدارة الأعضاء مرتبطة حالياً بأوامر المشرفين والتحذيرات.", reply_markup=back("more_menu"))


async def handle_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    user = update.effective_user
    if not user or not is_owner(user.id):
        return
    if not update.message:
        return

    if update.message.photo:
        st = user_state(user.id)
        gid = selected_group_id(user.id)
        if gid and st.get("waiting") == "set_welcome_photo":
            cfg = DATA["groups"][gid]
            cfg["welcome_photo"] = update.message.photo[-1].file_id
            st["waiting"] = None
            save_data()
            await update.message.reply_text("✅ تم حفظ صورة الترحيب.", reply_markup=main_menu(user.id))
        return

    if not update.message.text:
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
    elif waiting == "set_buttons":
        buttons = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if "|" not in line:
                await update.message.reply_text("❌ الصيغة غلط\nمثال:\nالقوانين | https://t.me/xxxxx")
                return
            btn_text, btn_url = line.split("|", 1)
            btn_text = btn_text.strip()
            btn_url = btn_url.strip()
            if not btn_text or not btn_url:
                await update.message.reply_text("❌ الصيغة غلط\nمثال:\nالقوانين | https://t.me/xxxxx")
                return
            buttons.append({"text": btn_text, "url": btn_url})
        cfg["welcome_buttons"] = buttons
    elif waiting == "set_commands_intro":
        cfg["commands_intro_text"] = text
    elif waiting == "add_category_name":
        if text in cfg["command_categories"]:
            await update.message.reply_text("❌ هذا القسم موجود مسبقًا.")
            return
        cfg["command_categories"][text] = {"description": "", "commands": {}}
        st["waiting"] = "add_category_desc"
        st["temp_key"] = text
        save_data()
        await update.message.reply_text("أرسل وصف القسم الجديد.")
        return
    elif waiting == "add_category_desc":
        cat_name = st.get("temp_key")
        if cat_name:
            cfg["command_categories"].setdefault(cat_name, {"description": "", "commands": {}})
            cfg["command_categories"][cat_name]["description"] = text
            st["temp_key"] = None
    elif waiting == "rename_category_old_name":
        if text not in cfg["command_categories"]:
            await update.message.reply_text("❌ هذا القسم غير موجود.")
            return
        st["temp_key"] = text
        st["waiting"] = "rename_category_new_name"
        await update.message.reply_text("أرسل الاسم الجديد للقسم.")
        return
    elif waiting == "rename_category_new_name":
        old_name = st.get("temp_key")
        new_name = text.strip()
        if not old_name or old_name not in cfg["command_categories"]:
            await update.message.reply_text("❌ القسم القديم غير موجود.")
            return
        if not new_name:
            await update.message.reply_text("❌ الاسم الجديد غير صالح.")
            return
        if new_name != old_name and new_name in cfg["command_categories"]:
            await update.message.reply_text("❌ يوجد قسم بهذا الاسم مسبقًا.")
            return
        cfg["command_categories"][new_name] = cfg["command_categories"].pop(old_name)
        st["temp_key"] = None
    elif waiting == "delete_category_name":
        if text not in cfg["command_categories"]:
            await update.message.reply_text("❌ هذا القسم غير موجود.")
            return
        del cfg["command_categories"][text]
    elif waiting == "set_category_desc":
        cat_name = st.get("temp_key") or st.get("temp_category")
        if cat_name:
            cfg["command_categories"].setdefault(cat_name, {"description": "", "commands": {}})
            cfg["command_categories"][cat_name]["description"] = text
            st["temp_key"] = None
            st["temp_category"] = None
    elif waiting == "add_exact_command_name":
        st["temp_command_name"] = text
        st["waiting"] = "add_exact_command_reply"
        if not st.get("temp_category"):
            st["waiting"] = "add_exact_command_pick_category"
            categories_text = "\n".join([f"• {name}" for name in cfg["command_categories"].keys()])
            await update.message.reply_text(f"أرسل اسم القسم لهذا الأمر.\n\nالأقسام المتاحة:\n{categories_text}")
            return
        await update.message.reply_text("أرسل الرد أو الرابط الخاص بهذا الأمر.")
        return
    elif waiting == "add_exact_command_pick_category":
        cat_name = text
        if cat_name not in cfg["command_categories"]:
            await update.message.reply_text("❌ هذا القسم غير موجود. أرسل اسم قسم صحيح.")
            return
        st["temp_category"] = cat_name
        st["waiting"] = "add_exact_command_reply"
        await update.message.reply_text("أرسل الرد أو الرابط الخاص بهذا الأمر.")
        return
    elif waiting == "add_exact_command_reply":
        cmd_name = st.get("temp_command_name")
        cat_name = st.get("temp_category")
        if cmd_name and cat_name:
            cfg["command_categories"].setdefault(cat_name, {"description": "", "commands": {}})
            cfg["command_categories"][cat_name]["commands"][cmd_name] = text
        st["temp_command_name"] = None
        st["temp_category"] = None
    elif waiting == "delete_exact_command_name":
        target_name = text.strip().casefold()
        target_category = st.get("temp_category")
        deleted = False
        for cat_name, cat_cfg in cfg["command_categories"].items():
            if target_category and cat_name != target_category:
                continue
            for cmd_name in list(cat_cfg.get("commands", {}).keys()):
                if cmd_name.strip().casefold() == target_name:
                    del cat_cfg["commands"][cmd_name]
                    deleted = True
                    break
            if deleted:
                break
        st["temp_category"] = None
    elif waiting == "set_group_link":
        cfg["group_link"] = text
    elif waiting == "set_log_channel":
        cfg["log_channel"] = text
    elif waiting == "set_discussion_group":
        cfg["discussion_group"] = text

    st["waiting"] = None
    save_data()
    await update.message.reply_text("✅ تم الحفظ.", reply_markup=main_menu(user.id))



def _welcome_cache(context: ContextTypes.DEFAULT_TYPE) -> dict[str, str]:
    return context.application.bot_data.setdefault("recent_welcomes", {})


def _already_welcomed(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, ttl_seconds: int = 8) -> bool:
    cache = _welcome_cache(context)
    key = f"{chat_id}:{user_id}"
    now = datetime.now(timezone.utc)
    old_keys = []
    for k, v in cache.items():
        try:
            ts = datetime.fromisoformat(v)
            if (now - ts).total_seconds() > ttl_seconds:
                old_keys.append(k)
        except Exception:
            old_keys.append(k)
    for k in old_keys:
        cache.pop(k, None)

    if key in cache:
        return True

    cache[key] = now.isoformat()
    return False


async def send_welcome_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, group_name: str, member, cfg: dict[str, Any]) -> None:
    if _already_welcomed(context, chat_id, member.id):
        return

    text = format_welcome(cfg, member.first_name or "يا هلا", group_name, member.id)
    keyboard = build_welcome_keyboard(cfg)

    if cfg["welcome_photo"]:
        try:
            if len(text) > 1024:
                text = text[:1000] + "..."
            if cfg.get("media_below_text", True):
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard,
                )
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=cfg["welcome_photo"],
                )
            else:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=cfg["welcome_photo"],
                    caption=text,
                    reply_markup=keyboard,
                )
            return
        except Exception as e:
            print(f"Welcome photo error: {e}")

    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)


async def handle_my_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.my_chat_member:
        return

    chat = update.my_chat_member.chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    new_status = getattr(update.my_chat_member.new_chat_member, "status", None)
    if new_status in {"administrator", "member"}:
        ensure_group(chat.id, chat.title or "")
        save_data()


async def handle_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.chat_member:
        return

    chat = update.chat_member.chat
    cfg = get_or_create_group(chat.id, chat.title or "")
    if not cfg["welcome_enabled"]:
        return

    old_status = getattr(update.chat_member.old_chat_member, "status", None)
    new_status = getattr(update.chat_member.new_chat_member, "status", None)

    joined_statuses = {"member", "administrator", "creator"}
    left_statuses = {"left", "kicked", "restricted"}

    if old_status not in joined_statuses and new_status in joined_statuses:
        await send_welcome_message(
            context=context,
            chat_id=chat.id,
            group_name=chat.title or "القروب",
            member=update.chat_member.new_chat_member.user,
            cfg=cfg,
        )


async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return
    cfg = get_or_create_group(update.effective_chat.id, update.effective_chat.title or "")
    if not cfg["welcome_enabled"]:
        return

    group_name = update.effective_chat.title or "القروب"

    for member in update.message.new_chat_members:
        await send_welcome_message(
            context=context,
            chat_id=update.effective_chat.id,
            group_name=group_name,
            member=member,
            cfg=cfg,
        )

    if cfg["auto_pin_note"] and cfg["note_text"]:
        await pin_note_now(context, update.effective_chat.id, cfg["note_text"])


async def handle_group_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    cfg = get_or_create_group(update.effective_chat.id, update.effective_chat.title or "")

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

        if cfg["long_messages"] and len(text) > 1200:
            try:
                await update.message.delete()
            except Exception:
                pass
            await warn_user(update, context, "رسالة طويلة جداً")
            return

    admin_handled = await handle_admin_text_command(update, context, text)
    if admin_handled:
        return

    normalized_text = normalize_digits(text).strip()
    if normalized_text.casefold() in {"الأوامر", "اوامر", "/commands"}:
        keyboard = build_public_categories_keyboard(cfg)
        if keyboard is None:
            await update.message.reply_text("لا يوجد أوامر متاحة حالياً.")
        else:
            await update.message.reply_text(build_public_commands_intro_text(cfg), reply_markup=keyboard)
        return

    if normalized_text in {"القوانين", "قوانين"}:
        await cmd_rules(update, context)
        return

    if normalized_text in {"الترحيب", "ترحيب"}:
        await cmd_welcome(update, context)
        return

    if normalized_text in {"الإعدادات", "الاعدادات", "اعدادات"}:
        await cmd_settings(update, context)
        return

    if normalized_text in {"آيدي", "ايدي"}:
        await cmd_id(update, context)
        return

    number_command_reply = get_command_reply_by_number(cfg, normalized_text)
    if number_command_reply is not None:
        await update.message.reply_text(number_command_reply)
        return

    exact_command_reply = find_exact_command(cfg, text)
    if exact_command_reply is not None:
        await update.message.reply_text(exact_command_reply)
        return

    for key, reply in cfg["auto_replies"].items():
        if key and key.lower() in text.lower():
            await update.message.reply_text(reply)
            break




async def cmd_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text("استخدم هذا الأمر داخل القروب.")
        return
    cfg = get_or_create_group(update.effective_chat.id, update.effective_chat.title or "")
    keyboard = build_public_categories_keyboard(cfg)
    if keyboard is None:
        await update.message.reply_text("لا يوجد أوامر متاحة حالياً.")
        return
    await update.message.reply_text(build_public_commands_intro_text(cfg), reply_markup=keyboard)

def main():
    if not TOKEN:
        raise ValueError("TOKEN غير موجود. حطه في Variables باسم TOKEN")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("bindgroup", cmd_bindgroup))
    app.add_handler(CommandHandler("rules", cmd_rules))
    app.add_handler(CommandHandler("welcome", cmd_welcome))
    app.add_handler(CommandHandler("commands", cmd_commands))
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
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_private))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members))
    app.add_handler(ChatMemberHandler(handle_chat_member_update, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(handle_my_chat_member_update, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND, handle_group_text))

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
