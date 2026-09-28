# -*- coding: utf-8 -*-
"""
ربات بازی جنگ‌های صلیبی — نسخه کامل تک‌فایلی فارسی
==================================================
همه‌چیز در یک فایل:
  • کاتالوگ دارایی با ویرایش کامل
  • ویرایش per-country (کشور خاص)
  • تولید هفتگی با مصرف منابع
  • جنگ با کسر خودکار نیرو
  • سیستم تجارت کامل + نقشه
  • بیانیه و لشکرکشی با پیش‌نمایش
  • پنل ادمین کامل
  • تم جنگ‌های صلیبی

اجرا:  python app.py
"""

import heapq
import html
import json
import os
import re
import sqlite3
import sys
import threading
import time
import traceback

import telebot
from telebot import types

# ═══════════════════════════════════════════════════════════════════════════
# بخش ۱: پیکربندی
# ═══════════════════════════════════════════════════════════════════════════

CONFIG_FILE = 'bot_config.json'


def _load_config():
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
    cfg['token'] = os.environ.get('BOT_TOKEN') or cfg.get('token')
    cfg['admin_id'] = int(os.environ.get('ADMIN_ID') or cfg.get('admin_id') or 0)
    cfg['channel_id'] = os.environ.get('CHANNEL_ID') or cfg.get('channel_id')
    cfg['war_channel_id'] = (os.environ.get('WAR_CHANNEL_ID')
                              or cfg.get('war_channel_id') or cfg.get('channel_id'))
    if not cfg['token']:
        cfg['token'] = input("توکن ربات: ").strip()
    if not cfg['admin_id']:
        cfg['admin_id'] = int(input("شناسه عددی مالک: ").strip())
    if not cfg['channel_id']:
        cfg['channel_id'] = input("شناسه کانال خبری: ").strip()
    if not cfg['war_channel_id']:
        cfg['war_channel_id'] = cfg['channel_id']
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return cfg


_conf = _load_config()
API_TOKEN = _conf['token']
ADMIN_ID = _conf['admin_id']
CHANNEL_ID = _conf['channel_id']
WAR_CHANNEL_ID = _conf['war_channel_id']

bot = telebot.TeleBot(API_TOKEN)

try :
    conn = sqlite3.connect('data/game_bot.db', check_same_thread=False)
except:
    conn = sqlite3.connect('game_bot.db', check_same_thread=False)

cursor = conn.cursor()
DB_LOCK = threading.RLock()

# ═══════════════════════════════════════════════════════════════════════════
# بخش ۲: ابزارهای دیتابیس
# ═══════════════════════════════════════════════════════════════════════════


def q(sql, params=()):
    with DB_LOCK:
        cur = conn.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def ex(sql, params=()):
    with DB_LOCK:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۳: رشته‌های فارسی
# ═══════════════════════════════════════════════════════════════════════════

STRINGS = {
    'err_generic': "خطایی رخ داد. دوباره تلاش کنید.",
    'not_admin': "شما ادمین نیستید.",
    'not_owner': "فقط مالک ربات می‌تواند این کار را انجام دهد.",
    'not_registered': "شما هنوز لرد نیستید. یک ادمین باید روی پیام شما در گروه ریپلای کند و /setlord بزند.",
    'not_lord': "فقط لرد این گروه می‌تواند این کار را انجام دهد.",
    'feature_disabled': "این بخش توسط مدیریت غیرفعال شده است.",
    'back': "🔙 بازگشت",
    'cancel': "❌ لغو",
    'confirm': "✅ تأیید",
    'prev': "➡️ قبلی",
    'next': "بعدی ⬅️",
    'yes': "بله",
    'no': "خیر",
    'none': "ندارد",
    'menu_welcome': "خوش آمدید قربان",
    'btn_assets': "💰 دارایی‌ها",
    'btn_upgrade': "🛠 ارتقا",
    'btn_weekly': "🔨 تولید هفتگی",
    'btn_war': "⚔️ لشکرکشی",
    'btn_statement': "🙌 بیانیه",
    'btn_treaty': "📜 معاهده",
    'btn_trade': "🚢 تجارت",
    'btn_private': "✉️ پیام خصوصی",
    'btn_panel': "🛡 پنل مدیریت",
    'assets_title': "💰 دارایی‌های کشور شما:\n\n{sections}",
    'sec_resource': "📦 منابع:",
    'sec_unit': "⚔️ ارتش:",
    'sec_building': "🏭 ساختمان‌ها:",
    'upgrade_pick': "کدام ساختمون را ارتقا می‌دهید؟",
    'upgrade_confirm': "برای ارتقای {label} به سطح {level}:\n<blockquote>{costs}</blockquote>\n{sources}تأیید؟",
    'upgrade_sources': "🧾 منابع در دسترس:\n<blockquote>{balances}</blockquote>\n",
    'upgrade_insufficient': "💸 منابع کافی نیست.",
    'upgraded': "✅ {label} به سطح {level} ارتقا یافت.",
    'btn_upgrade_yes': "✅ بله، ارتقا بده",
    'weekly_title': "🔨 چرخه تولید هفتگی:\n<blockquote>✅ تولید:\n{lines}</blockquote>",
    'weekly_consumed': "\n🔻 مصرف منابع:\n<blockquote>{lines}</blockquote>",
    'weekly_scaled': "\n⚠️ به‌دلیل کمبود منابع، تولید فقط به میزان {pct}٪ انجام شد.",
    'weekly_no_inputs': "🚫 منابع کافی برای تولید وجود ندارد:\n<blockquote>{needs}</blockquote>",
    'weekly_empty': "🏭 هیچ ساختمون فعالی برای تولید ندارید.",
    'war_pick_type': "نوع لشکرکشی:",
    'war_land': "🐫 زمینی",
    'war_sea': "🚢 دریایی",
    'war_ask_troops': "⚔️ نیروهای اعزامی را انتخاب کنید:\n<blockquote>روی هر نیرو بزنید و تعداد بدهید.\nپس از اتمام «ادامه» را بزنید.</blockquote>\n🧾 انتخاب شما:\n<blockquote>{lines}</blockquote>📊 مجموع: {total}",
    'war_troops_none': "هیچ نیرویی انتخاب نشده",
    'war_troop_row': "• {name}: {n}",
    'war_ask_count': "تعداد {name} را وارد کنید (موجودی: {bal}):",
    'war_too_much': "بیشتر از موجودی است (موجودی: {bal}).",
    'war_no_troops': "حداقل یک نیرو انتخاب کنید.",
    'war_btn_done': "✅ ادامه",
    'war_ask_origin': "مبدأ لشکرکشی را وارد کنید:",
    'war_ask_dest': "مقصد لشکرکشی را وارد کنید:",
    'war_ask_time': "زمان رسیدن را وارد کنید:",
    'war_preview': "⚔️ <b>پیش‌نمایش لشکرکشی</b>\n<blockquote>{headline}</blockquote>\n\n📊 نیروهای اعزامی:\n<blockquote>{troops}</blockquote>\n\nفرستاده شود؟",
    'war_headline': "🔖 ارتش {src} به مقصد {dst} حرکت کرد ({kind})\n\n⚜️ فرمانده: {u}\n⌛️ زمان رسیدن: {when}",
    'war_deducted': "✅ {n} نیرو از ارتش شما کسر شد و لشکرکشی اعلام شد.\nادمین نتیجه را اعلام خواهد کرد.",
    'war_deduct_failed': "❌ کسر نیروها ممکن نشد.",
    'war_admin_report': "{headline}\n\n📊 نیروها:\n{troops}",
    'war_sent': "✅ لشکرکشی اعلام شد.",
    'war_cancelled': "🚫 لشکرکشی لغو شد.",
    'war_empty': "چیزی وارد نشد.",
    'panel_title': "🛡 <b>پنل مدیریت</b>\n<blockquote>👑 مالک: {owner}\n👤 ادمین‌ها: {admins}\n🏳 کشورها: {groups}\n⚙️ بخش‌های فعال: {on}/{total}</blockquote>",
    'panel_stats': "📊 آمار کلی",
    'panel_econ': "💰 اقتصاد",
    'panel_mil': "⚔️ نظامی",
    'panel_catalog': "🧩 کاتالوگ",
    'panel_countries': "🏳 کشورها",
    'panel_features': "⚙️ فعال/غیرفعال",
    'panel_log': "🧾 گزارش",
    'panel_reset': "♻️ بازنشانی",
    'panel_admins': "👑 مدیران",
    'log_title': "🧾 گزارش اقدامات (صفحه {p} از {n}):",
    'log_empty': "گزارشی ثبت نشده.",
    'log_row': "▫️ <b>{action}</b> — {actor}\n   {target}{detail}\n   🕓 {ts}",
    'trade_title': "🌍 تجارت جهانی — نوع را انتخاب کنید:",
    'trade_sea': "🚢 دریایی",
    'trade_land': "🐫 زمینی",
    'trade_no_home': "موقعیت {mode} شما تعیین نشده.",
    'trade_pick_dest': "مقصد را انتخاب کنید:",
    'trade_goods': "📦 کالاها را انتخاب کنید:\n<blockquote>{lines}</blockquote>\nحجم: {vol}",
    'trade_ask_amount': "مقدار {res} (موجودی: {bal}):",
    'trade_ask_ships': "تعداد {v} (در اختیار: {bal} | ظرفیت هرکدام: {cap}):",
    'trade_not_enough': "بیشتر از موجودی است.",
    'trade_confirm': "📜 خلاصه تجارت:\n<blockquote>🎯 مقصد: {dest}\n📦 کالاها:\n{goods}\n🧭 مسیر: {path}\n💰 هزینه: {cost}</blockquote>\nتأیید؟",
    'trade_send': "✅ ارسال پیشنهاد",
    'trade_sent': "📨 پیشنهاد تجارت #{tid} به {dest} ارسال شد.",
    'trade_offer': "📦 پیشنهاد تجارت #{tid}\n\n🌍 از: {sender}\n📦 کالاها:\n<blockquote>{goods}</blockquote>\n💰 هزینه: {cost}\n\nآیا قبول می‌کنید؟",
    'trade_accept': "✅ قبول",
    'trade_decline': "❌ رد",
    'trade_accepted': "✅ قبول شد! محموله حرکت کرد.",
    'trade_declined': "❌ رد شد.",
    'trade_choose_vehicles': "🚢 ناوگان تجاری خود را انتخاب کنید:\n<blockquote>{fleet}</blockquote>\n🧾 انتخاب شما:\n<blockquote>{lines}</blockquote>\n📦 حجم: {vol}\n🚛 ظرفیت: {cap}",
    'trade_route': "🧭 مسیر: {path}",
    'trade_ask_ship_count': "تعداد {v} (در اختیار: {bal} | ظرفیت هرکدام: {cap}):",
    'trade_ask_caravan_cost': "🐫 تعداد کاروان (در اختیار: {bal} | ظرفیت: {cap} | هزینه هرکدام: {p} پول):",
    'trade_not_enough_cap': "ظرفیت کافی نیست! حجم {vol} اما ظرفیت {cap}.",
    'feat_assets': "💰 دارایی",
    'feat_upgrade': "🛠 ارتقا",
    'feat_weekly': "🔨 تولید هفتگی",
    'feat_war': "⚔️ لشکرکشی",
    'feat_trade': "🚢 تجارت",
    'feat_statement': "🙌 بیانیه",
    'feat_treaty': "📜 معاهده",
    'feat_private': "✉️ پیام خصوصی",
    'feat_setlord': "👤 ثبت لرد",
    # کاتالوگ
    'cat_title': "🧩 کاتالوگ بازی",
    'cat_edit': "✏️ ویرایش",
    'cat_rename': "تغییر نام",
    'cat_default': "مقدار اولیه",
    'cat_output': "📈 تولید",
    'cat_costs': "💸 هزینه ارتقا",
    'cat_inputs': "🔻 مصرف تولید",
    'cat_hide': "🗑 حذف از بازی",
    'cat_unhide': "♻️ بازگرداندن",
    'cat_delete': "❌ حذف دائمی",
    'cat_add': "➕ افزودن نوع جدید",
    'cat_order': "🔀 ترتیب بخش‌ها",
    'cat_up': "⬆️ بالاتر",
    'cat_down': "⬇️ پایین‌تر",
    'cat_ask_key': "کلید انگلیسی (حروف کوچک و زیرخط):",
    'cat_ask_label': "نام نمایشی فارسی:",
    'cat_ask_default': "مقدار اولیه:",
    'cat_ask_output': "خروجی هر سطح در هفته:",
    'cat_ask_cost': "هزینه {res} برای هر ارتقا (۰ = بدون هزینه):",
    'cat_ask_input': "مصرف {res} در هر سطح در هفته (۰ = بدون مصرف):",
    'cat_ask_max': "سقف سطح (۰ = بدون سقف):",
    'cat_bad_number': "عدد معتبر نیست.",
    'cat_saved': "✅ ذخیره شد.",
    'cat_err_key': "❌ کلید نامعتبر. فقط حروف کوچک، عدد و زیرخط؛ با حرف شروع شود.",
    'cat_err_exists': "❌ این کلید قبلاً وجود دارد.",
    'cat_err_reserved': "❌ این کلید رزرو شده است.",
    'cat_err_unknown': "❌ چنین نوعی وجود ندارد.",
    'cat_err_engine': "❌ این کلید موتور بازی است و قابل حذف نیست.",
    'cat_err_in_transit': "❌ محموله‌ای در حال حمل این کالاست.",
    'country_assets': "🎛 دارایی هر کشور",
    'ca_pick': "کدام کشور؟",
    'ca_title': "🎛 <b>{g}</b>\n<blockquote>🚫 حذف‌شده: {off}\n⏸ خاموش: {paused}</blockquote>",
    'ca_kind': "🎛 {g} — {kind}",
    'ca_toggle': "روی هر مورد بزنید:",
    'ca_removed': "🚫 حذف شد از این کشور",
    'ca_restored': "✅ بازگردانده شد",
    'ca_paused': "⏸ خاموش شد",
    'ca_running': "▶️ روشن شد",
    'ca_clear': "♻️ حذف همه تنظیمات این کشور",
    'ca_cleared': "♻️ پاک شد ({n} مورد)",
    # نقشه تجارت
    'map_title': "🗺 نقشه‌ها:",
    'map_sea': "🚢 دریایی",
    'map_land': "🐫 زمینی",
    'map_nodes': "🗺 جاهای {mode} (صفحه {p}/{n}):",
    'map_edges': "🛣 مسیرهای {mode} (صفحه {p}/{n}):",
    'map_node': "📍 <b>{name}</b>\n<blockquote>🔑 {id}\n📁 {kind}\n🏠 {home}\n🪙 عوارض: {toll}\n👑 مالک: {owner}</blockquote>",
    'map_edge': "🛣 <b>{a}</b> ↔ <b>{b}</b>\n<blockquote>📏 طول: {units}\n⏱ زمان: {min} دقیقه</blockquote>",
    'map_yes': "بله",
    'map_no': "خیر",
    'map_add_node': "➕ افزودن جا",
    'map_add_edge': "➕ افزودن مسیر",
    'map_edit_units': "📏 طول مسیر",
    'map_edit_minutes': "⏱ زمان سفر (۰ = خودکار)",
    'map_rename': "✏️ تغییر نام",
    'map_set_kind': "📁 نوع",
    'map_set_home': "🏠 محل استقرار",
    'map_set_toll': "🪙 عوارض",
    'map_del_node': "❌ حذف این جا",
    'map_del_edge': "❌ حذف مسیر",
    'map_ask_id': "شناسه انگلیسی جای جدید:",
    'map_ask_name': "نام نمایشی:",
    'map_ask_units': "طول مسیر (عدد صحیح >= 1):",
    'map_ask_minutes': "زمان سفر به دقیقه (۰ = خودکار):",
    'map_ask_toll': "عوارض عبور (۰ = رایگان):",
    'map_saved': "✅ ذخیره شد.",
    'map_deleted': "🔥 حذف شد.",
    # تنظیمات تجارت
    'cfg_title': "⚙️ تنظیمات تجارت:",
    'cfg_journey': "⏱ سفر و کرایه",
    'cfg_capacity': "📦 ظرفیت و هزینه",
    'cfg_toll': "🛣 عوارض گذرگاه",
    'cfg_ask': "مقدار جدید برای {name} (فعلی: {val}):",
    'cfg_saved': "✅ ذخیره شد.",
    # عکس جنگ
    'wp_title': "🖼 عکس‌های لشکرکشی:",
    'wp_land': "🐫 زمینی",
    'wp_sea': "🚢 دریایی",
    'wp_set': "تنظیم‌شده",
    'wp_unset': "تنظیم‌نشده",
    'wp_ask': "عکس را بفرستید:",
    'wp_saved': "✅ ذخیره شد.",
    'wp_clear': "🗑 حذف عکس",
    'wp_not_photo': "این عکس نیست.",
    # آپ هفتگی ادمین
    'weekly_adm_done': "✅ آپ هفتگی برای {n} کشور انجام شد.",
    'weekly_adm_pick': "آپ هفتگی برای کدام کشور؟ (خالی = همه)",
}

def t(key, **kw):
    s = STRINGS.get(key, key)
    return s.format(**kw) if kw else s


def esc(x):
    return html.escape(str(x), quote=False) if x else x


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۴: داده‌های پایه (تم صلیبی)
# ═══════════════════════════════════════════════════════════════════════════

BUILTIN_RESOURCES = ('money', 'gold', 'iron', 'stones', 'wood', 'food', 'meat', 'clothes')
RESOURCE_DEFAULT = 2000

BUILTIN_UNITS = ('swordsmen', 'gunmen', 'cavalry_swordsmen', 'cavalry_gunmen',
                 'special_guard', 'medium_cannons', 'large_cannons',
                 'small_ships', 'medium_ships', 'large_ships', 'caravans')
UNIT_DEFAULT = 500

BUILTIN_BUILDINGS = (
    ('stone_factory', 'stones', 15),
    ('wood_factory', 'wood', 15),
    ('iron_factory', 'iron', 17),
    ('gold_mine', 'gold', 10),
    ('farm', 'food', 20),
    ('animal_farm', 'meat', 12),
    ('clothes_factory', 'clothes', 10),
    ('bank', 'money', 100),
    ('swordsmen_camp', 'swordsmen', 20),
    ('gunmen_camp', 'gunmen', 15),
    ('cavalry_swordsmen_camp', 'cavalry_swordsmen', 10),
    ('cavalry_gunmen_camp', 'cavalry_gunmen', 8),
    ('special_guard_camp', 'special_guard', 5),
    ('medium_cannon_factory', 'medium_cannons', 4),
    ('large_cannon_factory', 'large_cannons', 2),
    ('small_shipyard', 'small_ships', 3),
    ('medium_shipyard', 'medium_ships', 2),
    ('large_shipyard', 'large_ships', 1),
)
BUILDING_DEFAULT = 0

BUILTIN_COSTS = {
    'stone_factory': {'wood': 500, 'money': 500},
    'wood_factory': {'stones': 500, 'money': 500},
    'iron_factory': {'stones': 500, 'money': 500},
    'gold_mine': {'wood': 500, 'stones': 500, 'money': 500},
    'farm': {'wood': 500, 'stones': 500},
    'animal_farm': {'wood': 500, 'iron': 500, 'stones': 500},
    'clothes_factory': {'gold': 500, 'money': 500, 'stones': 500},
    'bank': {'stones': 500, 'iron': 500, 'gold': 500},
    'swordsmen_camp': {'money': 500, 'stones': 500, 'wood': 500},
    'gunmen_camp': {'money': 500, 'gold': 500, 'iron': 500},
    'cavalry_swordsmen_camp': {'iron': 500, 'gold': 250, 'stones': 500, 'money': 250},
    'cavalry_gunmen_camp': {'gold': 800, 'stones': 800, 'money': 500},
    'special_guard_camp': {'money': 1000, 'stones': 1000, 'wood': 1000},
    'medium_cannon_factory': {'iron': 500, 'money': 250, 'wood': 250},
    'large_cannon_factory': {'iron': 500, 'stones': 500, 'money': 250, 'gold': 200},
    'small_shipyard': {'iron': 200, 'wood': 200, 'money': 200},
    'medium_shipyard': {'iron': 500, 'wood': 500, 'money': 500},
    'large_shipyard': {'iron': 1000, 'wood': 1000, 'money': 1000},
}

BUILTIN_PRODUCTION_INPUTS = {
    'stone_factory':          {'money': 10},
    'wood_factory':           {'money': 10},
    'iron_factory':           {'money': 15, 'wood': 5},
    'gold_mine':              {'money': 30, 'wood': 10},
    'farm':                   {'money': 10, 'wood': 5},
    'animal_farm':            {'money': 20, 'food': 5},
    'clothes_factory':        {'money': 40, 'gold': 5},
    'bank':                   {},
    'swordsmen_camp':         {'iron': 20, 'money': 15, 'food': 5},
    'gunmen_camp':            {'iron': 15, 'wood': 10, 'money': 20},
    'cavalry_swordsmen_camp': {'iron': 20, 'food': 10, 'money': 30},
    'cavalry_gunmen_camp':    {'iron': 20, 'gold': 5, 'food': 10, 'money': 40},
    'special_guard_camp':     {'iron': 30, 'gold': 10, 'food': 15, 'money': 60},
    'medium_cannon_factory':  {'iron': 40, 'wood': 20, 'money': 50},
    'large_cannon_factory':   {'iron': 60, 'wood': 30, 'money': 80},
    'small_shipyard':         {'iron': 20, 'wood': 30, 'money': 25},
    'medium_shipyard':        {'iron': 40, 'wood': 60, 'money': 50},
    'large_shipyard':         {'iron': 80, 'wood': 100, 'money': 100},
}

