# -*- coding: utf-8 -*-
"""
籟柏太極易占 LINE Bot
Version: 1.1.0 - 加入搖卦儀式
"""

import os
from dotenv import load_dotenv
load_dotenv()

import random
import sqlite3
from datetime import datetime
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage, ImageMessage,
    QuickReply, QuickReplyItem, PostbackAction
)
from linebot.v3.webhooks import (
    MessageEvent, PostbackEvent, FollowEvent,
    TextMessageContent
)
from linebot.v3.exceptions import InvalidSignatureError
import pytz

from data.hexagrams import TRIGRAMS, get_hexagram, CATEGORIES, FORTUNE_LEVELS
from data.shichen import get_current_shichen, format_shichen_tip
from data.crystals import recommend_crystal, format_crystal_basic
from utils.question_lock import QuestionLock, get_question_category
from utils.template_render import render_basic_template, render_detailed_template, render_premium_template

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', '')
CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET', '')

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

DB_PATH = 'yizhan.db'
user_states = {}

# 太極圖片網址
TAIJI_IMAGE_URL = 'https://hml1980.github.io/laibai-linebot/images/taiji_ritual.png'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_premium INTEGER DEFAULT 0, referral_code TEXT UNIQUE,
        first_divination_done INTEGER DEFAULT 0)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS question_locks (
        id INTEGER PRIMARY KEY, user_id TEXT, question_hash TEXT,
        lock_date TEXT, hexagram_code TEXT,
        UNIQUE(user_id, question_hash, lock_date))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS daily_usage (
        user_id TEXT, usage_date TEXT, count INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, usage_date))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS divination_records (
        id INTEGER PRIMARY KEY, user_id TEXT, question TEXT, category TEXT,
        hexagram_name TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_db()
    cursor = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_user(user_id):
    conn = get_db()
    referral_code = f"LAI-{user_id[-6:].upper()}"
    conn.execute('INSERT OR IGNORE INTO users (user_id, referral_code) VALUES (?, ?)', (user_id, referral_code))
    conn.commit()
    conn.close()
    return get_user(user_id)

def check_daily_usage(user_id):
    conn = get_db()
    tz = pytz.timezone('Asia/Taipei')
    today = datetime.now(tz).strftime('%Y-%m-%d')
    cursor = conn.execute('SELECT count FROM daily_usage WHERE user_id = ? AND usage_date = ?', (user_id, today))
    row = cursor.fetchone()
    conn.close()
    return {'count': row[0] if row else 0}

def increment_daily_usage(user_id):
    conn = get_db()
    tz = pytz.timezone('Asia/Taipei')
    today = datetime.now(tz).strftime('%Y-%m-%d')
    conn.execute('INSERT INTO daily_usage (user_id, usage_date, count) VALUES (?, ?, 1) ON CONFLICT(user_id, usage_date) DO UPDATE SET count = count + 1', (user_id, today))
    conn.commit()
    conn.close()

def is_first_divination(user_id):
    user = get_user(user_id)
    return user and user['first_divination_done'] == 0

def mark_first_divination_done(user_id):
    conn = get_db()
    conn.execute('UPDATE users SET first_divination_done = 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def save_record(user_id, question, category, hexagram_name):
    conn = get_db()
    conn.execute('INSERT INTO divination_records (user_id, question, category, hexagram_name) VALUES (?, ?, ?, ?)',
        (user_id, question, category, hexagram_name))
    conn.commit()
    conn.close()

def generate_hexagram():
    trigram_names = list(TRIGRAMS.keys())
    upper = random.choice(trigram_names)
    lower = random.choice(trigram_names)
    return get_hexagram(upper, lower)

def generate_yao_sequence(hexagram):
    """生成六爻序列，用於搖卦儀式顯示"""
    lower_info = hexagram['lower_info']
    upper_info = hexagram['upper_info']
    
    # 根據卦象決定爻的陰陽（簡化版：用卦的二進制表示）
    trigram_yao = {
        '乾': ['⚊', '⚊', '⚊'],  # 陽陽陽
        '兌': ['⚋', '⚊', '⚊'],  # 陰陽陽
        '離': ['⚊', '⚋', '⚊'],  # 陽陰陽
        '震': ['⚋', '⚋', '⚊'],  # 陰陰陽
        '巽': ['⚊', '⚊', '⚋'],  # 陽陽陰
        '坎': ['⚋', '⚊', '⚋'],  # 陰陽陰
        '艮': ['⚊', '⚋', '⚋'],  # 陽陰陰
        '坤': ['⚋', '⚋', '⚋'],  # 陰陰陰
    }
    
    lower_yao = trigram_yao.get(hexagram['lower'], ['⚊', '⚊', '⚊'])
    upper_yao = trigram_yao.get(hexagram['upper'], ['⚊', '⚊', '⚊'])
    
    return lower_yao + upper_yao

def format_ritual_process(hexagram):
    """格式化搖卦儀式過程"""
    yao = generate_yao_sequence(hexagram)
    lower_info = hexagram['lower_info']
    upper_info = hexagram['upper_info']
    
    ritual_text = f"""☯️ 搖卦中...

初爻 {yao[0]}　二爻 {yao[1]}　三爻 {yao[2]}
▸ 下卦成形：{lower_info['symbol']} {hexagram['lower']}（{lower_info['nature']}）

四爻 {yao[3]}　五爻 {yao[4]}　上爻 {yao[5]}
▸ 上卦成形：{upper_info['symbol']} {hexagram['upper']}（{upper_info['nature']}）

═══════════════════════════════

✨ 卦象已成！

{hexagram['symbol']} {hexagram['name']}
【{hexagram['fortune']}】"""
    
    return ritual_text

def build_category_quick_reply():
    items = [QuickReplyItem(action=PostbackAction(label=f"{info['emoji']} {info['name']}", data=f"category:{code}")) for code, info in CATEGORIES.items()]
    return QuickReply(items=items)

@app.route('/callback', methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(FollowEvent)
def handle_follow(event):
    user_id = event.source.user_id
    if not get_user(user_id):
        create_user(user_id)
    welcome = """☯️ 歡迎來到籟柏太極易占！

🔮 輸入「問事」開始占卜
📅 輸入「運勢」查看今日運勢
📖 輸入「說明」了解更多

願卦象為您帶來智慧與啟發！"""
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(ReplyMessageRequest(
            reply_token=event.reply_token, messages=[TextMessage(text=welcome)]))

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    user = get_user(user_id) or create_user(user_id)
    state = user_states.get(user_id, {})

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)

        if text in ['問事', '占卜', '搖卦']:
            if user['is_premium'] == 0 and check_daily_usage(user_id)['count'] >= 3:
                api.reply_message(ReplyMessageRequest(reply_token=event.reply_token,
                    messages=[TextMessage(text="⚠️ 今日免費次數已用完（3次/天）\n\n💎 升級VIP享無限問事\n輸入「VIP」查看方案")]))
                return
            user_states[user_id] = {'step': 'waiting_question'}
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token,
                messages=[TextMessage(text="☯️ 請輸入您想問的問題\n\n例如：\n• 這份工作適合我嗎？\n• 我和他有緣分嗎？\n• 這個月財運如何？")]))
            return

        if text == '運勢':
            shichen = get_current_shichen()
            hexagram = generate_hexagram()
            fortune_info = FORTUNE_LEVELS.get(hexagram['fortune'], {})
            tz = pytz.timezone('Asia/Taipei')
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token,
                messages=[TextMessage(text=f"""☀️ 今日運勢 {datetime.now(tz).strftime('%m/%d')}

{hexagram['symbol']} {hexagram['name']}
【{hexagram['fortune']}】{fortune_info.get('description', '')}

⏰ 時辰：{shichen['name']}
📍 方位：{shichen['direction']}

💎 開運水晶：白水晶

輸入「問事」開始占卜""")]))
            return

        if text == 'VIP':
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token,
                messages=[TextMessage(text="""👑 VIP 訂閱方案

📍 月訂閱：NT$99/月
📍 季訂閱：NT$249/季
📍 年訂閱：NT$799/年

【VIP 專屬功能】
✅ 無限次問事占卜
✅ 詳細版卦象解讀
✅ 每月1次AI深度解讀
✅ 無限合卦配對

（金流整合中，敬請期待）""")]))
            return

        if text == '次數':
            usage = check_daily_usage(user_id)
            remaining = max(0, 3 - usage['count']) if user['is_premium'] == 0 else '無限'
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token,
                messages=[TextMessage(text=f"📊 今日剩餘問事：{remaining}次")]))
            return

        if text in ['說明', '幫助', 'help']:
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token,
                messages=[TextMessage(text="""📖 使用說明

🔮 問事 - 開始占卜
📅 運勢 - 今日運勢
📊 次數 - 剩餘次數
👑 VIP - 查看方案
🎁 推廣碼 - 查看推廣碼

聯繫：linelaobai2024@gmail.com""")]))
            return

        if text == '推廣碼':
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token,
                messages=[TextMessage(text=f"🎁 您的專屬推廣碼\n\n{user['referral_code']}\n\n分享好友加入可獲得額外問事次數！")]))
            return

        if state.get('step') == 'waiting_question':
            question = text
            auto_category = get_question_category(question)
            user_states[user_id] = {'step': 'confirm_category', 'question': question}
            category_info = CATEGORIES.get(auto_category, {})
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token,
                messages=[TextMessage(
                    text=f"📝 您的問題：\n「{question}」\n\n系統判斷類別：{category_info.get('emoji', '🔮')} {category_info.get('name', '其他')}\n\n請選擇類別：",
                    quick_reply=build_category_quick_reply())]))
            return

        api.reply_message(ReplyMessageRequest(reply_token=event.reply_token,
            messages=[TextMessage(text="☯️ 籟柏太極易占\n\n輸入「問事」開始占卜\n輸入「說明」查看使用方式")]))

