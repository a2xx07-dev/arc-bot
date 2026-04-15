# ARC ZONE LEGEND BOT - cleaned and reordered
import io
import json
import os
import random
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageFont
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
    InputFile,
)
from telegram.constants import ChatType, ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


TOKEN = os.getenv("TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "8406441503"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

DATA_FILE = Path("data.json")
BADWORDS_FILE = Path("badwords.txt")
BACKUP_FILE = Path("backup_data.json")
LINK_RE = re.compile(r"(https?://\S+|www\.\S+|t\.me/\S+)", re.IGNORECASE)

DEFAULT_GROUP = {
    "title": "",
    "welcome_enabled": True,
    "welcome_text": (
        "🔥 {MENTION} حياك في {group} 🔥\n\n"
        "🎮 Arc Zone - ارك زون\n"
        "🚀 هنا المكان اللي يفرق بين العادي والمحترف\n\n"
        "📜 القوانين: /القوانين\n"
        "🆔 آيديك: {user_id}\n"
        "👑 شد حيلك وخل بصمتك تبان"
    ),
    "welcome_png_enabled": True,
    "welcome_photo": "",
    "rules_text": (
        "📜 قوانين القروب:\n"
        "1) احترام الجميع\n"
        "2) ممنوع السب والشتم\n"
        "3) ممنوع الإعلانات والروابط\n"
        "4) الالتزام بموضوع القروب\n"
        "5) قرارات الإدارة ملزمة"
    ),
    "note_text": "📌 لا توجد رسالة مثبتة حاليًا.",
    "auto_replies": {},
    "anti_links": False,
    "anti_badwords": False,
    "anti_spam": True,
    "ai_reply_enabled": False,
    "ai_reply_chance": 15,
    "media_allowed": True,
    "auto_pin_note": False,
    "warnings": {},
    "mute_after": 3,
    "ban_after": 5,
    "vip_users": [],
    "xp": {},
    "clans": {},
    "user_clan": {},
    "group_link": "",
    "log_channel": "",
}

owner_states: dict[int, dict[str, Any]] = {}
spam_tracker: dict[str, list[datetime]] = {}


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
            if not isinstance(merged["auto_replies"], dict):
                merged["auto_replies"] = {}
            if not isinstance(merged["warnings"], dict):
                merged["warnings"] = {}
            if not isinstance(merged["vip_users"], list):
                merged["vip_users"] = []
            if not isinstance(merged["xp"], dict):
                merged["xp"] = {}
            if not isinstance(merged["clans"], dict):
                merged["clans"] = {}
            if not isinstance(merged["user_clan"], dict):
                merged["user_clan"] = {}
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


def get_group(chat_id: int) -> Optional[dict[str, Any]]:
    return DATA["groups"].get(str(chat_id))


def user_state(user_id: int) -> dict[str, Any]:
    if user_id not in owner_states:
        owner_states[user_id] = {"selected_group": None, "waiting": None, "temp_key": None}
    return owner_states[user_id]


def selected_group_id(user_id: int) -> Optional[str]:
    st = user_state(user_id)
    gid = st.get("selected_group")
    if gid and gid in DATA["groups"]:
        return gid
    if DATA["groups"]:
        gid = next(iter(DATA["groups"].keys()))
        st["selected_group"] = gid
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


def mention_html(user_id: int, name: str) -> str:
    safe_name = str(name).replace("<", "").replace(">", "")
    return f"<a href='tg://user?id={user_id}'>{safe_name}</a>"


def rank_from_xp(xp: int) -> str:
    if xp >= 3000:
        return "👑 أسطورة"
    if xp >= 2000:
        return "🔥 محترف"
    if xp >= 1200:
        return "⚔️ مقاتل"
    if xp >= 600:
        return "🎯 متقدم"
    if xp >= 200:
        return "🚀 نشيط"
    return "🌱 مبتدئ"


def format_welcome(cfg: dict[str, Any], name: str, group_title: str, user_id: int) -> str:
    mention = mention_html(user_id, name)
    return (
        cfg["welcome_text"]
        .replace("{name}", name)
        .replace("{group}", group_title)
        .replace("{user_id}", str(user_id))
        .replace("{MENTION}", mention)
    )


def stats_text(chat_id: int) -> str:
    cfg = get_group(chat_id)
    if not cfg:
        return "لا توجد بيانات."
    return (
        f"📊 إحصائيات القروب\n\n"
        f"🆔 آيدي القروب: {chat_id}\n"
        f"🤖 عدد الردود: {len(cfg['auto_replies'])}\n"
        f"👑 عدد VIP: {len(cfg['vip_users'])}\n"
        f"🎮 عدد الكلانات: {len(cfg['clans'])}\n"
        f"📈 عدد اللاعبين المسجلين XP: {len(cfg['xp'])}\n"
        f"🛡️ منع الروابط: {'مفعل ✅' if cfg['anti_links'] else 'معطل ❌'}\n"
        f"🤖 GPT: {'مفعل ✅' if cfg['ai_reply_enabled'] else 'معطل ❌'}"
    )


def make_backup() -> None:
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(DATA, f, ensure_ascii=False, indent=2)


def get_font(size: int):
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def make_welcome_png(name: str, group_name: str, rank: str) -> io.BytesIO:
    width, height = 1200, 675
    img = Image.new("RGB", (width, height), (9, 16, 28))
    draw = ImageDraw.Draw(img)

    for i in range(height):
        color = (10 + int(i * 0.03), 20 + int(i * 0.06), 40 + int(i * 0.08))
        draw.line((0, i, width, i), fill=color)

    draw.rounded_rectangle((40, 40, width - 40, height - 40), radius=28, outline=(255, 140, 40), width=4)
    draw.rounded_rectangle((70, 90, width - 70, height - 120), radius=24, outline=(80, 160, 255), width=2)

    title_font = get_font(54)
    big_font = get_font(78)
    mid_font = get_font(36)
    small_font = get_font(28)

    draw.text((90, 90), "ARC ZONE VIP", font=title_font, fill=(255, 190, 70))
    draw.text((90, 200), "WELCOME", font=big_font, fill=(255, 255, 255))
    draw.text((90, 315), name[:22], font=big_font, fill=(90, 200, 255))
    draw.text((90, 425), f"القروب: {group_name[:26]}", font=mid_font, fill=(255, 255, 255))
    draw.text((90, 485), f"الرتبة: {rank}", font=mid_font, fill=(255, 180, 90))
    draw.text((90, 555), "شد حيلك وخل بصمتك تبان 👑", font=small_font, fill=(220, 220, 220))

    draw.ellipse((860, 150, 1080, 370), outline=(255, 150, 50), width=6)
    draw.ellipse((900, 190, 1040, 330), outline=(100, 200, 255), width=4)
    draw.text((912, 235), "VIP", font=get_font(56), fill=(255, 255, 255))

    bio = io.BytesIO()
    bio.name = "welcome.png"
    img.save(bio, "PNG")
    bio.seek(0)
    return bio


def openai_client():
    if not OPENAI_API_KEY or OpenAI is None:
        return None
    try:
        return OpenAI(api_key=OPENAI_API_KEY)
    except Exception:
        return None


async def ai_answer(prompt: str) -> Optional[str]:
    client = openai_client()
    if not client:
        return None
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "أنت مساعد عربي مختصر داخل قروب ألعاب. رد بلغة عربية مناسبة للشباب وبشكل قصير ومفيد."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return None


def build_main_menu(user_id: int) -> InlineKeyboardMarkup:
    gid = selected_group_id(user_id)
    title = DATA["groups"].get(gid, {}).get("title", "غير محدد") if gid else "غير محدد"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 اختيار القروب", callback_data="groups")],
        [InlineKeyboardButton(f"🎯 الحالي: {title}", callback_data="panel")],
        [InlineKeyboardButton("👑 لوحة VIP الأسطورية", callback_data="panel")],
    ])