LABELS = {
    'money': '🪙 دینار طلا', 'gold': '👑 طلای سلطنتی', 'iron': '⚒ آهن آهنگری',
    'stones': '🪨 سنگ قلعه', 'wood': '🌲 چوب بلوط', 'food': '🍞 آذوقه',
    'meat': '🍖 گوشت شکار', 'clothes': '🧵 زره پارچه‌ای',
    'swordsmen': '⚔️ پیاده‌نظام صلیبی', 'gunmen': '🏹 کماندار صلیبی',
    'cavalry_swordsmen': '🐎 شوالیه معبد', 'cavalry_gunmen': '🛡 شوالیه هاسپیتالر',
    'special_guard': '✝️ گارد مقدس پاپ', 'medium_cannons': '🎯 منجنیق',
    'large_cannons': '💣 منجنیق سنگین', 'small_ships': '⛵ کشتی بادبانی',
    'medium_ships': '🚢 گالری جنگی', 'large_ships': '🛳 کشتی جنگی سنگین',
    'caravans': '🐪 کاروان صلیبی',
    'stone_factory': '⛏ معدن سنگ', 'wood_factory': '🌲 هیزم‌شکن',
    'iron_factory': '⚒ آهنگری', 'gold_mine': '⛏ معدن طلا',
    'farm': '🌾 مزرعه', 'animal_farm': '🐄 دامداری',
    'clothes_factory': '🧵 کارگاه پارچه', 'bank': '🏦 خزانه سلطنتی',
    'swordsmen_camp': '⚔️ پادگان پیاده‌نظام', 'gunmen_camp': '🏹 میدان تیراندازی',
    'cavalry_swordsmen_camp': '🏰 اصطبل شوالیه معبد',
    'cavalry_gunmen_camp': '🏰 اصطبل شوالیه هاسپیتالر',
    'special_guard_camp': '⛪ مقر گارد مقدس',
    'medium_cannon_factory': '🏗 کارگاه منجنیق',
    'large_cannon_factory': '🏗 کارگاه منجنیق سنگین',
    'small_shipyard': '⚓ بندرگاه کوچک', 'medium_shipyard': '⚓ بندرگاه نظامی',
    'large_shipyard': '⚓ بندرگاه جنگی',
}


def label(key):
    return LABELS.get(key, key)


ENGINE_KEYS = frozenset({'money', 'small_ships', 'medium_ships', 'large_ships', 'caravans'})
RESERVED_COLS = frozenset({'user_id', 'group_id', 'treaties', 'home_sea', 'home_land'})
KEY_RE = re.compile(r'^[a-z][a-z0-9_]{1,30}$')
LEVEL_CEILING = 100

# ═══════════════════════════════════════════════════════════════════════════
# بخش ۵: نقشه تجارت (داده پایه)
# ═══════════════════════════════════════════════════════════════════════════

SEA_NODES = {
    'nat': ('ocean', True, 'اقیانوس اطلس شمالی'),
    'sat': ('ocean', True, 'اقیانوس اطلس جنوبی'),
    'ind': ('ocean', True, 'اقیانوس هند'),
    'npa': ('ocean', True, 'اقیانوس آرام شمالی'),
    'spa': ('ocean', True, 'اقیانوس آرام جنوبی'),
    'arc': ('ocean', True, 'اقیانوس منجمد شمالی'),
    'nor': ('sea', True, 'دریای شمال'),
    'bal': ('sea', True, 'دریای بالتیک'),
    'med': ('sea', True, 'دریای مدیترانه'),
    'bla': ('sea', True, 'دریای سیاه'),
    'red': ('sea', True, 'دریای سرخ'),
    'per': ('sea', True, 'خلیج فارس'),
    'car': ('sea', True, 'خلیج کارائیب'),
    'gmx': ('sea', True, 'خلیج مکزیک'),
    'scs': ('sea', True, 'دریای چین جنوبی'),
    'ecs': ('sea', True, 'دریای چین شرقی'),
    'gib': ('strait', False, 'تنگه جبل‌الطارق'),
    'bos': ('strait', False, 'تنگه بسفر'),
    'hor': ('strait', False, 'تنگه هرمز'),
    'bab': ('strait', False, 'تنگه باب‌المندب'),
    'mal': ('strait', False, 'تنگه مالاکا'),
    'ber': ('strait', False, 'تنگه برینگ'),
    'mag': ('strait', False, 'تنگه ماژلان'),
    'sue': ('canal', False, 'کانال سوئز'),
    'pan': ('canal', False, 'کانال پاناما'),
    'cgh': ('cape', False, 'دماغه امید نیک'),
    'chn': ('cape', False, 'دماغه هورن'),
}
SEA_EDGES = [
    ('nat', 'nor', 2), ('nor', 'bal', 2),
    ('nat', 'gib', 2), ('gib', 'med', 1),
    ('med', 'bos', 2), ('bos', 'bla', 1),
    ('med', 'sue', 2), ('sue', 'red', 1), ('red', 'bab', 2),
    ('bab', 'ind', 2), ('ind', 'hor', 1), ('hor', 'per', 1),
    ('ind', 'mal', 3), ('mal', 'scs', 1),
    ('nat', 'car', 4), ('car', 'gmx', 1), ('car', 'pan', 1), ('pan', 'spa', 2),
    ('sat', 'mag', 5), ('mag', 'spa', 3), ('sat', 'chn', 6), ('chn', 'spa', 4),
    ('sat', 'cgh', 5), ('cgh', 'ind', 5),
    ('scs', 'ecs', 2), ('ecs', 'npa', 3), ('npa', 'spa', 5),
    ('npa', 'ber', 4), ('ber', 'arc', 1), ('arc', 'nat', 5),
]
LAND_NODES = {
    'ibe': ('region', True, 'ایبریا'),
    'weu': ('region', True, 'اروپای غربی'),
    'eeu': ('region', True, 'اروپای شرقی'),
    'ana': ('region', True, 'آناتولی'),
    'lev': ('region', True, 'شام'),
    'egy': ('region', True, 'مصر'),
    'naf': ('region', True, 'شمال آفریقا'),
    'waf': ('region', True, 'غرب آفریقا'),
    'eaf': ('region', True, 'شرق آفریقا'),
    'ara': ('region', True, 'عربستان'),
    'prs': ('region', True, 'پارس'),
    'cas': ('region', True, 'آسیای میانه'),
    'hnd': ('region', True, 'هند'),
    'chi': ('region', True, 'چین'),
    'sin': ('pass', False, 'گذرگاه سینا'),
    'sah': ('pass', False, 'مسیر صحرا'),
    'cau': ('pass', False, 'دروازه قفقاز'),
    'zag': ('pass', False, 'دروازه زاگرس'),
    'khy': ('pass', False, 'گذرگاه خیبر'),
}
LAND_EDGES = [
    ('ibe', 'weu', 2), ('weu', 'eeu', 2), ('eeu', 'ana', 2), ('ana', 'lev', 2),
    ('lev', 'sin', 1), ('sin', 'egy', 1), ('lev', 'ara', 2), ('ara', 'egy', 2),
    ('egy', 'naf', 2), ('naf', 'ibe', 2), ('naf', 'sah', 2), ('sah', 'waf', 2),
    ('egy', 'eaf', 3), ('eaf', 'ara', 2),
    ('eeu', 'cau', 1), ('cau', 'prs', 2), ('lev', 'zag', 1), ('zag', 'prs', 1),
    ('prs', 'cas', 2), ('cas', 'pam', 3) if False else ('cas', 'chi', 3),
    ('prs', 'khy', 1), ('khy', 'hnd', 1), ('hnd', 'chi', 3),
]

# ═══════════════════════════════════════════════════════════════════════════
# بخش ۶: مقدار پیش‌فرض تنظیمات تجارت
# ═══════════════════════════════════════════════════════════════════════════

CONFIG_DEFAULTS = {
    'sea_min_per_unit': 30,
    'land_min_per_unit': 45,
    'fee_per_unit': 20,
    'cap_small': 500, 'cap_medium': 1500, 'cap_large': 4000,
    'cap_caravan': 250, 'caravan_cost': 50,
    'offer_expiry_min': 120,
}
# عوارض پیش‌فرض هر گذرگاه
TOLL_DEFAULTS = {
    'gib': 100, 'bos': 100, 'hor': 100, 'bab': 100, 'mal': 200,
    'ber': 100, 'mag': 150, 'sue': 500, 'pan': 500, 'cgh': 0, 'chn': 0,
    'sin': 50, 'sah': 100, 'cau': 100, 'zag': 100, 'khy': 100,
}

SHIPS = (
    ('s', 'small_ships', 'cap_small'),
    ('m', 'medium_ships', 'cap_medium'),
    ('l', 'large_ships', 'cap_large'),
)
CARAVANS = (('c', 'caravans', 'cap_caravan'),)
VEHICLES = {'sea': SHIPS, 'land': CARAVANS}
VEH_BY_CODE = {code: col for table in VEHICLES.values() for code, col, _ in table}
CAP_KEY = {col: cap for table in VEHICLES.values() for _, col, cap in table}

# ═══════════════════════════════════════════════════════════════════════════
# بخش ۷: راه‌اندازی دیتابیس
# ═══════════════════════════════════════════════════════════════════════════