@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
    user = get_user(user_id) or create_user(user_id)
    state = user_states.get(user_id, {})

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)

        if data.startswith('category:'):
            category = data.split(':')[1]
            question = state.get('question', '')
            if not question:
                api.reply_message(ReplyMessageRequest(reply_token=event.reply_token,
                    messages=[TextMessage(text="⚠️ 請先輸入「問事」開始")]))
                return

            conn = get_db()
            lock = QuestionLock(conn)
            if lock.check_lock(user_id, question)['locked']:
                conn.close()
                api.reply_message(ReplyMessageRequest(reply_token=event.reply_token,
                    messages=[TextMessage(text="☯️ 此問題今日已占卜過\n\n同一問題每天只能占卜一次\n\n🔮 若有新問題，請輸入「問事」")]))
                return

            hexagram = generate_hexagram()
            lock.create_lock(user_id, question, f"{hexagram['upper']}{hexagram['lower']}")
            conn.close()

            is_first = is_first_divination(user_id)
            if is_first:
                interpretation = render_premium_template(hexagram, category)
                mark_first_divination_done(user_id)
            elif user['is_premium'] == 1:
                interpretation = render_detailed_template(hexagram, category)
            else:
                interpretation = render_basic_template(hexagram, category)

            shichen = get_current_shichen()
            shichen_tip = format_shichen_tip(shichen, hexagram['element'])
            crystal = recommend_crystal(hexagram['element'], category, hexagram['fortune'])

            save_record(user_id, question, category, hexagram['name'])
            increment_daily_usage(user_id)
            user_states.pop(user_id, None)

            # 搖卦儀式：三段訊息
            # 1. 太極圖 + 靜心提示
            ritual_image = ImageMessage(
                original_content_url=TAIJI_IMAGE_URL,
                preview_image_url=TAIJI_IMAGE_URL
            )
            
            # 2. 搖卦過程
            ritual_process = format_ritual_process(hexagram)
            
            # 3. 解讀結果
            result_text = f"""{interpretation}

───────────────────

{shichen_tip}

{format_crystal_basic(crystal)}"""

            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    ritual_image,
                    TextMessage(text="🙏 請閉眼靜心，默念您的問題三次...\n\n準備好後，卦象即將揭曉..."),
                    TextMessage(text=ritual_process),
                    TextMessage(text=result_text)
                ]
            ))

@app.route('/health', methods=['GET'])
def health_check():
    return 'OK'

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5003))
    app.run(host='0.0.0.0', port=port, debug=False)