def panel_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎉 الترحيب", callback_data="welcome_menu"),
         InlineKeyboardButton("🤖 الذكاء الاصطناعي", callback_data="ai_menu")],
        [InlineKeyboardButton("🛡️ الحماية", callback_data="protect_menu"),
         InlineKeyboardButton("🤖 الردود", callback_data="replies_menu")],
        [InlineKeyboardButton("👑 VIP الأعضاء", callback_data="vip_menu"),
         InlineKeyboardButton("📈 اللفل + XP", callback_data="xp_menu")],
        [InlineKeyboardButton("🎮 الكلان / الفرق", callback_data="clan_menu"),
         InlineKeyboardButton("📌 التثبيت", callback_data="pin_menu")],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats_menu"),
         InlineKeyboardButton("🛠️ أدوات المشرف", callback_data="mod_menu")],
        [InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings_menu"),
         InlineKeyboardButton("💾 النسخ الاحتياطي", callback_data="backup_menu")],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="main")],
    ])


def groups_menu() -> InlineKeyboardMarkup:
    rows = []
    for gid, cfg in DATA["groups"].items():
        title = cfg.get("title") or gid
        rows.append([InlineKeyboardButton(f"📌 {title}", callback_data=f"select_group:{gid}")])
    rows.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="main")])
    return InlineKeyboardMarkup(rows)


def back(to: str = "panel") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ العودة", callback_data=to)]])


def welcome_menu_markup(gid: str) -> InlineKeyboardMarkup:
    cfg = DATA["groups"][gid]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"تشغيل الترحيب {'✅' if cfg['welcome_enabled'] else '❌'}", callback_data="toggle_welcome")],
        [InlineKeyboardButton(f"صورة PNG {'✅' if cfg['welcome_png_enabled'] else '❌'}", callback_data="toggle_welcome_png")],
        [InlineKeyboardButton("تعديل نص الترحيب", callback_data="set_welcome_text")],
        [InlineKeyboardButton("تجربة الترحيب", callback_data="test_welcome")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="panel")],
    ])