def init_db():
    with DB_LOCK:
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            group_id INTEGER UNIQUE,
            treaties TEXT DEFAULT '',
            home_sea TEXT DEFAULT '',
            home_land TEXT DEFAULT ''
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS asset_catalog (
            key TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            position INTEGER DEFAULT 0,
            default_value INTEGER DEFAULT 0,
            builtin INTEGER DEFAULT 0,
            hidden INTEGER DEFAULT 0,
            produces TEXT DEFAULT '',
            output INTEGER DEFAULT 0,
            max_level INTEGER DEFAULT 0,
            tradeable INTEGER DEFAULT 0
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS asset_labels (
            key TEXT NOT NULL, lang TEXT NOT NULL, label TEXT NOT NULL,
            PRIMARY KEY (key, lang))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS asset_upgrade_costs (
            building TEXT NOT NULL, resource TEXT NOT NULL, amount INTEGER NOT NULL,
            PRIMARY KEY (building, resource))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS asset_production_inputs (
            building TEXT NOT NULL, resource TEXT NOT NULL, amount INTEGER NOT NULL,
            PRIMARY KEY (building, resource))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS asset_level_costs (
            building TEXT NOT NULL, level INTEGER NOT NULL, resource TEXT NOT NULL,
            amount INTEGER NOT NULL, PRIMARY KEY (building, level, resource))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS asset_level_output (
            building TEXT NOT NULL, level INTEGER NOT NULL, output INTEGER NOT NULL,
            PRIMARY KEY (building, level))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS asset_kind_order (
            kind TEXT PRIMARY KEY, position INTEGER NOT NULL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS asset_removed (
            key TEXT PRIMARY KEY)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS bot_admins (
            user_id INTEGER PRIMARY KEY, added_at INTEGER, username TEXT DEFAULT '')''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS bot_features (
            key TEXT PRIMARY KEY, enabled INTEGER DEFAULT 1)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY, value TEXT NOT NULL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS admin_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL, actor_id INTEGER NOT NULL,
            action TEXT NOT NULL, target TEXT DEFAULT '', detail TEXT DEFAULT '')''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS country_assets (
            group_id INTEGER NOT NULL, key TEXT NOT NULL,
            hidden INTEGER DEFAULT 0, paused INTEGER DEFAULT 0,
            PRIMARY KEY (group_id, key))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_group_id INTEGER NOT NULL, sender_user_id INTEGER NOT NULL,
            receiver_group_id INTEGER NOT NULL, receiver_user_id INTEGER NOT NULL,
            mode TEXT NOT NULL, goods TEXT NOT NULL, vehicles TEXT NOT NULL,
            route TEXT NOT NULL, leg_minutes TEXT NOT NULL, tolls TEXT DEFAULT '[]',
            leg INTEGER DEFAULT 0, fee_paid INTEGER DEFAULT 0,
            status TEXT DEFAULT 'offered', offered_at INTEGER,
            departed_at INTEGER, next_eta INTEGER,
            offer_chat_id INTEGER, offer_msg_id INTEGER,
            track_chat_id INTEGER, track_msg_id INTEGER)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS trade_config (
            key TEXT PRIMARY KEY, value INTEGER NOT NULL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS trade_settings (
            key TEXT PRIMARY KEY, value TEXT NOT NULL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS chokepoint_owners (
            node_id TEXT PRIMARY KEY, group_id INTEGER NOT NULL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS group_trade_modes (
            group_id INTEGER NOT NULL, mode TEXT NOT NULL,
            open INTEGER DEFAULT 1, PRIMARY KEY (group_id, mode))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS trade_nodes (
            id TEXT PRIMARY KEY, mode TEXT NOT NULL, kind TEXT NOT NULL,
            home INTEGER DEFAULT 0, position INTEGER DEFAULT 0, builtin INTEGER DEFAULT 0)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS trade_node_labels (
            node_id TEXT NOT NULL, lang TEXT NOT NULL, label TEXT NOT NULL,
            PRIMARY KEY (node_id, lang))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS trade_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT, mode TEXT NOT NULL,
            a TEXT NOT NULL, b TEXT NOT NULL, units INTEGER NOT NULL,
            minutes INTEGER DEFAULT 0, UNIQUE (mode, a, b))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS trade_map_removed (
            kind TEXT NOT NULL, ref TEXT NOT NULL, PRIMARY KEY (kind, ref))''')
        conn.commit()
    _ensure_asset_columns()
    _seed_catalog()
    _seed_map()
    _seed_trade_config()
    for key in FEATURES:
        ex("INSERT OR IGNORE INTO bot_features (key, enabled) VALUES (?, 1)", (key,))
    for kind, i in (('resource', 1), ('building', 2), ('unit', 3)):
        ex("INSERT OR IGNORE INTO asset_kind_order (kind, position) VALUES (?, ?)",
           (kind, i * 10))


def _ensure_asset_columns():
    with DB_LOCK:
        existing = {r[1] for r in cursor.execute("PRAGMA table_info(users)").fetchall()}
        rows = q("SELECT key, default_value FROM asset_catalog")
        for row in rows:
            if row['key'] in existing:
                continue
            key = row['key']
            if not KEY_RE.match(key):
                continue
            cursor.execute(
                f"ALTER TABLE users ADD COLUMN {key} INTEGER DEFAULT {int(row['default_value'])}")
        conn.commit()


def _seed_catalog():
    existing = q("SELECT COUNT(*) AS n FROM asset_catalog")[0]['n']
    if existing > 0:
        return
    for i, key in enumerate(BUILTIN_RESOURCES, 1):
        ex("INSERT INTO asset_catalog (key, kind, position, default_value, builtin, tradeable) "
           "VALUES (?, 'resource', ?, ?, 1, 1)", (key, i * 10, RESOURCE_DEFAULT))
        ex("INSERT OR IGNORE INTO asset_labels (key, lang, label) VALUES (?, 'fa', ?)",
           (key, label(key)))
    for i, key in enumerate(BUILTIN_UNITS, 1):
        ex("INSERT INTO asset_catalog (key, kind, position, default_value, builtin) "
           "VALUES (?, 'unit', ?, ?, 1)", (key, i * 10, UNIT_DEFAULT))
        ex("INSERT OR IGNORE INTO asset_labels (key, lang, label) VALUES (?, 'fa', ?)",
           (key, label(key)))
    for i, (key, produces, output) in enumerate(BUILTIN_BUILDINGS, 1):
        ex("INSERT INTO asset_catalog (key, kind, position, default_value, builtin, "
           "produces, output) VALUES (?, 'building', ?, 0, 1, ?, ?)",
           (key, i * 10, produces, output))
        ex("INSERT OR IGNORE INTO asset_labels (key, lang, label) VALUES (?, 'fa', ?)",
           (key, label(key)))
    for building, table in BUILTIN_COSTS.items():
        for res, amt in table.items():
            ex("INSERT OR IGNORE INTO asset_upgrade_costs (building, resource, amount) "
               "VALUES (?, ?, ?)", (building, res, amt))
    for building, table in BUILTIN_PRODUCTION_INPUTS.items():
        for res, amt in table.items():
            ex("INSERT OR IGNORE INTO asset_production_inputs (building, resource, amount) "
               "VALUES (?, ?, ?)", (building, res, amt))
    conn.commit()


def _seed_map():
    existing = q("SELECT COUNT(*) AS n FROM trade_nodes")[0]['n']
    if existing > 0:
        return
    for mode, nodes in (('sea', SEA_NODES), ('land', LAND_NODES)):
        for i, (nid, (kind, home, name)) in enumerate(nodes.items(), 1):
            ex("INSERT OR IGNORE INTO trade_nodes (id, mode, kind, home, position, builtin) "
               "VALUES (?, ?, ?, ?, ?, 1)", (nid, mode, kind, 1 if home else 0, i * 10))
            ex("INSERT OR IGNORE INTO trade_node_labels (node_id, lang, label) "
               "VALUES (?, 'fa', ?)", (nid, name))
    for mode, edges in (('sea', SEA_EDGES), ('land', LAND_EDGES)):
        for a, b, units in edges:
            a, b = (a, b) if a <= b else (b, a)
            ex("INSERT OR IGNORE INTO trade_edges (mode, a, b, units, minutes) "
               "VALUES (?, ?, ?, ?, 0)", (mode, a, b, units))
    conn.commit()


def _seed_trade_config():
    for k, v in CONFIG_DEFAULTS.items():
        ex("INSERT OR IGNORE INTO trade_config (key, value) VALUES (?, ?)", (k, v))
    for nid, amt in TOLL_DEFAULTS.items():
        ex("INSERT OR IGNORE INTO trade_config (key, value) VALUES (?, ?)",
           ('toll_' + nid, amt))


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۸: توابع کاتالوگ
# ═══════════════════════════════════════════════════════════════════════════

FEATURES = ('assets', 'upgrade', 'weekly', 'war', 'trade', 'statement',
            'treaty', 'private', 'setlord')


def _kind_case():
    order = q("SELECT kind, position FROM asset_kind_order ORDER BY position")
    ranked = {r['kind']: r['position'] for r in order}
    default = ('resource', 'building', 'unit')
    keys = sorted(('resource', 'unit', 'building'),
                  key=lambda k: (ranked.get(k, 999), default.index(k)))
    return "CASE kind " + ' '.join(f"WHEN '{k}' THEN {i}" for i, k in enumerate(keys)) + " ELSE 99 END"


def cat_entries(kind=None, include_hidden=False):
    sql = "SELECT * FROM asset_catalog"
    where, params = [], []
    if kind:
        where.append("kind=?")
        params.append(kind)
    if not include_hidden:
        where.append("hidden=0")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {_kind_case()}, position, key"
    return q(sql, tuple(params))


def cat_keys(kind=None, include_hidden=False):
    return tuple(r['key'] for r in cat_entries(kind, include_hidden))


def cat_all_keys(include_hidden=False):
    return cat_keys(None, include_hidden)


def cat_entry(key):
    rows = q("SELECT * FROM asset_catalog WHERE key=?", (key,))
    return rows[0] if rows else None


def cat_label(key):
    rows = q("SELECT label FROM asset_labels WHERE key=? AND lang='fa'", (key,))
    return rows[0]['label'] if rows else label(key)


def cat_defaults():
    return {r['key']: r['default_value'] for r in cat_entries(None, True)}


def cat_upgrade_cost(building, level=None):
    visible = set(cat_keys('resource'))
    if level is not None:
        rows = q("SELECT resource, amount FROM asset_level_costs "
                 "WHERE building=? AND level=?", (building, int(level)))
        if rows:
            return {r['resource']: r['amount'] for r in rows
                    if r['amount'] > 0 and r['resource'] in visible}
    rows = q("SELECT resource, amount FROM asset_upgrade_costs WHERE building=?",
             (building,))
    return {r['resource']: r['amount'] for r in rows
            if r['amount'] > 0 and r['resource'] in visible}


def cat_production_inputs(building, level=None):
    visible = set(cat_keys('resource'))
    rows = q("SELECT resource, amount FROM asset_production_inputs WHERE building=?",
             (building,))
    return {r['resource']: r['amount'] for r in rows
            if r['amount'] > 0 and r['resource'] in visible}


def cat_production():
    out = []
    visible = set(cat_all_keys())
    for row in cat_entries('building'):
        if row['produces'] and row['output'] > 0 and row['produces'] in visible:
            out.append((row['key'], row['produces'], row['output']))
    return out


def cat_output_at_level(building, level):
    if level <= 0:
        return 0
    row = cat_entry(building)
    if not row:
        return 0
    flat = row['output']
    total = flat * level
    tuned = q("SELECT level, output FROM asset_level_output WHERE building=? AND level<=?",
              (building, int(level)))
    for tr in tuned:
        total += tr['output'] - flat
    return max(0, total)


def cat_inputs_at_level(building, level):
    if level <= 0:
        return {}
    per = cat_production_inputs(building)
    return {res: amt * level for res, amt in per.items()}


def cat_max_level(building):
    row = cat_entry(building)
    return row['max_level'] if row else 0


def cat_at_max(building, level):
    cap = cat_max_level(building)
    return bool(cap) and int(level) >= cap


def cat_tradeable():
    return tuple(r['key'] for r in cat_entries('resource') if r['tradeable'])


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۹: ادمین‌ها، ویژگی‌ها، لاگ
# ═══════════════════════════════════════════════════════════════════════════


def feature_enabled(key):
    rows = q("SELECT enabled FROM bot_features WHERE key=?", (key,))
    return bool(rows[0]['enabled']) if rows else True


def set_feature(key, enabled):
    ex("INSERT OR REPLACE INTO bot_features (key, enabled) VALUES (?, ?)",
       (key, 1 if enabled else 0))


def is_admin(user_id):
    if int(user_id) == ADMIN_ID:
        return True
    return bool(q("SELECT 1 FROM bot_admins WHERE user_id=?", (int(user_id),)))


def is_owner(user_id):
    return int(user_id) == ADMIN_ID


def admin_ids():
    ids = [ADMIN_ID]
    for r in q("SELECT user_id FROM bot_admins ORDER BY added_at"):
        if r['user_id'] != ADMIN_ID:
            ids.append(r['user_id'])
    return ids


def log_action(actor_id, action, target='', detail=''):
    ex("INSERT INTO admin_log (ts, actor_id, action, target, detail) VALUES (?, ?, ?, ?, ?)",
       (int(time.time()), int(actor_id), action, str(target), str(detail)))


def get_setting(key, default=''):
    rows = q("SELECT value FROM bot_settings WHERE key=?", (key,))
    return rows[0]['value'] if rows else default


def set_setting(key, value):
    if value is None or value == '':
        ex("DELETE FROM bot_settings WHERE key=?", (key,))
    else:
        ex("INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)",
           (key, str(value)))


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۱۰: کمک‌کننده‌های عمومی
# ═══════════════════════════════════════════════════════════════════════════


def get_lord(group_id):
    rows = q("SELECT user_id FROM users WHERE group_id=?", (group_id,))
    return rows[0]['user_id'] if rows else None


def is_lord(group_id, user_id):
    return bool(q("SELECT 1 FROM users WHERE group_id=? AND user_id=?",
                  (group_id, user_id)))


def user_link(user_id):
    try:
        chat = bot.get_chat(user_id)
        name = (chat.first_name or '') + (' ' + chat.last_name if chat.last_name else '')
        return f"<a href='tg://user?id={user_id}'>{esc(name.strip())}</a>"
    except Exception:
        return str(user_id)


def group_title(group_id):
    try:
        return bot.get_chat(group_id).title or str(group_id)
    except Exception:
        return str(group_id)


def get_balances(group_id, columns):
    if not columns:
        return {}
    with DB_LOCK:
        cur = conn.execute(
            f"SELECT {', '.join(columns)} FROM users WHERE group_id=?", (group_id,))
        row = cur.fetchone()
    if row is None:
        return None
    return dict(zip(columns, row))


def send(chat_id, text, **kw):
    try:
        kw.setdefault('parse_mode', 'HTML')
        return bot.send_message(chat_id, text, **kw)
    except Exception:
        traceback.print_exc()


def answer(call, text=None, alert=False):
    try:
        bot.answer_callback_query(call.id, text, show_alert=alert)
    except Exception:
        pass


def edit(call, text, markup=None):
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                              reply_markup=markup, parse_mode='HTML')
    except Exception:
        send(call.message.chat.id, text, reply_markup=markup)


def back_btn(markup, target='menu:home'):
    markup.add(types.InlineKeyboardButton(t('back'), callback_data=target))
    return markup


def next_step(message, user_id, fn):
    def wrapper(msg):
        if msg.from_user is None or msg.from_user.id != user_id:
            bot.register_next_step_handler(message, wrapper)
            return
        fn(msg)
    bot.register_next_step_handler(message, wrapper)


def ask_number(chat_id, user_id, anchor_msg, prompt, done, minimum=None):
    """پرسیدن یک عدد صحیح. اگر minimum داده بشه، حتماً >= اون."""
    send(chat_id, prompt)

    def on_text(msg):
        try:
            val = int((msg.text or '').strip())
            if minimum is not None and val < minimum:
                raise ValueError
        except (ValueError, AttributeError):
            send(chat_id, t('cat_bad_number'))
            next_step(anchor_msg, user_id, on_text)
            return
        done(val)

    next_step(anchor_msg, user_id, on_text)


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۱۱: دارایی‌های هر کشور (country_assets)
# ═══════════════════════════════════════════════════════════════════════════


def ca_hidden(group_id):
    return frozenset(r['key'] for r in
                     q("SELECT key FROM country_assets WHERE group_id=? AND hidden=1",
                       (group_id,)))


def ca_paused(group_id):
    return frozenset(r['key'] for r in
                     q("SELECT key FROM country_assets WHERE group_id=? AND paused=1",
                       (group_id,)))


def ca_is_hidden(group_id, key):
    return key in ca_hidden(group_id)


def ca_is_paused(group_id, key):
    return key in ca_paused(group_id)


def ca_keys_for(group_id, kind=None):
    gone = ca_hidden(group_id)
    return tuple(k for k in cat_keys(kind) if k not in gone)


def ca_production_for(group_id):
    gone = ca_hidden(group_id)
    off = ca_paused(group_id)
    return [(b, p, o) for b, p, o in cat_production()
            if b not in gone and b not in off and p not in gone]


def ca_set(group_id, key, field, value):
    if field not in ('hidden', 'paused'):
        raise ValueError(field)
    with DB_LOCK:
        conn.execute(
            "INSERT INTO country_assets (group_id, key, hidden, paused) VALUES (?, ?, 0, 0) "
            "ON CONFLICT(group_id, key) DO NOTHING", (group_id, key))
        conn.execute(f"UPDATE country_assets SET {field}=? WHERE group_id=? AND key=?",
                     (1 if value else 0, group_id, key))
        conn.execute("DELETE FROM country_assets WHERE group_id=? AND key=? "
                     "AND hidden=0 AND paused=0", (group_id, key))
        conn.commit()


def ca_clear(group_id):
    cnt = q("SELECT COUNT(*) AS n FROM country_assets WHERE group_id=?",
            (group_id,))[0]['n']
    ex("DELETE FROM country_assets WHERE group_id=?", (group_id,))
    return cnt


def ca_overrides(group_id):
    rows = q("SELECT hidden, paused FROM country_assets WHERE group_id=?", (group_id,))
    return (sum(1 for r in rows if r['hidden']),
            sum(1 for r in rows if r['paused']))


def ca_forget(key):
    ex("DELETE FROM country_assets WHERE key=?", (key,))


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۱۲: نقشه تجارت — خواندن/نوشتن
# ═══════════════════════════════════════════════════════════════════════════


def map_nodes(mode):
    rows = q("SELECT id, kind, home FROM trade_nodes WHERE mode=? ORDER BY position, id",
             (mode,))
    out = {}
    for r in rows:
        names = q("SELECT lang, label FROM trade_node_labels WHERE node_id=?", (r['id'],))
        name_map = {n['lang']: n['label'] for n in names}
        out[r['id']] = {'kind': r['kind'], 'home': bool(r['home']),
                        'names': name_map}
    return out


def map_node(mode, nid):
    return map_nodes(mode).get(nid)


def map_mode_of(nid):
    rows = q("SELECT mode FROM trade_nodes WHERE id=?", (nid,))
    return rows[0]['mode'] if rows else None


def map_name(nid):
    rows = q("SELECT label FROM trade_node_labels WHERE node_id=? AND lang='fa'", (nid,))
    return rows[0]['label'] if rows else nid


def map_edges(mode):
    return q("SELECT a, b, units, minutes FROM trade_edges WHERE mode=? ORDER BY a, b",
             (mode,))


def map_edge(mode, a, b):
    a, b = (a, b) if a <= b else (b, a)
    rows = q("SELECT a, b, units, minutes FROM trade_edges "
             "WHERE mode=? AND a=? AND b=?", (mode, a, b))
    return rows[0] if rows else None


def map_edge_ref(mode, a, b):
    a, b = (a, b) if a <= b else (b, a)
    return f"{mode}:{a}:{b}"


def map_chokepoints():
    out = []
    for mode in ('sea', 'land'):
        for nid, n in map_nodes(mode).items():
            if n['kind'] in ('strait', 'canal', 'pass'):
                out.append(nid)
    return out


def map_adjacency(mode):
    out = {nid: [] for nid in map_nodes(mode)}
    for e in map_edges(mode):
        if e['a'] in out and e['b'] in out:
            out[e['a']].append((e['b'], e['units']))
            out[e['b']].append((e['a'], e['units']))
    return out


def map_add_node(mode, nid, kind, home, name):
    if not KEY_RE.match(nid):
        raise ValueError('bad_key')
    if q("SELECT 1 FROM trade_nodes WHERE id=?", (nid,)):
        raise ValueError('exists')
    with DB_LOCK:
        rows = q("SELECT COALESCE(MAX(position), 0) AS p FROM trade_nodes WHERE mode=?",
                 (mode,))
        pos = (rows[0]['p'] if rows else 0) + 10
        conn.execute("INSERT INTO trade_nodes (id, mode, kind, home, position, builtin) "
                     "VALUES (?, ?, ?, ?, ?, 0)",
                     (nid, mode, kind, 1 if home else 0, pos))
        conn.execute("DELETE FROM trade_map_removed WHERE kind='node' AND ref=?", (nid,))
        conn.commit()
    ex("INSERT OR REPLACE INTO trade_node_labels (node_id, lang, label) VALUES (?, 'fa', ?)",
       (nid, name))


def map_set_node(mode, nid, **fields):
    sets, params = [], []
    if 'kind' in fields:
        sets.append("kind=?")
        params.append(fields['kind'])
    if 'home' in fields:
        sets.append("home=?")
        params.append(1 if fields['home'] else 0)
    if not sets:
        return
    params.append(nid)
    ex(f"UPDATE trade_nodes SET {', '.join(sets)} WHERE id=?", params)


def map_set_name(nid, name):
    ex("INSERT OR REPLACE INTO trade_node_labels (node_id, lang, label) VALUES (?, 'fa', ?)",
       (nid, name))


def map_remove_node(nid):
    with DB_LOCK:
        conn.execute("DELETE FROM trade_edges WHERE a=? OR b=?", (nid, nid))
        conn.execute("DELETE FROM trade_node_labels WHERE node_id=?", (nid,))
        conn.execute("DELETE FROM trade_nodes WHERE id=?", (nid,))
        conn.execute("UPDATE users SET home_sea='' WHERE home_sea=?", (nid,))
        conn.execute("UPDATE users SET home_land='' WHERE home_land=?", (nid,))
        conn.execute("DELETE FROM chokepoint_owners WHERE node_id=?", (nid,))
        conn.execute("INSERT OR REPLACE INTO trade_config (key, value) VALUES (?, 0)",
                     ('toll_' + nid,))
        conn.commit()
    ex("INSERT OR IGNORE INTO trade_map_removed (kind, ref) VALUES ('node', ?)", (nid,))


def map_add_edge(mode, a, b, units, minutes=0):
    if a == b:
        raise ValueError('self')
    a, b = (a, b) if a <= b else (b, a)
    if map_edge(mode, a, b):
        raise ValueError('exists')
    ex("INSERT INTO trade_edges (mode, a, b, units, minutes) VALUES (?, ?, ?, ?, ?)",
       (mode, a, b, int(units), int(minutes)))
    ex("DELETE FROM trade_map_removed WHERE kind='edge' AND ref=?",
       (map_edge_ref(mode, a, b),))


def map_set_edge(mode, a, b, units=None, minutes=None):
    a, b = (a, b) if a <= b else (b, a)
    sets, params = [], []
    if units is not None:
        sets.append("units=?")
        params.append(int(units))
    if minutes is not None:
        sets.append("minutes=?")
        params.append(max(0, int(minutes)))
    if not sets:
        return
    params += [mode, a, b]
    ex(f"UPDATE trade_edges SET {', '.join(sets)} WHERE mode=? AND a=? AND b=?", params)


def map_remove_edge(mode, a, b):
    a, b = (a, b) if a <= b else (b, a)
    ex("DELETE FROM trade_edges WHERE mode=? AND a=? AND b=?", (mode, a, b))
    ex("INSERT OR IGNORE INTO trade_map_removed (kind, ref) VALUES ('edge', ?)",
       (map_edge_ref(mode, a, b),))


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۱۳: تنظیمات تجارت
# ═══════════════════════════════════════════════════════════════════════════


def cfg(key):
    rows = q("SELECT value FROM trade_config WHERE key=?", (key,))
    return rows[0]['value'] if rows else CONFIG_DEFAULTS.get(key, 0)


def set_cfg(key, value):
    ex("INSERT OR REPLACE INTO trade_config (key, value) VALUES (?, ?)",
       (key, int(value)))


def toll_of(nid):
    return cfg('toll_' + nid)


def owner_of(nid):
    rows = q("SELECT group_id FROM chokepoint_owners WHERE node_id=?", (nid,))
    return rows[0]['group_id'] if rows else None


def set_owner(nid, gid):
    if gid:
        ex("INSERT OR REPLACE INTO chokepoint_owners (node_id, group_id) VALUES (?, ?)",
           (nid, gid))
    else:
        ex("DELETE FROM chokepoint_owners WHERE node_id=?", (nid,))


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۱۴: روتینگ
# ═══════════════════════════════════════════════════════════════════════════


def _dijkstra(adj, src, dst, blocked=frozenset(), cost_fn=None):
    if src in blocked or dst in blocked or src not in adj or dst not in adj:
        return None
    dist = {src: 0}
    prev = {}
    pq = [(0, src)]
    done = set()
    while pq:
        d, u = heapq.heappop(pq)
        if u in done:
            continue
        done.add(u)
        if u == dst:
            path = [dst]
            while path[-1] != src:
                path.append(prev[path[-1]])
            return d, path[::-1]
        for v, w in adj[u]:
            if v in blocked or v in done:
                continue
            nd = d + (cost_fn(u, v, w) if cost_fn else w)
            if nd < dist.get(v, float('inf')):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    return None


def _route_info(mode, path, label, sender_gid=None):
    mpu = cfg('sea_min_per_unit' if mode == 'sea' else 'land_min_per_unit')
    legs = [map_edge(mode, path[i], path[i + 1]) or {'units': 0, 'minutes': 0}
            for i in range(len(path) - 1)]
    leg_units = [l['units'] for l in legs]
    leg_minutes = [l['minutes'] if l['minutes'] > 0 else l['units'] * mpu for l in legs]
    units = sum(leg_units)
    tolls = []
    for nid in path:
        amt = toll_of(nid)
        if amt > 0:
            if sender_gid is not None and owner_of(nid) == sender_gid:
                amt = 0
            if amt > 0:
                tolls.append((nid, amt))
    base_fee = units * cfg('fee_per_unit')
    toll_total = sum(a for _, a in tolls)
    return {
        'label': label, 'path': path, 'units': units,
        'minutes': sum(leg_minutes), 'leg_minutes': leg_minutes,
        'base_fee': base_fee, 'tolls': tolls, 'toll_total': toll_total,
        'money': base_fee + toll_total,
    }


def find_routes(mode, src, dst, sender_gid=None):
    if src == dst:
        return []
    adj = map_adjacency(mode)
    fee = cfg('fee_per_unit')
    tolled = frozenset(n for n in map_nodes(mode) if toll_of(n) > 0)
    candidates = []
    r = _dijkstra(adj, src, dst)
    if r:
        candidates.append((r[1], 'fast'))
    r = _dijkstra(adj, src, dst, blocked=tolled)
    if r:
        candidates.append((r[1], 'free'))
    r = _dijkstra(adj, src, dst,
                  cost_fn=lambda u, v, w: (w * fee + (0 if sender_gid and owner_of(v) == sender_gid else toll_of(v))) * 1000 + w)
    if r:
        candidates.append((r[1], 'cheap'))
    out, seen = [], set()
    for path, label in candidates:
        key = tuple(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(_route_info(mode, path, label, sender_gid))
    return out


def path_names(mode, path):
    return ' ← '.join(map_name(nid) for nid in path)


def dur_text(minutes):
    h, m = divmod(int(minutes), 60)
    return f"{h} ساعت و {m} دقیقه" if h else f"{m} دقیقه"

# ═══════════════════════════════════════════════════════════════════════════
# بخش ۱۵: منوی اصلی و دارایی‌ها (بازیکن)
# ═══════════════════════════════════════════════════════════════════════════


def send_main_menu(chat_id, user_id):
    if not is_lord(chat_id, user_id) and not is_admin(user_id):
        send(chat_id, t('not_registered'))
        return
    markup = types.InlineKeyboardMarkup(row_width=2)
    for key, lbl in (
        ('assets', t('btn_assets')), ('upgrade', t('btn_upgrade')),
        ('weekly', t('btn_weekly')), ('war', t('btn_war')),
        ('trade', t('btn_trade')), ('statement', t('btn_statement')),
        ('treaty', t('btn_treaty')), ('private', t('btn_private')),
    ):
        if feature_enabled(key):
            markup.add(types.InlineKeyboardButton(lbl, callback_data=f'menu:{key}'))
    if is_admin(user_id):
        markup.add(types.InlineKeyboardButton(t('btn_panel'), callback_data='ap:home'))
    send(chat_id, t('menu_welcome'), reply_markup=markup)


def show_assets(chat_id, group_id):
    all_keys = list(cat_all_keys())
    balances = get_balances(group_id, all_keys)
    if balances is None:
        send(chat_id, t('not_registered'))
        return
    gone = ca_hidden(group_id)
    lines = [t('sec_resource')]
    for k in cat_keys('resource'):
        if k in gone:
            continue
        lines.append(f"  {cat_label(k)}: {balances.get(k, 0):,}")
    lines.append('')
    lines.append(t('sec_unit'))
    for k in cat_keys('unit'):
        if k in gone:
            continue
        lines.append(f"  {cat_label(k)}: {balances.get(k, 0):,}")
    lines.append('')
    lines.append(t('sec_building'))
    for k in cat_keys('building'):
        if k in gone:
            continue
        lines.append(f"  {cat_label(k)}: سطح {balances.get(k, 0)}")
    text = t('assets_title', sections='\n'.join(lines))
    markup = types.InlineKeyboardMarkup()
    back_btn(markup, 'menu:home')
    send(chat_id, text, reply_markup=markup)


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۱۶: ارتقا
# ═══════════════════════════════════════════════════════════════════════════


def upgrade_menu(chat_id, group_id):
    buildings = ca_keys_for(group_id, 'building')
    if not buildings:
        send(chat_id, t('weekly_empty'))
        return
    balances = get_balances(group_id, list(buildings))
    if balances is None:
        send(chat_id, t('not_registered'))
        return
    markup = types.InlineKeyboardMarkup(row_width=2)
    for k in buildings:
        lvl = balances.get(k, 0)
        cap = cat_max_level(k)
        suffix = f" ({lvl}/{cap})" if cap else f" ({lvl})"
        markup.add(types.InlineKeyboardButton(cat_label(k) + suffix,
                                              callback_data=f'up:c:{k}'))
    back_btn(markup, 'menu:home')
    send(chat_id, t('upgrade_pick'), reply_markup=markup)


def confirm_upgrade(call, key):
    row = cat_entry(key)
    if not row or row['kind'] != 'building' or row['hidden']:
        answer(call, t('err_generic'), alert=True)
        return
    group_id = call.message.chat.id
    if ca_is_hidden(group_id, key):
        answer(call, t('err_generic'), alert=True)
        return
    balances = get_balances(group_id, [key])
    if balances is None:
        answer(call, t('not_registered'), alert=True)
        return
    level = balances[key] or 0
    if cat_at_max(key, level):
        answer(call)
        send(group_id, f"🏁 {cat_label(key)} به سقف ({cat_max_level(key)}) رسیده.")
        return
    target = level + 1
    costs = cat_upgrade_cost(key, target)
    res_keys = list(costs.keys())
    res_bal = get_balances(group_id, res_keys) if res_keys else {}
    balances_text = '\n'.join(
        f"  {cat_label(r)}: {res_bal.get(r, 0):,}" for r in res_keys) if res_keys else ''
    costs_text = '\n'.join(
        f"  {cat_label(r)}: {amt:,}" for r, amt in costs.items()) or '  رایگان'
    text = t('upgrade_confirm',
             label=cat_label(key), level=target, costs=costs_text,
             sources=t('upgrade_sources', balances=balances_text) if res_keys else '')
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(t('btn_upgrade_yes'),
                                          callback_data=f'up:y:{key}'))
    back_btn(markup, 'menu:home')
    send(group_id, text, reply_markup=markup)


def do_upgrade(call, key):
    row = cat_entry(key)
    if not row or row['kind'] != 'building' or row['hidden']:
        answer(call, t('err_generic'), alert=True)
        return
    group_id = call.message.chat.id
    if ca_is_hidden(group_id, key):
        answer(call, t('err_generic'), alert=True)
        return
    with DB_LOCK:
        cur = conn.execute(f"SELECT {key} FROM users WHERE group_id=?", (group_id,))
        r = cur.fetchone()
        if r is None:
            answer(call, t('not_registered'), alert=True)
            return
        level = r[0] or 0
        if cat_at_max(key, level):
            answer(call)
            send(group_id, f"🏁 به سقف رسیده ({cat_max_level(key)}).")
            return
        target = level + 1
        costs = cat_upgrade_cost(key, target)
        cols = list(costs.keys())
        if cols:
            cur = conn.execute(
                f"SELECT {', '.join(cols)} FROM users WHERE group_id=?", (group_id,))
            have = cur.fetchone()
            for i, c in enumerate(cols):
                if have[i] < costs[c]:
                    answer(call, t('upgrade_insufficient'), alert=True)
                    return
        sets = [f"{key} = {key} + 1"]
        params = []
        for c, need in costs.items():
            sets.append(f"{c} = {c} - ?")
            params.append(need)
        params.append(group_id)
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE group_id=?", params)
        conn.commit()
    answer(call)
    send(group_id, t('upgraded', label=cat_label(key), level=target))


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۱۷: تولید هفتگی با مصرف منابع
# ═══════════════════════════════════════════════════════════════════════════


def weekly_update(chat_id, group_id, silent=False):
    plan = ca_production_for(group_id)
    if not plan:
        if not silent:
            send(chat_id, t('weekly_empty'))
        return None
    buildings = [b for b, _, _ in plan]
    balances = get_balances(group_id, buildings)
    if balances is None:
        if not silent:
            send(chat_id, t('not_registered'))
        return None
    outputs = {}
    inputs = {}
    for building, produces, _flat in plan:
        lvl = balances.get(building, 0) or 0
        if lvl <= 0:
            continue
        amount = cat_output_at_level(building, lvl)
        if amount <= 0:
            continue
        needs = cat_inputs_at_level(building, lvl)
        outputs[produces] = outputs.get(produces, 0) + amount
        for res, amt in needs.items():
            inputs[res] = inputs.get(res, 0) + amt
    if not outputs:
        if not silent:
            send(chat_id, t('weekly_empty'))
        return None
    all_cols = sorted(set(list(outputs) + list(inputs)))
    with DB_LOCK:
        cur = conn.execute(
            f"SELECT {', '.join(all_cols)} FROM users WHERE group_id=?", (group_id,))
        row = cur.fetchone()
        if row is None:
            return None
        have = dict(zip(all_cols, row))
        scale = 1.0
        for res, need in inputs.items():
            if need > 0:
                ratio = have.get(res, 0) / need
                if ratio < scale:
                    scale = ratio
        scale = max(0.0, min(1.0, scale))
        if scale <= 0 and inputs:
            if not silent:
                needs_text = '\n'.join(
                    f"  {cat_label(r)}: نیاز {n:,} | موجود {have.get(r, 0):,}"
                    for r, n in inputs.items())
                send(chat_id, t('weekly_no_inputs', needs=needs_text))
            return None
        actual_inputs = {k: int(v * scale) for k, v in inputs.items() if int(v * scale) > 0}
        actual_outputs = {k: int(v * scale) for k, v in outputs.items() if int(v * scale) > 0}
        if not actual_outputs:
            return None
        sets, params = [], []
        for c in actual_inputs:
            sets.append(f"{c} = {c} - ?")
            params.append(actual_inputs[c])
        for c in actual_outputs:
            sets.append(f"{c} = {c} + ?")
            params.append(actual_outputs[c])
        params.append(group_id)
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE group_id=?", params)
        conn.commit()
    out_lines = '\n'.join(f"  {cat_label(k)}: +{v:,}" for k, v in actual_outputs.items())
    text = t('weekly_title', lines=out_lines)
    if actual_inputs:
        in_lines = '\n'.join(f"  {cat_label(k)}: -{v:,}" for k, v in actual_inputs.items())
        text += t('weekly_consumed', lines=in_lines)
    if scale < 1.0:
        text += t('weekly_scaled', pct=int(scale * 100))
    if not silent:
        markup = types.InlineKeyboardMarkup()
        back_btn(markup, 'menu:home')
        send(chat_id, text, reply_markup=markup)
    return text


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۱۸: جنگ با کسر خودکار نیرو
# ═══════════════════════════════════════════════════════════════════════════

_war_drafts = {}


def _war_units():
    return [k for k in cat_keys('unit')
            if k not in ('small_ships', 'medium_ships', 'large_ships', 'caravans')]


def start_war(chat_id, user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(t('war_land'), callback_data='war:t:land'),
        types.InlineKeyboardButton(t('war_sea'), callback_data='war:t:sea'))
    back_btn(markup, 'menu:home')
    send(chat_id, t('war_pick_type'), reply_markup=markup)


def war_pick_type(call, kind):
    if kind not in ('land', 'sea'):
        answer(call, t('err_generic'))
        return
    user_id = call.from_user.id
    group_id = call.message.chat.id
    _war_drafts[user_id] = {
        'kind': 'war', 'chat_id': group_id, 'group_id': group_id,
        'type': kind, 'troops': {},
    }
    answer(call)
    war_send_troop_picker(user_id)


def war_send_troop_picker(user_id):
    draft = _war_drafts.get(user_id)
    if not draft:
        return
    units = _war_units()
    balances = get_balances(draft['group_id'], units) or {}
    markup = types.InlineKeyboardMarkup(row_width=2)
    for unit in units:
        have = balances.get(unit, 0)
        picked = draft['troops'].get(unit, 0)
        lbl = cat_label(unit)
        if picked:
            lbl += f" ({picked})"
        elif have == 0:
            continue
        markup.add(types.InlineKeyboardButton(lbl, callback_data=f'war:u:{unit}'))
    markup.add(
        types.InlineKeyboardButton(t('war_btn_done'), callback_data='war:ud'),
        types.InlineKeyboardButton(t('cancel'), callback_data='war:x'))
    if draft['troops']:
        lines = '\n'.join(t('war_troop_row', name=cat_label(k), n=v)
                          for k, v in draft['troops'].items())
    else:
        lines = t('war_troops_none')
    total = sum(draft['troops'].values())
    send(draft['chat_id'], t('war_ask_troops', lines=lines, total=total),
         reply_markup=markup)


def war_ask_count(call, unit):
    user_id = call.from_user.id
    draft = _war_drafts.get(user_id)
    if not draft or unit not in _war_units():
        answer(call, t('err_generic'))
        return
    balances = get_balances(draft['group_id'], [unit]) or {}
    have = balances.get(unit, 0)
    answer(call)
    send(draft['chat_id'], t('war_ask_count', name=cat_label(unit), bal=have))

    def on_count(msg):
        d = _war_drafts.get(user_id)
        if not d:
            return
        try:
            val = int((msg.text or '').strip())
        except (ValueError, AttributeError):
            send(d['chat_id'], t('war_empty'))
            return
        if val < 0:
            send(d['chat_id'], t('war_empty'))
        elif val > have:
            send(d['chat_id'], t('war_too_much', bal=have))
        elif val == 0:
            d['troops'].pop(unit, None)
        else:
            d['troops'][unit] = val
        war_send_troop_picker(user_id)

    next_step(call.message, user_id, on_count)


def war_troops_done(call):
    user_id = call.from_user.id
    draft = _war_drafts.get(user_id)
    if not draft:
        answer(call, t('err_generic'), alert=True)
        return
    if not draft['troops']:
        answer(call, t('war_no_troops'), alert=True)
        return
    answer(call)
    war_ask_field(user_id, 'origin', t('war_ask_origin'))


def war_ask_field(user_id, field, prompt):
    draft = _war_drafts.get(user_id)
    if not draft:
        return
    sent = send(draft['chat_id'], prompt)

    def on_answer(msg):
        d = _war_drafts.get(user_id)
        if not d or d.get('kind') != 'war':
            return
        val = (msg.text or '').strip()
        if not val:
            send(d['chat_id'], t('war_empty'))
            war_ask_field(user_id, field, prompt)
            return
        d[field] = esc(val)
        if field == 'origin':
            war_ask_field(user_id, 'destination', t('war_ask_dest'))
        elif field == 'destination':
            war_ask_field(user_id, 'when', t('war_ask_time'))
        else:
            war_preview(user_id)

    next_step(sent, user_id, on_answer)


def war_headline(draft, user_id):
    return t('war_headline',
             src=draft.get('origin', ''), dst=draft.get('destination', ''),
             kind=t('war_' + draft['type']), u=user_link(user_id),
             when=draft.get('when', ''))


def war_preview(user_id):
    draft = _war_drafts.get(user_id)
    if not draft:
        return
    troops = '\n'.join(t('war_troop_row', name=cat_label(k), n=v)
                       for k, v in draft['troops'].items())
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(t('confirm'), callback_data='war:ok'),
        types.InlineKeyboardButton(t('cancel'), callback_data='war:x'))
    send(draft['chat_id'],
         t('war_preview', headline=war_headline(draft, user_id), troops=troops),
         reply_markup=markup)


def war_deduct(group_id, troops):
    cols = [c for c, n in troops.items() if n > 0]
    if not cols:
        return True
    with DB_LOCK:
        cur = conn.execute(
            f"SELECT {', '.join(cols)} FROM users WHERE group_id=?", (group_id,))
        row = cur.fetchone()
        if row is None:
            return False
        for i, col in enumerate(cols):
            if row[i] < troops[col]:
                return False
        sets = ', '.join(f"{c} = {c} - ?" for c in cols)
        conn.execute(f"UPDATE users SET {sets} WHERE group_id=?",
                     [troops[c] for c in cols] + [group_id])
        conn.commit()
    return True


def war_send(call):
    user_id = call.from_user.id
    draft = _war_drafts.pop(user_id, None)
    if not draft or draft.get('kind') != 'war':
        answer(call, t('err_generic'), alert=True)
        return
    if not war_deduct(draft['group_id'], draft['troops']):
        answer(call)
        send(draft['chat_id'], t('war_deduct_failed'))
        return
    answer(call)
    headline = war_headline(draft, user_id)
    troops = '\n'.join(t('war_troop_row', name=cat_label(k), n=v)
                       for k, v in draft['troops'].items())
    # اطلاع به ادمین‌ها
    for uid in admin_ids():
        try:
            send(uid, t('war_admin_report', headline=headline, troops=troops))
        except Exception:
            pass
    # اعلام عمومی در کانال جنگ
    photo = get_setting('war_photo_' + draft['type'], '')
    try:
        if photo:
            bot.send_photo(WAR_CHANNEL_ID, photo, caption=headline, parse_mode='HTML')
        else:
            send(WAR_CHANNEL_ID, headline)
    except Exception:
        pass
    log_action(user_id, 'war', draft.get('destination', ''), draft['type'])
    total = sum(draft['troops'].values())
    send(draft['chat_id'], t('war_deducted', n=total))


def war_cancel(call):
    _war_drafts.pop(call.from_user.id, None)
    answer(call)
    send(call.message.chat.id, t('war_cancelled'))


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۱۹: تجارت کامل
# ═══════════════════════════════════════════════════════════════════════════

_trade_drafts = {}
_trade_ticker_started = False


def mode_open(group_id, mode):
    rows = q("SELECT open FROM group_trade_modes WHERE group_id=? AND mode=?",
             (group_id, mode))
    return bool(rows[0]['open']) if rows else True


def set_mode_open(group_id, mode, is_open):
    ex("INSERT OR REPLACE INTO group_trade_modes (group_id, mode, open) VALUES (?, ?, ?)",
       (group_id, mode, 1 if is_open else 0))


def start_trade(call):
    user_id = call.from_user.id
    group_id = call.message.chat.id
    _trade_drafts[user_id] = {'chat_id': group_id, 'group_id': group_id,
                              'goods': {}, 'vehicles': {}}
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for m in ('sea', 'land'):
        if mode_open(group_id, m):
            buttons.append(types.InlineKeyboardButton(t('trade_' + m),
                                                      callback_data=f'trade:m:{m}'))
    if not buttons:
        answer(call, "هر دو مسیر بسته است.", alert=True)
        return
    markup.add(*buttons)
    back_btn(markup, 'menu:home')
    answer(call)
    send(group_id, t('trade_title'), reply_markup=markup)


def trade_pick_mode(call, mode):
    user_id = call.from_user.id
    draft = _trade_drafts.get(user_id)
    if not draft:
        return
    draft['mode'] = mode
    group_id = draft['group_id']
    home_col = 'home_sea' if mode == 'sea' else 'home_land'
    home = get_balances(group_id, [home_col])
    if not home or not home[home_col]:
        answer(call)
        send(group_id, t('trade_no_home', mode=t('trade_' + mode)))
        return
    dests = [d for d in q(f"SELECT group_id FROM users WHERE group_id != ? AND {home_col} != ''",
                          (group_id,)) if mode_open(d['group_id'], mode)]
    if not dests:
        answer(call)
        send(group_id, "مقصدی در دسترس نیست.")
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for d in dests:
        markup.add(types.InlineKeyboardButton(
            group_title(d['group_id']),
            callback_data=f"trade:d:{d['group_id']}"))
    back_btn(markup, 'menu:home')
    answer(call)
    send(group_id, t('trade_pick_dest'), reply_markup=markup)


def trade_pick_dest(call, dest_gid):
    draft = _trade_drafts.get(call.from_user.id)
    if not draft:
        return
    draft['dest'] = dest_gid
    answer(call)
    trade_show_goods(call.from_user.id)


def trade_show_goods(user_id):
    draft = _trade_drafts.get(user_id)
    if not draft:
        return
    resources = cat_tradeable()
    markup = types.InlineKeyboardMarkup(row_width=2)
    for r in resources:
        amt = draft['goods'].get(r, 0)
        lbl = cat_label(r) + (f" ({amt})" if amt else '')
        markup.add(types.InlineKeyboardButton(lbl, callback_data=f'trade:g:{r}'))
    markup.add(types.InlineKeyboardButton(t('war_btn_done'), callback_data='trade:gd'))
    back_btn(markup, 'menu:home')
    if draft['goods']:
        lines = '\n'.join(f"• {cat_label(k)}: {v}" for k, v in draft['goods'].items())
    else:
        lines = t('none')
    vol = sum(draft['goods'].values())
    send(draft['chat_id'], t('trade_goods', lines=lines, vol=vol), reply_markup=markup)


def trade_ask_amount(call, resource):
    user_id = call.from_user.id
    draft = _trade_drafts.get(user_id)
    if not draft:
        return
    if resource not in cat_tradeable():
        answer(call, "این کالا قابل تجارت نیست.")
        return
    bal = (get_balances(draft['group_id'], [resource]) or {}).get(resource, 0)
    answer(call)
    send(draft['chat_id'], t('trade_ask_amount', res=cat_label(resource), bal=bal))

    def on_amt(msg):
        d = _trade_drafts.get(user_id)
        if not d:
            return
        try:
            val = int((msg.text or '').strip())
        except (ValueError, AttributeError):
            send(d['chat_id'], t('err_generic'))
            return
        if val < 0 or val > bal:
            send(d['chat_id'], t('trade_not_enough'))
        elif val == 0:
            d['goods'].pop(resource, None)
        else:
            d['goods'][resource] = val
        trade_show_goods(user_id)

    next_step(call.message, user_id, on_amt)


def trade_show_vehicles(user_id):
    draft = _trade_drafts.get(user_id)
    if not draft:
        return
    mode = draft['mode']
    vehicle_defs = VEHICLES[mode]
    vol = sum(draft['goods'].values())
    cap = sum(draft['vehicles'].get(col, 0) * cfg(cap_key)
              for _, col, cap_key in vehicle_defs)
    markup = types.InlineKeyboardMarkup(row_width=2)
    for code, col, _cap in vehicle_defs:
        n = draft['vehicles'].get(col, 0)
        lbl = cat_label(col) + (f" ({n})" if n else '')
        markup.add(types.InlineKeyboardButton(lbl, callback_data=f'trade:v:{code}'))
    markup.add(types.InlineKeyboardButton(t('war_btn_done'), callback_data='trade:vd'))
    back_btn(markup, 'menu:home')
    if draft['vehicles']:
        lines = '\n'.join(
            f"• {cat_label(col)}: {n} × {cfg(cap_key)} = {n * cfg(cap_key)}"
            for _, col, cap_key in vehicle_defs
            for n in [draft['vehicles'].get(col, 0)] if n)
    else:
        lines = '—'
    fleet_lines = '\n'.join(
        f"  {cat_label(col)}: ظرفیت {cfg(cap_key)} | موجودی {(get_balances(draft['group_id'], [col]) or {}).get(col, 0)}"
        for _, col, cap_key in vehicle_defs)
    send(draft['chat_id'],
         t('trade_choose_vehicles', fleet=fleet_lines, lines=lines, vol=vol, cap=cap),
         reply_markup=markup)


def trade_goods_done(call):
    draft = _trade_drafts.get(call.from_user.id)
    if not draft:
        return
    if not draft['goods']:
        answer(call, "حداقل یک کالا انتخاب کنید.", alert=True)
        return
    answer(call)
    trade_show_vehicles(call.from_user.id)


def trade_ask_vehicle_count(call, code):
    user_id = call.from_user.id
    draft = _trade_drafts.get(user_id)
    if not draft:
        return
    mode = draft['mode']
    col = VEH_BY_CODE.get(code)
    if not col or col not in [v[1] for v in VEHICLES[mode]]:
        answer(call, t('err_generic'))
        return
    bal = (get_balances(draft['group_id'], [col]) or {}).get(col, 0)
    cap_key = CAP_KEY[col]
    cap = cfg(cap_key)
    answer(call)
    if col == 'caravans':
        send(draft['chat_id'],
             t('trade_ask_caravan_cost', bal=bal, cap=cap, p=cfg('caravan_cost')))
    else:
        send(draft['chat_id'],
             t('trade_ask_ship_count', v=cat_label(col), bal=bal, cap=cap))

    def on_count(msg):
        d = _trade_drafts.get(user_id)
        if not d:
            return
        try:
            val = int((msg.text or '').strip())
        except (ValueError, AttributeError):
            send(d['chat_id'], t('err_generic'))
            return
        if val < 0 or val > bal:
            send(d['chat_id'], t('trade_not_enough'))
        elif val == 0:
            d['vehicles'].pop(col, None)
        else:
            d['vehicles'][col] = val
        trade_show_vehicles(user_id)

    next_step(call.message, user_id, on_count)


def trade_vehicles_done(call):
    draft = _trade_drafts.get(call.from_user.id)
    if not draft:
        return
    vol = sum(draft['goods'].values())
    mode = draft['mode']
    cap = sum(draft['vehicles'].get(col, 0) * cfg(cap_key)
              for _, col, cap_key in VEHICLES[mode])
    if cap < vol:
        answer(call, t('trade_not_enough_cap', vol=vol, cap=cap), alert=True)
        return
    # محاسبه مسیر
    group_id = draft['group_id']
    home_col = 'home_sea' if mode == 'sea' else 'home_land'
    src_row = get_balances(group_id, [home_col])
    dst_row = get_balances(draft['dest'], [home_col])
    if not src_row or not src_row[home_col] or not dst_row or not dst_row[home_col]:
        answer(call)
        send(group_id, t('trade_no_home', mode=t('trade_' + mode)))
        return
    routes = find_routes(mode, src_row[home_col], dst_row[home_col], sender_gid=group_id)
    if not routes:
        answer(call)
        send(group_id, "مسیری یافت نشد!")
        return
    draft['routes'] = routes
    draft['route_i'] = 0
    answer(call)
    trade_confirm(call.from_user.id)


def trade_confirm(user_id):
    draft = _trade_drafts.get(user_id)
    if not draft:
        return
    r = draft['routes'][draft['route_i']]
    dest_title = group_title(draft['dest'])
    goods = '\n'.join(f"• {cat_label(k)}: {v}" for k, v in draft['goods'].items())
    # هزینه کاروان
    caravan_cost = 0
    if draft['mode'] == 'land':
        caravan_cost = draft['vehicles'].get('caravans', 0) * cfg('caravan_cost')
    total = r['money'] + caravan_cost
    path = path_names(draft['mode'], r['path'])
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("💱 مسیر دیگر", callback_data='trade:nextroute'))
    markup.add(
        types.InlineKeyboardButton(t('trade_send'), callback_data='trade:ok'),
        types.InlineKeyboardButton(t('cancel'), callback_data='trade:x'))
    send(draft['chat_id'],
         t('trade_confirm', dest=esc(dest_title), goods=goods,
           path=path, cost=total),
         reply_markup=markup)


def trade_next_route(call):
    draft = _trade_drafts.get(call.from_user.id)
    if not draft or not draft.get('routes'):
        return
    n = len(draft['routes'])
    draft['route_i'] = (draft['route_i'] + 1) % n
    answer(call, f"مسیر {draft['route_i'] + 1} از {n}")
    trade_confirm(call.from_user.id)


def trade_send_offer(call):
    user_id = call.from_user.id
    draft = _trade_drafts.get(user_id)
    if not draft:
        answer(call, t('err_generic'), alert=True)
        return
    group_id = draft['group_id']
    r = draft['routes'][draft['route_i']]
    # بررسی و کسر
    caravan_cost = 0
    if draft['mode'] == 'land':
        caravan_cost = draft['vehicles'].get('caravans', 0) * cfg('caravan_cost')
    fee = r['money'] + caravan_cost
    res_keys = list(draft['goods'].keys())
    with DB_LOCK:
        # موجودی
        cols = res_keys + ['money']
        cur = conn.execute(
            f"SELECT {', '.join(cols)} FROM users WHERE group_id=?", (group_id,))
        row = cur.fetchone()
        if row is None:
            answer(call, t('err_generic'), alert=True)
            return
        have = dict(zip(cols, row))
        for k in res_keys:
            if have.get(k, 0) < draft['goods'][k]:
                answer(call, "موجودی کافی نیست.", alert=True)
                return
        if have.get('money', 0) < fee:
            answer(call, "💰 پول کافی نیست.", alert=True)
            return
        # کسر
        sets = [f"{k} = {k} - ?" for k in res_keys]
        params = [draft['goods'][k] for k in res_keys]
        sets.append("money = money - ?")
        params.append(fee)
        params.append(group_id)
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE group_id=?", params)
        # درج
        cur = conn.execute(
            """INSERT INTO trades (sender_group_id, sender_user_id, receiver_group_id,
                                    receiver_user_id, mode, goods, vehicles, route,
                                    leg_minutes, tolls, fee_paid, status, offered_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'offered', ?)""",
            (group_id, user_id, draft['dest'], get_lord(draft['dest']) or 0,
             draft['mode'], json.dumps(draft['goods']),
             json.dumps(draft['vehicles']),
             json.dumps(r['path']), json.dumps(r['leg_minutes']),
             json.dumps(r['tolls']), fee, int(time.time())))
        tid = cur.lastrowid
        conn.commit()
    _trade_drafts.pop(user_id, None)
    answer(call)
    # ارسال پیشنهاد
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(t('trade_accept'), callback_data=f'trade:a:{tid}'),
        types.InlineKeyboardButton(t('trade_decline'), callback_data=f'trade:n:{tid}'))
    goods_text = '\n'.join(f"• {cat_label(k)}: {v}" for k, v in draft['goods'].items())
    try:
        send(draft['dest'],
             t('trade_offer', tid=tid, sender=esc(group_title(group_id)),
               goods=goods_text, cost=fee),
             reply_markup=markup)
    except Exception:
        # بازگشت
        with DB_LOCK:
            sets = [f"{k} = {k} + ?" for k in res_keys]
            params = [draft['goods'][k] for k in res_keys]
            sets.append("money = money + ?")
            params.append(fee)
            params.append(group_id)
            conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE group_id=?", params)
            conn.execute("UPDATE trades SET status='cancelled' WHERE id=?", (tid,))
            conn.commit()
        send(group_id, "❌ ارسال پیشنهاد ممکن نشد.")
        return
    send(group_id, t('trade_sent', tid=tid, dest=esc(group_title(draft['dest']))))


def trade_accept(call, tid):
    trade = q("SELECT * FROM trades WHERE id=?", (tid,))
    if not trade:
        answer(call, "تجارت یافت نشد.", alert=True)
        return
    trade = trade[0]
    if trade['status'] != 'offered':
        answer(call, "قبلاً رسیدگی شده.", alert=True)
        return
    if not is_lord(trade['receiver_group_id'], call.from_user.id):
        answer(call, t('not_lord'), alert=True)
        return
    goods = json.loads(trade['goods'])
    with DB_LOCK:
        cols = list(goods.keys())
        sets = ', '.join(f"{k} = {k} + ?" for k in cols)
        params = [goods[k] for k in cols] + [trade['receiver_group_id']]
        conn.execute(f"UPDATE users SET {sets} WHERE group_id=?", params)
        # بازگشت کشتی‌ها به مبدأ
        vehicles = json.loads(trade['vehicles'])
        if vehicles:
            vcols = list(vehicles.keys())
            vsets = ', '.join(f"{k} = {k} + ?" for k in vcols)
            vparams = [vehicles[k] for k in vcols] + [trade['sender_group_id']]
            conn.execute(f"UPDATE users SET {vsets} WHERE group_id=?", vparams)
        # عوارض به مالکان گذرگاه
        tolls = json.loads(trade['tolls'])
        for nid, amt in tolls:
            owner = owner_of(nid)
            if owner:
                conn.execute("UPDATE users SET money = money + ? WHERE group_id=?",
                             (amt, owner))
        conn.execute("UPDATE trades SET status='delivered' WHERE id=?", (tid,))
        conn.commit()
    answer(call)
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                      reply_markup=None)
    except Exception:
        pass
    send(trade['sender_group_id'], t('trade_accepted'))
    send(trade['receiver_group_id'],
         f"✅ تجارت دریافت شد و کالاها به خزانه اضافه شد.\n<blockquote>{_goods_display(goods)}</blockquote>")


def trade_decline(call, tid):
    trade = q("SELECT * FROM trades WHERE id=?", (tid,))
    if not trade:
        return
    trade = trade[0]
    if trade['status'] != 'offered':
        answer(call, "قبلاً رسیدگی شده.", alert=True)
        return
    goods = json.loads(trade['goods'])
    with DB_LOCK:
        cols = list(goods.keys())
        sets = ', '.join(f"{k} = {k} + ?" for k in cols)
        params = [goods[k] for k in cols]
        sets += ", money = money + ?"
        params.append(trade['fee_paid'])
        params.append(trade['sender_group_id'])
        conn.execute(f"UPDATE users SET {sets} WHERE group_id=?", params)
        # بازگشت کشتی
        vehicles = json.loads(trade['vehicles'])
        if vehicles:
            vcols = list(vehicles.keys())
            vsets = ', '.join(f"{k} = {k} + ?" for k in vcols)
            vparams = [vehicles[k] for k in vcols] + [trade['sender_group_id']]
            conn.execute(f"UPDATE users SET {vsets} WHERE group_id=?", vparams)
        conn.execute("UPDATE trades SET status='declined' WHERE id=?", (tid,))
        conn.commit()
    answer(call)
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                      reply_markup=None)
    except Exception:
        pass
    send(trade['sender_group_id'], t('trade_declined'))


def _goods_display(goods):
    return '\n'.join(f"• {cat_label(k)}: {v}" for k, v in goods.items())


def trade_cancel(call):
    _trade_drafts.pop(call.from_user.id, None)
    answer(call)
    send(call.message.chat.id, "🚫 لغو شد.")


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۲۰: بیانیه / معاهده / پیام خصوصی
# ═══════════════════════════════════════════════════════════════════════════

_states = {}


def start_statement(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    _states[user_id] = {'kind': 'statement', 'chat_id': chat_id}
    answer(call)
    sent = send(chat_id, "🙌 متن بیانیه را بفرستید:")

    def on_text(msg):
        st = _states.pop(user_id, None)
        if not st:
            return
        text = (msg.text or '').strip()
        if not text:
            send(chat_id, "چیزی وارد نشد.")
            return
        sender = group_title(chat_id) if msg.chat.type != 'private' else 'ناشناس'
        try:
            send(CHANNEL_ID, f"🙌 <b>بیانیه</b>\nاز: {esc(sender)}\n\n{esc(text)}")
            send(chat_id, "✅ بیانیه ارسال شد.")
        except Exception:
            send(chat_id, "❌ ارسال ممکن نشد.")

    next_step(sent, user_id, on_text)


def start_treaty(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    _states[user_id] = {'kind': 'treaty', 'chat_id': chat_id}
    answer(call)
    sent = send(chat_id, "📜 متن معاهده را بفرستید:")

    def on_text(msg):
        st = _states.pop(user_id, None)
        if not st:
            return
        text = (msg.text or '').strip()
        if not text:
            send(chat_id, "چیزی وارد نشد.")
            return
        # ذخیره در treaties
        cur = q("SELECT treaties FROM users WHERE group_id=?", (chat_id,))
        old = cur[0]['treaties'] if cur else ''
        new = (old + '\n\n' + text) if old else text
        ex("UPDATE users SET treaties=? WHERE group_id=?", (new, chat_id))
        log_action(user_id, 'treaty', group_title(chat_id), text[:50])
        send(chat_id, "✅ معاهده ثبت شد.")

    next_step(sent, user_id, on_text)


def start_private(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    _states[user_id] = {'kind': 'private', 'chat_id': chat_id}
    answer(call)
    sent = send(chat_id, "✉️ متن پیام را بفرستید:")

    def on_text(msg):
        st = _states.pop(user_id, None)
        if not st:
            return
        text = (msg.text or '').strip()
        if not text:
            return
        # ارسال به همه گروه‌ها
        groups = q("SELECT DISTINCT group_id FROM users")
        markup = types.InlineKeyboardMarkup(row_width=2)
        for g in groups:
            gid = g['group_id']
            markup.add(types.InlineKeyboardButton(
                group_title(gid),
                callback_data=f'priv:send:{gid}'))
        _states[user_id] = {'kind': 'private_send', 'text': text}
        send(chat_id, "به کدام گروه بفرستیم؟", reply_markup=markup)

    next_step(sent, user_id, on_text)


def priv_send(call, gid):
    user_id = call.from_user.id
    st = _states.get(user_id)
    if not st or st.get('kind') != 'private_send':
        answer(call, "اطلاعات یافت نشد.", alert=True)
        return
    text = st['text']
    try:
        send(gid, f"📬 <b>پیام خصوصی</b>\nاز: {user_link(user_id)}\n\n{esc(text)}")
        answer(call, "✅ ارسال شد.")
    except Exception:
        answer(call, "❌ ارسال ممکن نشد.", alert=True)
    _states.pop(user_id, None)


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۲۱: کاتالوگ — ویرایش پیشرفته (ادمین)
# ═══════════════════════════════════════════════════════════════════════════

CAT_PAGE_SIZE = 8


def panel_catalog(call):
    if not is_admin(call.from_user.id):
        return
    counts = {k: len(cat_keys(k)) for k in ('resource', 'unit', 'building')}
    text = (f"🧩 <b>{t('cat_title')}</b>\n\n"
            f"📦 منابع: {counts['resource']}\n"
            f"⚔️ نیروها: {counts['unit']}\n"
            f"🏭 ساختمون‌ها: {counts['building']}")
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(f"📦 منابع ({counts['resource']})",
                                   callback_data='ap:catk:resource:0'),
        types.InlineKeyboardButton(f"⚔️ نیروها ({counts['unit']})",
                                   callback_data='ap:catk:unit:0'),
        types.InlineKeyboardButton(f"🏭 ساختمون‌ها ({counts['building']})",
                                   callback_data='ap:catk:building:0'))
    markup.add(types.InlineKeyboardButton("🔀 ترتیب بخش‌ها",
                                          callback_data='ap:catorder'))
    back_btn(markup, 'ap:home')
    edit(call, text, markup)
    answer(call)


def panel_cat_kind(call, kind, page=0):
    if not is_admin(call.from_user.id):
        return
    rows = cat_entries(kind, include_hidden=True)
    pages = max(1, (len(rows) + CAT_PAGE_SIZE - 1) // CAT_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    window = rows[page * CAT_PAGE_SIZE:(page + 1) * CAT_PAGE_SIZE]
    markup = types.InlineKeyboardMarkup(row_width=1)
    for r in window:
        mark = '🚫 ' if r['hidden'] else ''
        markup.add(types.InlineKeyboardButton(
            f"{mark}{cat_label(r['key'])}",
            callback_data=f"ap:cate:{r['key']}"))
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton(t('prev'),
                                              callback_data=f'ap:catk:{kind}:{page - 1}'))
    if page < pages - 1:
        nav.append(types.InlineKeyboardButton(t('next'),
                                              callback_data=f'ap:catk:{kind}:{page + 1}'))
    if nav:
        markup.add(*nav)
    markup.add(types.InlineKeyboardButton(t('cat_add'), callback_data=f'ap:catadd:{kind}'))
    back_btn(markup, 'ap:cat')
    kind_names = {'resource': '📦 منابع', 'unit': '⚔️ نیروها', 'building': '🏭 ساختمون‌ها'}
    edit(call, f"🧩 {kind_names.get(kind, kind)} (صفحه {page + 1}/{pages}):", markup)
    answer(call)


def panel_cat_entry(call, key):
    if not is_admin(call.from_user.id):
        return
    row = cat_entry(key)
    if not row:
        answer(call, t('cat_err_unknown'), alert=True)
        return
    lines = [f"🧩 <b>{cat_label(key)}</b>"]
    lines.append(f"🔑 کلید: <code>{key}</code>")
    lines.append(f"📁 دسته: {row['kind']}")
    lines.append(f"🎁 مقدار اولیه: {row['default_value']}")
    if row['kind'] == 'building':
        produces = cat_label(row['produces']) if row['produces'] else '—'
        lines.append(f"🏭 تولید: {produces} × {row['output']}")
        lines.append(f"🏁 سقف سطح: {row['max_level'] or 'بی‌نهایت'}")
        costs = cat_upgrade_cost(key)
        if costs:
            lines.append("💸 هزینه ارتقا:")
            for r, amt in costs.items():
                lines.append(f"  {cat_label(r)}: {amt}")
        inputs = cat_production_inputs(key)
        if inputs:
            lines.append("🔻 مصرف تولید:")
            for r, amt in inputs.items():
                lines.append(f"  {cat_label(r)}: {amt}")
        else:
            lines.append("🔻 مصرف: ندارد")
    if row['hidden']:
        lines.append("🚫 <b>از بازی حذف شده</b>")
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("✏️ تغییر نام",
                                          callback_data=f'ap:catren:{key}'))
    markup.add(types.InlineKeyboardButton("🎁 مقدار اولیه",
                                          callback_data=f'ap:catdef:{key}'))
    if row['kind'] == 'building':
        markup.add(types.InlineKeyboardButton("📈 خروجی تولید",
                                              callback_data=f'ap:catout:{key}'))
        markup.add(types.InlineKeyboardButton("🔻 مصرف تولید",
                                              callback_data=f'ap:catinput:{key}'))
        markup.add(types.InlineKeyboardButton("💸 هزینه ارتقا",
                                              callback_data=f'ap:catcost:{key}'))
        markup.add(types.InlineKeyboardButton("🏁 سقف سطح",
                                              callback_data=f'ap:catmax:{key}'))
    if row['hidden']:
        markup.add(types.InlineKeyboardButton("♻️ بازگرداندن به بازی",
                                              callback_data=f'ap:catunhide:{key}'))
    else:
        markup.add(types.InlineKeyboardButton("🗑 حذف از بازی",
                                              callback_data=f'ap:cathide:{key}'))
    if key not in ENGINE_KEYS:
        markup.add(types.InlineKeyboardButton("❌ حذف دائمی",
                                              callback_data=f'ap:catdel:{key}'))
    back_btn(markup, f'ap:catk:{row["kind"]}:0')
    edit(call, '\n'.join(lines), markup)
    answer(call)


def cat_ask_rename(call, key):
    if not is_admin(call.from_user.id):
        return
    answer(call)
    sent = send(call.message.chat.id, "نام نمایشی فارسی جدید:")
    next_step(sent, call.from_user.id,
              lambda m: cat_do_rename(call, key, m))


def cat_do_rename(call, key, message):
    text = (message.text or '').strip()
    if not text:
        send(message.chat.id, "نام خالی.")
        return
    ex("INSERT OR REPLACE INTO asset_labels (key, lang, label) VALUES (?, 'fa', ?)",
       (key, text))
    log_action(call.from_user.id, 'cat_rename', key, text)
    send(message.chat.id, t('cat_saved'))
    panel_cat_entry(call, key)


def cat_ask_default(call, key):
    if not is_admin(call.from_user.id):
        return
    answer(call)
    ask_number(call.message.chat.id, call.from_user.id, call.message,
               "مقدار اولیه جدید:",
               lambda v: cat_do_default(call, key, v))


def cat_do_default(call, key, value):
    ex("UPDATE asset_catalog SET default_value=? WHERE key=?", (int(value), key))
    log_action(call.from_user.id, 'cat_default', key, str(value))
    send(call.message.chat.id, t('cat_saved'))
    panel_cat_entry(call, key)


def cat_ask_output(call, key):
    if not is_admin(call.from_user.id):
        return
    answer(call)
    # انتخاب کالا
    resources = cat_keys('resource') + cat_keys('unit')
    markup = types.InlineKeyboardMarkup(row_width=2)
    for r in resources:
        markup.add(types.InlineKeyboardButton(cat_label(r),
                                              callback_data=f'ap:catoutpick:{key}:{r}'))
    markup.add(types.InlineKeyboardButton("🚫 هیچ‌چیز",
                                          callback_data=f'ap:catoutpick:{key}:-'))
    back_btn(markup, f'ap:cate:{key}')
    send(call.message.chat.id, "چه چیزی تولید کند؟", reply_markup=markup)


def cat_pick_output_target(call, key, target):
    if not is_admin(call.from_user.id):
        return
    if target == '-':
        ex("UPDATE asset_catalog SET produces='', output=0 WHERE key=?", (key,))
        log_action(call.from_user.id, 'cat_output', key, 'none')
        send(call.message.chat.id, t('cat_saved'))
        panel_cat_entry(call, key)
        return
    answer(call)
    ask_number(call.message.chat.id, call.from_user.id, call.message,
               f"خروجی {cat_label(target)} در هر سطح در هفته:",
               lambda v: cat_do_output(call, key, target, v))


def cat_do_output(call, key, target, value):
    ex("UPDATE asset_catalog SET produces=?, output=? WHERE key=?",
       (target, int(value), key))
    log_action(call.from_user.id, 'cat_output', key, f'{target}={value}')
    send(call.message.chat.id, t('cat_saved'))
    panel_cat_entry(call, key)


def cat_ask_input(call, key):
    """نمایش لیست ورودی‌های فعلی + دکمه ویرایش هر کدام."""
    if not is_admin(call.from_user.id):
        return
    inputs = cat_production_inputs(key)
    resources = cat_keys('resource')
    lines = [f"🔻 مصرف تولید {cat_label(key)}:"]
    if inputs:
        for r, amt in inputs.items():
            lines.append(f"  {cat_label(r)}: {amt}")
    else:
        lines.append("  هیچ مصرفی ندارد")
    markup = types.InlineKeyboardMarkup(row_width=2)
    for r in resources:
        cur = inputs.get(r, 0)
        lbl = f"{cat_label(r)}: {cur}" if cur else cat_label(r)
        markup.add(types.InlineKeyboardButton(lbl,
                                              callback_data=f'ap:catinputedit:{key}:{r}'))
    back_btn(markup, f'ap:cate:{key}')
    edit(call, '\n'.join(lines), markup)
    answer(call)


def cat_edit_input(call, key, resource):
    if not is_admin(call.from_user.id):
        return
    cur = cat_production_inputs(key).get(resource, 0)
    answer(call)
    ask_number(call.message.chat.id, call.from_user.id, call.message,
               f"مصرف {cat_label(resource)} در هر سطح (۰ = بدون مصرف):",
               lambda v: cat_do_input(call, key, resource, v))


def cat_do_input(call, key, resource, value):
    if value <= 0:
        ex("DELETE FROM asset_production_inputs WHERE building=? AND resource=?",
           (key, resource))
    else:
        ex("INSERT OR REPLACE INTO asset_production_inputs (building, resource, amount) "
           "VALUES (?, ?, ?)", (key, resource, int(value)))
    log_action(call.from_user.id, 'cat_input', key, f'{resource}={value}')
    send(call.message.chat.id, t('cat_saved'))
    cat_ask_input(call, key)


def cat_ask_cost(call, key):
    """لیست هزینه‌های فعلی + ویرایش."""
    if not is_admin(call.from_user.id):
        return
    costs = cat_upgrade_cost(key)
    resources = cat_keys('resource')
    lines = [f"💸 هزینه ارتقا {cat_label(key)}:"]
    if costs:
        for r, amt in costs.items():
            lines.append(f"  {cat_label(r)}: {amt}")
    else:
        lines.append("  رایگان")
    markup = types.InlineKeyboardMarkup(row_width=2)
    for r in resources:
        cur = costs.get(r, 0)
        lbl = f"{cat_label(r)}: {cur}" if cur else cat_label(r)
        markup.add(types.InlineKeyboardButton(lbl,
                                              callback_data=f'ap:catcostedit:{key}:{r}'))
    back_btn(markup, f'ap:cate:{key}')
    edit(call, '\n'.join(lines), markup)
    answer(call)


def cat_edit_cost(call, key, resource):
    if not is_admin(call.from_user.id):
        return
    cur = cat_upgrade_cost(key).get(resource, 0)
    answer(call)
    ask_number(call.message.chat.id, call.from_user.id, call.message,
               f"هزینه {cat_label(resource)} برای هر ارتقا (۰ = بدون هزینه):",
               lambda v: cat_do_cost(call, key, resource, v))


def cat_do_cost(call, key, resource, value):
    if value <= 0:
        ex("DELETE FROM asset_upgrade_costs WHERE building=? AND resource=?",
           (key, resource))
    else:
        ex("INSERT OR REPLACE INTO asset_upgrade_costs (building, resource, amount) "
           "VALUES (?, ?, ?)", (key, resource, int(value)))
    log_action(call.from_user.id, 'cat_cost', key, f'{resource}={value}')
    send(call.message.chat.id, t('cat_saved'))
    cat_ask_cost(call, key)


def cat_ask_max(call, key):
    if not is_admin(call.from_user.id):
        return
    cur = cat_max_level(key) or 0
    answer(call)
    ask_number(call.message.chat.id, call.from_user.id, call.message,
               f"سقف سطح (فعلی: {cur or 'بی‌نهایت'} | ۰ = بی‌نهایت):",
               lambda v: cat_do_max(call, key, v), minimum=0)


def cat_do_max(call, key, value):
    ex("UPDATE asset_catalog SET max_level=? WHERE key=?", (int(value), key))
    log_action(call.from_user.id, 'cat_max', key, str(value))
    send(call.message.chat.id, t('cat_saved'))
    panel_cat_entry(call, key)


def cat_hide(call, key):
    if not is_admin(call.from_user.id):
        return
    ex("UPDATE asset_catalog SET hidden=1 WHERE key=?", (key,))
    log_action(call.from_user.id, 'cat_hide', key, '')
    answer(call, f"🚫 {cat_label(key)} حذف شد.")
    panel_cat_entry(call, key)


def cat_unhide(call, key):
    if not is_admin(call.from_user.id):
        return
    ex("UPDATE asset_catalog SET hidden=0 WHERE key=?", (key,))
    _ensure_asset_columns()
    log_action(call.from_user.id, 'cat_unhide', key, '')
    answer(call, f"♻️ {cat_label(key)} بازگشت.")
    panel_cat_entry(call, key)


def cat_ask_delete(call, key):
    if not is_owner(call.from_user.id):
        return
    row = cat_entry(key)
    if not row:
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("🔥 بله، برای همیشه حذف کن",
                                          callback_data=f'ap:catdelok:{key}'))
    back_btn(markup, f'ap:cate:{key}')
    edit(call, f"❌ <b>حذف دائمی {cat_label(key)}</b>\n\n"
               "این کار برگشت‌پذیر نیست. مقدار فعلی همه کشورها پاک می‌شود.",
         markup)
    answer(call)


def cat_do_delete(call, key):
    if not is_owner(call.from_user.id):
        return
    row = cat_entry(key)
    if not row:
        return
    if key in ENGINE_KEYS:
        answer(call, t('cat_err_engine'), alert=True)
        return
    with DB_LOCK:
        conn.execute("DELETE FROM asset_catalog WHERE key=?", (key,))
        conn.execute("DELETE FROM asset_labels WHERE key=?", (key,))
        conn.execute("DELETE FROM asset_upgrade_costs WHERE building=? OR resource=?", (key, key))
        conn.execute("DELETE FROM asset_production_inputs WHERE building=? OR resource=?", (key, key))
        # غیرفعال کردن تولید ساختمون‌ها که این را تولید می‌کردند
        conn.execute("UPDATE asset_catalog SET produces='', output=0 WHERE produces=?", (key,))
        try:
            conn.execute(f"ALTER TABLE users DROP COLUMN {key}")
        except sqlite3.OperationalError:
            pass
        conn.commit()
    ca_forget(key)
    log_action(call.from_user.id, 'cat_delete', key, '')
    answer(call, f"🔥 {cat_label(key)} حذف شد.")
    panel_cat_kind(call, row['kind'], 0)


# --- افزودن نوع جدید ---

_cat_wizards = {}


def cat_add_start(call, kind):
    if not is_admin(call.from_user.id):
        return
    if kind not in ('resource', 'unit', 'building'):
        answer(call, t('err_generic'))
        return
    _cat_wizards[call.from_user.id] = {'kind': kind}
    answer(call)
    sent = send(call.message.chat.id, t('cat_ask_key'))
    next_step(sent, call.from_user.id,
              lambda m: cat_add_key(call, m, sent))


def cat_add_key(call, message, anchor):
    user_id = call.from_user.id
    wiz = _cat_wizards.get(user_id)
    if not wiz:
        return
    key = (message.text or '').strip().lower()
    if not KEY_RE.match(key):
        send(message.chat.id, t('cat_err_key'))
        next_step(anchor, user_id, lambda m: cat_add_key(call, m, anchor))
        return
    if key in RESERVED_COLS:
        send(message.chat.id, t('cat_err_reserved'))
        next_step(anchor, user_id, lambda m: cat_add_key(call, m, anchor))
        return
    if q("SELECT 1 FROM asset_catalog WHERE key=?", (key,)):
        send(message.chat.id, t('cat_err_exists'))
        next_step(anchor, user_id, lambda m: cat_add_key(call, m, anchor))
        return
    wiz['key'] = key
    sent2 = send(message.chat.id, t('cat_ask_label'))
    next_step(sent2, user_id, lambda m: cat_add_label(call, m, sent2))


def cat_add_label(call, message, anchor):
    user_id = call.from_user.id
    wiz = _cat_wizards.get(user_id)
    if not wiz:
        return
    text = (message.text or '').strip()
    if not text:
        send(message.chat.id, "نام خالی.")
        next_step(anchor, user_id, lambda m: cat_add_label(call, m, anchor))
        return
    wiz['label'] = text
    sent2 = send(message.chat.id, t('cat_ask_default'))
    next_step(sent2, user_id, lambda m: cat_add_default(call, m, sent2))


def cat_add_default(call, message, anchor):
    user_id = call.from_user.id
    wiz = _cat_wizards.get(user_id)
    if not wiz:
        return
    try:
        val = int((message.text or '').strip())
    except (ValueError, AttributeError):
        send(message.chat.id, t('cat_bad_number'))
        next_step(anchor, user_id, lambda m: cat_add_default(call, m, anchor))
        return
    wiz['default'] = val
    if wiz['kind'] != 'building':
        cat_add_finish(call)
        return
    # برای building: انتخاب تولید
    markup = types.InlineKeyboardMarkup(row_width=2)
    targets = cat_keys('resource') + cat_keys('unit')
    for r in targets:
        markup.add(types.InlineKeyboardButton(cat_label(r),
                                              callback_data=f'ap:cataddprod:{r}'))
    markup.add(types.InlineKeyboardButton("🚫 هیچ‌چیز",
                                          callback_data='ap:cataddprod:-'))
    send(message.chat.id, "چه چیزی تولید کند؟", reply_markup=markup)


def cat_add_pick_produces(call, target):
    user_id = call.from_user.id
    wiz = _cat_wizards.get(user_id)
    if not wiz:
        answer(call, t('err_generic'))
        return
    if target == '-':
        wiz['produces'] = ''
        wiz['output'] = 0
        answer(call)
        cat_add_finish(call)
        return
    wiz['produces'] = target
    answer(call)
    sent = send(call.message.chat.id, f"خروجی {cat_label(target)} در هر سطح:")
    next_step(sent, user_id, lambda m: cat_add_output(call, m, sent))


def cat_add_output(call, message, anchor):
    user_id = call.from_user.id
    wiz = _cat_wizards.get(user_id)
    if not wiz:
        return
    try:
        val = int((message.text or '').strip())
    except (ValueError, AttributeError):
        send(message.chat.id, t('cat_bad_number'))
        next_step(anchor, user_id, lambda m: cat_add_output(call, m, anchor))
        return
    wiz['output'] = val
    cat_add_finish(call)


def cat_add_finish(call):
    user_id = call.from_user.id
    wiz = _cat_wizards.pop(user_id, None)
    if not wiz:
        return
    key = wiz['key']
    kind = wiz['kind']
    label_text = wiz['label']
    with DB_LOCK:
        rows = q("SELECT COALESCE(MAX(position), 0) AS p FROM asset_catalog WHERE kind=?",
                 (kind,))
        pos = (rows[0]['p'] if rows else 0) + 10
        conn.execute(
            "INSERT INTO asset_catalog (key, kind, position, default_value, builtin, "
            "produces, output, tradeable) VALUES (?, ?, ?, ?, 0, ?, ?, ?)",
            (key, kind, pos, wiz.get('default', 0),
             wiz.get('produces', '') if kind == 'building' else '',
             wiz.get('output', 0) if kind == 'building' else 0,
             1 if kind == 'resource' else 0))
        conn.execute("INSERT INTO asset_labels (key, lang, label) VALUES (?, 'fa', ?)",
                     (key, label_text))
        conn.commit()
    _ensure_asset_columns()
    log_action(call.from_user.id, 'cat_add', key, kind)
    send(call.message.chat.id, f"✅ {label_text} اضافه شد.")
    panel_cat_kind(call, kind, 0)


def panel_cat_order(call):
    if not is_admin(call.from_user.id):
        return
    order = q("SELECT kind, position FROM asset_kind_order ORDER BY position")
    lines = ["🔀 ترتیب بخش‌ها:"]
    kind_names = {'resource': '📦 منابع', 'unit': '⚔️ نیروها', 'building': '🏭 ساختمون‌ها'}
    for r in order:
        lines.append(f"  {kind_names.get(r['kind'], r['kind'])}")
    markup = types.InlineKeyboardMarkup(row_width=2)
    for r in order:
        k = r['kind']
        markup.add(
            types.InlineKeyboardButton(f"⬆️ {kind_names.get(k, k)}",
                                       callback_data=f'ap:catorderup:{k}'),
            types.InlineKeyboardButton(f"⬇️ {kind_names.get(k, k)}",
                                       callback_data=f'ap:catorderdn:{k}'))
    back_btn(markup, 'ap:cat')
    edit(call, '\n'.join(lines), markup)
    answer(call)


def cat_move_kind(call, kind, direction):
    if not is_admin(call.from_user.id):
        return
    order = q("SELECT kind FROM asset_kind_order ORDER BY position")
    kinds = [r['kind'] for r in order]
    if kind not in kinds:
        return
    idx = kinds.index(kind)
    other = idx - 1 if direction == 'up' else idx + 1
    if not 0 <= other < len(kinds):
        answer(call, "در انتهای فهرست است.")
        return
    kinds[idx], kinds[other] = kinds[other], kinds[idx]
    with DB_LOCK:
        for i, k in enumerate(kinds, 1):
            conn.execute("INSERT OR REPLACE INTO asset_kind_order (kind, position) VALUES (?, ?)",
                         (k, i * 10))
        conn.commit()
    log_action(call.from_user.id, 'cat_order', kind, direction)
    answer(call, "✅")
    panel_cat_order(call)


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۲۲: دارایی هر کشور (country_assets)
# ═══════════════════════════════════════════════════════════════════════════

CA_PAGE_SIZE = 8


def panel_ca_list(call, page=0):
    if not is_admin(call.from_user.id):
        return
    groups = q("SELECT DISTINCT group_id FROM users ORDER BY group_id")
    if not groups:
        edit(call, "هیچ کشوری نیست.", back_btn(types.InlineKeyboardMarkup(), 'ap:home'))
        answer(call)
        return
    pages = max(1, (len(groups) + CA_PAGE_SIZE - 1) // CA_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    window = groups[page * CA_PAGE_SIZE:(page + 1) * CA_PAGE_SIZE]
    markup = types.InlineKeyboardMarkup(row_width=1)
    for g in window:
        gid = g['group_id']
        off, paused = ca_overrides(gid)
        mark = f" ({off}🚫 {paused}⏸)" if (off or paused) else ''
        markup.add(types.InlineKeyboardButton(f"{group_title(gid)}{mark}",
                                              callback_data=f'ap:ca:{gid}'))
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton(t('prev'), callback_data=f'ap:cal:{page - 1}'))
    if page < pages - 1:
        nav.append(types.InlineKeyboardButton(t('next'), callback_data=f'ap:cal:{page + 1}'))
    if nav:
        markup.add(*nav)
    back_btn(markup, 'ap:home')
    edit(call, t('ca_pick') + f" (صفحه {page + 1}/{pages})", markup)
    answer(call)


def panel_ca_country(call, gid):
    if not is_admin(call.from_user.id):
        return
    off, paused = ca_overrides(gid)
    gone = ca_hidden(gid)
    stopped = ca_paused(gid)
    lines = [t('ca_title', g=esc(group_title(gid)),
               off=', '.join(cat_label(k) for k in sorted(gone)) or 'ندارد',
               paused=', '.join(cat_label(k) for k in sorted(stopped)) or 'ندارد')]
    markup = types.InlineKeyboardMarkup(row_width=1)
    for kind in ('resource', 'unit', 'building'):
        total = len(cat_keys(kind))
        has = len(ca_keys_for(gid, kind))
        markup.add(types.InlineKeyboardButton(
            f"{kind}: {has}/{total}",
            callback_data=f'ap:cak:{gid}:{kind}:0'))
    if off or paused:
        markup.add(types.InlineKeyboardButton(t('ca_clear'),
                                              callback_data=f'ap:caclear:{gid}'))
    back_btn(markup, 'ap:cal:0')
    edit(call, '\n'.join(lines), markup)
    answer(call)


def panel_ca_kind(call, gid, kind, page=0):
    if not is_admin(call.from_user.id):
        return
    keys = cat_keys(kind)
    pages = max(1, (len(keys) + CA_PAGE_SIZE - 1) // CA_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    window = keys[page * CA_PAGE_SIZE:(page + 1) * CA_PAGE_SIZE]
    gone = ca_hidden(gid)
    stopped = ca_paused(gid)
    markup = types.InlineKeyboardMarkup(row_width=2)
    for key in window:
        mark = '🚫' if key in gone else '✅'
        row = [types.InlineKeyboardButton(
            f"{mark} {cat_label(key)}",
            callback_data=f'ap:catoggle:{gid}:{key}')]
        if kind == 'building' and key not in gone:
            row.append(types.InlineKeyboardButton(
                '▶️' if key in stopped else '⏸',
                callback_data=f'ap:capause:{gid}:{key}'))
        markup.row(*row)
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton(t('prev'),
                                              callback_data=f'ap:cak:{gid}:{kind}:{page - 1}'))
    if page < pages - 1:
        nav.append(types.InlineKeyboardButton(t('next'),
                                              callback_data=f'ap:cak:{gid}:{kind}:{page + 1}'))
    if nav:
        markup.add(*nav)
    back_btn(markup, f'ap:ca:{gid}')
    kind_names = {'resource': '📦', 'unit': '⚔️', 'building': '🏭'}
    edit(call, f"{kind_names.get(kind, '')} {kind} — {esc(group_title(gid))} "
               f"(صفحه {page + 1}/{pages})", markup)
    answer(call)


def panel_ca_toggle(call, gid, key):
    if not is_admin(call.from_user.id):
        return
    if not cat_entry(key):
        answer(call, t('cat_err_unknown'), alert=True)
        return
    new_state = not ca_is_hidden(gid, key)
    ca_set(gid, key, 'hidden', new_state)
    log_action(call.from_user.id, 'ca_toggle', group_title(gid),
               f"{key}={'hidden' if new_state else 'shown'}")
    answer(call, t('ca_removed') if new_state else t('ca_restored'))
    kind = cat_entry(key)['kind']
    panel_ca_kind(call, gid, kind, 0)


def panel_ca_pause(call, gid, key):
    if not is_admin(call.from_user.id):
        return
    row = cat_entry(key)
    if not row or row['kind'] != 'building':
        return
    new_state = not ca_is_paused(gid, key)
    ca_set(gid, key, 'paused', new_state)
    log_action(call.from_user.id, 'ca_pause', group_title(gid),
               f"{key}={'paused' if new_state else 'running'}")
    answer(call, t('ca_paused') if new_state else t('ca_running'))
    panel_ca_kind(call, gid, 'building', 0)


def panel_ca_clear(call, gid):
    if not is_admin(call.from_user.id):
        return
    n = ca_clear(gid)
    log_action(call.from_user.id, 'ca_clear', group_title(gid), str(n))
    answer(call, t('ca_cleared', n=n))
    panel_ca_country(call, gid)


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۲۳: ویرایش نقشه (ادمین)
# ═══════════════════════════════════════════════════════════════════════════

MAP_PAGE_SIZE = 8


def panel_map(call):
    if not is_admin(call.from_user.id):
        return
    markup = types.InlineKeyboardMarkup(row_width=2)
    for m in ('sea', 'land'):
        n = len(map_nodes(m))
        markup.add(types.InlineKeyboardButton(
            f"{t('map_' + m)} ({n})",
            callback_data=f'ap:mapn:{m}:0'))
    back_btn(markup, 'ap:home')
    edit(call, t('map_title'), markup)
    answer(call)


def panel_map_nodes(call, mode, page=0):
    if not is_admin(call.from_user.id):
        return
    nodes = list(map_nodes(mode).items())
    pages = max(1, (len(nodes) + MAP_PAGE_SIZE - 1) // MAP_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    window = nodes[page * MAP_PAGE_SIZE:(page + 1) * MAP_PAGE_SIZE]
    markup = types.InlineKeyboardMarkup(row_width=1)
    for nid, n in window:
        markup.add(types.InlineKeyboardButton(
            f"{map_name(nid)}",
            callback_data=f'ap:mapnode:{nid}'))
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton(t('prev'),
                                              callback_data=f'ap:mapn:{mode}:{page - 1}'))
    if page < pages - 1:
        nav.append(types.InlineKeyboardButton(t('next'),
                                              callback_data=f'ap:mapn:{mode}:{page + 1}'))
    if nav:
        markup.add(*nav)
    markup.add(
        types.InlineKeyboardButton(t('map_add_node'),
                                   callback_data=f'ap:mapadd:{mode}'),
        types.InlineKeyboardButton("🛣 مسیرها",
                                   callback_data=f'ap:mapedges:{mode}:0'))
    back_btn(markup, 'ap:map')
    edit(call, t('map_nodes', mode=t('map_' + mode), p=page + 1, n=pages), markup)
    answer(call)


def panel_map_node(call, nid):
    if not is_admin(call.from_user.id):
        return
    mode = map_mode_of(nid)
    if not mode:
        answer(call, "یافت نشد.", alert=True)
        return
    n = map_node(mode, nid)
    toll = toll_of(nid)
    owner = owner_of(nid)
    owner_name = group_title(owner) if owner else 'ندارد'
    lines = [t('map_node',
               name=esc(map_name(nid)), id=nid,
               kind=n['kind'], home=t('map_yes') if n['home'] else t('map_no'),
               toll=toll, owner=esc(owner_name))]
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(t('map_rename'),
                                          callback_data=f'ap:mapren:{nid}'))
    markup.add(types.InlineKeyboardButton(t('map_set_kind'),
                                          callback_data=f'ap:mapkind:{nid}'))
    markup.add(types.InlineKeyboardButton(t('map_set_home'),
                                          callback_data=f'ap:maphome:{nid}'))
    markup.add(types.InlineKeyboardButton(t('map_set_toll'),
                                          callback_data=f'ap:maptoll:{nid}'))
    if n['kind'] in ('strait', 'canal', 'pass'):
        markup.add(types.InlineKeyboardButton("👑 مالک",
                                              callback_data=f'ap:mapowner:{nid}'))
    markup.add(types.InlineKeyboardButton(t('map_del_node'),
                                          callback_data=f'ap:mapdel:{nid}'))
    back_btn(markup, f'ap:mapn:{mode}:0')
    edit(call, '\n'.join(lines), markup)
    answer(call)


def panel_map_rename(call, nid):
    if not is_admin(call.from_user.id):
        return
    answer(call)
    sent = send(call.message.chat.id, t('map_ask_name'))
    next_step(sent, call.from_user.id,
              lambda m: panel_map_do_rename(call, nid, m))


def panel_map_do_rename(call, nid, message):
    text = (message.text or '').strip()
    if not text:
        return
    map_set_name(nid, text)
    log_action(call.from_user.id, 'map_rename', nid, text)
    send(message.chat.id, t('map_saved'))
    panel_map_node(call, nid)


def panel_map_kind(call, nid):
    if not is_admin(call.from_user.id):
        return
    mode = map_mode_of(nid)
    if not mode:
        return
    kinds = {
        'sea': ['ocean', 'sea', 'strait', 'canal', 'cape'],
        'land': ['region', 'pass'],
    }.get(mode, [])
    markup = types.InlineKeyboardMarkup(row_width=2)
    for k in kinds:
        markup.add(types.InlineKeyboardButton(k,
                                              callback_data=f'ap:mapsk:{nid}:{k}'))
    back_btn(markup, f'ap:mapnode:{nid}')
    edit(call, "نوع جدید:", markup)
    answer(call)


def panel_map_set_kind(call, nid, kind):
    if not is_admin(call.from_user.id):
        return
    map_set_node(map_mode_of(nid), nid, kind=kind)
    log_action(call.from_user.id, 'map_kind', nid, kind)
    answer(call, t('map_saved'))
    panel_map_node(call, nid)


def panel_map_home(call, nid):
    if not is_admin(call.from_user.id):
        return
    n = map_node(map_mode_of(nid), nid)
    new_state = not n['home']
    map_set_node(map_mode_of(nid), nid, home=new_state)
    log_action(call.from_user.id, 'map_home', nid, str(new_state))
    answer(call, t('map_saved'))
    panel_map_node(call, nid)


def panel_map_toll(call, nid):
    if not is_admin(call.from_user.id):
        return
    cur = toll_of(nid)
    answer(call)
    ask_number(call.message.chat.id, call.from_user.id, call.message,
               f"عوارض عبور (فعلی: {cur}، ۰ = رایگان):",
               lambda v: panel_map_do_toll(call, nid, v), minimum=0)


def panel_map_do_toll(call, nid, value):
    set_cfg('toll_' + nid, value)
    log_action(call.from_user.id, 'map_toll', nid, str(value))
    send(call.message.chat.id, t('map_saved'))
    panel_map_node(call, nid)


def panel_map_owner(call, nid):
    if not is_admin(call.from_user.id):
        return
    groups = q("SELECT DISTINCT group_id FROM users")
    markup = types.InlineKeyboardMarkup(row_width=1)
    for g in groups:
        markup.add(types.InlineKeyboardButton(
            group_title(g['group_id']),
            callback_data=f'ap:mapowset:{nid}:{g["group_id"]}'))
    markup.add(types.InlineKeyboardButton("🚫 بدون مالک",
                                          callback_data=f'ap:mapowset:{nid}:0'))
    back_btn(markup, f'ap:mapnode:{nid}')
    edit(call, f"مالک {map_name(nid)} را انتخاب کنید:", markup)
    answer(call)


def panel_map_set_owner(call, nid, gid):
    if not is_admin(call.from_user.id):
        return
    set_owner(nid, gid if gid else None)
    log_action(call.from_user.id, 'map_owner', nid, str(gid))
    answer(call, t('map_saved'))
    panel_map_node(call, nid)


def panel_map_delete(call, nid):
    if not is_owner(call.from_user.id):
        answer(call, t('not_owner'), alert=True)
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("🔥 بله حذف کن",
                                          callback_data=f'ap:mapdelok:{nid}'))
    back_btn(markup, f'ap:mapnode:{nid}')
    edit(call, f"❌ <b>حذف {map_name(nid)}</b>\n\nاین کار برگشت‌پذیر نیست.", markup)
    answer(call)


def panel_map_do_delete(call, nid):
    if not is_owner(call.from_user.id):
        return
    mode = map_mode_of(nid)
    map_remove_node(nid)
    log_action(call.from_user.id, 'map_del_node', nid, '')
    answer(call, t('map_deleted'))
    panel_map_nodes(call, mode or 'sea', 0)


def panel_map_edges(call, mode, page=0):
    if not is_admin(call.from_user.id):
        return
    edges = map_edges(mode)
    pages = max(1, (len(edges) + MAP_PAGE_SIZE - 1) // MAP_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    window = edges[page * MAP_PAGE_SIZE:(page + 1) * MAP_PAGE_SIZE]
    markup = types.InlineKeyboardMarkup(row_width=1)
    for e in window:
        markup.add(types.InlineKeyboardButton(
            f"{map_name(e['a'])} ↔ {map_name(e['b'])} ({e['units']})",
            callback_data=f'ap:mapedge:{mode}:{e["a"]}:{e["b"]}'))
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton(t('prev'),
                                              callback_data=f'ap:mapedges:{mode}:{page - 1}'))
    if page < pages - 1:
        nav.append(types.InlineKeyboardButton(t('next'),
                                              callback_data=f'ap:mapedges:{mode}:{page + 1}'))
    if nav:
        markup.add(*nav)
    markup.add(types.InlineKeyboardButton(t('map_add_edge'),
                                          callback_data=f'ap:mapaddedge:{mode}:0'))
    back_btn(markup, f'ap:mapn:{mode}:0')
    edit(call, t('map_edges', mode=t('map_' + mode), p=page + 1, n=pages), markup)
    answer(call)


def panel_map_edge(call, mode, a, b):
    if not is_admin(call.from_user.id):
        return
    e = map_edge(mode, a, b)
    if not e:
        return
    lines = [t('map_edge', a=esc(map_name(a)), b=esc(map_name(b)),
               units=e['units'], min=e['minutes'] or 'خودکار')]
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(t('map_edit_units'),
                                          callback_data=f'ap:mapedgeu:{mode}:{a}:{b}'))
    markup.add(types.InlineKeyboardButton(t('map_edit_minutes'),
                                          callback_data=f'ap:mapedgem:{mode}:{a}:{b}'))
    markup.add(types.InlineKeyboardButton(t('map_del_edge'),
                                          callback_data=f'ap:mapedgedel:{mode}:{a}:{b}'))
    back_btn(markup, f'ap:mapedges:{mode}:0')
    edit(call, '\n'.join(lines), markup)
    answer(call)


def panel_map_edge_units(call, mode, a, b):
    if not is_admin(call.from_user.id):
        return
    e = map_edge(mode, a, b)
    answer(call)
    ask_number(call.message.chat.id, call.from_user.id, call.message,
               f"طول مسیر (فعلی: {e['units']}):",
               lambda v: panel_map_do_edge_units(call, mode, a, b, v), minimum=1)


def panel_map_do_edge_units(call, mode, a, b, value):
    map_set_edge(mode, a, b, units=value)
    log_action(call.from_user.id, 'map_edge_units', f'{a}-{b}', str(value))
    send(call.message.chat.id, t('map_saved'))
    panel_map_edge(call, mode, a, b)


def panel_map_edge_minutes(call, mode, a, b):
    if not is_admin(call.from_user.id):
        return
    e = map_edge(mode, a, b)
    answer(call)
    ask_number(call.message.chat.id, call.from_user.id, call.message,
               f"زمان سفر به دقیقه (فعلی: {e['minutes']}، ۰ = خودکار):",
               lambda v: panel_map_do_edge_minutes(call, mode, a, b, v), minimum=0)


def panel_map_do_edge_minutes(call, mode, a, b, value):
    map_set_edge(mode, a, b, minutes=value)
    log_action(call.from_user.id, 'map_edge_minutes', f'{a}-{b}', str(value))
    send(call.message.chat.id, t('map_saved'))
    panel_map_edge(call, mode, a, b)


def panel_map_edge_delete(call, mode, a, b):
    if not is_owner(call.from_user.id):
        answer(call, t('not_owner'), alert=True)
        return
    map_remove_edge(mode, a, b)
    log_action(call.from_user.id, 'map_edge_del', f'{a}-{b}', '')
    answer(call, t('map_deleted'))
    panel_map_edges(call, mode, 0)


# --- افزودن نود ---

_map_wizards = {}


def panel_map_add_node(call, mode):
    if not is_admin(call.from_user.id):
        return
    _map_wizards[call.from_user.id] = {'mode': mode}
    answer(call)
    sent = send(call.message.chat.id, t('map_ask_id'))
    next_step(sent, call.from_user.id, lambda m: map_add_node_id(call, m, sent))


def map_add_node_id(call, message, anchor):
    user_id = call.from_user.id
    wiz = _map_wizards.get(user_id)
    if not wiz:
        return
    nid = (message.text or '').strip().lower()
    if not KEY_RE.match(nid):
        send(message.chat.id, "شناسه نامعتبر.")
        next_step(anchor, user_id, lambda m: map_add_node_id(call, m, anchor))
        return
    if q("SELECT 1 FROM trade_nodes WHERE id=?", (nid,)):
        send(message.chat.id, "این شناسه قبلاً وجود دارد.")
        next_step(anchor, user_id, lambda m: map_add_node_id(call, m, anchor))
        return
    wiz['id'] = nid
    sent2 = send(message.chat.id, t('map_ask_name'))
    next_step(sent2, user_id, lambda m: map_add_node_name(call, m, sent2))


def map_add_node_name(call, message, anchor):
    user_id = call.from_user.id
    wiz = _map_wizards.get(user_id)
    if not wiz:
        return
    name = (message.text or '').strip()
    if not name:
        send(message.chat.id, "نام خالی.")
        next_step(anchor, user_id, lambda m: map_add_node_name(call, m, anchor))
        return
    wiz['name'] = name
    mode = wiz['mode']
    kinds = ['ocean', 'sea', 'strait', 'canal', 'cape'] if mode == 'sea' else ['region', 'pass']
    markup = types.InlineKeyboardMarkup(row_width=2)
    for k in kinds:
        markup.add(types.InlineKeyboardButton(k,
                                              callback_data=f'ap:mapaddkind:{k}'))
    send(message.chat.id, "نوع:", reply_markup=markup)


def map_add_node_kind(call, kind):
    user_id = call.from_user.id
    wiz = _map_wizards.get(user_id)
    if not wiz:
        return
    wiz['kind'] = kind
    answer(call)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("بله",
                                   callback_data='ap:mapaddhome:1'),
        types.InlineKeyboardButton("خیر",
                                   callback_data='ap:mapaddhome:0'))
    send(call.message.chat.id, "محل استقرار کشورها؟", reply_markup=markup)


def map_add_node_home(call, flag):
    user_id = call.from_user.id
    wiz = _map_wizards.pop(user_id, None)
    if not wiz:
        return
    try:
        map_add_node(wiz['mode'], wiz['id'], wiz['kind'], flag == '1', wiz['name'])
    except ValueError as e:
        send(call.message.chat.id, f"❌ {e}")
        return
    log_action(call.from_user.id, 'map_add_node', wiz['id'], wiz['kind'])
    answer(call, t('map_saved'))
    send(call.message.chat.id, f"✅ {wiz['name']} اضافه شد.")
    panel_map_node(call, wiz['id'])


# --- افزودن یال ---

_edge_wizards = {}


def panel_map_add_edge(call, mode, page=0):
    if not is_admin(call.from_user.id):
        return
    _edge_wizards[call.from_user.id] = {'mode': mode}
    _pick_first_node(call, mode, page)


def _pick_first_node(call, mode, page=0):
    nodes = list(map_nodes(mode).items())
    pages = max(1, (len(nodes) + MAP_PAGE_SIZE - 1) // MAP_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    window = nodes[page * MAP_PAGE_SIZE:(page + 1) * MAP_PAGE_SIZE]
    markup = types.InlineKeyboardMarkup(row_width=2)
    for nid, n in window:
        markup.add(types.InlineKeyboardButton(map_name(nid),
                                              callback_data=f'ap:mapedge1:{mode}:{nid}'))
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton(t('prev'),
                                              callback_data=f'ap:mapaddedge:{mode}:{page - 1}'))
    if page < pages - 1:
        nav.append(types.InlineKeyboardButton(t('next'),
                                              callback_data=f'ap:mapaddedge:{mode}:{page + 1}'))
    if nav:
        markup.add(*nav)
    answer(call)
    send(call.message.chat.id, "مبدأ:", reply_markup=markup)


def panel_map_edge_first(call, mode, nid):
    user_id = call.from_user.id
    wiz = _edge_wizards.get(user_id)
    if not wiz:
        return
    wiz['a'] = nid
    answer(call)
    _pick_second_node(call, mode)


def _pick_second_node(call, mode, page=0):
    wiz = _edge_wizards.get(call.from_user.id)
    if not wiz or 'a' not in wiz:
        return
    nodes = [(nid, n) for nid, n in map_nodes(mode).items() if nid != wiz['a']]
    pages = max(1, (len(nodes) + MAP_PAGE_SIZE - 1) // MAP_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    window = nodes[page * MAP_PAGE_SIZE:(page + 1) * MAP_PAGE_SIZE]
    markup = types.InlineKeyboardMarkup(row_width=2)
    for nid, n in window:
        markup.add(types.InlineKeyboardButton(map_name(nid),
                                              callback_data=f'ap:mapedge2:{mode}:{nid}'))
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton(t('prev'),
                                              callback_data=f'ap:mapedge2p:{mode}:{page - 1}'))
    if page < pages - 1:
        nav.append(types.InlineKeyboardButton(t('next'),
                                              callback_data=f'ap:mapedge2p:{mode}:{page + 1}'))
    if nav:
        markup.add(*nav)
    send(call.message.chat.id, "مقصد:", reply_markup=markup)


def panel_map_edge_second(call, mode, nid, page=0):
    user_id = call.from_user.id
    wiz = _edge_wizards.get(user_id)
    if not wiz:
        return
    wiz['b'] = nid
    answer(call)
    sent = send(call.message.chat.id, t('map_ask_units'))
    next_step(sent, user_id, lambda m: map_edge_units(call, m, sent))


def map_edge_units(call, message, anchor):
    user_id = call.from_user.id
    wiz = _edge_wizards.get(user_id)
    if not wiz:
        return
    try:
        val = int((message.text or '').strip())
        if val < 1:
            raise ValueError
    except (ValueError, AttributeError):
        send(message.chat.id, t('cat_bad_number'))
        next_step(anchor, user_id, lambda m: map_edge_units(call, m, anchor))
        return
    try:
        map_add_edge(wiz['mode'], wiz['a'], wiz['b'], val)
    except ValueError as e:
        send(message.chat.id, f"❌ {e}")
        _edge_wizards.pop(user_id, None)
        return
    log_action(call.from_user.id, 'map_add_edge', f"{wiz['a']}-{wiz['b']}", str(val))
    send(message.chat.id, t('map_saved'))
    _edge_wizards.pop(user_id, None)
    panel_map_edges(call, wiz['mode'], 0)


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۲۴: تنظیمات تجارت (ادمین)
# ═══════════════════════════════════════════════════════════════════════════

CFG_LABELS = {
    'sea_min_per_unit': "⏱ زمان سفر دریایی (دقیقه/واحد)",
    'land_min_per_unit': "⏱ زمان سفر زمینی (دقیقه/واحد)",
    'fee_per_unit': "💵 کرایه مسیر (پول/واحد)",
    'offer_expiry_min': "⌛️ مهلت پاسخ پیشنهاد (دقیقه)",
    'cap_small': "⛵ ظرفیت کشتی کوچک",
    'cap_medium': "🚢 ظرفیت کشتی متوسط",
    'cap_large': "🛳 ظرفیت کشتی بزرگ",
    'cap_caravan': "🐫 ظرفیت کاروان",
    'caravan_cost': "💰 هزینه هر کاروان در هر سفر",
}

CFG_SECTIONS = {
    'journey': ('sea_min_per_unit', 'land_min_per_unit', 'fee_per_unit', 'offer_expiry_min'),
    'capacity': ('cap_small', 'cap_medium', 'cap_large', 'cap_caravan', 'caravan_cost'),
    'toll': None,  # پویا
}


def panel_cfg(call):
    if not is_admin(call.from_user.id):
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for sec, label in (('journey', t('cfg_journey')),
                       ('capacity', t('cfg_capacity')),
                       ('toll', t('cfg_toll'))):
        keys = _cfg_keys(sec)
        markup.add(types.InlineKeyboardButton(f"{label} ({len(keys)})",
                                              callback_data=f'ap:cfg:{sec}:0'))
    back_btn(markup, 'ap:home')
    edit(call, t('cfg_title'), markup)
    answer(call)


def _cfg_keys(section):
    if section == 'toll':
        return ['toll_' + nid for nid in map_chokepoints()]
    return list(CFG_SECTIONS.get(section, ()))


def panel_cfg_section(call, section, page=0):
    if not is_admin(call.from_user.id):
        return
    keys = _cfg_keys(section)
    pages = max(1, (len(keys) + CAT_PAGE_SIZE - 1) // CAT_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    window = keys[page * CAT_PAGE_SIZE:(page + 1) * CAT_PAGE_SIZE]
    markup = types.InlineKeyboardMarkup(row_width=1)
    for k in window:
        lbl = CFG_LABELS.get(k, k)
        if k.startswith('toll_'):
            nid = k[5:]
            lbl = f"🛣 عوارض {map_name(nid)}"
        markup.add(types.InlineKeyboardButton(f"{lbl} — {cfg(k)}",
                                              callback_data=f'ap:cfgk:{k}'))
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton(t('prev'),
                                              callback_data=f'ap:cfg:{section}:{page - 1}'))
    if page < pages - 1:
        nav.append(types.InlineKeyboardButton(t('next'),
                                              callback_data=f'ap:cfg:{section}:{page + 1}'))
    if nav:
        markup.add(*nav)
    back_btn(markup, 'ap:cfg')
    edit(call, f"⚙️ {section} (صفحه {page + 1}/{pages}):", markup)
    answer(call)


def panel_cfg_edit(call, key):
    if not is_admin(call.from_user.id):
        return
    cur = cfg(key)
    lbl = CFG_LABELS.get(key, key)
    if key.startswith('toll_'):
        nid = key[5:]
        lbl = f"عوارض {map_name(nid)}"
    answer(call)
    ask_number(call.message.chat.id, call.from_user.id, call.message,
               t('cfg_ask', name=lbl, val=cur),
               lambda v: panel_cfg_save(call, key, v), minimum=0)


def panel_cfg_save(call, key, value):
    set_cfg(key, value)
    log_action(call.from_user.id, 'cfg_set', key, str(value))
    send(call.message.chat.id, t('cfg_saved'))


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۲۵: عکس‌های جنگ (ادمین)
# ═══════════════════════════════════════════════════════════════════════════


def panel_war_photo(call):
    if not is_admin(call.from_user.id):
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for mode in ('land', 'sea'):
        cur = get_setting('war_photo_' + mode, '')
        state = t('wp_set') if cur else t('wp_unset')
        markup.add(types.InlineKeyboardButton(
            f"{t('wp_' + mode)} — {state}",
            callback_data=f'ap:wpask:{mode}'))
        if cur:
            markup.add(types.InlineKeyboardButton(
                f"🗑 حذف {t('wp_' + mode)}",
                callback_data=f'ap:wpclear:{mode}'))
    back_btn(markup, 'ap:home')
    edit(call, t('wp_title'), markup)
    answer(call)


def panel_war_photo_ask(call, mode):
    if not is_admin(call.from_user.id):
        return
    answer(call)
    sent = send(call.message.chat.id, t('wp_ask'))
    next_step(sent, call.from_user.id,
              lambda m: panel_war_photo_save(call, mode, m))


def panel_war_photo_save(call, mode, message):
    if not is_admin(call.from_user.id):
        return
    if not getattr(message, 'photo', None):
        send(message.chat.id, t('wp_not_photo'))
        return
    file_id = message.photo[-1].file_id
    set_setting('war_photo_' + mode, file_id)
    log_action(call.from_user.id, 'war_photo', mode, 'set')
    send(message.chat.id, t('wp_saved'))


def panel_war_photo_clear(call, mode):
    if not is_admin(call.from_user.id):
        return
    set_setting('war_photo_' + mode, '')
    log_action(call.from_user.id, 'war_photo', mode, 'cleared')
    answer(call, "🗑 حذف شد.")
    panel_war_photo(call)


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۲۶: آمار و مدیریت کشورها (ادمین)
# ═══════════════════════════════════════════════════════════════════════════


def panel_stats(call):
    if not is_admin(call.from_user.id):
        return
    groups = q("SELECT COUNT(*) AS n FROM users")[0]['n']
    resources = cat_keys('resource')
    units = cat_keys('unit')
    lines = ["📊 <b>آمار کلی</b>", ""]
    lines.append(f"🏳 کشورها: {groups}")
    total_res = 0
    total_units = 0
    for r in resources:
        s = q(f"SELECT COALESCE(SUM({r}), 0) AS s FROM users")[0]['s']
        total_res += s
    for u in units:
        s = q(f"SELECT COALESCE(SUM({u}), 0) AS s FROM users")[0]['s']
        total_units += s
    lines.append(f"💰 مجموع منابع: {total_res:,}")
    lines.append(f"⚔️ مجموع نیروها: {total_units:,}")
    lines.append("")
    lines.append("💰 <b>منابع:</b>")
    for r in resources:
        s = q(f"SELECT COALESCE(SUM({r}), 0) AS s FROM users")[0]['s']
        lines.append(f"  {cat_label(r)}: {s:,}")
    lines.append("")
    lines.append("⚔️ <b>نیروها:</b>")
    for u in units:
        s = q(f"SELECT COALESCE(SUM({u}), 0) AS s FROM users")[0]['s']
        lines.append(f"  {cat_label(u)}: {s:,}")
    markup = types.InlineKeyboardMarkup()
    back_btn(markup, 'ap:home')
    edit(call, '\n'.join(lines), markup)
    answer(call)


def panel_countries(call, page=0):
    if not is_admin(call.from_user.id):
        return
    groups = q("SELECT DISTINCT group_id FROM users ORDER BY group_id")
    if not groups:
        edit(call, "هیچ کشوری نیست.", back_btn(types.InlineKeyboardMarkup(), 'ap:home'))
        answer(call)
        return
    pages = max(1, (len(groups) + CAT_PAGE_SIZE - 1) // CAT_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    window = groups[page * CAT_PAGE_SIZE:(page + 1) * CAT_PAGE_SIZE]
    markup = types.InlineKeyboardMarkup(row_width=1)
    for g in window:
        gid = g['group_id']
        markup.add(types.InlineKeyboardButton(group_title(gid),
                                              callback_data=f'ap:g:{gid}'))
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton(t('prev'), callback_data=f'ap:countries:{page - 1}'))
    if page < pages - 1:
        nav.append(types.InlineKeyboardButton(t('next'), callback_data=f'ap:countries:{page + 1}'))
    if nav:
        markup.add(*nav)
    back_btn(markup, 'ap:home')
    edit(call, f"🏳 کشورها (صفحه {page + 1}/{pages}):", markup)
    answer(call)


def panel_country_card(call, gid):
    if not is_admin(call.from_user.id):
        return
    all_keys = list(cat_all_keys())
    balances = get_balances(gid, all_keys)
    if not balances:
        answer(call, "یافت نشد.", alert=True)
        return
    lord = get_lord(gid)
    lines = [f"🏳 <b>{esc(group_title(gid))}</b>"]
    lines.append(f"👤 لرد: {user_link(lord) if lord else 'ندارد'}")
    lines.append("")
    lines.append("💰 منابع:")
    for k in cat_keys('resource'):
        lines.append(f"  {cat_label(k)}: {balances.get(k, 0):,}")
    lines.append("")
    lines.append("⚔️ نیروها:")
    for k in cat_keys('unit'):
        lines.append(f"  {cat_label(k)}: {balances.get(k, 0):,}")
    lines.append("")
    lines.append("🏭 ساختمون‌ها:")
    for k in cat_keys('building'):
        lines.append(f"  {cat_label(k)}: سطح {balances.get(k, 0)}")
    markup = types.InlineKeyboardMarkup()
    back_btn(markup, 'ap:countries:0')
    edit(call, '\n'.join(lines), markup)
    answer(call)


def panel_features(call):
    if not is_admin(call.from_user.id):
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for key in FEATURES:
        state = '✅' if feature_enabled(key) else '❌'
        markup.add(types.InlineKeyboardButton(
            f"{state} {t('feat_' + key)}",
            callback_data=f'ap:ft:{key}'))
    back_btn(markup, 'ap:home')
    edit(call, "⚙️ بخش‌ها:", markup)
    answer(call)


def panel_toggle_feature(call, key):
    if not is_admin(call.from_user.id):
        return
    if key not in FEATURES:
        answer(call, t('err_generic'))
        return
    new_state = not feature_enabled(key)
    set_feature(key, new_state)
    log_action(call.from_user.id, 'feature_toggle', key, 'on' if new_state else 'off')
    answer(call, f"{t('feat_' + key)}: {'فعال' if new_state else 'غیرفعال'}")
    panel_features(call)


def panel_log(call, page=0):
    if not is_admin(call.from_user.id):
        return
    LIMIT, PAGE_SIZE = 200, 10
    rows = q("SELECT * FROM admin_log ORDER BY id DESC LIMIT ?", (LIMIT,))
    if not rows:
        edit(call, t('log_empty'), back_btn(types.InlineKeyboardMarkup(), 'ap:home'))
        answer(call)
        return
    pages = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    window = rows[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    lines = [t('log_title', p=page + 1, n=pages), ""]
    for r in window:
        ts = time.strftime('%Y-%m-%d %H:%M', time.localtime(r['ts']))
        lines.append(t('log_row', action=r['action'],
                       actor=user_link(r['actor_id']),
                       target=r['target'],
                       detail=(' — ' + esc(r['detail'])) if r['detail'] else '',
                       ts=ts))
        lines.append("")
    markup = types.InlineKeyboardMarkup(row_width=2)
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton(t('prev'), callback_data=f'ap:log:{page - 1}'))
    if page < pages - 1:
        nav.append(types.InlineKeyboardButton(t('next'), callback_data=f'ap:log:{page + 1}'))
    if nav:
        markup.add(*nav)
    back_btn(markup, 'ap:home')
    edit(call, '\n'.join(lines), markup)
    answer(call)


def panel_admins(call):
    if not is_owner(call.from_user.id):
        answer(call, t('not_owner'), alert=True)
        return
    extra = q("SELECT user_id FROM bot_admins ORDER BY added_at")
    lines = [f"👑 مالک: {user_link(ADMIN_ID)}", ""]
    if extra:
        lines.append("ادمین‌های اضافه:")
        for r in extra:
            lines.append(f"  • {user_link(r['user_id'])}")
    else:
        lines.append("ادمین دیگری وجود ندارد.")
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("➕ افزودن ادمین", callback_data='ap:addadm'))
    if extra:
        for r in extra:
            markup.add(types.InlineKeyboardButton(
                f"🗑 حذف {r['user_id']}",
                callback_data=f'ap:rmadm:{r["user_id"]}'))
    back_btn(markup, 'ap:home')
    edit(call, '\n'.join(lines), markup)
    answer(call)


def panel_add_admin_start(call):
    if not is_owner(call.from_user.id):
        return
    answer(call)
    sent = send(call.message.chat.id,
                "پیامی از کاربر را فوروارد کنید یا شناسه عددی را بفرستید:")
    next_step(sent, call.from_user.id,
              lambda m: panel_add_admin_apply(call, m))


def panel_add_admin_apply(call, message):
    if not is_owner(call.from_user.id):
        return
    uid = None
    if getattr(message, 'forward_from', None):
        uid = message.forward_from.id
    elif message.text:
        try:
            uid = int(message.text.strip())
        except ValueError:
            pass
    if uid is None:
        send(message.chat.id, "شناسه معتبر نیست.")
        return
    if uid == ADMIN_ID:
        send(message.chat.id, "این کاربر مالک است.")
        return
    if q("SELECT 1 FROM bot_admins WHERE user_id=?", (uid,)):
        send(message.chat.id, "قبلاً ادمین است.")
        return
    ex("INSERT INTO bot_admins (user_id, added_at) VALUES (?, ?)", (uid, int(time.time())))
    log_action(call.from_user.id, 'admin_add', str(uid), '')
    send(message.chat.id, f"✅ {user_link(uid)} ادمین شد.")


def panel_remove_admin(call, uid):
    if not is_owner(call.from_user.id):
        return
    if uid == ADMIN_ID:
        return
    ex("DELETE FROM bot_admins WHERE user_id=?", (uid,))
    log_action(call.from_user.id, 'admin_remove', str(uid), '')
    answer(call, "🗑 حذف شد.")
    panel_admins(call)


def panel_reset(call):
    if not is_admin(call.from_user.id):
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(
        "♻️ بازنشانی کاتالوگ به حالت اولیه",
        callback_data='ap:resetok'))
    back_btn(markup, 'ap:home')
    edit(call, "♻️ بازنشانی کاتالوگ؟\n\n⚠️ همه ویرایش‌ها پاک می‌شود.", markup)
    answer(call)


def panel_reset_apply(call):
    if not is_owner(call.from_user.id):
        return
    with DB_LOCK:
        conn.execute("DELETE FROM asset_catalog")
        conn.execute("DELETE FROM asset_labels")
        conn.execute("DELETE FROM asset_upgrade_costs")
        conn.execute("DELETE FROM asset_production_inputs")
        conn.execute("DELETE FROM asset_kind_order")
        conn.commit()
    _seed_catalog()
    for kind, i in (('resource', 1), ('building', 2), ('unit', 3)):
        ex("INSERT OR IGNORE INTO asset_kind_order (kind, position) VALUES (?, ?)",
           (kind, i * 10))
    log_action(call.from_user.id, 'reset_catalog', '', '')
    answer(call, "✅ کاتالوگ بازنشانی شد.")
    panel_home(call)


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۲۷: تیکر تجارت (پس‌زمینه)
# ═══════════════════════════════════════════════════════════════════════════


def _tick_trades():
    """منقضی کردن پیشنهادها و پردازش محموله‌های در راه."""
    now = int(time.time())
    expiry = cfg('offer_expiry_min') * 60
    stale = q("SELECT * FROM trades WHERE status='offered' AND offered_at + ? <= ?",
              (expiry, now))
    for trade in stale:
        goods = json.loads(trade['goods'])
        with DB_LOCK:
            cols = list(goods.keys())
            sets = ', '.join(f"{k} = {k} + ?" for k in cols)
            params = [goods[k] for k in cols]
            sets += ", money = money + ?"
            params.append(trade['fee_paid'])
            params.append(trade['sender_group_id'])
            conn.execute(f"UPDATE users SET {sets} WHERE group_id=?", params)
            vehicles = json.loads(trade['vehicles'])
            if vehicles:
                vcols = list(vehicles.keys())
                vsets = ', '.join(f"{k} = {k} + ?" for k in vcols)
                vparams = [vehicles[k] for k in vcols] + [trade['sender_group_id']]
                conn.execute(f"UPDATE users SET {vsets} WHERE group_id=?", vparams)
            conn.execute("UPDATE trades SET status='expired' WHERE id=?", (trade['id'],))
            conn.commit()
        try:
            send(trade['sender_group_id'], f"⌛️ پیشنهاد #{trade['id']} منقضی شد.")
        except Exception:
            pass


def _start_ticker():
    def loop():
        while True:
            try:
                _tick_trades()
            except Exception:
                traceback.print_exc()
            time.sleep(60)
    t_ = threading.Thread(target=loop, daemon=True)
    t_.start()


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۲۸: هندلر اصلی callback
# ═══════════════════════════════════════════════════════════════════════════


def panel_home(call):
    if not is_admin(call.from_user.id):
        answer(call, t('not_admin'), alert=True)
        return
    groups = q("SELECT COUNT(*) AS n FROM users")[0]['n']
    admins = len(admin_ids())
    enabled = sum(1 for k in FEATURES if feature_enabled(k))
    text = t('panel_title', owner=user_link(ADMIN_ID), admins=admins,
             groups=groups, on=enabled, total=len(FEATURES))
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(t('panel_stats'), callback_data='ap:stats'),
        types.InlineKeyboardButton(t('panel_econ'), callback_data='ap:stats'))
    markup.add(
        types.InlineKeyboardButton(t('panel_mil'), callback_data='ap:stats'),
        types.InlineKeyboardButton(t('panel_catalog'), callback_data='ap:cat'))
    markup.add(
        types.InlineKeyboardButton(t('panel_countries'), callback_data='ap:countries:0'),
        types.InlineKeyboardButton(t('panel_features'), callback_data='ap:feat'))
    markup.add(
        types.InlineKeyboardButton(t('panel_log'), callback_data='ap:log:0'),
        types.InlineKeyboardButton(t('panel_reset'), callback_data='ap:reset'))
    markup.add(
        types.InlineKeyboardButton("🎛 دارایی کشورها", callback_data='ap:cal:0'),
        types.InlineKeyboardButton("🗺 نقشه تجارت", callback_data='ap:map'))
    markup.add(
        types.InlineKeyboardButton("⚙️ تنظیمات تجارت", callback_data='ap:cfg'),
        types.InlineKeyboardButton("🖼 عکس جنگ", callback_data='ap:wp'))
    if is_owner(call.from_user.id):
        markup.add(types.InlineKeyboardButton(t('panel_admins'), callback_data='ap:admins'))
    edit(call, text, markup)
    answer(call)


@bot.callback_query_handler(func=lambda call: True)
def on_callback(call):
    try:
        data = call.data or ''

        # ========== پنل ادمین ==========
        if data.startswith('ap:'):
            parts = data.split(':')
            op = parts[1] if len(parts) > 1 else ''

            if op == 'home': panel_home(call)
            elif op == 'stats': panel_stats(call)
            elif op == 'econ': panel_stats(call)
            elif op == 'mil': panel_stats(call)
            elif op == 'cat': panel_catalog(call)
            elif op == 'catk': panel_cat_kind(call, parts[2], int(parts[3]))
            elif op == 'cate': panel_cat_entry(call, parts[2])
            elif op == 'catren': cat_ask_rename(call, parts[2])
            elif op == 'catdef': cat_ask_default(call, parts[2])
            elif op == 'catout': cat_ask_output(call, parts[2])
            elif op == 'catoutpick': cat_pick_output_target(call, parts[2], parts[3])
            elif op == 'catinput': cat_ask_input(call, parts[2])
            elif op == 'catinputedit': cat_edit_input(call, parts[2], parts[3])
            elif op == 'catcost': cat_ask_cost(call, parts[2])
            elif op == 'catcostedit': cat_edit_cost(call, parts[2], parts[3])
            elif op == 'catmax': cat_ask_max(call, parts[2])
            elif op == 'cathide': cat_hide(call, parts[2])
            elif op == 'catunhide': cat_unhide(call, parts[2])
            elif op == 'catdel': cat_ask_delete(call, parts[2])
            elif op == 'catdelok': cat_do_delete(call, parts[2])
            elif op == 'catadd': cat_add_start(call, parts[2])
            elif op == 'cataddprod': cat_add_pick_produces(call, parts[2])
            elif op == 'catorder': panel_cat_order(call)
            elif op == 'catorderup': cat_move_kind(call, parts[2], 'up')
            elif op == 'catorderdn': cat_move_kind(call, parts[2], 'down')
            # country assets
            elif op == 'cal': panel_ca_list(call, int(parts[2]))
            elif op == 'ca': panel_ca_country(call, int(parts[2]))
            elif op == 'cak': panel_ca_kind(call, int(parts[2]), parts[3], int(parts[4]))
            elif op == 'catoggle': panel_ca_toggle(call, int(parts[2]), parts[3])
            elif op == 'capause': panel_ca_pause(call, int(parts[2]), parts[3])
            elif op == 'caclear': panel_ca_clear(call, int(parts[2]))
            # map
            elif op == 'map': panel_map(call)
            elif op == 'mapn': panel_map_nodes(call, parts[2], int(parts[3]))
            elif op == 'mapnode': panel_map_node(call, parts[2])
            elif op == 'mapren': panel_map_rename(call, parts[2])
            elif op == 'mapkind': panel_map_kind(call, parts[2])
            elif op == 'mapsk': panel_map_set_kind(call, parts[2], parts[3])
            elif op == 'maphome': panel_map_home(call, parts[2])
            elif op == 'maptoll': panel_map_toll(call, parts[2])
            elif op == 'mapowner': panel_map_owner(call, parts[2])
            elif op == 'mapowset': panel_map_set_owner(call, parts[2], int(parts[3]))
            elif op == 'mapdel': panel_map_delete(call, parts[2])
            elif op == 'mapdelok': panel_map_do_delete(call, parts[2])
            elif op == 'mapedges': panel_map_edges(call, parts[2], int(parts[3]))
            elif op == 'mapedge': panel_map_edge(call, parts[2], parts[3], parts[4])
            elif op == 'mapedgeu': panel_map_edge_units(call, parts[2], parts[3], parts[4])
            elif op == 'mapedgem': panel_map_edge_minutes(call, parts[2], parts[3], parts[4])
            elif op == 'mapedgedel': panel_map_edge_delete(call, parts[2], parts[3], parts[4])
            elif op == 'mapadd': panel_map_add_node(call, parts[2])
            elif op == 'mapaddkind': map_add_node_kind(call, parts[2])
            elif op == 'mapaddhome': map_add_node_home(call, parts[2])
            elif op == 'mapaddedge': panel_map_add_edge(call, parts[2], int(parts[3]))
            elif op == 'mapedge1': panel_map_edge_first(call, parts[2], parts[3])
            elif op == 'mapedge2': panel_map_edge_second(call, parts[2], parts[3])
            elif op == 'mapedge2p': _pick_second_node(call, parts[2], int(parts[3]))
            # config
            elif op == 'cfg': panel_cfg_section(call, parts[2], int(parts[3]))
            elif op == 'cfgk': panel_cfg_edit(call, parts[2])
            # war photos
            elif op == 'wp': panel_war_photo(call)
            elif op == 'wpask': panel_war_photo_ask(call, parts[2])
            elif op == 'wpclear': panel_war_photo_clear(call, parts[2])
            # countries
            elif op == 'countries': panel_countries(call, int(parts[2]))
            elif op == 'g': panel_country_card(call, int(parts[2]))
            # features
            elif op == 'feat': panel_features(call)
            elif op == 'ft': panel_toggle_feature(call, parts[2])
            # log
            elif op == 'log': panel_log(call, int(parts[2]))
            # admins
            elif op == 'admins': panel_admins(call)
            elif op == 'addadm': panel_add_admin_start(call)
            elif op == 'rmadm': panel_remove_admin(call, int(parts[2]))
            # reset
            elif op == 'reset': panel_reset(call)
            elif op == 'resetok': panel_reset_apply(call)
            else:
                answer(call, t('err_generic'))
            return

        # ========== منوی بازیکن ==========
        if data.startswith('menu:'):
            op = data.split(':')[1]
            user_id = call.from_user.id
            chat_id = call.message.chat.id
            if op == 'home':
                answer(call)
                send_main_menu(chat_id, user_id)
            elif op == 'assets':
                if not feature_enabled('assets'):
                    answer(call, t('feature_disabled'), alert=True); return
                answer(call)
                show_assets(chat_id, chat_id)
            elif op == 'upgrade':
                if not feature_enabled('upgrade'):
                    answer(call, t('feature_disabled'), alert=True); return
                answer(call)
                upgrade_menu(chat_id, chat_id)
            elif op == 'weekly':
                if not feature_enabled('weekly'):
                    answer(call, t('feature_disabled'), alert=True); return
                answer(call)
                weekly_update(chat_id, chat_id)
            elif op == 'war':
                if not feature_enabled('war'):
                    answer(call, t('feature_disabled'), alert=True); return
                answer(call)
                start_war(chat_id, user_id)
            elif op == 'trade':
                if not feature_enabled('trade'):
                    answer(call, t('feature_disabled'), alert=True); return
                start_trade(call)
            elif op == 'statement':
                if not feature_enabled('statement'):
                    answer(call, t('feature_disabled'), alert=True); return
                start_statement(call)
            elif op == 'treaty':
                if not feature_enabled('treaty'):
                    answer(call, t('feature_disabled'), alert=True); return
                start_treaty(call)
            elif op == 'private':
                if not feature_enabled('private'):
                    answer(call, t('feature_disabled'), alert=True); return
                start_private(call)
            return

        # ========== ارتقا ==========
        if data.startswith('up:'):
            parts = data.split(':')
            if parts[1] == 'c': confirm_upgrade(call, parts[2])
            elif parts[1] == 'y': do_upgrade(call, parts[2])
            return

        # ========== جنگ ==========
        if data.startswith('war:'):
            parts = data.split(':')
            op = parts[1]
            if op == 't': war_pick_type(call, parts[2])
            elif op == 'u': war_ask_count(call, parts[2])
            elif op == 'ud': war_troops_done(call)
            elif op == 'ok': war_send(call)
            elif op == 'x': war_cancel(call)
            return

        # ========== تجارت ==========
        if data.startswith('trade:'):
            parts = data.split(':')
            op = parts[1]
            if op == 'm': trade_pick_mode(call, parts[2])
            elif op == 'd': trade_pick_dest(call, int(parts[2]))
            elif op == 'g': trade_ask_amount(call, parts[2])
            elif op == 'gd': trade_goods_done(call)
            elif op == 'v': trade_ask_vehicle_count(call, parts[2])
            elif op == 'vd': trade_vehicles_done(call)
            elif op == 'nextroute': trade_next_route(call)
            elif op == 'ok': trade_send_offer(call)
            elif op == 'x': trade_cancel(call)
            elif op == 'a': trade_accept(call, int(parts[2]))
            elif op == 'n': trade_decline(call, int(parts[2]))
            return

        # ========== پیام خصوصی ==========
        if data.startswith('priv:'):
            parts = data.split(':')
            if parts[1] == 'send':
                priv_send(call, int(parts[2]))
            return

        answer(call, t('err_generic'))
    except Exception:
        traceback.print_exc()
        try:
            answer(call, t('err_generic'), alert=True)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۲۹: هندلرهای دستور
# ═══════════════════════════════════════════════════════════════════════════


@bot.message_handler(commands=['start'])
def cmd_start(message):
    send_main_menu(message.chat.id, message.from_user.id)


@bot.message_handler(commands=['admin'])
def cmd_admin(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, t('not_admin'))
        return
    # پیام اول پنل رو می‌فرستیم (بدون call ساختگی)
    groups = q("SELECT COUNT(*) AS n FROM users")[0]['n']
    admins = len(admin_ids())
    enabled = sum(1 for k in FEATURES if feature_enabled(k))
    text = t('panel_title', owner=user_link(ADMIN_ID), admins=admins,
             groups=groups, on=enabled, total=len(FEATURES))
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(t('panel_stats'), callback_data='ap:stats'),
        types.InlineKeyboardButton(t('panel_econ'), callback_data='ap:stats'))
    markup.add(
        types.InlineKeyboardButton(t('panel_mil'), callback_data='ap:stats'),
        types.InlineKeyboardButton(t('panel_catalog'), callback_data='ap:cat'))
    markup.add(
        types.InlineKeyboardButton(t('panel_countries'), callback_data='ap:countries:0'),
        types.InlineKeyboardButton(t('panel_features'), callback_data='ap:feat'))
    markup.add(
        types.InlineKeyboardButton(t('panel_log'), callback_data='ap:log:0'),
        types.InlineKeyboardButton(t('panel_reset'), callback_data='ap:reset'))
    markup.add(
        types.InlineKeyboardButton("🎛 دارایی کشورها", callback_data='ap:cal:0'),
        types.InlineKeyboardButton("🗺 نقشه تجارت", callback_data='ap:map'))
    markup.add(
        types.InlineKeyboardButton("⚙️ تنظیمات تجارت", callback_data='ap:cfg'),
        types.InlineKeyboardButton("🖼 عکس جنگ", callback_data='ap:wp'))
    if is_owner(message.from_user.id):
        markup.add(types.InlineKeyboardButton(t('panel_admins'), callback_data='ap:admins'))
    send(message.chat.id, text, reply_markup=markup)


@bot.message_handler(commands=['setlord'])
def cmd_setlord(message):
    if message.chat.type not in ('group', 'supergroup'):
        bot.reply_to(message, "این دستور فقط در گروه‌ها کار می‌کند.")
        return
    if not feature_enabled('setlord'):
        bot.reply_to(message, t('feature_disabled'))
        return
    if not is_admin(message.from_user.id):
        bot.reply_to(message, t('not_admin'))
        return
    reply = getattr(message, 'reply_to_message', None)
    if not reply or not reply.from_user:
        bot.reply_to(message, "روی پیام بازیکن ریپلای کنید.")
        return
    target = reply.from_user
    if getattr(target, 'is_bot', False):
        bot.reply_to(message, "ربات نمی‌تواند لرد شود.")
        return
    group_id = message.chat.id
    if is_lord(group_id, target.id):
        bot.reply_to(message, f"{user_link(target.id)} قبلاً لرد است.")
        return
    # حذف لرد قبلی + پر کردن مقادیر پیش‌فرض
    with DB_LOCK:
        conn.execute("DELETE FROM users WHERE group_id=?", (group_id,))
        cols = list(cat_all_keys())
        defaults = cat_defaults()
        col_names = ['user_id', 'group_id'] + cols
        placeholders = ', '.join('?' * len(col_names))
        values = [target.id, group_id] + [defaults.get(c, 0) for c in cols]
        conn.execute(f"INSERT INTO users ({', '.join(col_names)}) VALUES ({placeholders})",
                     values)
        conn.commit()
    log_action(message.from_user.id, 'setlord', group_title(group_id), str(target.id))
    bot.reply_to(message, f"👤 {user_link(target.id)} به عنوان لرد ثبت شد.",
                 parse_mode='HTML')


@bot.message_handler(commands=['unsetlord'])
def cmd_unsetlord(message):
    if message.chat.type not in ('group', 'supergroup'):
        return
    if not is_owner(message.from_user.id):
        bot.reply_to(message, t('not_owner'))
        return
    group_id = message.chat.id
    ex("DELETE FROM users WHERE group_id=?", (group_id,))
    log_action(message.from_user.id, 'unsetlord', group_title(group_id), '')
    bot.reply_to(message, "✅ گروه بازنشسته شد.")


@bot.message_handler(commands=['on'])
def cmd_on(message):
    if not is_admin(message.from_user.id):
        return
    set_setting('players_enabled', '1')
    bot.reply_to(message, "✅ ربات فعال شد.")


@bot.message_handler(commands=['off'])
def cmd_off(message):
    if not is_admin(message.from_user.id):
        return
    set_setting('players_enabled', '0')
    bot.reply_to(message, "⛔️ ربات غیرفعال شد.")


@bot.message_handler(commands=['weekly'])
def cmd_weekly(message):
    """اجرای دستی آپ هفتگی توسط ادمین."""
    if not is_admin(message.from_user.id):
        return
    groups = q("SELECT DISTINCT group_id FROM users")
    count = 0
    for g in groups:
        try:
            r = weekly_update(None, g['group_id'], silent=True)
            if r:
                count += 1
        except Exception:
            traceback.print_exc()
    bot.reply_to(message, t('weekly_adm_done', n=count))
    log_action(message.from_user.id, 'weekly_adm', '', f'{count} groups')


@bot.message_handler(func=lambda m: (m.text or '').strip().lower() in ('panel', 'پنل'))
def cmd_panel_word(message):
    send_main_menu(message.chat.id, message.from_user.id)


# ═══════════════════════════════════════════════════════════════════════════
# بخش ۳۰: راه‌اندازی
# ═══════════════════════════════════════════════════════════════════════════


def main():
    print("🚀 راه‌اندازی ربات جنگ‌های صلیبی...")
    init_db()
    print(f"✅ دیتابیس آماده. ادمین: {ADMIN_ID}")
    _start_ticker()
    print("📡 شروع polling...")
    bot.infinity_polling()


if __name__ == '__main__':
    main()