def ai_menu_markup(gid: str) -> InlineKeyboardMarkup:
    cfg = DATA["groups"][gid]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"رد GPT {'✅' if cfg['ai_reply_enabled'] else '❌'}", callback_data="toggle_ai")],
        [InlineKeyboardButton("نسبة رد الذكاء", callback_data="set_ai_chance")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="panel")],
    ])


def protect_menu_markup(gid: str) -> InlineKeyboardMarkup:
    cfg = DATA["groups"][gid]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"منع الروابط {'✅' if cfg['anti_links'] else '❌'}", callback_data="toggle_links")],
        [InlineKeyboardButton(f"منع الكلمات {'✅' if cfg['anti_badwords'] else '❌'}", callback_data="toggle_badwords")],
        [InlineKeyboardButton(f"حماية السبام {'✅' if cfg['anti_spam'] else '❌'}", callback_data="toggle_spam")],
        [InlineKeyboardButton(f"السماح بالوسائط {'✅' if cfg['media_allowed'] else '❌'}", callback_data="toggle_media")],
        [InlineKeyboardButton("إضافة كلمة ممنوعة", callback_data="add_badword")],
        [InlineKeyboardButton("حذف كلمة ممنوعة", callback_data="del_badword")],
        [InlineKeyboardButton("عرض الكلمات", callback_data="show_badwords")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="panel")],
    ])


def replies_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("إضافة رد", callback_data="add_reply")],
        [InlineKeyboardButton("حذف رد", callback_data="del_reply")],
        [InlineKeyboardButton("عرض الردود", callback_data="show_replies")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="panel")],
    ])


def vip_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("إضافة VIP", callback_data="vip_help")],
        [InlineKeyboardButton("عرض VIP", callback_data="show_vips")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="panel")],
    ])


def xp_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("عرض الترتيب", callback_data="leaderboard")],
        [InlineKeyboardButton("عرض المستويات", callback_data="xp_info")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="panel")],
    ])


def clan_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("إنشاء كلان", callback_data="clan_create")],
        [InlineKeyboardButton("عرض الكلانات", callback_data="clan_list")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="panel")],
    ])


def pin_menu_markup(gid: str) -> InlineKeyboardMarkup:
    cfg = DATA["groups"][gid]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("تعديل التثبيت", callback_data="set_note")],
        [InlineKeyboardButton("تثبيت الآن", callback_data="pin_now")],
        [InlineKeyboardButton(f"تثبيت تلقائي {'✅' if cfg['auto_pin_note'] else '❌'}", callback_data="toggle_auto_pin")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="panel")],
    ])


def mod_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("عرض أوامر المشرف", callback_data="mod_help")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="panel")],
    ])


def backup_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("إنشاء نسخة احتياطية", callback_data="backup_make")],
        [InlineKeyboardButton("إرسال النسخة", callback_data="backup_send")],
        [InlineKeyboardButton("⬅️ العودة", callback_data="panel")],
    ])


def settings_menu_markup(gid: str) -> InlineKeyboardMarkup:
    cfg = DATA["groups"][gid]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("تعديل القوانين", callback_data="set_rules")],
        [InlineKeyboardButton("رابط المجموعة", callback_data="set_group_link")],
        [InlineKeyboardButton(f"الكتم بعد: {cfg['mute_after']}", callback_data="set_mute_after"),
         InlineKeyboardButton(f"الحظر بعد: {cfg['ban_after']}", callback_data="set_ban_after")],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="main"),
         InlineKeyboardButton("⬅️ العودة", callback_data="panel")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.message.reply_text("👑 افتح البوت في الخاص عشان لوحة التحكم الكاملة.")
        return
    user = update.effective_user
    if not user or not is_owner(user.id):
        await update.message.reply_text("هذا البوت مخصص للإدارة فقط.")
        return
    await update.message.reply_text(
        "👑 ARC ZONE LEGEND CONTROL\nاختر اللي تبيه:",
        reply_markup=build_main_menu(user.id),
    )


async def bind_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text("استخدم هذا الأمر داخل القروب.")
        return
    if not await is_admin(update, context):
        await update.message.reply_text("هذا الأمر للمشرفين فقط.")
        return
    cfg = ensure_group(update.effective_chat.id, update.effective_chat.title or "")
    save_data()
    await update.message.reply_text(f"✅ تم ربط القروب\n📌 الاسم: {cfg['title']}\n🆔 الآيدي: {update.effective_chat.id}")


async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = get_group(update.effective_chat.id)
    if not cfg:
        return await update.message.reply_text("هذا القروب غير مربوط. استخدم /ربط")
    await update.message.reply_text(cfg["rules_text"])


async def cmd_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = get_group(update.effective_chat.id)
    if not cfg:
        return await update.message.reply_text("هذا القروب غير مربوط.")
    text = format_welcome(cfg, update.effective_user.first_name, update.effective_chat.title or "القروب", update.effective_user.id)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🆔 آيديك: {update.effective_user.id}\n💬 آيدي القروب: {update.effective_chat.id}")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = await context.bot.get_chat_member_count(update.effective_chat.id)
    await update.message.reply_text(stats_text(update.effective_chat.id) + f"\n👥 عدد الأعضاء: {count}")


async def clean(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("هذا الأمر للمشرفين فقط.")
    try:
        amount = int(context.args[0])
    except Exception:
        return await update.message.reply_text("استخدم: /تنظيف 100")
    deleted = 0
    for i in range(amount + 1):
        try:
            await context.bot.delete_message(update.effective_chat.id, update.message.message_id - i)
            deleted += 1
        except Exception:
            pass
    await update.message.reply_text(f"🧹 تم حذف {deleted} رسالة.")


async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("هذا الأمر للمشرفين فقط.")
    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        return await update.message.reply_text("رد على رسالة العضو ثم استخدم /تحذير")
    target = update.message.reply_to_message.from_user
    if await is_target_admin(context, update.effective_chat.id, target.id):
        return await update.message.reply_text("لا يمكن تحذير مشرف.")
    cfg = ensure_group(update.effective_chat.id, update.effective_chat.title or "")
    uid = str(target.id)
    cfg["warnings"][uid] = int(cfg["warnings"].get(uid, 0)) + 1
    count = cfg["warnings"][uid]
    save_data()

    extra = ""
    try:
        if count >= int(cfg["ban_after"]):
            await context.bot.ban_chat_member(update.effective_chat.id, target.id)
            extra = "\n⛔ تم حظره تلقائياً."
        elif count >= int(cfg["mute_after"]):
            until = datetime.now(timezone.utc) + timedelta(minutes=30)
            await context.bot.restrict_chat_member(
                update.effective_chat.id,
                target.id,
                ChatPermissions(can_send_messages=False),
                until_date=until,
            )
            extra = "\n🔇 تم كتمه 30 دقيقة."
    except Exception:
        pass

    await update.message.reply_text(f"⚠️ تم تحذير {target.first_name}\nالتحذيرات: {count}{extra}")


async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("هذا الأمر للمشرفين فقط.")
    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        return await update.message.reply_text("رد على رسالة العضو ثم استخدم /كتم")
    target = update.message.reply_to_message.from_user
    try:
        until = datetime.now(timezone.utc) + timedelta(minutes=30)
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            target.id,
            ChatPermissions(can_send_messages=False),
            until_date=until,
        )
        await update.message.reply_text(f"🔇 تم كتم {target.first_name}")
    except Exception:
        await update.message.reply_text("تعذر الكتم.")


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("هذا الأمر للمشرفين فقط.")
    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        return await update.message.reply_text("رد على رسالة العضو ثم استخدم /حظر")
    target = update.message.reply_to_message.from_user
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await update.message.reply_text(f"⛔ تم حظر {target.first_name}")
    except Exception:
        await update.message.reply_text("تعذر الحظر.")


async def pin_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("هذا الأمر للمشرفين فقط.")
    if not update.message.reply_to_message:
        return await update.message.reply_text("رد على الرسالة ثم استخدم /تثبيت")
    try:
        await context.bot.pin_chat_message(
            update.effective_chat.id,
            update.message.reply_to_message.message_id,
            disable_notification=True,
        )
        await update.message.reply_text("📌 تم التثبيت")
    except Exception:
        await update.message.reply_text("تعذر التثبيت.")


async def unpin_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("هذا الأمر للمشرفين فقط.")
    try:
        await context.bot.unpin_all_chat_messages(update.effective_chat.id)
        await update.message.reply_text("📌 تم فك التثبيت")
    except Exception:
        await update.message.reply_text("تعذر فك التثبيت.")


async def add_reply_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("هذا الأمر للمشرفين فقط.")
    if len(context.args) < 2:
        return await update.message.reply_text("استخدم: /اضف_رد الكلمة الرد")
    cfg = ensure_group(update.effective_chat.id, update.effective_chat.title or "")
    key = context.args[0].strip().lower()
    value = " ".join(context.args[1:]).strip()
    cfg["auto_replies"][key] = value
    save_data()
    await update.message.reply_text("✅ تم إضافة الرد")


async def del_reply_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("هذا الأمر للمشرفين فقط.")
    if not context.args:
        return await update.message.reply_text("استخدم: /حذف_رد الكلمة")
    cfg = ensure_group(update.effective_chat.id, update.effective_chat.title or "")
    key = context.args[0].strip().lower()
    if key in cfg["auto_replies"]:
        del cfg["auto_replies"][key]
        save_data()
        await update.message.reply_text("🗑️ تم حذف الرد")
    else:
        await update.message.reply_text("ما لقيت هذا الرد.")


async def my_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = ensure_group(update.effective_chat.id, update.effective_chat.title or "")
    uid = str(update.effective_user.id)
    xp = int(cfg["xp"].get(uid, 0))
    rank = rank_from_xp(xp)
    clan_name = cfg["user_clan"].get(uid, "بدون")
    vip_badge = "👑 VIP" if update.effective_user.id in cfg["vip_users"] else "عضو"
    await update.message.reply_text(
        f"📈 لفلك الحالي\n\n"
        f"👤 الاسم: {update.effective_user.first_name}\n"
        f"⭐ XP: {xp}\n"
        f"🏅 الرتبة: {rank}\n"
        f"👑 الحالة: {vip_badge}\n"
        f"🎮 الكلان: {clan_name}"
    )


async def add_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("هذا الأمر للمشرفين فقط.")
    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        return await update.message.reply_text("رد على العضو ثم استخدم /vip")
    target = update.message.reply_to_message.from_user
    cfg = ensure_group(update.effective_chat.id, update.effective_chat.title or "")
    if target.id not in cfg["vip_users"]:
        cfg["vip_users"].append(target.id)
        save_data()
    await update.message.reply_text(f"👑 {target.first_name} صار VIP")


async def create_clan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = ensure_group(update.effective_chat.id, update.effective_chat.title or "")
    uid = str(update.effective_user.id)
    if not context.args:
        return await update.message.reply_text("استخدم: /انشاء_كلان اسم_الكلان")
    clan_name = " ".join(context.args).strip()
    if clan_name in cfg["clans"]:
        return await update.message.reply_text("هذا الكلان موجود مسبقاً.")
    cfg["clans"][clan_name] = {
        "owner": update.effective_user.id,
        "members": [update.effective_user.id],
    }
    cfg["user_clan"][uid] = clan_name
    save_data()
    await update.message.reply_text(f"🎮 تم إنشاء الكلان: {clan_name}")


async def join_clan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = ensure_group(update.effective_chat.id, update.effective_chat.title or "")
    uid = str(update.effective_user.id)
    if not context.args:
        return await update.message.reply_text("استخدم: /دخول_كلان اسم_الكلان")
    clan_name = " ".join(context.args).strip()
    if clan_name not in cfg["clans"]:
        return await update.message.reply_text("هذا الكلان غير موجود.")
    clan = cfg["clans"][clan_name]
    if update.effective_user.id not in clan["members"]:
        clan["members"].append(update.effective_user.id)
    cfg["user_clan"][uid] = clan_name
    save_data()
    await update.message.reply_text(f"✅ دخلت الكلان: {clan_name}")


async def leave_clan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = ensure_group(update.effective_chat.id, update.effective_chat.title or "")
    uid = str(update.effective_user.id)
    clan_name = cfg["user_clan"].get(uid)
    if not clan_name:
        return await update.message.reply_text("أنت مو داخل أي كلان.")
    clan = cfg["clans"].get(clan_name)
    if clan and update.effective_user.id in clan["members"]:
        clan["members"].remove(update.effective_user.id)
    cfg["user_clan"].pop(uid, None)
    save_data()
    await update.message.reply_text(f"🚪 طلعت من الكلان: {clan_name}")


async def clan_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = ensure_group(update.effective_chat.id, update.effective_chat.title or "")
    uid = str(update.effective_user.id)
    clan_name = cfg["user_clan"].get(uid)
    if not clan_name:
        return await update.message.reply_text("أنت مو داخل أي كلان.")
    clan = cfg["clans"].get(clan_name, {})
    await update.message.reply_text(
        f"🎮 معلومات الكلان\n\n"
        f"📛 الاسم: {clan_name}\n"
        f"👑 المالك: {clan.get('owner')}\n"
        f"👥 الأعضاء: {len(clan.get('members', []))}"
    )


async def panel_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user = query.from_user
    if not is_owner(user.id):
        await query.edit_message_text("هذا القسم للمالك فقط.")
        return

    st = user_state(user.id)
    gid = selected_group_id(user.id)
    data = query.data

    if data == "main":
        await query.edit_message_text("👑 ARC ZONE LEGEND CONTROL", reply_markup=build_main_menu(user.id))
        return

    if data == "groups":
        if not DATA["groups"]:
            await query.edit_message_text(
                "لا يوجد قروبات مربوطة بعد. أضف البوت للقروب واكتب /ربط",
                reply_markup=back("main"),
            )
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

    menus = {
        "panel": ("👑 لوحة التحكم الأسطورية", panel_menu()),
        "welcome_menu": ("🎉 قسم الترحيب", welcome_menu_markup(gid)),
        "ai_menu": ("🤖 قسم الذكاء الاصطناعي", ai_menu_markup(gid)),
        "protect_menu": ("🛡️ قسم الحماية", protect_menu_markup(gid)),
        "replies_menu": ("🤖 قسم الردود", replies_menu_markup()),
        "vip_menu": ("👑 قسم VIP", vip_menu_markup()),
        "xp_menu": ("📈 قسم XP / اللفل", xp_menu_markup()),
        "clan_menu": ("🎮 قسم الكلان / الفرق", clan_menu_markup()),
        "pin_menu": ("📌 قسم التثبيت", pin_menu_markup(gid)),
        "mod_menu": ("🛠️ أدوات المشرف", mod_menu_markup()),
        "settings_menu": ("⚙️ الإعدادات", settings_menu_markup(gid)),
        "backup_menu": ("💾 النسخ الاحتياطي", backup_menu_markup()),
    }

    if data in menus:
        title, markup = menus[data]
        await query.edit_message_text(title, reply_markup=markup)
        return

    if data == "stats_menu":
        await query.edit_message_text(stats_text(int(gid)), reply_markup=back("panel"))
        return

    toggle_map = {
        "toggle_welcome": "welcome_enabled",
        "toggle_welcome_png": "welcome_png_enabled",
        "toggle_ai": "ai_reply_enabled",
        "toggle_links": "anti_links",
        "toggle_badwords": "anti_badwords",
        "toggle_spam": "anti_spam",
        "toggle_media": "media_allowed",
        "toggle_auto_pin": "auto_pin_note",
    }

    if data in toggle_map:
        key = toggle_map[data]
        cfg[key] = not cfg[key]
        save_data()

        target = (
            "welcome_menu" if "welcome" in data
            else "ai_menu" if data == "toggle_ai"
            else "pin_menu" if data == "toggle_auto_pin"
            else "protect_menu"
        )

        markup = (
            welcome_menu_markup(gid) if target == "welcome_menu"
            else ai_menu_markup(gid) if target == "ai_menu"
            else pin_menu_markup(gid) if target == "pin_menu"
            else protect_menu_markup(gid)
        )
        await query.edit_message_text("✅ تم تحديث الإعداد.", reply_markup=markup)
        return

    waiting_map = {
        "set_welcome_text": ("set_welcome_text", "أرسل نص الترحيب الجديد في الخاص."),
        "set_ai_chance": ("set_ai_chance", "أرسل نسبة رد GPT من 1 إلى 100."),
        "add_badword": ("add_badword", "أرسل الكلمة الممنوعة."),
        "del_badword": ("del_badword", "أرسل الكلمة المراد حذفها."),
        "add_reply": ("add_reply_key", "أرسل كلمة الرد أولاً."),
        "del_reply": ("del_reply_key", "أرسل كلمة الرد لحذفها."),
        "set_note": ("set_note", "أرسل نص التثبيت الجديد."),
        "set_rules": ("set_rules", "أرسل القوانين الجديدة."),
        "set_group_link": ("set_group_link", "أرسل رابط المجموعة."),
        "set_mute_after": ("set_mute_after", "أرسل رقم الكتم بعد كم تحذير."),
        "set_ban_after": ("set_ban_after", "أرسل رقم الحظر بعد كم تحذير."),
    }

    if data in waiting_map:
        st["waiting"], prompt = waiting_map[data]
        await query.edit_message_text(prompt, reply_markup=back("panel"))
        return

    if data == "show_badwords":
        text = "لا توجد كلمات." if not BADWORDS else "\n".join([f"• {w}" for w in BADWORDS[:100]])
        await query.edit_message_text(text, reply_markup=back("protect_menu"))

    elif data == "show_replies":
        replies = cfg["auto_replies"]
        text = "لا توجد ردود." if not replies else "\n".join([f"• {k} ➜ {v}" for k, v in list(replies.items())[:50]])
        await query.edit_message_text(text, reply_markup=back("replies_menu"))

    elif data == "show_vips":
        vips = cfg["vip_users"]
        text = "لا يوجد VIP." if not vips else "\n".join([f"• {uid}" for uid in vips[:100]])
        await query.edit_message_text(text, reply_markup=back("vip_menu"))

    elif data == "vip_help":
        await query.edit_message_text("استخدم داخل القروب: /vip بالرد على العضو", reply_markup=back("vip_menu"))

    elif data == "leaderboard":
        xp_map = cfg["xp"]
        ranking = sorted(xp_map.items(), key=lambda x: int(x[1]), reverse=True)[:10]
        if not ranking:
            text = "لا توجد بيانات XP."
        else:
            lines = ["🏆 أفضل 10 لاعبين:\n"]
            for i, (uid, xp) in enumerate(ranking, start=1):
                lines.append(f"{i}- {uid} | XP: {xp} | {rank_from_xp(int(xp))}")
            text = "\n".join(lines)
        await query.edit_message_text(text, reply_markup=back("xp_menu"))

    elif data == "xp_info":
        await query.edit_message_text("كل رسالة مفيدة تعطي XP تلقائياً. استخدم /لفلي داخل القروب.", reply_markup=back("xp_menu"))

    elif data == "clan_create":
        await query.edit_message_text("استخدم داخل القروب: /انشاء_كلان اسم", reply_markup=back("clan_menu"))

    elif data == "clan_list":
        clans = cfg["clans"]
        text = "لا توجد كلانات." if not clans else "\n".join([f"• {name} | أعضاء: {len(info.get('members', []))}" for name, info in list(clans.items())[:50]])
        await query.edit_message_text(text, reply_markup=back("clan_menu"))

    elif data == "pin_now":
        try:
            msg = await context.bot.send_message(int(gid), cfg["note_text"])
            await context.bot.pin_chat_message(int(gid), msg.message_id, disable_notification=True)
            await query.edit_message_text("✅ تم التثبيت.", reply_markup=pin_menu_markup(gid))
        except Exception:
            await query.edit_message_text("تعذر التثبيت. تأكد من صلاحيات البوت.", reply_markup=pin_menu_markup(gid))

    elif data == "mod_help":
        await query.edit_message_text(
            "🛠️ أوامر المشرف بالعربي:\n\n"
            "/تنظيف 100\n/تحذير (رد)\n/كتم (رد)\n/حظر (رد)\n/تثبيت (رد)\n/فك_التثبيت\n"
            "/ايدي\n/احصائيات\n/اضف_رد كلمة الرد\n/حذف_رد كلمة\n/vip (رد)\n/لفلي\n"
            "/انشاء_كلان اسم\n/دخول_كلان اسم\n/خروج_كلان\n/كلاني\n/القوانين\n/ربط",
            reply_markup=back("mod_menu"),
        )

    elif data == "backup_make":
        make_backup()
        await query.edit_message_text("✅ تم إنشاء نسخة احتياطية.", reply_markup=backup_menu_markup())

    elif data == "backup_send":
        make_backup()
        with open(BACKUP_FILE, "rb") as f:
            await query.message.reply_document(
                document=InputFile(f, filename="arc_zone_backup.json"),
                caption="💾 النسخة الاحتياطية",
            )
        await query.edit_message_text("✅ تم إرسال النسخة.", reply_markup=backup_menu_markup())

    elif data == "test_welcome":
        fake_name = user.first_name
        text = format_welcome(cfg, fake_name, cfg.get("title") or "القروب", user.id)
        if cfg["welcome_png_enabled"]:
            xp = int(cfg["xp"].get(str(user.id), 0))
            png = make_welcome_png(fake_name, cfg.get("title") or "القروب", rank_from_xp(xp))
            await query.message.reply_photo(photo=png, caption=text, parse_mode=ParseMode.HTML)
        else:
            await query.message.reply_text(text, parse_mode=ParseMode.HTML)


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

    if waiting == "set_welcome_text":
        cfg["welcome_text"] = text
    elif waiting == "set_ai_chance" and text.isdigit():
        cfg["ai_reply_chance"] = max(1, min(100, int(text)))
    elif waiting == "add_badword":
        if text not in BADWORDS:
            BADWORDS.append(text)
            save_badwords(BADWORDS)
    elif waiting == "del_badword":
        if text in BADWORDS:
            BADWORDS.remove(text)
            save_badwords(BADWORDS)
    elif waiting == "add_reply_key":
        st["temp_key"] = text.lower()
        st["waiting"] = "add_reply_value"
        await update.message.reply_text("أرسل الرد الآن.")
        return
    elif waiting == "add_reply_value":
        if st.get("temp_key"):
            cfg["auto_replies"][st["temp_key"]] = text
            st["temp_key"] = None
    elif waiting == "del_reply_key":
        cfg["auto_replies"].pop(text.lower(), None)
    elif waiting == "set_note":
        cfg["note_text"] = text
    elif waiting == "set_rules":
        cfg["rules_text"] = text
    elif waiting == "set_group_link":
        cfg["group_link"] = text
    elif waiting == "set_mute_after" and text.isdigit():
        cfg["mute_after"] = int(text)
    elif waiting == "set_ban_after" and text.isdigit():
        cfg["ban_after"] = int(text)

    st["waiting"] = None
    save_data()
    await update.message.reply_text("✅ تم الحفظ.", reply_markup=build_main_menu(user.id))


async def welcome_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return
    cfg = get_group(update.effective_chat.id)
    if not cfg or not cfg["welcome_enabled"]:
        return

    group_name = update.effective_chat.title or "القروب"
    for member in update.message.new_chat_members:
        text = format_welcome(cfg, member.first_name or "يا هلا", group_name, member.id)
        xp = int(cfg["xp"].get(str(member.id), 0))
        if cfg["welcome_png_enabled"]:
            try:
                png = make_welcome_png(member.first_name or "يا هلا", group_name, rank_from_xp(xp))
                await update.message.reply_photo(png, caption=text, parse_mode=ParseMode.HTML)
            except Exception:
                await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        elif cfg["welcome_photo"]:
            try:
                await update.message.reply_photo(cfg["welcome_photo"], caption=text, parse_mode=ParseMode.HTML)
            except Exception:
                await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    if cfg["auto_pin_note"] and cfg["note_text"]:
        try:
            msg = await context.bot.send_message(update.effective_chat.id, cfg["note_text"])
            await context.bot.pin_chat_message(update.effective_chat.id, msg.message_id, disable_notification=True)
        except Exception:
            pass


async def group_message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat = update.effective_chat
    user = update.effective_user
    if not chat or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP) or not user:
        return

    cfg = ensure_group(chat.id, chat.title or "")

    if not cfg["media_allowed"] and (
        update.message.photo or update.message.video or update.message.document or update.message.sticker
    ):
        if not await is_target_admin(context, chat.id, user.id):
            try:
                await update.message.delete()
            except Exception:
                pass
            return

    text = update.message.text or update.message.caption or ""
    uid = str(user.id)

    if text and len(text.strip()) > 1:
        cfg["xp"][uid] = int(cfg["xp"].get(uid, 0)) + 5
        save_data()

    is_admin_user = await is_target_admin(context, chat.id, user.id)

    if cfg["anti_spam"] and text and not is_admin_user:
        key = f"{chat.id}:{user.id}"
        now = datetime.now(timezone.utc)
        history = spam_tracker.get(key, [])
        history = [t for t in history if (now - t).total_seconds() <= 8]
        history.append(now)
        spam_tracker[key] = history

        if len(history) >= 6:
            try:
                await update.message.delete()
            except Exception:
                pass
            try:
                until = now + timedelta(minutes=5)
                await context.bot.restrict_chat_member(
                    chat.id,
                    user.id,
                    ChatPermissions(can_send_messages=False),
                    until_date=until,
                )
            except Exception:
                pass
            return

    if cfg["anti_links"] and text and not is_admin_user and LINK_RE.search(text):
        try:
            await update.message.delete()
        except Exception:
            pass
        try:
            await context.bot.send_message(chat.id, f"⚠️ تم حذف رابط من {user.first_name}")
        except Exception:
            pass
        return

    if cfg["anti_badwords"] and text and not is_admin_user:
        lowered = text.lower()
        for bad in BADWORDS:
            if bad.lower() in lowered:
                try:
                    await update.message.delete()
                except Exception:
                    pass
                try:
                    await context.bot.send_message(chat.id, f"⚠️ تم حذف كلمة ممنوعة من {user.first_name}")
                except Exception:
                    pass
                return

    if text:
        reply = cfg["auto_replies"].get(text.strip().lower())
        if reply:
            await update.message.reply_text(reply)
            return

    if text and cfg["ai_reply_enabled"]:
        chance = int(cfg.get("ai_reply_chance", 15))
        if random.randint(1, 100) <= chance:
            answer = await ai_answer(text)
            if answer:
                await update.message.reply_text(answer)


def main():
    if not TOKEN:
        raise ValueError("TOKEN غير موجود. حطه في Railway Variables")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ربط", bind_group))
    app.add_handler(CommandHandler("القوانين", cmd_rules))
    app.add_handler(CommandHandler("الترحيب", cmd_welcome))
    app.add_handler(CommandHandler("ايدي", cmd_id))
    app.add_handler(CommandHandler("احصائيات", cmd_stats))
    app.add_handler(CommandHandler("تنظيف", clean))
    app.add_handler(CommandHandler("تحذير", warn))
    app.add_handler(CommandHandler("كتم", mute))
    app.add_handler(CommandHandler("حظر", ban))
    app.add_handler(CommandHandler("تثبيت", pin_msg))
    app.add_handler(CommandHandler("فك_التثبيت", unpin_msg))
    app.add_handler(CommandHandler("اضف_رد", add_reply_cmd))
    app.add_handler(CommandHandler("حذف_رد", del_reply_cmd))
    app.add_handler(CommandHandler("لفلي", my_level))
    app.add_handler(CommandHandler("vip", add_vip))
    app.add_handler(CommandHandler("انشاء_كلان", create_clan))
    app.add_handler(CommandHandler("دخول_كلان", join_clan))
    app.add_handler(CommandHandler("خروج_كلان", leave_clan))
    app.add_handler(CommandHandler("كلاني", clan_info))

    app.add_handler(CallbackQueryHandler(panel_buttons))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, handle_private))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_members))
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.CAPTION | filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.Sticker.ALL)
            & ~filters.COMMAND,
            group_message_router,
        )
    )

    print("🔥 ARC ZONE LEGEND BOT شغال")
    app.run_polling()


if __name__ == "__main__":
    main()
