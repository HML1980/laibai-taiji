#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
籟柏太極易占 LINE Bot - 加強版 v5.6
功能：問事占卜、快速問題按鈕、用戶資料收集、個人化解讀、每日運勢推送、簽到系統、AI 深度解讀、水晶推薦

Author: SAROW / 籟柏
License: MIT
Version: 5.8
"""

import os
import random
import hashlib
import sqlite3
from datetime import datetime, date, timedelta, timezone

# 台灣時區 UTC+8
TW_TIMEZONE = timezone(timedelta(hours=8))

def get_tw_now():
    """取得台灣時間"""
    return datetime.now(TW_TIMEZONE)

def get_tw_today():
    """取得台灣今天日期"""
    return get_tw_now().date()
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest,
    TextMessage, FlexMessage, FlexContainer
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent
from linebot.v3.exceptions import InvalidSignatureError
from dotenv import load_dotenv

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

load_dotenv()

app = Flask(__name__)
configuration = Configuration(access_token=os.environ.get('CHANNEL_ACCESS_TOKEN', ''))
handler = WebhookHandler(os.environ.get('CHANNEL_SECRET', ''))
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

FREE_DAILY_LIMIT = 3

# ============================================================
# 問事分類系統
# ============================================================
QUESTION_CATEGORIES = {
    'love': {'name': '感情姻緣', 'icon': '💕', 'color': '#FF69B4'},
    'career': {'name': '事業工作', 'icon': '💼', 'color': '#4169E1'},
    'wealth': {'name': '財運投資', 'icon': '💰', 'color': '#FFD700'},
    'health': {'name': '健康平安', 'icon': '🏥', 'color': '#32CD32'},
    'study': {'name': '考試學業', 'icon': '📚', 'color': '#9370DB'},
    'general': {'name': '綜合運勢', 'icon': '🔮', 'color': '#1a1a2e'}
}

# 針對不同分類的卦象解讀（根據用戶狀態會動態調整）
CATEGORY_INTERPRETATIONS = {
    'love': {
        'single': {
            '大吉': '桃花運大開！近期有望遇到命定之人，多參加社交活動，緣分就在身邊。把握每一次相遇的機會！',
            '吉': '感情運勢穩定向好，適合主動認識新朋友。保持開放的心態，對的人正在向你靠近。',
            '平': '感情方面需要耐心，不宜急躁。專注於提升自己，自然會吸引到對的人。',
            '小心': '感情上可能遇到一些波折，不要被表象迷惑。仔細觀察對方，避免被花言巧語所騙。',
            '凶': '感情運勢低迷，暫時不宜積極追求。專注於自我成長，等待更好的時機。'
        },
        'married': {
            '大吉': '夫妻感情和諧美滿！適合一起規劃未來、增進感情。家庭運勢興旺，多關心另一半。',
            '吉': '婚姻關係穩定，適合與伴侶深度交流。安排一次浪漫約會，重溫當初的甜蜜。',
            '平': '家庭生活平穩，但要注意溝通。多花時間陪伴家人，避免因工作忽略另一半。',
            '小心': '夫妻間可能有小摩擦，需要冷靜處理。避免衝動發言，多站在對方角度思考。',
            '凶': '婚姻關係需要用心經營，可能面臨考驗。放下成見，用愛與包容化解矛盾。'
        },
        'relationship': {
            '大吉': '感情甜蜜升溫！你們的關係將更進一步，可能有好消息。把握這段美好時光！',
            '吉': '戀愛運順遂，適合規劃共同的未來。兩人之間的默契越來越好。',
            '平': '感情穩定但缺乏新鮮感，可以嘗試一起做些新事物。維持熱情需要用心經營。',
            '小心': '感情上可能有誤會或小爭執，需要坦誠溝通。不要讓小事變成大問題。',
            '凶': '感情遇到瓶頸，需要雙方共同努力。冷靜思考這段關係，決定是否繼續。'
        }
    },
    'career': {
        '大吉': '事業運勢大旺！貴人運強，適合推動重要專案或提出新想法。領導會看到你的努力與才華。',
        '吉': '工作運順遂，努力會得到回報。適合拓展人脈、爭取表現機會。團隊合作會帶來意外收穫。',
        '平': '工作穩定但缺乏突破，適合蓄積能量。專注於提升技能，等待更好的時機。',
        '小心': '職場上需謹慎行事，避免捲入是非。低調做事，不宜與人爭功或正面衝突。',
        '凶': '事業運低迷，可能遇到阻礙。退一步海闘天空，韜光養晦等待轉機。'
    },
    'wealth': {
        '大吉': '財運亨通！正財偏財皆有望，可適度把握投資機會。但切記見好就收，不可貪心。',
        '吉': '財運穩健向上，正財運佳。工作收入有望增加，適合穩健理財。',
        '平': '財運平穩，不宜冒險。守住現有資產，避免大額投資或借貸。',
        '小心': '財運起伏，需謹慎理財。避免衝動消費，注意防範詐騙。',
        '凶': '財運不佳，破財風險高。不宜投資、借貸或賭博，守財為上。'
    },
    'health': {
        '大吉': '身體狀態極佳！精力充沛，適合開始新的運動計畫或健康習慣。',
        '吉': '健康運良好，但不可大意。保持規律作息，適度運動。',
        '平': '健康狀況普通，需要多加注意。注意飲食均衡，避免過度勞累。',
        '小心': '身體可能發出警訊，留意不適症狀。建議做健康檢查，調整生活作息。',
        '凶': '健康運勢低迷，務必重視身體狀況。避免熬夜、暴飲暴食，必要時就醫檢查。'
    },
    'study': {
        '大吉': '學業運大吉！頭腦清晰，記憶力強，是考試衝刺的最佳時機。金榜題名可期！',
        '吉': '學習效率高，適合挑戰難題。專注複習重點，考試會有好成績。',
        '平': '學業運平穩，需要加倍努力。制定讀書計畫，一步步穩紮穩打。',
        '小心': '學習上可能遇到瓶頸，不要氣餒。找出問題所在，尋求師長協助。',
        '凶': '學業運低迷，容易分心或受挫。調整心態，重新找回學習動力。'
    },
    'general': {
        '大吉': '整體運勢極佳！諸事順遂，把握機會大膽前進。天時地利人和，正是行動的好時機。',
        '吉': '運勢良好，穩中向上。保持積極態度，好事自然來。',
        '平': '運勢平穩，宜靜不宜動。適合規劃、準備，等待更好的時機。',
        '小心': '運勢起伏，需謹慎行事。避免冒險，凡事三思而後行。',
        '凶': '運勢低迷，諸事不宜。韜光養晦，靜待否極泰來。'
    }
}

def get_category_interpretation(category, aspect, user_profile=None):
    """根據分類、卦運和用戶資料取得解讀"""
    if category not in CATEGORY_INTERPRETATIONS:
        return None
    
    cat_data = CATEGORY_INTERPRETATIONS[category]
    
    # 感情類別根據婚姻狀態選擇不同解讀
    if category == 'love' and user_profile:
        marital = user_profile.get('marital_status', 'single')
        if marital in cat_data:
            return cat_data[marital].get(aspect, '')
        return cat_data.get('single', {}).get(aspect, '')
    
    # 其他類別直接取得解讀
    if isinstance(cat_data, dict) and aspect in cat_data:
        return cat_data[aspect]
    
    return None

# ============================================================
# 易經六十四卦 - 每日運勢系統（梅花易數）
# ============================================================
# 八卦對應數字：乾1 兌2 離3 震4 巽5 坎6 艮7 坤8
BAGUA = {
    1: {'name': '乾', 'nature': '天', 'element': '金'},
    2: {'name': '兌', 'nature': '澤', 'element': '金'},
    3: {'name': '離', 'nature': '火', 'element': '火'},
    4: {'name': '震', 'nature': '雷', 'element': '木'},
    5: {'name': '巽', 'nature': '風', 'element': '木'},
    6: {'name': '坎', 'nature': '水', 'element': '水'},
    7: {'name': '艮', 'nature': '山', 'element': '土'},
    8: {'name': '坤', 'nature': '地', 'element': '土'},
}

# 64卦每日運勢（根據傳統卦義編寫）
DAILY_HEXAGRAMS = {
    '1_1': {'name': '乾為天', 'symbol': '䷀', 'level': '大吉', 'color': '#FFD700',
            'overall': '龍騰九天，氣勢如虹！今日精力充沛，適合開創新局。',
            'love': {'single': '魅力四射，主動出擊必有收穫', 'relationship': '感情穩固，可規劃未來', 'married': '夫妻同心，家運昌隆'},
            'career': '事業運極佳，適合提案、談判、爭取機會', 'wealth': '財運亨通，投資可得回報', 'advice': '宜積極進取，但切忌驕傲自滿'},
    '8_8': {'name': '坤為地', 'symbol': '䷁', 'level': '吉', 'color': '#32CD32',
            'overall': '厚德載物，以柔克剛。今日適合配合他人，穩紮穩打。',
            'love': {'single': '緣分天定，順其自然為宜', 'relationship': '多傾聽對方，包容為上', 'married': '相夫教子，家庭和樂'},
            'career': '配合團隊，輔助他人反而有功', 'wealth': '守財為上，不宜冒險投資', 'advice': '宜謙虛低調，厚積薄發'},
    '6_4': {'name': '水雷屯', 'symbol': '䷂', 'level': '平', 'color': '#4169E1',
            'overall': '萬事起頭難，但困難中蘊含機會。耐心等待時機。',
            'love': {'single': '緣分初萌，需要時間培養', 'relationship': '關係正在磨合，多點耐心', 'married': '共度難關，感情更堅固'},
            'career': '創業艱難但有希望，堅持下去', 'wealth': '暫時困頓，但後勢可期', 'advice': '宜穩健前進，不宜急躁'},
    '7_6': {'name': '山水蒙', 'symbol': '䷃', 'level': '平', 'color': '#808080',
            'overall': '啟蒙開智之時，適合學習新事物，虛心請教。',
            'love': {'single': '對感情懵懂，需要更多了解', 'relationship': '彼此還在認識階段', 'married': '重新認識對方，發現新優點'},
            'career': '適合進修學習，請教前輩', 'wealth': '理財知識不足，宜多學習', 'advice': '宜虛心學習，不恥下問'},
    '6_1': {'name': '水天需', 'symbol': '䷄', 'level': '吉', 'color': '#32CD32',
            'overall': '等待是智慧。時機未到，養精蓄銳，機會自來。',
            'love': {'single': '耐心等待，緣分會來', 'relationship': '感情需要時間沉澱', 'married': '平淡中見真情'},
            'career': '時機未到，先做好準備', 'wealth': '投資需等待好時機', 'advice': '宜耐心等待，蓄勢待發'},
    '1_6': {'name': '天水訟', 'symbol': '䷅', 'level': '凶', 'color': '#FF6347',
            'overall': '口舌是非之日，避免爭執，退一步海闊天空。',
            'love': {'single': '易生誤會，言多必失', 'relationship': '小心爭吵，多忍讓', 'married': '避免口角，冷靜處理'},
            'career': '職場是非多，低調行事', 'wealth': '慎防因爭執而破財', 'advice': '宜忍讓退避，不宜爭強'},
    '8_6': {'name': '地水師', 'symbol': '䷆', 'level': '平', 'color': '#4169E1',
            'overall': '團隊合作之日，發揮領導力，帶領眾人前進。',
            'love': {'single': '社交場合有機會', 'relationship': '一起參與團體活動', 'married': '家庭事務需協調'},
            'career': '適合帶領團隊，組織活動', 'wealth': '合夥投資可考慮', 'advice': '宜統籌規劃，凝聚人心'},
    '6_8': {'name': '水地比', 'symbol': '䷇', 'level': '大吉', 'color': '#FFD700',
            'overall': '貴人相助之日！廣結善緣，合作共贏。',
            'love': {'single': '有人暗中欣賞你', 'relationship': '感情親密無間', 'married': '夫妻恩愛，相互扶持'},
            'career': '貴人運強，合作順利', 'wealth': '有人提供好機會', 'advice': '宜廣結善緣，真誠待人'},
    '5_1': {'name': '風天小畜', 'symbol': '䷈', 'level': '平', 'color': '#808080',
            'overall': '小有積蓄，但力量尚小。先積累實力，不宜大動作。',
            'love': {'single': '感情萌芽，慢慢培養', 'relationship': '小甜蜜，慢慢累積', 'married': '小確幸的日常'},
            'career': '穩步前進，不宜冒進', 'wealth': '小財可得，大財需等', 'advice': '宜積少成多，穩紮穩打'},
    '1_2': {'name': '天澤履', 'symbol': '䷉', 'level': '吉', 'color': '#32CD32',
            'overall': '如履薄冰，謹慎行事。小心翼翼反而平安順利。',
            'love': {'single': '小心試探，不要太急', 'relationship': '謹言慎行，維護關係', 'married': '尊重對方，維持和諧'},
            'career': '謹慎處事，避免風險', 'wealth': '穩健投資，不冒險', 'advice': '宜謹慎小心，步步為營'},
    '8_1': {'name': '地天泰', 'symbol': '䷊', 'level': '大吉', 'color': '#FFD700',
            'overall': '否極泰來，萬事亨通！天地交感，好運連連。',
            'love': {'single': '桃花旺盛，把握機會', 'relationship': '感情升溫，甜蜜加倍', 'married': '家庭美滿，幸福洋溢'},
            'career': '事業順利，步步高升', 'wealth': '財源廣進，投資得利', 'advice': '宜把握時機，大展宏圖'},
    '1_8': {'name': '天地否', 'symbol': '䷋', 'level': '凶', 'color': '#FF6347',
            'overall': '閉塞不通之時，宜守不宜進。靜待時機轉變。',
            'love': {'single': '緣分受阻，不宜強求', 'relationship': '溝通不順，暫時冷靜', 'married': '避免爭執，各退一步'},
            'career': '事業受阻，暫時蟄伏', 'wealth': '財運不佳，守財為上', 'advice': '宜沉潛蓄力，等待轉機'},
    '1_3': {'name': '天火同人', 'symbol': '䷌', 'level': '大吉', 'color': '#FFD700',
            'overall': '志同道合，眾人齊心！合作無間，共創佳績。',
            'love': {'single': '遇到志趣相投的人', 'relationship': '心靈契合，感情深厚', 'married': '夫妻同心，其利斷金'},
            'career': '團隊合作順利，人和運旺', 'wealth': '合夥投資有利', 'advice': '宜廣結盟友，團隊合作'},
    '3_1': {'name': '火天大有', 'symbol': '䷍', 'level': '大吉', 'color': '#FFD700',
            'overall': '豐收之日！事業有成，名利雙收。',
            'love': {'single': '條件優越，追求者多', 'relationship': '感情穩定，令人羨慕', 'married': '家庭富足，幸福美滿'},
            'career': '成就非凡，備受肯定', 'wealth': '財運大旺，收穫豐富', 'advice': '宜感恩惜福，回饋社會'},
    '8_7': {'name': '地山謙', 'symbol': '䷎', 'level': '大吉', 'color': '#FFD700',
            'overall': '謙受益，滿招損。謙虛低調，反得貴人相助。',
            'love': {'single': '謙和態度招人喜愛', 'relationship': '互相尊重，感情融洽', 'married': '彼此謙讓，家庭和睦'},
            'career': '低調做事，反得提拔', 'wealth': '不張揚，默默收穫', 'advice': '宜謙虛為懷，功成不居'},
    '4_8': {'name': '雷地豫', 'symbol': '䷏', 'level': '吉', 'color': '#32CD32',
            'overall': '歡樂愉悅之日！適合娛樂、聚會、慶祝。',
            'love': {'single': '社交場合有桃花', 'relationship': '甜蜜約會，歡樂時光', 'married': '家庭聚會，其樂融融'},
            'career': '工作順心，同事和睦', 'wealth': '有意外之財', 'advice': '宜放鬆心情，適度享樂'},
    '2_4': {'name': '澤雷隨', 'symbol': '䷐', 'level': '吉', 'color': '#32CD32',
            'overall': '順勢而為，隨機應變。跟隨正確的方向前進。',
            'love': {'single': '隨緣而遇，不強求', 'relationship': '互相配合，和諧相處', 'married': '順應對方，家庭和樂'},
            'career': '順應趨勢，把握機會', 'wealth': '跟隨市場，穩健獲利', 'advice': '宜順勢而為，靈活應變'},
    '7_5': {'name': '山風蠱', 'symbol': '䷑', 'level': '平', 'color': '#FF8C00',
            'overall': '積弊已久，需要整頓。正視問題，徹底解決。',
            'love': {'single': '檢視自己的問題', 'relationship': '處理感情中的積怨', 'married': '解決長期矛盾'},
            'career': '整頓工作中的問題', 'wealth': '清理財務漏洞', 'advice': '宜除舊佈新，革除弊端'},
    '8_2': {'name': '地澤臨', 'symbol': '䷒', 'level': '大吉', 'color': '#FFD700',
            'overall': '好運降臨！貴人到來，機會眷顧。',
            'love': {'single': '緣分將至，做好準備', 'relationship': '感情升級的時機', 'married': '喜事臨門'},
            'career': '晉升機會到來', 'wealth': '財運臨門，把握機會', 'advice': '宜把握時機，主動爭取'},
    '5_8': {'name': '風地觀', 'symbol': '䷓', 'level': '平', 'color': '#4169E1',
            'overall': '觀察學習之日。多看少動，洞察形勢。',
            'love': {'single': '觀察對方，了解更多', 'relationship': '重新審視這段感情', 'married': '關注對方的需求'},
            'career': '觀察局勢，謀定後動', 'wealth': '觀望市場，不急出手', 'advice': '宜靜觀其變，審時度勢'},
    '3_4': {'name': '火雷噬嗑', 'symbol': '䷔', 'level': '平', 'color': '#4169E1',
            'overall': '排除障礙之日。果斷處理問題，清除阻礙。',
            'love': {'single': '掃除心理障礙', 'relationship': '解決感情中的問題', 'married': '化解家庭矛盾'},
            'career': '解決工作難題', 'wealth': '處理財務糾紛', 'advice': '宜果斷行動，解決問題'},
    '7_3': {'name': '山火賁', 'symbol': '䷕', 'level': '吉', 'color': '#32CD32',
            'overall': '文飾之日，注重外在。適合打扮、裝修、美化。',
            'love': {'single': '注意形象，增加魅力', 'relationship': '製造浪漫氛圍', 'married': '為生活增添情趣'},
            'career': '注重包裝，提升形象', 'wealth': '外表投資有回報', 'advice': '宜注重外表，內外兼修'},
    '7_8': {'name': '山地剝', 'symbol': '䷖', 'level': '凶', 'color': '#FF6347',
            'overall': '剝落衰退之時，宜守不宜進。保存實力。',
            'love': {'single': '感情運低迷', 'relationship': '關係可能動搖', 'married': '小心感情裂痕'},
            'career': '事業低潮，韜光養晦', 'wealth': '謹防破財，減少開支', 'advice': '宜保守謹慎，休養生息'},
    '8_4': {'name': '地雷復', 'symbol': '䷗', 'level': '吉', 'color': '#32CD32',
            'overall': '一陽復始，否極泰來！低谷已過，即將回升。',
            'love': {'single': '感情運開始回升', 'relationship': '感情修復，重新開始', 'married': '關係回溫'},
            'career': '事業開始好轉', 'wealth': '財運逐漸復甦', 'advice': '宜把握轉機，重新出發'},
    '1_4': {'name': '天雷無妄', 'symbol': '䷘', 'level': '吉', 'color': '#32CD32',
            'overall': '真誠無妄，順應天意。誠實做事，自有好報。',
            'love': {'single': '真心待人，自有緣分', 'relationship': '真誠相待，感情穩固', 'married': '坦誠溝通，和諧美滿'},
            'career': '腳踏實地，穩步前進', 'wealth': '誠信經營，財源自來', 'advice': '宜真誠無欺，順其自然'},
    '7_1': {'name': '山天大畜', 'symbol': '䷙', 'level': '大吉', 'color': '#FFD700',
            'overall': '大有積蓄，實力雄厚！適合大展拳腳。',
            'love': {'single': '條件成熟，可以追求', 'relationship': '感情穩固，可談未來', 'married': '家庭富足，生活美滿'},
            'career': '實力充足，可爭取大機會', 'wealth': '財富豐厚，可做投資', 'advice': '宜厚積薄發，適時出擊'},
    '7_4': {'name': '山雷頤', 'symbol': '䷚', 'level': '平', 'color': '#4169E1',
            'overall': '頤養之日，注重養生。照顧身體，滋養心靈。',
            'love': {'single': '充實自己，提升魅力', 'relationship': '互相關心，照顧對方', 'married': '關注家人健康'},
            'career': '充電學習，提升能力', 'wealth': '投資自己，長期有益', 'advice': '宜養精蓄銳，照顧身心'},
    '2_5': {'name': '澤風大過', 'symbol': '䷛', 'level': '凶', 'color': '#FF8C00',
            'overall': '物極必反，過猶不及。凡事適度，避免過頭。',
            'love': {'single': '不要太過主動', 'relationship': '給對方空間', 'married': '避免管太多'},
            'career': '不要過度操勞', 'wealth': '不要過度投資', 'advice': '宜適可而止，避免過度'},
    '6_6': {'name': '坎為水', 'symbol': '䷜', 'level': '凶', 'color': '#FF6347',
            'overall': '重重險阻，如臨深淵。謹慎小心，穩步前行。',
            'love': {'single': '感情路上多波折', 'relationship': '關係遇到困難', 'married': '家庭有挑戰'},
            'career': '工作充滿挑戰', 'wealth': '財務有風險', 'advice': '宜謹慎應對，穩步前行'},
    '3_3': {'name': '離為火', 'symbol': '䷝', 'level': '吉', 'color': '#FF8C00',
            'overall': '光明照耀，文思泉湧！適合創作、表現、展示。',
            'love': {'single': '魅力綻放，吸引異性', 'relationship': '熱情似火，感情升溫', 'married': '增添生活情趣'},
            'career': '表現出色，備受矚目', 'wealth': '投資眼光獨到', 'advice': '宜展現才華，把握機會'},
    '2_7': {'name': '澤山咸', 'symbol': '䷞', 'level': '大吉', 'color': '#FFD700',
            'overall': '心心相印，感應相通！緣分天成，心意相連。',
            'love': {'single': '遇到心動的人', 'relationship': '心靈相通，默契十足', 'married': '夫妻恩愛，心有靈犀'},
            'career': '團隊默契佳', 'wealth': '投資直覺準確', 'advice': '宜真心交流，感應自然'},
    '4_5': {'name': '雷風恆', 'symbol': '䷟', 'level': '吉', 'color': '#32CD32',
            'overall': '持之以恆，堅持不懈。長期努力必有收穫。',
            'love': {'single': '堅持會遇到對的人', 'relationship': '長久穩定的感情', 'married': '恆久的婚姻'},
            'career': '持續努力，終會成功', 'wealth': '長期投資有回報', 'advice': '宜持之以恆，堅定信念'},
    '1_7': {'name': '天山遯', 'symbol': '䷠', 'level': '平', 'color': '#808080',
            'overall': '退避三舍，以退為進。暫時退讓，保存實力。',
            'love': {'single': '暫時不宜追求', 'relationship': '給彼此一些空間', 'married': '避免正面衝突'},
            'career': '暫避風頭，等待時機', 'wealth': '收縮投資，保守為上', 'advice': '宜退避三舍，蓄勢待發'},
    '4_1': {'name': '雷天大壯', 'symbol': '䷡', 'level': '大吉', 'color': '#FFD700',
            'overall': '聲勢浩大，實力強盛！可以大膽行動。',
            'love': {'single': '魅力強大，大膽追求', 'relationship': '感情熱烈', 'married': '家庭興旺'},
            'career': '事業鼎盛，大展宏圖', 'wealth': '財運強勁，大有斬獲', 'advice': '宜乘勢而上，但勿衝動'},
    '3_8': {'name': '火地晉', 'symbol': '䷢', 'level': '大吉', 'color': '#FFD700',
            'overall': '日出東方，步步高升！晉升、進步之時。',
            'love': {'single': '感情運上升', 'relationship': '關係更進一步', 'married': '家庭更上層樓'},
            'career': '晉升有望，事業進步', 'wealth': '財富增長，節節高升', 'advice': '宜積極進取，把握機會'},
    '8_3': {'name': '地火明夷', 'symbol': '䷣', 'level': '凶', 'color': '#FF6347',
            'overall': '光明受損，韜光養晦。暫時隱忍，等待黎明。',
            'love': {'single': '感情運低迷', 'relationship': '感情受挫', 'married': '家庭有隱憂'},
            'career': '懷才不遇，暫時蟄伏', 'wealth': '財運不佳，謹慎理財', 'advice': '宜韜光養晦，等待時機'},
    '5_3': {'name': '風火家人', 'symbol': '䷤', 'level': '吉', 'color': '#32CD32',
            'overall': '家和萬事興！適合處理家庭事務，與家人相處。',
            'love': {'single': '注重家庭觀念', 'relationship': '可以見家長', 'married': '家庭和睦美滿'},
            'career': '家庭支持事業', 'wealth': '家庭理財得當', 'advice': '宜關注家庭，經營親情'},
    '3_2': {'name': '火澤睽', 'symbol': '䷥', 'level': '平', 'color': '#FF8C00',
            'overall': '意見分歧，各行其是。求同存異，化解矛盾。',
            'love': {'single': '眼光太高，難遇合適', 'relationship': '有些分歧，需溝通', 'married': '意見不同，互相包容'},
            'career': '團隊有分歧，需協調', 'wealth': '投資意見分歧', 'advice': '宜求同存異，包容理解'},
    '6_7': {'name': '水山蹇', 'symbol': '䷦', 'level': '凶', 'color': '#FF6347',
            'overall': '前路艱難，舉步維艱。宜退不宜進，等待轉機。',
            'love': {'single': '感情路上障礙重重', 'relationship': '關係遇到瓶頸', 'married': '家庭困難需共同面對'},
            'career': '事業遇到瓶頸', 'wealth': '財務困難', 'advice': '宜退守等待，不宜冒進'},
    '4_6': {'name': '雷水解', 'symbol': '䷧', 'level': '吉', 'color': '#32CD32',
            'overall': '冰雪消融，困難解除！問題得到解決，壓力釋放。',
            'love': {'single': '心結打開，重新開始', 'relationship': '誤會消除，和好如初', 'married': '矛盾化解，關係修復'},
            'career': '困難解決，事業好轉', 'wealth': '財務問題得到解決', 'advice': '宜把握時機，順勢而為'},
    '7_2': {'name': '山澤損', 'symbol': '䷨', 'level': '平', 'color': '#808080',
            'overall': '有捨有得，先損後益。適度犧牲，換取更大收穫。',
            'love': {'single': '降低標準，擴大範圍', 'relationship': '適度妥協，維護感情', 'married': '互相退讓，家庭和諧'},
            'career': '小損大益，放眼長遠', 'wealth': '短期損失，長期獲益', 'advice': '宜有捨有得，著眼長遠'},
    '5_4': {'name': '風雷益', 'symbol': '䷩', 'level': '大吉', 'color': '#FFD700',
            'overall': '損上益下，受益良多！貴人相助，收穫滿滿。',
            'love': {'single': '有人對你表示好感', 'relationship': '感情得到祝福', 'married': '家庭蒸蒸日上'},
            'career': '獲得提攜，事業進步', 'wealth': '財運亨通，收益增加', 'advice': '宜把握機會，感恩圖報'},
    '2_1': {'name': '澤天夬', 'symbol': '䷪', 'level': '吉', 'color': '#32CD32',
            'overall': '決斷果敢，當機立斷！適合做重要決定。',
            'love': {'single': '勇敢表白', 'relationship': '決定未來方向', 'married': '處理重要家事'},
            'career': '果斷決策，把握機會', 'wealth': '果斷投資，獲得回報', 'advice': '宜當機立斷，果敢行動'},
    '1_5': {'name': '天風姤', 'symbol': '䷫', 'level': '平', 'color': '#FF8C00',
            'overall': '不期而遇，機緣巧合。但要小心，來者不善。',
            'love': {'single': '突然出現的桃花要謹慎', 'relationship': '注意第三者', 'married': '提防外在誘惑'},
            'career': '突來的機會要評估', 'wealth': '意外之財要謹慎', 'advice': '宜謹慎應對，辨明真偽'},
    '2_8': {'name': '澤地萃', 'symbol': '䷬', 'level': '吉', 'color': '#32CD32',
            'overall': '人才匯聚，眾志成城！適合聚會、合作、團建。',
            'love': {'single': '聚會中有機會', 'relationship': '共同社交活動', 'married': '家族聚會'},
            'career': '團隊凝聚，合作順利', 'wealth': '集資投資有利', 'advice': '宜廣結善緣，凝聚人心'},
    '8_5': {'name': '地風升', 'symbol': '䷭', 'level': '大吉', 'color': '#FFD700',
            'overall': '步步高升，蒸蒸日上！上升期，把握機會。',
            'love': {'single': '感情運上升', 'relationship': '關係更進一步', 'married': '家庭運勢上升'},
            'career': '晉升機會大，事業騰飛', 'wealth': '財運上升，收入增加', 'advice': '宜積極進取，乘勢而上'},
    '2_6': {'name': '澤水困', 'symbol': '䷮', 'level': '凶', 'color': '#FF6347',
            'overall': '困頓之時，舉步維艱。但君子困而不失其志。',
            'love': {'single': '感情路上受阻', 'relationship': '關係陷入困境', 'married': '家庭面臨困難'},
            'career': '事業受困，需要堅持', 'wealth': '財務困難，節流為上', 'advice': '宜堅守正道，困中求變'},
    '6_5': {'name': '水風井', 'symbol': '䷯', 'level': '吉', 'color': '#32CD32',
            'overall': '取之不盡，用之不竭。發掘潛力，滋養他人。',
            'love': {'single': '提升內在吸引力', 'relationship': '深入了解對方', 'married': '家庭根基穩固'},
            'career': '發掘自身潛力', 'wealth': '開發新的財源', 'advice': '宜深入挖掘，滋養自身'},
    '2_3': {'name': '澤火革', 'symbol': '䷰', 'level': '吉', 'color': '#32CD32',
            'overall': '革故鼎新，除舊佈新！適合改變、轉型、創新。',
            'love': {'single': '改變形象，吸引新緣', 'relationship': '感情需要新鮮感', 'married': '為婚姻注入活力'},
            'career': '事業轉型，創新突破', 'wealth': '投資方向需調整', 'advice': '宜革新求變，與時俱進'},
    '3_5': {'name': '火風鼎', 'symbol': '䷱', 'level': '大吉', 'color': '#FFD700',
            'overall': '鼎新革故，大業可成！事業有成，名聲遠揚。',
            'love': {'single': '身價提升，更有魅力', 'relationship': '感情穩固，可談婚論嫁', 'married': '家庭富足美滿'},
            'career': '事業鼎盛，成就非凡', 'wealth': '財運旺盛，收穫豐厚', 'advice': '宜把握機會，成就大業'},
    '4_4': {'name': '震為雷', 'symbol': '䷲', 'level': '平', 'color': '#FF8C00',
            'overall': '驚雷震動，變化突來。保持警覺，應對變局。',
            'love': {'single': '可能有突來的桃花', 'relationship': '感情可能有變化', 'married': '家庭有突發狀況'},
            'career': '工作有突發狀況', 'wealth': '財務有變動', 'advice': '宜保持警覺，隨機應變'},
    '7_7': {'name': '艮為山', 'symbol': '䷳', 'level': '平', 'color': '#808080',
            'overall': '靜止不動，適可而止。宜靜不宜動，休養生息。',
            'love': {'single': '暫時不宜追求', 'relationship': '感情進入穩定期', 'married': '家庭平靜安穩'},
            'career': '工作求穩，不宜冒進', 'wealth': '守財為上，不宜投資', 'advice': '宜靜觀其變，休養生息'},
    '5_7': {'name': '風山漸', 'symbol': '䷴', 'level': '吉', 'color': '#32CD32',
            'overall': '循序漸進，穩步前行。急不得，慢慢來反而順利。',
            'love': {'single': '感情慢慢培養', 'relationship': '關係穩步發展', 'married': '家庭穩定成長'},
            'career': '事業穩步上升', 'wealth': '財富穩健增長', 'advice': '宜循序漸進，穩紮穩打'},
    '4_2': {'name': '雷澤歸妹', 'symbol': '䷵', 'level': '凶', 'color': '#FF8C00',
            'overall': '名不正言不順，有隱患。行事需謹慎。',
            'love': {'single': '感情複雜，需謹慎', 'relationship': '關係有些不明朗', 'married': '家庭有隱憂'},
            'career': '職位不穩，需小心', 'wealth': '投資有風險', 'advice': '宜謹言慎行，名正言順'},
    '4_3': {'name': '雷火豐', 'symbol': '䷶', 'level': '大吉', 'color': '#FFD700',
            'overall': '豐收盛大，鼎盛時期！把握巔峰，居安思危。',
            'love': {'single': '桃花旺盛，選擇多', 'relationship': '感情甜蜜幸福', 'married': '家庭美滿興旺'},
            'career': '事業巔峰，成就輝煌', 'wealth': '財運大旺，收穫豐厚', 'advice': '宜把握機會，居安思危'},
    '3_7': {'name': '火山旅', 'symbol': '䷷', 'level': '平', 'color': '#808080',
            'overall': '羈旅在外，漂泊不定。適合出行，但要小心。',
            'love': {'single': '旅途中可能有緣分', 'relationship': '一起旅行增進感情', 'married': '家庭出遊'},
            'career': '出差洽公', 'wealth': '外地有財運', 'advice': '宜謹慎出行，隨遇而安'},
    '5_5': {'name': '巽為風', 'symbol': '䷸', 'level': '吉', 'color': '#32CD32',
            'overall': '順風順水，柔順進取。隨風而行，自然順利。',
            'love': {'single': '柔和的態度吸引異性', 'relationship': '順其自然最好', 'married': '家庭和順'},
            'career': '順勢而為，事半功倍', 'wealth': '投資順利', 'advice': '宜柔順處事，順勢而為'},
    '2_2': {'name': '兌為澤', 'symbol': '䷹', 'level': '大吉', 'color': '#FFD700',
            'overall': '喜悅歡樂，人緣極佳！適合社交、表達、娛樂。',
            'love': {'single': '開朗性格吸引異性', 'relationship': '感情甜蜜愉快', 'married': '家庭歡樂和諧'},
            'career': '人緣佳，溝通順利', 'wealth': '口才生財', 'advice': '宜開朗樂觀，廣結善緣'},
    '5_6': {'name': '風水渙', 'symbol': '䷺', 'level': '平', 'color': '#4169E1',
            'overall': '渙散離分，需要凝聚。把分散的力量聚攏起來。',
            'love': {'single': '注意力分散，難以專注', 'relationship': '關係有些疏離', 'married': '家人各忙各的'},
            'career': '團隊需要凝聚', 'wealth': '財務需整合', 'advice': '宜凝聚人心，收攏力量'},
    '6_2': {'name': '水澤節', 'symbol': '䷻', 'level': '吉', 'color': '#32CD32',
            'overall': '節制有度，適可而止。凡事適度，過猶不及。',
            'love': {'single': '不要太過熱情', 'relationship': '保持適當距離', 'married': '節制情緒'},
            'career': '控制工作量', 'wealth': '節約開支', 'advice': '宜適可而止，節制有度'},
    '5_2': {'name': '風澤中孚', 'symbol': '䷼', 'level': '大吉', 'color': '#FFD700',
            'overall': '誠信為本，言出必行。真誠感動天地。',
            'love': {'single': '真心會被看見', 'relationship': '彼此信任，感情穩固', 'married': '夫妻互信，家庭和睦'},
            'career': '誠信經營，贏得信賴', 'wealth': '信譽帶來財富', 'advice': '宜真誠守信，言行一致'},
    '4_7': {'name': '雷山小過', 'symbol': '䷽', 'level': '平', 'color': '#808080',
            'overall': '小有過失，無傷大雅。小心謹慎，不犯大錯。',
            'love': {'single': '小心言行', 'relationship': '注意小節', 'married': '小事不計較'},
            'career': '注意細節，避免小錯', 'wealth': '小心小額損失', 'advice': '宜謹小慎微，不越雷池'},
    '6_3': {'name': '水火既濟', 'symbol': '䷾', 'level': '大吉', 'color': '#FFD700',
            'overall': '大功告成，萬事順遂！完美達成，但要居安思危。',
            'love': {'single': '感情開花結果', 'relationship': '修成正果', 'married': '家庭美滿幸福'},
            'career': '事業有成，目標達成', 'wealth': '財務穩定，收穫豐厚', 'advice': '宜居安思危，保持謙遜'},
    '3_6': {'name': '火水未濟', 'symbol': '䷿', 'level': '平', 'color': '#FF8C00',
            'overall': '事未成功，仍需努力。接近目標，繼續堅持。',
            'love': {'single': '感情尚未成熟', 'relationship': '關係還在發展中', 'married': '家庭還有進步空間'},
            'career': '事業接近目標，再接再厲', 'wealth': '財務漸入佳境', 'advice': '宜堅持努力，善始善終'},
}

# 幸運色與方位對應
LUCKY_COLORS = {'金': ['白色', '金色', '銀色'], '木': ['綠色', '青色', '翠綠'], '水': ['黑色', '藍色', '深藍'], '火': ['紅色', '紫色', '橙色'], '土': ['黃色', '棕色', '咖啡色']}
LUCKY_DIRECTIONS = {'金': '西方', '木': '東方', '水': '北方', '火': '南方', '土': '中央'}

def calculate_daily_hexagram(user_id, today=None):
    """梅花易數計算每日卦象"""
    if today is None:
        today = get_tw_today()
    
    # 使用年月日時計算上下卦
    year = today.year
    month = today.month
    day = today.day
    
    # 用 user_id 的 hash 值加入計算，讓每個人卦象不同
    user_hash = int(hashlib.md5(user_id.encode()).hexdigest()[:8], 16) % 100
    
    # 上卦 = (年 + 月 + 日 + user_hash) % 8，結果 0 當作 8
    upper_num = (year + month + day + user_hash) % 8
    upper_num = 8 if upper_num == 0 else upper_num
    
    # 下卦 = (年 + 月 + 日 + user_hash + 時) % 8
    hour = 8  # 固定用辰時（早上7-9點）作為每日運勢的時辰
    lower_num = (year + month + day + user_hash + hour) % 8
    lower_num = 8 if lower_num == 0 else lower_num
    
    # 組合卦象 key
    hexagram_key = f"{upper_num}_{lower_num}"
    
    # 取得卦象資料
    hexagram = DAILY_HEXAGRAMS.get(hexagram_key)
    if not hexagram:
        # 如果找不到，使用預設卦（地天泰）
        hexagram_key = '8_1'
        hexagram = DAILY_HEXAGRAMS['8_1']
    
    # 計算幸運數字
    lucky_number = (year + month + day + user_hash) % 9
    lucky_number = 9 if lucky_number == 0 else lucky_number
    
    # 根據上卦五行決定幸運色和方位
    upper_element = BAGUA[upper_num]['element']
    lucky_color = random.choice(LUCKY_COLORS[upper_element])
    lucky_direction = LUCKY_DIRECTIONS[upper_element]
    
    return {
        'key': hexagram_key,
        'upper': BAGUA[upper_num],
        'lower': BAGUA[lower_num],
        'hexagram': hexagram,
        'lucky_number': lucky_number,
        'lucky_color': lucky_color,
        'lucky_direction': lucky_direction
    }

def get_daily_fortune(user_id, user_profile=None):
    """根據梅花易數生成每日運勢"""
    today = get_tw_today()
    
    # 計算今日卦象
    result = calculate_daily_hexagram(user_id, today)
    hexagram = result['hexagram']
    
    # 根據婚姻狀態選擇愛情運勢
    marital_status = 'single'
    if user_profile and user_profile.get('marital_status'):
        marital_status = user_profile['marital_status']
    
    love_text = hexagram['love'].get(marital_status, hexagram['love']['single'])
    
    return {
        'date': today.strftime('%Y年%m月%d日'),
        'weekday': ['一', '二', '三', '四', '五', '六', '日'][today.weekday()],
        'hexagram_name': hexagram['name'],
        'hexagram_symbol': hexagram['symbol'],
        'overall': {'level': hexagram['level'], 'color': hexagram['color'], 'desc': hexagram['overall']},
        'love': love_text,
        'career': hexagram['career'],
        'wealth': hexagram['wealth'],
        'lucky_color': result['lucky_color'],
        'lucky_direction': result['lucky_direction'],
        'lucky_number': result['lucky_number'],
        'advice': hexagram['advice']
    }

# ============================================================
# 水晶推薦系統（VIP 專屬）
# ============================================================
CRYSTAL_RECOMMENDATIONS = {
    '大吉': {
        'primary': {'name': '黃水晶', 'color': '#FFD700', 'benefit': '招財旺運，放大正能量', 'usage': '建議放在財位或隨身攜帶'},
        'secondary': {'name': '金髮晶', 'color': '#DAA520', 'benefit': '增強領導力，把握機遇', 'usage': '適合重要決策時佩戴'}
    },
    '吉': {
        'primary': {'name': '綠幽靈', 'color': '#90EE90', 'benefit': '事業穩健，貴人相助', 'usage': '適合放在辦公桌'},
        'secondary': {'name': '綠東陵', 'color': '#3CB371', 'benefit': '帶來好運，穩定情緒', 'usage': '隨身攜帶增強運勢'}
    },
    '平': {
        'primary': {'name': '白水晶', 'color': '#F5F5F5', 'benefit': '淨化磁場，提升智慧', 'usage': '適合冥想或放在書房'},
        'secondary': {'name': '月光石', 'color': '#E6E6FA', 'benefit': '增強直覺，平衡情緒', 'usage': '夜間效果更佳'}
    },
    '小心': {
        'primary': {'name': '紫水晶', 'color': '#9370DB', 'benefit': '安定心神，增強判斷力', 'usage': '放枕邊助眠並帶來清明'},
        'secondary': {'name': '螢石', 'color': '#7B68EE', 'benefit': '思緒清晰，化解困惑', 'usage': '工作學習時放桌上'}
    },
    '凶': {
        'primary': {'name': '黑曜石', 'color': '#1a1a1a', 'benefit': '強力避邪，化解負能量', 'usage': '佩戴左手或放門口'},
        'secondary': {'name': '黑碧璽', 'color': '#2F2F2F', 'benefit': '防護磁場，阻擋小人', 'usage': '放辦公室四角或隨身'}
    }
}

# ============================================================
# 資料庫
# ============================================================
def init_db():
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_premium INTEGER DEFAULT 0, premium_expires_at TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_profiles (user_id TEXT PRIMARY KEY, gender TEXT, age_range TEXT, marital_status TEXT, birth_year INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS divination_records (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, hexagram_code TEXT, hexagram_name TEXT, question TEXT, category TEXT, ai_interpretation TEXT, crystal_recommended TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS daily_usage (user_id TEXT, usage_date DATE, count INTEGER DEFAULT 0, PRIMARY KEY (user_id, usage_date))''')
    c.execute('''CREATE TABLE IF NOT EXISTS pending_questions (user_id TEXT PRIMARY KEY, question TEXT, category TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS pending_profile (user_id TEXT PRIMARY KEY, step TEXT, gender TEXT, age_range TEXT, marital_status TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS check_ins (user_id TEXT, check_date DATE, streak INTEGER DEFAULT 1, bonus_given TEXT, PRIMARY KEY (user_id, check_date))''')
    c.execute('''CREATE TABLE IF NOT EXISTS bonus_usage (user_id TEXT, usage_date DATE, bonus_count INTEGER DEFAULT 0, PRIMARY KEY (user_id, usage_date))''')
    c.execute('''CREATE TABLE IF NOT EXISTS push_settings (user_id TEXT PRIMARY KEY, daily_fortune_enabled INTEGER DEFAULT 0, push_time TEXT DEFAULT '08:00', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

def get_user(user_id):
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = c.fetchone()
    if not user:
        c.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
        conn.commit()
        user = (user_id, get_tw_now(), 0, None)
    conn.close()
    return {'user_id': user[0], 'is_premium': user[2], 'premium_expires_at': user[3]}

def get_daily_usage(user_id):
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    c.execute('SELECT count FROM daily_usage WHERE user_id = ? AND usage_date = ?', (user_id, get_tw_today().isoformat()))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def increment_daily_usage(user_id):
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    c.execute('INSERT INTO daily_usage (user_id, usage_date, count) VALUES (?, ?, 1) ON CONFLICT(user_id, usage_date) DO UPDATE SET count = count + 1', (user_id, get_tw_today().isoformat()))
    conn.commit()
    conn.close()

def can_divine(user_id):
    user = get_user(user_id)
    if user['is_premium'] and user['premium_expires_at']:
        try:
            expires_dt = datetime.fromisoformat(user['premium_expires_at'])
            now_dt = get_tw_now().replace(tzinfo=None)
            if expires_dt > now_dt:
                return True, -1
        except:
            pass
    # 基本次數 + 簽到獎勵次數
    bonus = get_bonus_usage(user_id)
    total_limit = FREE_DAILY_LIMIT + bonus
    remaining = total_limit - get_daily_usage(user_id)
    return remaining > 0, remaining

def save_divination_record(user_id, code, name, question=None, category=None, ai_interp=None, crystal=None):
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    c.execute('INSERT INTO divination_records (user_id, hexagram_code, hexagram_name, question, category, ai_interpretation, crystal_recommended) VALUES (?, ?, ?, ?, ?, ?, ?)', (user_id, code, name, question, category, ai_interp, crystal))
    conn.commit()
    conn.close()

def save_pending_question(user_id, question, category=None):
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO pending_questions (user_id, question, category, created_at) VALUES (?, ?, ?, ?)', (user_id, question, category, get_tw_now()))
    conn.commit()
    conn.close()

def get_pending_question(user_id):
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    c.execute('SELECT question, category FROM pending_questions WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    if result:
        c.execute('DELETE FROM pending_questions WHERE user_id = ?', (user_id,))
        conn.commit()
    conn.close()
    return {'question': result[0], 'category': result[1]} if result else None

def update_pending_category(user_id, category):
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    c.execute('UPDATE pending_questions SET category = ? WHERE user_id = ?', (category, user_id))
    conn.commit()
    conn.close()

def get_pending_status(user_id):
    """取得用戶的待處理問題狀態"""
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    c.execute('SELECT question, category FROM pending_questions WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return {'question': result[0], 'category': result[1]} if result else None

# ============================================================
# 用戶資料管理
# ============================================================
def get_user_profile(user_id):
    """取得用戶資料"""
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    c.execute('SELECT gender, age_range, marital_status FROM user_profiles WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    if result:
        return {'gender': result[0], 'age_range': result[1], 'marital_status': result[2]}
    return None

def save_user_profile(user_id, gender, age_range, marital_status):
    """儲存用戶資料"""
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO user_profiles 
                 (user_id, gender, age_range, marital_status, updated_at) 
                 VALUES (?, ?, ?, ?, ?)''', 
              (user_id, gender, age_range, marital_status, get_tw_now()))
    conn.commit()
    conn.close()

def get_pending_profile(user_id):
    """取得待填寫的用戶資料狀態"""
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    c.execute('SELECT step, gender, age_range FROM pending_profile WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    if result:
        return {'step': result[0], 'gender': result[1], 'age_range': result[2]}
    return None

def save_pending_profile(user_id, step, gender=None, age_range=None):
    """儲存待填寫的用戶資料狀態"""
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO pending_profile 
                 (user_id, step, gender, age_range, created_at) 
                 VALUES (?, ?, ?, ?, ?)''', 
              (user_id, step, gender, age_range, get_tw_now()))
    conn.commit()
    conn.close()

def clear_pending_profile(user_id):
    """清除待填寫的用戶資料狀態"""
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    c.execute('DELETE FROM pending_profile WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

# ============================================================
# 簽到系統
# ============================================================
def get_check_in_status(user_id):
    """取得用戶簽到狀態"""
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    today = get_tw_today().isoformat()
    yesterday = (get_tw_today() - timedelta(days=1)).isoformat()
    
    # 檢查今天是否已簽到
    c.execute('SELECT streak FROM check_ins WHERE user_id = ? AND check_date = ?', (user_id, today))
    today_check = c.fetchone()
    
    # 取得昨天的連續天數
    c.execute('SELECT streak FROM check_ins WHERE user_id = ? AND check_date = ?', (user_id, yesterday))
    yesterday_check = c.fetchone()
    
    # 計算總簽到天數
    c.execute('SELECT COUNT(*) FROM check_ins WHERE user_id = ?', (user_id,))
    total_days = c.fetchone()[0]
    
    conn.close()
    
    return {
        'checked_today': today_check is not None,
        'current_streak': today_check[0] if today_check else (yesterday_check[0] if yesterday_check else 0),
        'yesterday_streak': yesterday_check[0] if yesterday_check else 0,
        'total_days': total_days
    }

def do_check_in(user_id):
    """執行簽到"""
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    today = get_tw_today().isoformat()
    yesterday = (get_tw_today() - timedelta(days=1)).isoformat()
    
    # 檢查今天是否已簽到
    c.execute('SELECT streak FROM check_ins WHERE user_id = ? AND check_date = ?', (user_id, today))
    if c.fetchone():
        conn.close()
        return {'success': False, 'message': '今天已經簽到過了！'}
    
    # 取得昨天的連續天數
    c.execute('SELECT streak FROM check_ins WHERE user_id = ? AND check_date = ?', (user_id, yesterday))
    yesterday_result = c.fetchone()
    yesterday_streak = yesterday_result[0] if yesterday_result else 0
    
    # 計算新的連續天數
    new_streak = yesterday_streak + 1
    
    # 檢查獎勵
    bonus_given = None
    bonus_message = ""
    
    if new_streak == 7:
        bonus_given = 'vip_1day'
        bonus_message = "🎁 連續 7 天簽到！獲得 VIP 體驗券 1 天！"
        # 給予 VIP 1 天
        give_vip_bonus(user_id, 1)
    elif new_streak == 30:
        bonus_given = 'vip_3day'
        bonus_message = "🎁 連續 30 天簽到！獲得 VIP 體驗券 3 天！"
        give_vip_bonus(user_id, 3)
    elif new_streak % 7 == 0 and new_streak > 30:
        bonus_given = 'vip_1day'
        bonus_message = f"🎁 連續 {new_streak} 天簽到！獲得 VIP 體驗券 1 天！"
        give_vip_bonus(user_id, 1)
    
    # 記錄簽到
    c.execute('INSERT INTO check_ins (user_id, check_date, streak, bonus_given) VALUES (?, ?, ?, ?)',
              (user_id, today, new_streak, bonus_given))
    
    # 增加今日占卜次數
    c.execute('INSERT INTO bonus_usage (user_id, usage_date, bonus_count) VALUES (?, ?, 1) ON CONFLICT(user_id, usage_date) DO UPDATE SET bonus_count = bonus_count + 1',
              (user_id, today))
    
    conn.commit()
    conn.close()
    
    return {
        'success': True,
        'streak': new_streak,
        'bonus_message': bonus_message,
        'extra_divine': 1
    }

def give_vip_bonus(user_id, days):
    """給予 VIP 獎勵天數"""
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    
    # 確保用戶存在
    c.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    
    # 取得目前 VIP 狀態
    c.execute('SELECT is_premium, premium_expires_at FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    
    now = get_tw_now().replace(tzinfo=None)
    if result and result[0] and result[1]:
        # 已是 VIP，延長時間
        try:
            current_expires = datetime.fromisoformat(result[1])
            if current_expires > now:
                new_expires = current_expires + timedelta(days=days)
            else:
                new_expires = now + timedelta(days=days)
        except:
            new_expires = now + timedelta(days=days)
    else:
        # 非 VIP，新增時間
        new_expires = now + timedelta(days=days)
    
    c.execute('UPDATE users SET is_premium = 1, premium_expires_at = ? WHERE user_id = ?',
              (new_expires.isoformat(), user_id))
    
    conn.commit()
    conn.close()

def get_bonus_usage(user_id):
    """取得今日獎勵次數"""
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    c.execute('SELECT bonus_count FROM bonus_usage WHERE user_id = ? AND usage_date = ?',
              (user_id, get_tw_today().isoformat()))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

# ============================================================
# 推送設定系統
# ============================================================
def get_push_settings(user_id):
    """取得用戶推送設定"""
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    c.execute('SELECT daily_fortune_enabled, push_time FROM push_settings WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    if result:
        return {'enabled': result[0] == 1, 'time': result[1]}
    return None

def save_push_settings(user_id, enabled, push_time='08:00'):
    """儲存用戶推送設定"""
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    c.execute('''INSERT INTO push_settings (user_id, daily_fortune_enabled, push_time) 
                 VALUES (?, ?, ?) 
                 ON CONFLICT(user_id) DO UPDATE SET daily_fortune_enabled = ?, push_time = ?''',
              (user_id, 1 if enabled else 0, push_time, 1 if enabled else 0, push_time))
    conn.commit()
    conn.close()

def get_users_to_push(push_time):
    """取得需要推送的用戶列表"""
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM push_settings WHERE daily_fortune_enabled = 1 AND push_time = ?', (push_time,))
    results = c.fetchall()
    conn.close()
    return [r[0] for r in results]

def get_user_history(user_id, limit=5):
    conn = sqlite3.connect('yizhan.db')
    c = conn.cursor()
    c.execute('SELECT hexagram_code, hexagram_name, question, created_at FROM divination_records WHERE user_id = ? ORDER BY created_at DESC LIMIT ?', (user_id, limit))
    records = c.fetchall()
    conn.close()
    return records

# ============================================================
# 八卦與六十四卦（豐富版）
# ============================================================
TRIGRAMS = {
    1: {'name': '乾', 'symbol': '☰', 'nature': '天', 'element': '金'},
    2: {'name': '兌', 'symbol': '☱', 'nature': '澤', 'element': '金'},
    3: {'name': '離', 'symbol': '☲', 'nature': '火', 'element': '火'},
    4: {'name': '震', 'symbol': '☳', 'nature': '雷', 'element': '木'},
    5: {'name': '巽', 'symbol': '☴', 'nature': '風', 'element': '木'},
    6: {'name': '坎', 'symbol': '☵', 'nature': '水', 'element': '水'},
    7: {'name': '艮', 'symbol': '☶', 'nature': '山', 'element': '土'},
    8: {'name': '坤', 'symbol': '☷', 'nature': '地', 'element': '土'}
}

HEXAGRAM_NAMES = {
    '11': '乾為天', '12': '天澤履', '13': '天火同人', '14': '天雷無妄', '15': '天風姤', '16': '天水訟', '17': '天山遯', '18': '天地否',
    '21': '澤天夬', '22': '兌為澤', '23': '澤火革', '24': '澤雷隨', '25': '澤風大過', '26': '澤水困', '27': '澤山咸', '28': '澤地萃',
    '31': '火天大有', '32': '火澤睽', '33': '離為火', '34': '火雷噬嗑', '35': '火風鼎', '36': '火水未濟', '37': '火山旅', '38': '火地晉',
    '41': '雷天大壯', '42': '雷澤歸妹', '43': '雷火豐', '44': '震為雷', '45': '雷風恆', '46': '雷水解', '47': '雷山小過', '48': '雷地豫',
    '51': '風天小畜', '52': '風澤中孚', '53': '風火家人', '54': '風雷益', '55': '巽為風', '56': '風水渙', '57': '風山漸', '58': '風地觀',
    '61': '水天需', '62': '水澤節', '63': '水火既濟', '64': '水雷屯', '65': '水風井', '66': '坎為水', '67': '水山蹇', '68': '水地比',
    '71': '山天大畜', '72': '山澤損', '73': '山火賁', '74': '山雷頤', '75': '山風蠱', '76': '山水蒙', '77': '艮為山', '78': '山地剝',
    '81': '地天泰', '82': '地澤臨', '83': '地火明夷', '84': '地雷復', '85': '地風升', '86': '地水師', '87': '地山謙', '88': '坤為地'
}

# 豐富的卦象解讀 - 包含故事性描述、運勢預測、引導升級的懸念
HEXAGRAM_MEANINGS = {
    '11': {
        'aspect': '大吉',
        'brief': '龍騰九天，乾坤在握',
        'story': '天行健，君子以自強不息。此卦如日中天，正是大展宏圖之時。您的能量正處於巔峰狀態，無論事業、感情或財運都將迎來突破。',
        'fortune': '近七日內將有意想不到的好消息傳來，可能與一位貴人有關。把握住這波運勢，主動出擊將事半功倍...',
        'fortune_hook': '🔮 想知道貴人是誰？如何把握這波運勢的最佳時機？',
        'advice': '宜積極進取，大膽行動。此時猶豫不決反而錯失良機。'
    },
    '12': {
        'aspect': '小心',
        'brief': '如履薄冰，步步為營',
        'story': '履虎尾，不咥人，亨。此卦提醒您正行走在微妙的處境中，看似平靜的表面下暗藏玄機。但只要謹慎行事，終能化險為夷。',
        'fortune': '近期可能面臨一個需要抉擇的情況，表面上的好選擇未必是正確答案。有人在暗中觀察您的反應...',
        'fortune_hook': '🔮 想知道該如何識破迷局？哪個選擇才是正確的？',
        'advice': '謹言慎行，三思後行。遇事多觀察，少表態。'
    },
    '13': {
        'aspect': '吉',
        'brief': '志同道合，眾志成城',
        'story': '同人于野，亨。此卦象徵人際關係的和諧與合作的力量。您身邊正聚集著與您理念相近的人，這是難得的機緣。',
        'fortune': '近期將遇到一位與您「頻率相同」的人，可能在意想不到的場合。這段關係將為您帶來重要的轉變...',
        'fortune_hook': '🔮 想知道這個人會在哪裡出現？如何識別他/她？',
        'advice': '廣結善緣，真誠待人。合作比單打獨鬥更有力量。'
    },
    '14': {
        'aspect': '吉',
        'brief': '天道無妄，誠者自通',
        'story': '無妄，元亨利貞。此卦告訴您：保持真誠，不妄作為，天道自然會眷顧。近期發生的事情都有其深意，順其自然反而是最好的策略。',
        'fortune': '一件看似「意外」的事情正在醞釀，但這其實是宇宙的安排。表面的阻礙實際上是在保護您...',
        'fortune_hook': '🔮 想知道這個「意外」是什麼？如何將它轉化為機遇？',
        'advice': '保持真誠，順應天時。不強求，不妄動。'
    },
    '15': {
        'aspect': '平',
        'brief': '邂逅姻緣，隨緣應變',
        'story': '姤，女壯，勿用取女。此卦暗示意外的相遇，可能帶來新的機會或關係。但需要慧眼識人，不被表象迷惑。',
        'fortune': '近期會有一個「突然出現」的人或機會，看起來很誘人。但第一印象可能有所偏差...',
        'fortune_hook': '🔮 想知道如何辨別真偽？這個機會該不該把握？',
        'advice': '保持警覺，觀察為主。不要被一時的熱情沖昏頭。'
    },
    '16': {
        'aspect': '凶',
        'brief': '爭訟之象，退一步海闊天空',
        'story': '訟，有孚窒惕，中吉，終凶。此卦警示您正處於或即將進入一個爭端的處境。贏了道理，可能輸了更多。',
        'fortune': '近期要特別注意人際關係中的暗流。有人可能對您心存不滿，或者一場誤會正在發酵...',
        'fortune_hook': '🔮 想知道是誰在背後？如何化解這場危機？',
        'advice': '忍讓為上，和解為貴。爭一時不如謀長遠。'
    },
    '17': {
        'aspect': '平',
        'brief': '韜光養晦，以退為進',
        'story': '遯，亨，小利貞。此卦如同智者的戰略性撤退，暫時的隱忍是為了更好的出擊。現在不是正面對抗的時機。',
        'fortune': '近期您可能感到某些事情「不對勁」，這種直覺是對的。暫時的退讓會為您保存實力...',
        'fortune_hook': '🔮 想知道該退到什麼程度？何時才是反攻的時機？',
        'advice': '避其鋒芒，保存實力。蟄伏是為了更好的騰飛。'
    },
    '18': {
        'aspect': '凶',
        'brief': '天地閉塞，靜待春來',
        'story': '否之匪人，不利君子貞。此卦象徵暫時的阻滯，上下不通、內外不和。但請記住：否極泰來，黑暗之後必是黎明。',
        'fortune': '近期可能感到事事不順，溝通不暢。但這是黎明前的黑暗，一個重要的轉折點即將來臨...',
        'fortune_hook': '🔮 想知道轉機何時出現？如何度過這段低潮期？',
        'advice': '靜待時機，不宜強求。養精蓄銳，準備迎接轉機。'
    },
    '21': {
        'aspect': '吉',
        'brief': '果敢決斷，勇往直前',
        'story': '夬，揚于王庭。此卦如同破曉的陽光，衝破黑暗。是時候做出那個您一直猶豫的決定了。',
        'fortune': '近期有一件事需要您「當機立斷」，過多的猶豫反而會錯失良機。答案其實已在您心中...',
        'fortune_hook': '🔮 想知道應該選擇哪個方向？最佳決策時機是何時？',
        'advice': '當斷則斷，展現魄力。猶豫不決是最大的風險。'
    },
    '22': {
        'aspect': '吉',
        'brief': '和悅之象，喜樂盈門',
        'story': '兌，亨利貞。此卦如同春風拂面，帶來愉悅與和諧。您的磁場正在吸引美好的人事物。',
        'fortune': '近期將有令您開心的消息，可能來自朋友的邀約或一個期待已久的結果。笑容是您最好的開運符...',
        'fortune_hook': '🔮 想知道這個好消息具體是什麼？如何讓喜悅加倍？',
        'advice': '保持愉悅，廣結人緣。好心情會帶來好運氣。'
    },
    '23': {
        'aspect': '平',
        'brief': '除舊布新，蛻變重生',
        'story': '革，己日乃孚。此卦如同蝴蝶破繭，象徵重大的轉變。改變雖然不易，但這正是您需要的蛻變。',
        'fortune': '近期您的生活可能面臨一些變化，也許是主動的，也許是被動的。這個變化看似動盪，實則是新生...',
        'fortune_hook': '🔮 想知道該如何順利度過轉變期？變化後會更好嗎？',
        'advice': '勇於改變，擁抱新局。蛻變是成長的必經之路。'
    },
    '24': {
        'aspect': '吉',
        'brief': '隨機應變，順勢而為',
        'story': '隨，元亨利貞，無咎。此卦告訴您：識時務者為俊傑。能夠靈活應變的人，才能在變化中找到機會。',
        'fortune': '近期環境可能有所變化，但這恰恰是您展現應變能力的機會。有人正在觀察您如何處理變局...',
        'fortune_hook': '🔮 想知道應該跟隨什麼趨勢？如何在變化中勝出？',
        'advice': '靈活變通，順勢而為。僵化固執只會被淘汰。'
    },
    '25': {
        'aspect': '小心',
        'brief': '過猶不及，適可而止',
        'story': '大過，棟撓，利有攸往，亨。此卦警示您：再好的事情，過度了也會變成負擔。知道何時停下來，是一種智慧。',
        'fortune': '近期您可能在某件事上投入過多，無論是精力、金錢還是感情。過度的付出可能帶來反效果...',
        'fortune_hook': '🔮 想知道具體是哪方面過度了？如何找回平衡？',
        'advice': '量力而行，適可而止。過度的熱情可能燒傷自己。'
    },
    '26': {
        'aspect': '凶',
        'brief': '身陷困境，守正待援',
        'story': '困，亨，貞大人吉。此卦如同困獸之鬥，但請記住：真正的勇者，是在困境中依然保持希望的人。',
        'fortune': '近期可能遇到一些阻礙，感覺四處碰壁。但這個困境中藏著一個轉機，只有冷靜下來才能發現...',
        'fortune_hook': '🔮 想知道突破口在哪裡？誰能幫您走出困境？',
        'advice': '堅守正道，保持信心。困境是暫時的，成長是永恆的。'
    },
    '27': {
        'aspect': '吉',
        'brief': '心有靈犀，感應相通',
        'story': '咸，亨利貞，取女吉。此卦是感應之卦，象徵心靈的相通與情感的連結。您與某人或某事之間存在著微妙的緣分。',
        'fortune': '近期您會感受到一種「說不清的連結」，可能是對某人、某地或某個想法。這種直覺是真實的...',
        'fortune_hook': '🔮 想知道這個連結指向什麼？如何加深這份感應？',
        'advice': '敞開心扉，感受連結。真誠的能量會吸引相同的頻率。'
    },
    '28': {
        'aspect': '吉',
        'brief': '眾緣和合，聚沙成塔',
        'story': '萃，亨。王假有廟。此卦象徵聚集與凝聚，眾人的力量匯聚在一起，可以成就大事。',
        'fortune': '近期是拓展人脈、建立團隊的好時機。一群人正在向您靠近，或者您正被邀請加入某個圈子...',
        'fortune_hook': '🔮 想知道該加入哪個圈子？如何識別真正的夥伴？',
        'advice': '團結合作，凝聚力量。一個人走得快，一群人走得遠。'
    },
    '31': {
        'aspect': '大吉',
        'brief': '大有斬獲，前程似錦',
        'story': '大有，元亨。此卦是豐收之象，您之前的付出將得到豐厚的回報。這是值得慶祝的時刻。',
        'fortune': '近期將有意想不到的收穫，可能是物質上的，也可能是精神上的。一個機會正在向您敞開大門...',
        'fortune_hook': '🔮 想知道這個機會在哪個領域？如何最大化這波收穫？',
        'advice': '把握機遇，大展宏圖。好運來臨時，要有準備接住它的能力。'
    },
    '32': {
        'aspect': '平',
        'brief': '觀點分歧，各執己見',
        'story': '睽，小事吉。此卦象徵差異與分離，但差異不一定是壞事。有時候，不同的視角能帶來新的發現。',
        'fortune': '近期可能與某人產生意見分歧，表面上看是衝突，實際上可能是一個重新認識彼此的機會...',
        'fortune_hook': '🔮 想知道如何化解分歧？這段關係還有轉圜的餘地嗎？',
        'advice': '求同存異，理解差異。每個人都有自己的視角。'
    },
    '33': {
        'aspect': '吉',
        'brief': '光明正大，文采煥發',
        'story': '離，利貞，亨。此卦如同正午的太陽，光芒萬丈。這是展現自己、綻放光芒的時刻。',
        'fortune': '近期您的才華將得到展示的機會，無論是在工作還是生活中。有人正等著被您的光芒吸引...',
        'fortune_hook': '🔮 想知道該展現哪方面的才華？這個舞台在哪裡？',
        'advice': '展現自信，散發光芒。不要害怕成為焦點。'
    },
    '34': {
        'aspect': '吉',
        'brief': '撥雲見日，障礙消除',
        'story': '噬嗑，亨，利用獄。此卦象徵咬碎障礙，排除阻礙。那些困擾您的問題，終於要解決了。',
        'fortune': '近期一個懸而未決的問題將獲得解答。可能需要一些果斷的行動，但結果會是好的...',
        'fortune_hook': '🔮 想知道該採取什麼行動？解決問題的關鍵是什麼？',
        'advice': '果斷行動，排除障礙。問題不會自己消失，但會被解決。'
    },
    '35': {
        'aspect': '吉',
        'brief': '鼎新革故，創造新局',
        'story': '鼎，元吉，亨。此卦如同烹煮美食的鼎，象徵轉化與創新。舊的養分將轉化為新的能量。',
        'fortune': '近期是創新的好時機，一個新的想法或項目正在您心中醞釀。這個「新東西」可能改變您的軌道...',
        'fortune_hook': '🔮 想知道這個創新該往哪個方向發展？需要哪些資源？',
        'advice': '創新突破，轉化升級。不破不立，大破大立。'
    },
    '36': {
        'aspect': '平',
        'brief': '功敗垂成，再接再厲',
        'story': '未濟，亨，小狐汔濟，濡其尾，無攸利。此卦提醒您：雖然接近終點，但最後一哩路往往最難走。',
        'fortune': '近期某件事看似即將完成，但可能出現小變數。不要在最後關頭鬆懈...',
        'fortune_hook': '🔮 想知道變數可能出現在哪裡？如何確保完美收官？',
        'advice': '堅持到底，不要鬆懈。行百里者半九十。'
    },
    '37': {
        'aspect': '平',
        'brief': '旅途在外，隨遇而安',
        'story': '旅，小亨，旅貞吉。此卦象徵旅行與漂泊，在不熟悉的環境中尋找方向。',
        'fortune': '近期可能有出行的機會，或者在某個「陌生領域」探索。這段旅程會帶給您意想不到的收穫...',
        'fortune_hook': '🔮 想知道該往哪個方向去？旅途中會遇到什麼人？',
        'advice': '入境隨俗，保持彈性。旅行是最好的學習。'
    },
    '38': {
        'aspect': '吉',
        'brief': '步步高升，前程似錦',
        'story': '晉，康侯用錫馬蕃庶，晝日三接。此卦如同旭日東升，步步向上。您的努力即將得到認可。',
        'fortune': '近期將有晉升或進步的機會，無論是職位、能力還是聲望。有人正在關注您的表現...',
        'fortune_hook': '🔮 想知道機會何時降臨？該如何表現才能脫穎而出？',
        'advice': '穩健前進，展現實力。機會是給準備好的人。'
    },
    '41': {
        'aspect': '大吉',
        'brief': '氣勢如虹，大有可為',
        'story': '大壯，利貞。此卦如同春雷震天，氣勢正盛。這是您最有力量的時刻。',
        'fortune': '近期您的能量將達到高峰，無論做什麼都會事半功倍。一個大展身手的舞台正在等著您...',
        'fortune_hook': '🔮 想知道該如何運用這股力量？在哪個領域突破？',
        'advice': '乘勝追擊，大膽行動。力量巔峰時，就是出擊時。'
    },
    '42': {
        'aspect': '吉',
        'brief': '姻緣和合，情感順遂',
        'story': '歸妹，征凶，無攸利。此卦與情感關係密切，象徵著緣分的牽引與歸屬。',
        'fortune': '近期感情方面可能有新的發展，單身者有望遇到有緣人，有伴侶者關係可能更進一步...',
        'fortune_hook': '🔮 想知道緣分何時到來？對方是什麼樣的人？',
        'advice': '珍惜緣分，真誠相待。緣分天注定，但幸福靠經營。'
    },
    '43': {
        'aspect': '大吉',
        'brief': '豐盛圓滿，鼎盛時期',
        'story': '豐，亨，王假之，勿憂，宜日中。此卦是極致的豐盛之象，如同正午的太陽最為燦爛。',
        'fortune': '近期是您的高光時刻，各方面都將達到頂峰。但請記住：盛極必衰，要懂得在高處為低潮做準備...',
        'fortune_hook': '🔮 想知道如何延長這波好運？該提前做哪些準備？',
        'advice': '居安思危，未雨綢繆。最好的時候，要想到最壞的可能。'
    },
    '44': {
        'aspect': '平',
        'brief': '警醒振作，蓄勢待發',
        'story': '震，亨。震來虩虩，笑言啞啞。此卦如同雷聲隆隆，既是警示也是喚醒。',
        'fortune': '近期可能遇到一些「震動」，這些震動是在提醒您某些被忽略的事情。驚醒之後，就是行動...',
        'fortune_hook': '🔮 想知道這個警示是關於什麼？該如何應對？',
        'advice': '提高警覺，保持清醒。震動是宇宙的提醒。'
    },
    '45': {
        'aspect': '吉',
        'brief': '持之以恆，終有所成',
        'story': '恆，亨，無咎，利貞。此卦強調恆久之道，堅持的力量超乎想像。',
        'fortune': '您正在做的某件事，需要再堅持一段時間。勝利已經在望，放棄是最大的遺憾...',
        'fortune_hook': '🔮 想知道還需要堅持多久？如何保持動力？',
        'advice': '堅持不懈，持之以恆。成功屬於能堅持到最後的人。'
    },
    '46': {
        'aspect': '吉',
        'brief': '困難消解，否極泰來',
        'story': '解，利西南，無所往，其來復吉。此卦象徵解脫與釋放，困擾您的問題正在消解。',
        'fortune': '近期將感受到一種「解脫感」，壓力釋放、問題解決。一段艱難的時期即將結束...',
        'fortune_hook': '🔮 想知道問題如何被解決？解脫之後該往哪走？',
        'advice': '放下包袱，輕裝前行。過去的已經過去。'
    },
    '47': {
        'aspect': '小心',
        'brief': '小事謹慎，不宜躁進',
        'story': '小過，亨，利貞。可小事，不可大事。此卦提醒您：小地方的疏忽可能導致大問題。',
        'fortune': '近期在細節上要特別注意，一個小錯誤可能引發連鎖反應。檢查那些您覺得「應該沒問題」的地方...',
        'fortune_hook': '🔮 想知道該注意哪些細節？如何避免小錯誤？',
        'advice': '謹小慎微，穩紮穩打。魔鬼藏在細節裡。'
    },
    '48': {
        'aspect': '吉',
        'brief': '安樂順遂，享受當下',
        'story': '豫，利建侯行師。此卦是愉悅之象，象徵順遂與享受。這是一段可以稍微放鬆的時光。',
        'fortune': '近期適合享受生活，參與一些娛樂活動。一個讓您開心的事情即將發生...',
        'fortune_hook': '🔮 想知道這個開心的事是什麼？如何讓愉悅持續更久？',
        'advice': '享受當下，適度娛樂。人生需要張弛有度。'
    },
    '51': {
        'aspect': '吉',
        'brief': '積少成多，穩健前行',
        'story': '小畜，亨。密雲不雨，自我西郊。此卦如同細雨潤物，小的積累終將帶來大的成果。',
        'fortune': '近期可能感覺進展緩慢，但不要急躁。每一個小進步都在為大突破做準備...',
        'fortune_hook': '🔮 想知道突破何時到來？該如何加速積累？',
        'advice': '腳踏實地，積少成多。不積跬步，無以至千里。'
    },
    '52': {
        'aspect': '吉',
        'brief': '誠信為本，心靈相通',
        'story': '中孚，豚魚吉，利涉大川。此卦強調誠信的力量，真誠的心可以感動一切。',
        'fortune': '近期您的真誠將得到回報，有人會因為您的誠信而給予信任或機會...',
        'fortune_hook': '🔮 想知道誰會信任您？這份信任會帶來什麼？',
        'advice': '以誠待人，言行一致。誠信是最好的名片。'
    },
    '53': {
        'aspect': '吉',
        'brief': '家庭和睦，親情融洽',
        'story': '家人，利女貞。此卦關乎家庭與親密關係，強調內部和諧的重要性。',
        'fortune': '近期家庭運勢良好，適合處理家務事或加強與家人的連結。一個家庭相關的好消息可能傳來...',
        'fortune_hook': '🔮 想知道這個好消息是什麼？如何讓家庭更和諧？',
        'advice': '珍惜家人，維護和諧。家和萬事興。'
    },
    '54': {
        'aspect': '吉',
        'brief': '利人利己，互惠共贏',
        'story': '益，利有攸往，利涉大川。此卦象徵增益與助人，您給出去的，會以另一種形式回來。',
        'fortune': '近期是助人的好時機，您的善意將帶來意想不到的回報。一個需要您幫助的人可能出現...',
        'fortune_hook': '🔮 想知道該幫助誰？回報會以什麼形式出現？',
        'advice': '樂於助人，廣結善緣。施比受更有福。'
    },
    '55': {
        'aspect': '平',
        'brief': '柔順處世，以柔克剛',
        'story': '巽，小亨，利有攸往，利見大人。此卦象徵風的特性：柔順但無處不入。',
        'fortune': '近期適合採取柔性策略，硬碰硬可能適得其反。有時候退讓反而能達成目標...',
        'fortune_hook': '🔮 想知道該如何「以柔克剛」？在哪裡該退讓？',
        'advice': '謙遜低調，柔能克剛。水善利萬物而不爭。'
    },
    '56': {
        'aspect': '小心',
        'brief': '渙散之象，收心聚力',
        'story': '渙，亨。王假有廟。此卦提醒您注意分散的風險，無論是注意力、資源還是關係。',
        'fortune': '近期可能感到有些散亂，精力被分散在太多事情上。需要重新聚焦，找回核心...',
        'fortune_hook': '🔮 想知道該聚焦在什麼上？如何重整旗鼓？',
        'advice': '收心聚力，專注核心。分散是效率的敵人。'
    },
    '57': {
        'aspect': '吉',
        'brief': '循序漸進，水到渠成',
        'story': '漸，女歸吉，利貞。此卦如同樹木生長，強調自然節奏的重要性。',
        'fortune': '近期適合按部就班地推進，急於求成反而會出問題。該來的會來，時機成熟自然會結果...',
        'fortune_hook': '🔮 想知道時機何時成熟？如何判斷是否該加速？',
        'advice': '按部就班，穩步前行。欲速則不達。'
    },
    '58': {
        'aspect': '平',
        'brief': '觀察形勢，靜待時機',
        'story': '觀，盥而不薦，有孚顒若。此卦強調觀察的智慧，先看清楚再行動。',
        'fortune': '近期適合多觀察、少行動。形勢還不明朗，過早出手可能判斷失誤...',
        'fortune_hook': '🔮 想知道該觀察什麼？何時才是行動的信號？',
        'advice': '多看少動，審時度勢。靜觀其變，後發制人。'
    },
    '61': {
        'aspect': '平',
        'brief': '耐心等待，時機將至',
        'story': '需，有孚，光亨貞吉，利涉大川。此卦如同等待雨水的禾苗，強調等待的智慧。',
        'fortune': '近期您等待的事情需要再耐心一些，條件還沒完全具備。但好消息是：它一定會來...',
        'fortune_hook': '🔮 想知道還要等多久？等待期間該做什麼準備？',
        'advice': '耐心等待，做好準備。機會總是留給有準備的人。'
    },
    '62': {
        'aspect': '平',
        'brief': '適可而止，把握分寸',
        'story': '節，亨。苦節不可貞。此卦提醒您凡事要有度，知道何時該停是一種智慧。',
        'fortune': '近期注意把握「度」的問題，無論是花費、付出還是期待。過猶不及...',
        'fortune_hook': '🔮 想知道哪裡該節制？如何找到最佳平衡點？',
        'advice': '適度節制，恰到好處。過度的任何東西都會變成負擔。'
    },
    '63': {
        'aspect': '大吉',
        'brief': '大功告成，圓滿完成',
        'story': '既濟，亨小，利貞。初吉終亂。此卦象徵完成與圓滿，您的努力終於開花結果。',
        'fortune': '近期將迎來一個圓滿的結局，一件事情將告一段落。但記住：完成不是終點，而是新的起點...',
        'fortune_hook': '🔮 想知道下一個目標該是什麼？如何保持這波好運？',
        'advice': '善始善終，再創新高。一個結束是另一個開始。'
    },
    '64': {
        'aspect': '平',
        'brief': '萬事開頭，奠定基礎',
        'story': '屯，元亨利貞，勿用有攸往，利建侯。此卦如同破土而出的種子，代表新的開始。',
        'fortune': '近期可能開始一個新項目或進入新階段，開頭雖難，但只要根基穩固，後續就會順利...',
        'fortune_hook': '🔮 想知道如何打好基礎？開頭該注意什麼？',
        'advice': '穩紮穩打，奠定基礎。好的開始是成功的一半。'
    },
    '65': {
        'aspect': '吉',
        'brief': '涵養積累，厚積薄發',
        'story': '井，改邑不改井。此卦如同深井，象徵內在的涵養與積累。',
        'fortune': '近期適合充實自己，學習新技能或積累資源。現在的積累會成為未來的資本...',
        'fortune_hook': '🔮 想知道該學習什麼？積累的資源何時能派上用場？',
        'advice': '充實內在，積蓄能量。厚積才能薄發。'
    },
    '66': {
        'aspect': '凶',
        'brief': '險阻在前，謹慎應對',
        'story': '坎，有孚維心亨，行有尚。此卦象徵水的險惡，提醒您前方有坎坷。',
        'fortune': '近期可能遇到一些困難或阻礙，看起來有些棘手。但只要保持冷靜，一定能找到出路...',
        'fortune_hook': '🔮 想知道困難具體是什麼？如何安全度過？',
        'advice': '謹慎行事，保持冷靜。沒有過不去的坎。'
    },
    '67': {
        'aspect': '凶',
        'brief': '道路艱難，迂迴前進',
        'story': '蹇，利西南，不利東北，利見大人，貞吉。此卦象徵行路艱難，但有方法可解。',
        'fortune': '近期前進的道路不太順暢，可能需要繞路而行。直線不通，曲線也是一種智慧...',
        'fortune_hook': '🔮 想知道該繞向哪個方向？誰能幫您指路？',
        'advice': '靈活變通，迂迴前進。條條大路通羅馬。'
    },
    '68': {
        'aspect': '吉',
        'brief': '親善合作，貴人相助',
        'story': '比，吉。原筮元永貞，無咎。此卦象徵親近與合作，您不是孤軍奮戰。',
        'fortune': '近期將獲得他人的支持，可能是貴人相助或團隊合作。接受幫助不是軟弱...',
        'fortune_hook': '🔮 想知道貴人是誰？該如何建立這份連結？',
        'advice': '廣結善緣，接受幫助。眾人拾柴火焰高。'
    },
    '71': {
        'aspect': '吉',
        'brief': '蓄勢待發，大器晚成',
        'story': '大畜，利貞，不家食吉，利涉大川。此卦象徵大的積蓄，能量正在累積。',
        'fortune': '近期您的能量和資源正在持續累積，雖然還沒到爆發的時刻，但時機很快就會成熟...',
        'fortune_hook': '🔮 想知道爆發點何時到來？如何最大化累積的效果？',
        'advice': '繼續積蓄，等待時機。大器晚成，後來居上。'
    },
    '72': {
        'aspect': '平',
        'brief': '有捨有得，以退為進',
        'story': '損，有孚，元吉，無咎可貞。此卦提醒您：有時候減少反而是增加。',
        'fortune': '近期可能需要做出一些取捨，放棄某些東西來獲得更重要的。這是值得的交換...',
        'fortune_hook': '🔮 想知道該放棄什麼？能換來什麼？',
        'advice': '適當割捨，輕裝前行。捨得捨得，有捨才有得。'
    },
    '73': {
        'aspect': '平',
        'brief': '修飾外表，內外兼修',
        'story': '賁，亨，小利有攸往。此卦象徵修飾與美化，提醒您內外要兼顧。',
        'fortune': '近期注意自己的形象和表達，外在的改變可能帶來新的機會。但別忘了內在的修養...',
        'fortune_hook': '🔮 想知道該如何改變形象？哪些方面需要加強？',
        'advice': '內外兼修，表裡如一。外表是內心的鏡子。'
    },
    '74': {
        'aspect': '吉',
        'brief': '頤養身心，修身養性',
        'story': '頤，貞吉，觀頤，自求口實。此卦關乎滋養與照顧，提醒您照顧好自己。',
        'fortune': '近期適合調養身心，注意飲食和休息。身體發出的信號不要忽視...',
        'fortune_hook': '🔮 想知道身體哪些方面需要注意？如何更好地調養？',
        'advice': '照顧身體，滋養心靈。身體是革命的本錢。'
    },
    '75': {
        'aspect': '平',
        'brief': '撥亂反正，整頓問題',
        'story': '蠱，元亨，利涉大川，先甲三日，後甲三日。此卦象徵整頓積弊，是時候處理那些遺留問題了。',
        'fortune': '近期適合解決一些積壓已久的問題，拖延只會讓情況更糟。面對它，處理它...',
        'fortune_hook': '🔮 想知道最該優先處理什麼？如何有效解決？',
        'advice': '直面問題，徹底解決。拖延是問題的養分。'
    },
    '76': {
        'aspect': '吉',
        'brief': '虛心學習，啟蒙成長',
        'story': '蒙，亨。匪我求童蒙，童蒙求我。此卦象徵學習與啟蒙，保持學習的心態。',
        'fortune': '近期可能遇到學習的機會或遇見能指導您的人。保持謙虛，您會獲得重要的知識...',
        'fortune_hook': '🔮 想知道該學習什麼？誰會是您的指路人？',
        'advice': '保持謙遜，虛心學習。學無止境，活到老學到老。'
    },
    '77': {
        'aspect': '平',
        'brief': '止而不妄，靜待良機',
        'story': '艮，艮其背，不獲其身。此卦象徵停止與等待，有時候不動是最好的行動。',
        'fortune': '近期不適合大動作，維持現狀反而是最佳策略。時機未到，強行出擊會適得其反...',
        'fortune_hook': '🔮 想知道該等到什麼時候？在等待期間該做什麼？',
        'advice': '按兵不動，靜待時機。動不如靜，多不如少。'
    },
    '78': {
        'aspect': '小心',
        'brief': '暫時蟄伏，保存實力',
        'story': '剝，不利有攸往。此卦提醒您：現在是收縮的時候，不宜擴張。',
        'fortune': '近期運勢處於低谷期，要做好過冬的準備。減少不必要的消耗，保存核心實力...',
        'fortune_hook': '🔮 想知道低潮期多久？該保留什麼、放棄什麼？',
        'advice': '韜光養晦，保存實力。冬天之後一定是春天。'
    },
    '81': {
        'aspect': '大吉',
        'brief': '天地交泰，萬事亨通',
        'story': '泰，小往大來，吉亨。此卦是最吉祥的卦象之一，天地相交，萬物通泰。',
        'fortune': '近期您將迎來極為順遂的時期，各方面都會有好的發展。貴人、機遇都在向您靠近...',
        'fortune_hook': '🔮 想知道好運會持續多久？如何讓它最大化？',
        'advice': '把握時機，大膽行動。天時地利人和，正是此時。'
    },
    '82': {
        'aspect': '吉',
        'brief': '親臨督導，以身作則',
        'story': '臨，元亨利貞，至于八月有凶。此卦象徵親自參與和督導的重要性。',
        'fortune': '近期需要您親自出馬的事情會增多，您的親自參與會帶來不同的結果...',
        'fortune_hook': '🔮 想知道哪些事需要親自處理？如何有效管理時間？',
        'advice': '身先士卒，親力親為。榜樣的力量是無窮的。'
    },
    '83': {
        'aspect': '小心',
        'brief': '光明隱晦，蟄伏待機',
        'story': '明夷，利艱貞。此卦如同日落之象，光明暫時被遮蔽，但太陽終會再升起。',
        'fortune': '近期可能感覺不太順，才華得不到施展。但這是黎明前的黑暗，繼續蓄積能量...',
        'fortune_hook': '🔮 想知道光明何時重現？如何在黑暗中保持希望？',
        'advice': '韜光養晦，保持信心。黑夜終將過去，黎明終將來臨。'
    },
    '84': {
        'aspect': '吉',
        'brief': '否極泰來，一陽復始',
        'story': '復，亨。出入無疾，朋來無咎。此卦象徵轉機與新生，最黑暗之後就是光明。',
        'fortune': '近期您將走出困境，迎來轉機。之前的付出沒有白費，收穫即將來臨...',
        'fortune_hook': '🔮 想知道轉機會以什麼形式出現？如何把握？',
        'advice': '堅持信念，迎接曙光。冬天來了，春天還會遠嗎？'
    },
    '85': {
        'aspect': '吉',
        'brief': '穩步上升，蒸蒸日上',
        'story': '升，元亨，用見大人，勿恤。此卦如同植物向上生長，象徵穩定的上升。',
        'fortune': '近期您的運勢正在穩步上升，可能在職場、學業或其他方面獲得晉升...',
        'fortune_hook': '🔮 想知道能升到什麼高度？需要注意什麼？',
        'advice': '持續努力，穩健前進。每天進步一點點，終將到達頂峰。'
    },
    '86': {
        'aspect': '吉',
        'brief': '統御有方，眾望所歸',
        'story': '師，貞丈人吉，無咎。此卦象徵領導與團隊，您可能被賦予領導的責任。',
        'fortune': '近期可能需要承擔領導角色或帶領團隊。眾人期待您的指引...',
        'fortune_hook': '🔮 想知道如何成為好的領導？該帶領團隊往哪走？',
        'advice': '以德服人，凝聚人心。好的領導者是服務者。'
    },
    '87': {
        'aspect': '大吉',
        'brief': '謙虛為懷，福報無窮',
        'story': '謙，亨，君子有終。此卦是易經中唯一六爻皆吉的卦，謙虛的力量超乎想像。',
        'fortune': '近期保持謙虛的態度會帶來意想不到的好運，您的低調反而會吸引更多人的認可...',
        'fortune_hook': '🔮 想知道好運會以什麼形式出現？如何保持謙虛？',
        'advice': '謙受益，滿招損。越是有能力，越要懂得謙虛。'
    },
    '88': {
        'aspect': '吉',
        'brief': '厚德載物，包容萬象',
        'story': '坤，元亨，利牝馬之貞。此卦如同大地，象徵包容與承載的力量。',
        'fortune': '近期適合以包容的心態面對一切，接納不同的人和觀點會為您帶來意想不到的收穫...',
        'fortune_hook': '🔮 想知道該包容什麼？這份包容會帶來什麼？',
        'advice': '包容萬物，厚德載物。海納百川，有容乃大。'
    }
}

# ============================================================
# AI 深度解讀（VIP）
# ============================================================
def get_ai_interpretation(hexagram_name, hexagram_code, question, upper, lower, meaning):
    if not ANTHROPIC_AVAILABLE or not ANTHROPIC_API_KEY:
        return None
    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        
        # 根據問題內容調整提示
        question_context = ""
        if question:
            # 檢測敏感問題類型
            health_keywords = ['手術', '開刀', '治療', '病', '醫', '健康', '癌', '腫瘤', '住院']
            legal_keywords = ['官司', '訴訟', '法律', '告']
            is_health = any(kw in question for kw in health_keywords)
            is_legal = any(kw in question for kw in legal_keywords)
            
            if is_health:
                question_context = f"""
⚠️ 用戶問的是健康/醫療相關問題：「{question}」

重要：
- 你不是醫生，不能給予醫療建議
- 請從卦象的角度分析「時機」、「心態」、「貴人運」等
- 必須提醒用戶：最終決定請遵從專業醫師建議
- 可以分析：此時行動的吉凶、是否有貴人相助、需注意什麼"""
            elif is_legal:
                question_context = f"""
用戶問的是法律相關問題：「{question}」

請從卦象角度分析：
- 此事的整體走向
- 是否適合此時行動
- 需要注意的人事物
- 提醒用戶諮詢專業律師"""
            else:
                question_context = f"""
用戶的問題是：「{question}」

請直接針對這個問題回答：
- 如果問「該不該做」→ 明確說這個卦象建議做或不做，以及原因
- 如果問「會不會成功」→ 分析成功的可能性和需要的條件
- 如果問「何時」→ 根據卦象給出時機建議"""

        prompt = f"""你是精通易經的資深命理師「籟柏老師」。

【卦象資訊】
卦名：{hexagram_name}（第 {hexagram_code} 卦）
卦運：{meaning['aspect']}
上卦：{upper['name']}（{upper['nature']}，五行屬{upper['element']}）
下卦：{lower['name']}（{lower['nature']}，五行屬{lower['element']}）
卦意：{meaning['story']}
{question_context}

【回答要求】
1. 開頭先直接回應用戶的問題（一句話給出方向）
2. 再用卦象解釋為什麼這樣建議
3. 給出具體可行的建議
4. 結尾一句開運箴言

語氣溫暖專業，像智慧長輩給予指引。180字以內。"""

        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text
    except Exception as e:
        print(f"AI interpretation error: {e}")
        return None

# ============================================================
# 占卜核心：太極陰陽魚
# ============================================================
def generate_trigram_from_fish(is_yang, seed_value):
    """根據陰陽魚生成卦數"""
    group = [1, 2, 3, 4] if is_yang else [5, 6, 7, 8]
    return group[seed_value % 4]

def cast_yinyang_fish(user_id=None, question=None):
    """執行太極陰陽魚占卜"""
    now = get_tw_now()
    time_seed = now.hour * 3600 + now.minute * 60 + now.second + now.microsecond
    
    if user_id:
        time_seed = (time_seed + int(hashlib.md5(user_id.encode()).hexdigest()[:8], 16)) % 1000000
    
    # 第一條魚決定上卦
    fish1_yang = random.random() > 0.5
    upper_num = generate_trigram_from_fish(fish1_yang, (time_seed + random.randint(0, 9999)) % 10000)
    
    # 第二條魚決定下卦
    fish2_yang = random.random() > 0.5
    lower_num = generate_trigram_from_fish(fish2_yang, (time_seed + random.randint(0, 9999)) % 10000)
    
    upper, lower = TRIGRAMS[upper_num], TRIGRAMS[lower_num]
    code = f"{upper_num}{lower_num}"
    name = HEXAGRAM_NAMES.get(code, '未知卦')
    meaning = HEXAGRAM_MEANINGS.get(code, {
        'aspect': '平',
        'brief': '天機難測',
        'story': '此卦象需要更深的洞察。',
        'fortune': '近期運勢平穩，靜待時機...',
        'fortune_hook': '🔮 想知道更多？',
        'advice': '順其自然，隨遇而安。'
    })
    
    crystal = CRYSTAL_RECOMMENDATIONS.get(meaning['aspect'], CRYSTAL_RECOMMENDATIONS['平'])
    
    return {
        'fish1': {
            'type': 'yang' if fish1_yang else 'yin',
            'display': '☯ 白魚（陽）' if fish1_yang else '☯ 黑魚（陰）'
        },
        'fish2': {
            'type': 'yang' if fish2_yang else 'yin',
            'display': '☯ 白魚（陽）' if fish2_yang else '☯ 黑魚（陰）'
        },
        'upper_trigram': {'num': upper_num, **upper},
        'lower_trigram': {'num': lower_num, **lower},
        'hexagram': {'code': code, 'name': name, **meaning},
        'crystal': crystal,
        'question': question,
        'timestamp': now.strftime('%Y-%m-%d %H:%M:%S')
    }

# ============================================================
# Flex Messages（重新設計）
# ============================================================
def create_result_flex(result, remaining, is_premium=False, ai_interp=None, category=None, user_profile=None):
    """占卜結果 Flex Message - 免費版豐富，VIP版更豐富"""
    
    aspect_colors = {
        '大吉': '#B8860B',
        '吉': '#228B22', 
        '平': '#4169E1',
        '小心': '#FF8C00',
        '凶': '#DC143C'
    }
    aspect_bg_colors = {
        '大吉': '#FFF8DC',
        '吉': '#F0FFF0',
        '平': '#F0F8FF',
        '小心': '#FFF5EE',
        '凶': '#FFF0F5'
    }
    aspect_emoji = {
        '大吉': '🌟',
        '吉': '✨',
        '平': '☯',
        '小心': '⚠️',
        '凶': '🛡️'
    }
    
    aspect = result['hexagram']['aspect']
    aspect_color = aspect_colors.get(aspect, '#666666')
    aspect_bg = aspect_bg_colors.get(aspect, '#F5F5F5')
    emoji = aspect_emoji.get(aspect, '☯')
    remaining_text = "💎 VIP 無限占卜" if remaining == -1 else f"今日剩餘 {remaining} 次"
    
    # 取得分類資訊
    cat_info = QUESTION_CATEGORIES.get(category) if category else None
    
    # 主體內容
    body_contents = []
    
    # 問事顯示（如果有）
    if result.get('question'):
        cat_display = f" [{cat_info['icon']} {cat_info['name']}]" if cat_info else ""
        body_contents.append({
            "type": "box",
            "layout": "vertical",
            "paddingAll": "12px",
            "backgroundColor": "#FFFAF0",
            "cornerRadius": "8px",
            "contents": [
                {"type": "text", "text": f"🙏 您的問事{cat_display}", "size": "sm", "weight": "bold", "color": "#8B4513"},
                {"type": "text", "text": result['question'], "size": "md", "wrap": True, "margin": "sm", "color": "#333333"}
            ]
        })
        body_contents.append({"type": "separator", "margin": "lg"})
    
    # 卦象區塊 - 簡潔版
    body_contents.append({
        "type": "box",
        "layout": "vertical",
        "margin": "lg",
        "paddingAll": "15px",
        "backgroundColor": aspect_bg,
        "cornerRadius": "12px",
        "contents": [
            {"type": "text", "text": f"第 {result['hexagram']['code']} 卦", "size": "xs", "color": "#888888", "align": "center"},
            {"type": "text", "text": result['hexagram']['name'], "size": "xxl", "weight": "bold", "align": "center", "color": "#1a1a2e", "margin": "sm"},
            {
                "type": "box",
                "layout": "horizontal",
                "justifyContent": "center",
                "margin": "md",
                "contents": [
                    {"type": "text", "text": f"{result['upper_trigram']['symbol']} {result['upper_trigram']['name']}", "size": "lg", "color": "#333333"},
                    {"type": "text", "text": " ╱ ", "size": "lg", "color": "#CCCCCC"},
                    {"type": "text", "text": f"{result['lower_trigram']['symbol']} {result['lower_trigram']['name']}", "size": "lg", "color": "#333333"}
                ]
            },
            {
                "type": "box",
                "layout": "horizontal",
                "justifyContent": "center",
                "margin": "lg",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": aspect_color,
                        "cornerRadius": "20px",
                        "paddingAll": "8px",
                        "paddingStart": "15px",
                        "paddingEnd": "15px",
                        "contents": [
                            {"type": "text", "text": f"{emoji} {aspect}", "size": "md", "weight": "bold", "color": "#FFFFFF", "align": "center"}
                        ]
                    }
                ]
            }
        ]
    })
    
    # 卦意簡述
    body_contents.append({
        "type": "box",
        "layout": "vertical",
        "margin": "xl",
        "contents": [
            {"type": "text", "text": f"「{result['hexagram']['brief']}」", "size": "lg", "weight": "bold", "align": "center", "color": "#1a1a2e"}
        ]
    })
    
    body_contents.append({"type": "separator", "margin": "xl"})
    
    # 卦象故事
    body_contents.append({
        "type": "box",
        "layout": "vertical",
        "margin": "xl",
        "contents": [
            {"type": "text", "text": "📖 卦象解析", "size": "md", "weight": "bold", "color": "#1a1a2e"},
            {"type": "text", "text": result['hexagram']['story'], "size": "sm", "wrap": True, "margin": "md", "color": "#333333", "lineSpacing": "5px"}
        ]
    })
    
    # 分類專屬解讀（如果有選擇分類）
    if category and category in CATEGORY_INTERPRETATIONS:
        cat_info = QUESTION_CATEGORIES.get(category)
        cat_interp = get_category_interpretation(category, aspect, user_profile)
        if cat_interp:
            body_contents.append({"type": "separator", "margin": "xl"})
            body_contents.append({
                "type": "box",
                "layout": "vertical",
                "margin": "xl",
                "paddingAll": "15px",
                "backgroundColor": cat_info['color'] + "15",
                "cornerRadius": "12px",
                "contents": [
                    {"type": "text", "text": f"{cat_info['icon']} {cat_info['name']}解讀", "size": "md", "weight": "bold", "color": cat_info['color']},
                    {"type": "text", "text": cat_interp, "size": "sm", "wrap": True, "margin": "md", "color": "#333333", "lineSpacing": "5px"}
                ]
            })
    
    body_contents.append({"type": "separator", "margin": "xl"})
    
    # 近期運勢（免費版也有，但有懸念）
    body_contents.append({
        "type": "box",
        "layout": "vertical",
        "margin": "xl",
        "contents": [
            {"type": "text", "text": "🔮 近期運勢", "size": "md", "weight": "bold", "color": "#1a1a2e"},
            {"type": "text", "text": result['hexagram']['fortune'], "size": "sm", "wrap": True, "margin": "md", "color": "#333333", "lineSpacing": "5px"}
        ]
    })
    
    body_contents.append({"type": "separator", "margin": "xl"})
    
    # 建議
    body_contents.append({
        "type": "box",
        "layout": "vertical",
        "margin": "xl",
        "contents": [
            {"type": "text", "text": "💡 行動建議", "size": "md", "weight": "bold", "color": "#1a1a2e"},
            {"type": "text", "text": result['hexagram']['advice'], "size": "sm", "wrap": True, "margin": "md", "color": "#333333"}
        ]
    })
    
    # VIP 專屬內容
    if is_premium:
        # AI 深度解讀
        if ai_interp:
            body_contents.append({"type": "separator", "margin": "xl"})
            body_contents.append({
                "type": "box",
                "layout": "vertical",
                "margin": "xl",
                "paddingAll": "15px",
                "backgroundColor": "#F5F0FF",
                "cornerRadius": "12px",
                "contents": [
                    {"type": "text", "text": "🤖 籟柏老師 AI 深度解讀", "size": "md", "weight": "bold", "color": "#6B21A8"},
                    {"type": "text", "text": ai_interp, "size": "sm", "wrap": True, "margin": "md", "color": "#333333", "lineSpacing": "5px"}
                ]
            })
        
        # 水晶推薦
        crystal = result['crystal']['primary']
        body_contents.append({"type": "separator", "margin": "xl"})
        body_contents.append({
            "type": "box",
            "layout": "vertical",
            "margin": "xl",
            "paddingAll": "15px",
            "backgroundColor": "#FDF4FF",
            "cornerRadius": "12px",
            "contents": [
                {"type": "text", "text": "💎 開運水晶推薦", "size": "md", "weight": "bold", "color": "#9333EA"},
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "md",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "vertical",
                            "width": "50px",
                            "height": "50px",
                            "backgroundColor": crystal['color'],
                            "cornerRadius": "25px",
                            "contents": []
                        },
                        {
                            "type": "box",
                            "layout": "vertical",
                            "flex": 1,
                            "paddingStart": "15px",
                            "contents": [
                                {"type": "text", "text": crystal['name'], "size": "md", "weight": "bold", "color": "#333333"},
                                {"type": "text", "text": crystal['benefit'], "size": "sm", "color": "#666666", "wrap": True},
                                {"type": "text", "text": f"📍 {crystal['usage']}", "size": "xs", "color": "#888888", "wrap": True, "margin": "sm"}
                            ]
                        }
                    ]
                }
            ]
        })
    else:
        # 免費版 - 顯示解鎖提示
        body_contents.append({"type": "separator", "margin": "xl"})
        body_contents.append({
            "type": "box",
            "layout": "vertical",
            "margin": "xl",
            "paddingAll": "15px",
            "backgroundColor": "#F0F0F0",
            "cornerRadius": "12px",
            "contents": [
                {"type": "text", "text": result['hexagram']['fortune_hook'], "size": "sm", "wrap": True, "color": "#666666", "align": "center"},
                {"type": "text", "text": "🔓 升級 VIP 解鎖完整解讀", "size": "sm", "weight": "bold", "color": "#9333EA", "align": "center", "margin": "md"},
                {"type": "text", "text": "✦ AI 命理師深度分析\n✦ 專屬開運水晶推薦\n✦ 無限次占卜", "size": "xs", "color": "#888888", "align": "center", "margin": "sm", "wrap": True}
            ]
        })
    
    return {
        "type": "bubble",
        "size": "giga",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1a1a2e",
            "paddingAll": "15px",
            "contents": [
                {"type": "text", "text": "☯ 太極陰陽魚易占 ☯", "weight": "bold", "size": "lg", "color": "#FFFFFF", "align": "center"},
                {"type": "text", "text": f"{result['fish1']['display']} → 上卦　{result['fish2']['display']} → 下卦", "size": "xs", "color": "#CCCCCC", "align": "center", "margin": "sm"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "20px",
            "contents": body_contents
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "15px",
            "backgroundColor": "#F5F5F5",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "button", "action": {"type": "message", "label": "🙏 問事占卜", "text": "問事"}, "style": "primary", "color": "#6B21A8", "flex": 1},
                        {"type": "button", "action": {"type": "message", "label": "🏠 回首頁", "text": "首頁"}, "style": "secondary", "flex": 1, "margin": "md"}
                    ]
                },
                {"type": "text", "text": remaining_text, "size": "xs", "color": "#888888", "align": "center", "margin": "md"},
                {"type": "text", "text": f"占卜時間：{result['timestamp']}", "size": "xxs", "color": "#AAAAAA", "align": "center", "margin": "sm"}
            ]
        }
    }

def create_welcome_flex():
    """歡迎訊息 Flex Message"""
    return {
        "type": "bubble",
        "size": "giga",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1a1a2e",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "☯", "size": "3xl", "align": "center"},
                {"type": "text", "text": "籟柏太極易占", "weight": "bold", "size": "xl", "color": "#FFFFFF", "align": "center", "margin": "md"},
                {"type": "text", "text": "陰陽魚游，卦象自現", "size": "sm", "color": "#CCCCCC", "align": "center", "margin": "sm"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "歡迎來到太極易占的神秘世界！", "weight": "bold", "size": "lg", "align": "center", "color": "#1a1a2e"},
                {"type": "separator", "margin": "xl"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "xl",
                    "paddingAll": "15px",
                    "backgroundColor": "#F8F8F8",
                    "cornerRadius": "12px",
                    "contents": [
                        {"type": "text", "text": "🐟 占卜原理", "weight": "bold", "size": "md", "color": "#1a1a2e"},
                        {"type": "text", "text": "太極圖中的陰陽二魚，代表宇宙萬物的變化法則。當您誠心發問，兩條魚會翻轉顯示陰陽，組合成六十四卦之一，為您揭示天機。", "size": "sm", "wrap": True, "margin": "md", "color": "#333333", "lineSpacing": "5px"},
                        {"type": "separator", "margin": "lg"},
                        {"type": "text", "text": "☯ 白魚（陽）→ 乾兌離震\n☯ 黑魚（陰）→ 巽坎艮坤", "size": "sm", "margin": "lg", "color": "#666666", "wrap": True}
                    ]
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "xl",
                    "paddingAll": "15px",
                    "backgroundColor": "#FFF8DC",
                    "cornerRadius": "12px",
                    "contents": [
                        {"type": "text", "text": "✨ 每日免費 3 次占卜", "size": "md", "weight": "bold", "color": "#B8860B", "align": "center"},
                        {"type": "text", "text": "心誠則靈，靜心冥想後再開始", "size": "xs", "color": "#888888", "align": "center", "margin": "sm"}
                    ]
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "15px",
            "backgroundColor": "#F5F5F5",
            "contents": [
                {"type": "button", "action": {"type": "message", "label": "🙏 開始問事占卜", "text": "問事"}, "style": "primary", "color": "#6B21A8"},
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "md",
                    "contents": [
                        {"type": "button", "action": {"type": "message", "label": "☀️ 運勢", "text": "運勢"}, "style": "secondary", "flex": 1},
                        {"type": "button", "action": {"type": "message", "label": "📅 簽到", "text": "簽到"}, "style": "secondary", "flex": 1, "margin": "sm"}
                    ]
                },
                {"type": "button", "action": {"type": "message", "label": "💎 VIP 會員", "text": "VIP"}, "style": "secondary", "margin": "md"}
            ]
        }
    }

def create_ask_question_flex():
    """問事分類選擇 Flex Message"""
    return {
        "type": "bubble",
        "size": "giga",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1a1a2e",
            "paddingAll": "15px",
            "contents": [
                {"type": "text", "text": "🙏 問事占卜", "weight": "bold", "size": "lg", "color": "#FFFFFF", "align": "center"},
                {"type": "text", "text": "請先選擇問事類別", "size": "sm", "color": "#CCCCCC", "align": "center", "margin": "sm"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "選擇類別可獲得更精準的解讀", "size": "sm", "color": "#666666", "align": "center"},
                {"type": "separator", "margin": "lg"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "lg",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "spacing": "sm",
                            "contents": [
                                {"type": "button", "action": {"type": "message", "label": "💕 感情姻緣", "text": "問事:感情"}, "style": "secondary", "flex": 1, "height": "sm"},
                                {"type": "button", "action": {"type": "message", "label": "💼 事業工作", "text": "問事:事業"}, "style": "secondary", "flex": 1, "height": "sm"}
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "spacing": "sm",
                            "contents": [
                                {"type": "button", "action": {"type": "message", "label": "💰 財運投資", "text": "問事:財運"}, "style": "secondary", "flex": 1, "height": "sm"},
                                {"type": "button", "action": {"type": "message", "label": "🏥 健康平安", "text": "問事:健康"}, "style": "secondary", "flex": 1, "height": "sm"}
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "spacing": "sm",
                            "contents": [
                                {"type": "button", "action": {"type": "message", "label": "📚 考試學業", "text": "問事:學業"}, "style": "secondary", "flex": 1, "height": "sm"},
                                {"type": "button", "action": {"type": "message", "label": "🔮 綜合運勢", "text": "問事:綜合"}, "style": "secondary", "flex": 1, "height": "sm"}
                            ]
                        }
                    ]
                },
                {"type": "separator", "margin": "xl"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "lg",
                    "paddingAll": "12px",
                    "backgroundColor": "#FFF8DC",
                    "cornerRadius": "8px",
                    "contents": [
                        {"type": "text", "text": "💡 小提示", "size": "sm", "weight": "bold", "color": "#B8860B"},
                        {"type": "text", "text": "選擇對應類別，將獲得更貼切的卦象解讀與具體建議", "size": "xs", "color": "#888888", "margin": "sm", "wrap": True}
                    ]
                }
            ]
        }
    }

def create_category_input_flex(category):
    """選擇分類後的問題輸入提示 - 含快速問題按鈕"""
    cat_info = QUESTION_CATEGORIES.get(category, QUESTION_CATEGORIES['general'])
    
    # 常見問題按鈕（每個分類3個）
    quick_questions = {
        'love': [
            ('這段感情該繼續嗎？', '感情該繼續嗎'),
            ('對方對我有意思嗎？', '對方有意思嗎'),
            ('何時遇到對的人？', '何時遇到真愛')
        ],
        'career': [
            ('該換工作嗎？', '該換工作嗎'),
            ('這個專案會成功嗎？', '專案會成功嗎'),
            ('適合創業嗎？', '適合創業嗎')
        ],
        'wealth': [
            ('這筆投資可行嗎？', '投資可行嗎'),
            ('近期財運如何？', '近期財運'),
            ('適合買房嗎？', '適合買房嗎')
        ],
        'health': [
            ('身體會好轉嗎？', '身體會好轉嗎'),
            ('該做這個手術嗎？', '該做手術嗎'),
            ('家人健康如何？', '家人健康')
        ],
        'study': [
            ('考試會通過嗎？', '考試會過嗎'),
            ('該選什麼科系？', '選什麼科系'),
            ('適合出國留學嗎？', '適合留學嗎')
        ],
        'general': [
            ('這個決定正確嗎？', '決定正確嗎'),
            ('近期運勢如何？', '近期運勢'),
            ('有什麼要注意的？', '注意事項')
        ]
    }
    
    questions = quick_questions.get(category, quick_questions['general'])
    
    # 建立按鈕
    buttons = []
    for full_q, short_label in questions:
        buttons.append({
            "type": "button",
            "action": {"type": "message", "label": short_label, "text": f"問題:{category}:{full_q}"},
            "style": "secondary",
            "height": "sm",
            "margin": "sm"
        })
    
    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": cat_info['color'],
            "paddingAll": "15px",
            "contents": [
                {"type": "text", "text": f"{cat_info['icon']} {cat_info['name']}", "weight": "bold", "size": "lg", "color": "#FFFFFF", "align": "center"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "選擇常見問題或自行輸入", "size": "md", "align": "center", "weight": "bold", "color": "#1a1a2e"},
                {"type": "separator", "margin": "lg"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "lg",
                    "contents": buttons
                },
                {"type": "separator", "margin": "lg"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "lg",
                    "paddingAll": "12px",
                    "backgroundColor": "#F8F8F8",
                    "cornerRadius": "8px",
                    "contents": [
                        {"type": "text", "text": "💡 或直接輸入您的問題", "size": "sm", "weight": "bold", "color": "#666666", "align": "center"},
                        {"type": "text", "text": "輸入後自動為您占卜", "size": "xs", "color": "#888888", "align": "center", "margin": "sm"}
                    ]
                }
            ]
        }
    }

def create_profile_gender_flex():
    """用戶資料收集 - 性別選擇"""
    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1a1a2e",
            "paddingAll": "15px",
            "contents": [
                {"type": "text", "text": "📝 完善您的資料", "weight": "bold", "size": "lg", "color": "#FFFFFF", "align": "center"},
                {"type": "text", "text": "讓占卜結果更貼近您的情況", "size": "xs", "color": "#CCCCCC", "align": "center", "margin": "sm"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "請問您的性別？", "size": "lg", "weight": "bold", "align": "center", "color": "#1a1a2e"},
                {"type": "text", "text": "此資料僅用於提供更精準的解讀", "size": "xs", "color": "#888888", "align": "center", "margin": "md"},
                {"type": "separator", "margin": "xl"},
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "xl",
                    "spacing": "md",
                    "contents": [
                        {"type": "button", "action": {"type": "message", "label": "👨 男性", "text": "資料:性別:男"}, "style": "secondary", "flex": 1, "height": "sm"},
                        {"type": "button", "action": {"type": "message", "label": "👩 女性", "text": "資料:性別:女"}, "style": "secondary", "flex": 1, "height": "sm"}
                    ]
                },
                {"type": "button", "action": {"type": "message", "label": "🔮 不透露", "text": "資料:性別:不透露"}, "style": "secondary", "margin": "md", "height": "sm"}
            ]
        }
    }

def create_profile_age_flex():
    """用戶資料收集 - 年齡選擇"""
    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1a1a2e",
            "paddingAll": "15px",
            "contents": [
                {"type": "text", "text": "📝 完善您的資料", "weight": "bold", "size": "lg", "color": "#FFFFFF", "align": "center"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "請問您的年齡範圍？", "size": "lg", "weight": "bold", "align": "center", "color": "#1a1a2e"},
                {"type": "separator", "margin": "lg"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "lg",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "spacing": "sm",
                            "contents": [
                                {"type": "button", "action": {"type": "message", "label": "18-25歲", "text": "資料:年齡:18-25"}, "style": "secondary", "flex": 1, "height": "sm"},
                                {"type": "button", "action": {"type": "message", "label": "26-35歲", "text": "資料:年齡:26-35"}, "style": "secondary", "flex": 1, "height": "sm"}
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "spacing": "sm",
                            "contents": [
                                {"type": "button", "action": {"type": "message", "label": "36-45歲", "text": "資料:年齡:36-45"}, "style": "secondary", "flex": 1, "height": "sm"},
                                {"type": "button", "action": {"type": "message", "label": "46-55歲", "text": "資料:年齡:46-55"}, "style": "secondary", "flex": 1, "height": "sm"}
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "spacing": "sm",
                            "contents": [
                                {"type": "button", "action": {"type": "message", "label": "56歲以上", "text": "資料:年齡:56+"}, "style": "secondary", "flex": 1, "height": "sm"},
                                {"type": "button", "action": {"type": "message", "label": "不透露", "text": "資料:年齡:不透露"}, "style": "secondary", "flex": 1, "height": "sm"}
                            ]
                        }
                    ]
                }
            ]
        }
    }

def create_profile_marital_flex():
    """用戶資料收集 - 婚姻狀態選擇"""
    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1a1a2e",
            "paddingAll": "15px",
            "contents": [
                {"type": "text", "text": "📝 完善您的資料", "weight": "bold", "size": "lg", "color": "#FFFFFF", "align": "center"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "請問您的感情狀態？", "size": "lg", "weight": "bold", "align": "center", "color": "#1a1a2e"},
                {"type": "text", "text": "這將幫助我們提供更適切的感情建議", "size": "xs", "color": "#888888", "align": "center", "margin": "md"},
                {"type": "separator", "margin": "lg"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "lg",
                    "spacing": "sm",
                    "contents": [
                        {"type": "button", "action": {"type": "message", "label": "💑 已婚/同居", "text": "資料:婚姻:married"}, "style": "secondary", "height": "sm"},
                        {"type": "button", "action": {"type": "message", "label": "💕 戀愛中", "text": "資料:婚姻:relationship"}, "style": "secondary", "height": "sm"},
                        {"type": "button", "action": {"type": "message", "label": "💫 單身", "text": "資料:婚姻:single"}, "style": "secondary", "height": "sm"},
                        {"type": "button", "action": {"type": "message", "label": "🔮 不透露", "text": "資料:婚姻:不透露"}, "style": "secondary", "height": "sm"}
                    ]
                }
            ]
        }
    }

def create_profile_complete_flex():
    """用戶資料收集完成"""
    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#228B22",
            "paddingAll": "15px",
            "contents": [
                {"type": "text", "text": "✅ 資料設定完成", "weight": "bold", "size": "lg", "color": "#FFFFFF", "align": "center"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "感謝您完善資料！", "size": "lg", "weight": "bold", "align": "center", "color": "#1a1a2e"},
                {"type": "text", "text": "現在您可以獲得更個人化的占卜解讀", "size": "sm", "color": "#666666", "align": "center", "margin": "md", "wrap": True},
                {"type": "separator", "margin": "xl"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "xl",
                    "paddingAll": "12px",
                    "backgroundColor": "#F0FFF0",
                    "cornerRadius": "8px",
                    "contents": [
                        {"type": "text", "text": "💡 您可以隨時輸入「修改資料」來更新", "size": "xs", "color": "#228B22", "align": "center", "wrap": True}
                    ]
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "15px",
            "backgroundColor": "#F5F5F5",
            "contents": [
                {"type": "button", "action": {"type": "message", "label": "🙏 開始問事占卜", "text": "問事"}, "style": "primary", "color": "#6B21A8"},
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "md",
                    "contents": [
                        {"type": "button", "action": {"type": "message", "label": "☀️ 運勢", "text": "運勢"}, "style": "secondary", "flex": 1},
                        {"type": "button", "action": {"type": "message", "label": "📅 簽到", "text": "簽到"}, "style": "secondary", "flex": 1, "margin": "sm"}
                    ]
                },
                {"type": "button", "action": {"type": "message", "label": "💎 VIP 會員", "text": "VIP"}, "style": "secondary", "margin": "md"}
            ]
        }
    }

def create_check_in_flex(status, result=None):
    """簽到 Flex Message"""
    
    # 如果是簽到結果
    if result and result['success']:
        streak = result['streak']
        bonus_msg = result.get('bonus_message', '')
        
        # 計算下一個獎勵
        if streak < 7:
            next_reward = f"再簽 {7 - streak} 天獲得 VIP 體驗券 1 天"
            progress = streak / 7
        elif streak < 30:
            next_reward = f"再簽 {30 - streak} 天獲得 VIP 體驗券 3 天"
            progress = (streak - 7) / 23
        else:
            days_to_next = 7 - (streak % 7) if streak % 7 != 0 else 7
            next_reward = f"再簽 {days_to_next} 天獲得 VIP 體驗券 1 天"
            progress = (7 - days_to_next) / 7
        
        contents = [
            {"type": "text", "text": "🎉 簽到成功！", "size": "xl", "weight": "bold", "align": "center", "color": "#228B22"},
            {"type": "text", "text": f"連續簽到 {streak} 天", "size": "lg", "align": "center", "color": "#1a1a2e", "margin": "md"},
            {"type": "separator", "margin": "xl"},
            {
                "type": "box",
                "layout": "vertical",
                "margin": "xl",
                "paddingAll": "15px",
                "backgroundColor": "#F0FFF0",
                "cornerRadius": "12px",
                "contents": [
                    {"type": "text", "text": "✨ 獲得獎勵", "size": "md", "weight": "bold", "color": "#228B22"},
                    {"type": "text", "text": "📿 今日占卜次數 +1", "size": "sm", "margin": "md", "color": "#333333"}
                ]
            }
        ]
        
        if bonus_msg:
            contents.append({
                "type": "box",
                "layout": "vertical",
                "margin": "md",
                "paddingAll": "15px",
                "backgroundColor": "#FFF8DC",
                "cornerRadius": "12px",
                "contents": [
                    {"type": "text", "text": bonus_msg, "size": "sm", "weight": "bold", "color": "#B8860B", "wrap": True}
                ]
            })
        
        contents.append({"type": "separator", "margin": "xl"})
        contents.append({
            "type": "box",
            "layout": "vertical",
            "margin": "xl",
            "contents": [
                {"type": "text", "text": "🎯 下一個獎勵", "size": "sm", "weight": "bold", "color": "#666666"},
                {"type": "text", "text": next_reward, "size": "sm", "color": "#888888", "margin": "sm"}
            ]
        })
        
        header_bg = "#228B22"
        header_text = "每日簽到"
        
    # 如果今天已簽到
    elif status['checked_today']:
        streak = status['current_streak']
        
        if streak < 7:
            next_reward = f"再簽 {7 - streak} 天獲得 VIP 體驗券 1 天"
        elif streak < 30:
            next_reward = f"再簽 {30 - streak} 天獲得 VIP 體驗券 3 天"
        else:
            days_to_next = 7 - (streak % 7) if streak % 7 != 0 else 7
            next_reward = f"再簽 {days_to_next} 天獲得 VIP 體驗券 1 天"
        
        contents = [
            {"type": "text", "text": "✅ 今日已簽到", "size": "lg", "weight": "bold", "align": "center", "color": "#1a1a2e"},
            {"type": "text", "text": f"連續簽到 {streak} 天", "size": "md", "align": "center", "color": "#666666", "margin": "md"},
            {"type": "separator", "margin": "xl"},
            {
                "type": "box",
                "layout": "vertical",
                "margin": "xl",
                "contents": [
                    {"type": "text", "text": "🎯 下一個獎勵", "size": "sm", "weight": "bold", "color": "#666666"},
                    {"type": "text", "text": next_reward, "size": "sm", "color": "#888888", "margin": "sm"}
                ]
            },
            {"type": "text", "text": "明天記得回來簽到喔！", "size": "xs", "color": "#AAAAAA", "align": "center", "margin": "xl"}
        ]
        
        header_bg = "#4169E1"
        header_text = "簽到狀態"
        
    # 尚未簽到
    else:
        yesterday_streak = status['yesterday_streak']
        if yesterday_streak > 0:
            streak_text = f"目前連續 {yesterday_streak} 天，今天簽到可延續！"
        else:
            streak_text = "開始你的簽到之旅吧！"
        
        contents = [
            {"type": "text", "text": "📅 每日簽到", "size": "lg", "weight": "bold", "align": "center", "color": "#1a1a2e"},
            {"type": "text", "text": streak_text, "size": "sm", "align": "center", "color": "#666666", "margin": "md", "wrap": True},
            {"type": "separator", "margin": "xl"},
            {
                "type": "box",
                "layout": "vertical",
                "margin": "xl",
                "paddingAll": "15px",
                "backgroundColor": "#FFF8DC",
                "cornerRadius": "12px",
                "contents": [
                    {"type": "text", "text": "🎁 簽到獎勵", "size": "md", "weight": "bold", "color": "#B8860B"},
                    {"type": "text", "text": "• 每日簽到：占卜次數 +1\n• 連續 7 天：VIP 體驗券 1 天\n• 連續 30 天：VIP 體驗券 3 天", "size": "xs", "color": "#666666", "margin": "md", "wrap": True}
                ]
            }
        ]
        
        header_bg = "#FF8C00"
        header_text = "尚未簽到"
    
    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": header_bg,
            "paddingAll": "15px",
            "contents": [
                {"type": "text", "text": f"📅 {header_text}", "weight": "bold", "size": "lg", "color": "#FFFFFF", "align": "center"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "20px",
            "contents": contents
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "15px",
            "backgroundColor": "#F5F5F5",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "button", "action": {"type": "message", "label": "📅 簽到" if not status['checked_today'] else "🙏 去問事", "text": "簽到" if not status['checked_today'] else "問事"}, "style": "primary", "color": "#1a1a2e" if status['checked_today'] else "#228B22", "flex": 1},
                        {"type": "button", "action": {"type": "message", "label": "🏠 首頁", "text": "首頁"}, "style": "secondary", "flex": 1, "margin": "sm"}
                    ]
                }
            ]
        }
    }

def create_limit_reached_flex():
    """次數用完提示 Flex Message"""
    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#DC143C",
            "paddingAll": "15px",
            "contents": [
                {"type": "text", "text": "⏰ 今日次數已用完", "weight": "bold", "size": "lg", "color": "#FFFFFF", "align": "center"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": f"您今日 {FREE_DAILY_LIMIT} 次免費占卜已用完", "size": "md", "wrap": True, "align": "center", "color": "#333333"},
                {"type": "text", "text": "明日 00:00 重新獲得免費次數", "size": "sm", "color": "#888888", "align": "center", "margin": "md"},
                {"type": "separator", "margin": "xl"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "xl",
                    "paddingAll": "15px",
                    "backgroundColor": "#FDF4FF",
                    "cornerRadius": "12px",
                    "contents": [
                        {"type": "text", "text": "💎 升級 VIP 享受更多", "size": "md", "weight": "bold", "color": "#9333EA", "align": "center"},
                        {"type": "text", "text": "✦ 無限次占卜\n✦ AI 命理師深度解讀\n✦ 專屬開運水晶推薦", "size": "sm", "color": "#666666", "align": "center", "margin": "md", "wrap": True}
                    ]
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "15px",
            "backgroundColor": "#F5F5F5",
            "contents": [
                {"type": "button", "action": {"type": "message", "label": "💎 升級 VIP", "text": "VIP"}, "style": "primary", "color": "#9333EA"}
            ]
        }
    }

def create_help_flex():
    """使用說明 Flex Message"""
    return {
        "type": "bubble",
        "size": "giga",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1a1a2e",
            "paddingAll": "15px",
            "contents": [
                {"type": "text", "text": "📋 使用說明", "weight": "bold", "size": "xl", "color": "#FFFFFF", "align": "center"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "20px",
            "contents": [
                {
                    "type": "box",
                    "layout": "vertical",
                    "paddingAll": "15px",
                    "backgroundColor": "#F8F8F8",
                    "cornerRadius": "12px",
                    "contents": [
                        {"type": "text", "text": "🎯 指令一覽", "weight": "bold", "size": "md", "color": "#1a1a2e"},
                        {"type": "text", "text": "問事 → 選擇類別開始占卜\n運勢 → 查看今日運勢\n簽到 → 每日簽到領獎勵\n次數 → 查看今日剩餘次數\n紀錄 → 查看占卜歷史\n說明 → 顯示本說明\nVIP → 了解進階方案", "size": "sm", "margin": "md", "color": "#333333", "wrap": True}
                    ]
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "xl",
                    "paddingAll": "15px",
                    "backgroundColor": "#FFF8DC",
                    "cornerRadius": "12px",
                    "contents": [
                        {"type": "text", "text": "☯ 占卜原理", "weight": "bold", "size": "md", "color": "#B8860B"},
                        {"type": "text", "text": "白魚（陽）→ 乾兌離震\n黑魚（陰）→ 巽坎艮坤\n\n兩魚組合成六十四卦", "size": "sm", "margin": "md", "color": "#666666", "wrap": True}
                    ]
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "xl",
                    "paddingAll": "15px",
                    "backgroundColor": "#FDF4FF",
                    "cornerRadius": "12px",
                    "contents": [
                        {"type": "text", "text": "💎 VIP 專屬功能", "weight": "bold", "size": "md", "color": "#9333EA"},
                        {"type": "text", "text": "✦ 無限次占卜\n✦ AI 命理師深度解讀\n✦ 專屬開運水晶推薦\n✦ 完整運勢分析", "size": "sm", "margin": "md", "color": "#666666", "wrap": True}
                    ]
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "15px",
            "backgroundColor": "#F5F5F5",
            "contents": [
                {"type": "button", "action": {"type": "message", "label": "🙏 開始問事", "text": "問事"}, "style": "primary", "color": "#1a1a2e"}
            ]
        }
    }

def create_vip_flex():
    """VIP 方案 Flex Message"""
    return {
        "type": "bubble",
        "size": "giga",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#9333EA",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "💎", "size": "3xl", "align": "center"},
                {"type": "text", "text": "VIP 會員方案", "weight": "bold", "size": "xl", "color": "#FFFFFF", "align": "center", "margin": "md"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "20px",
            "contents": [
                {
                    "type": "box",
                    "layout": "vertical",
                    "paddingAll": "15px",
                    "backgroundColor": "#FAF5FF",
                    "cornerRadius": "12px",
                    "contents": [
                        {"type": "text", "text": "✨ VIP 專屬權益", "weight": "bold", "size": "md", "color": "#6B21A8"},
                        {"type": "text", "text": "✦ 無限次占卜 - 隨時隨地問卦\n✦ AI 深度解讀 - 籟柏老師親自分析\n✦ 開運水晶推薦 - 專屬能量建議\n✦ 完整運勢分析 - 不再有保留\n✦ 優先客服支援", "size": "sm", "margin": "md", "color": "#333333", "wrap": True, "lineSpacing": "3px"}
                    ]
                },
                {"type": "separator", "margin": "xl"},
                {"type": "text", "text": "📦 方案價格", "weight": "bold", "size": "md", "color": "#1a1a2e", "margin": "xl"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "md",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "paddingAll": "12px",
                            "backgroundColor": "#F8F8F8",
                            "cornerRadius": "8px",
                            "contents": [
                                {"type": "text", "text": "月費方案", "size": "sm", "flex": 2, "color": "#333333"},
                                {"type": "text", "text": "NT$ 99", "size": "sm", "weight": "bold", "flex": 1, "align": "end", "color": "#9333EA"}
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "paddingAll": "12px",
                            "backgroundColor": "#FAF5FF",
                            "cornerRadius": "8px",
                            "margin": "sm",
                            "contents": [
                                {"type": "text", "text": "季費方案", "size": "sm", "flex": 2, "color": "#333333"},
                                {"type": "text", "text": "NT$ 249", "size": "sm", "weight": "bold", "flex": 1, "align": "end", "color": "#9333EA"},
                                {"type": "text", "text": "省$48", "size": "xs", "color": "#22C55E", "margin": "sm"}
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "paddingAll": "12px",
                            "backgroundColor": "#F0E6FF",
                            "cornerRadius": "8px",
                            "margin": "sm",
                            "contents": [
                                {"type": "text", "text": "年費方案 👑", "size": "sm", "flex": 2, "weight": "bold", "color": "#6B21A8"},
                                {"type": "text", "text": "NT$ 899", "size": "sm", "weight": "bold", "flex": 1, "align": "end", "color": "#9333EA"},
                                {"type": "text", "text": "省$289", "size": "xs", "color": "#22C55E", "margin": "sm"}
                            ]
                        }
                    ]
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "xl",
                    "paddingAll": "12px",
                    "backgroundColor": "#FFF8DC",
                    "cornerRadius": "8px",
                    "contents": [
                        {"type": "text", "text": "🔜 付費功能即將開放！", "size": "sm", "weight": "bold", "color": "#B8860B", "align": "center"},
                        {"type": "text", "text": "敬請期待，我們正在為您準備最好的體驗", "size": "xs", "color": "#888888", "align": "center", "margin": "sm"}
                    ]
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "15px",
            "backgroundColor": "#F5F5F5",
            "contents": [
                {"type": "button", "action": {"type": "message", "label": "🙏 繼續問事", "text": "問事"}, "style": "secondary"}
            ]
        }
    }

def create_history_flex(records):
    """占卜紀錄 Flex Message"""
    if not records:
        return {
            "type": "bubble",
            "size": "kilo",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#1a1a2e",
                "paddingAll": "15px",
                "contents": [
                    {"type": "text", "text": "📜 占卜紀錄", "weight": "bold", "size": "lg", "color": "#FFFFFF", "align": "center"}
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "20px",
                "contents": [
                    {"type": "text", "text": "目前還沒有占卜紀錄", "size": "md", "align": "center", "color": "#888888"},
                    {"type": "text", "text": "開始您的第一次占卜吧！", "size": "sm", "align": "center", "color": "#AAAAAA", "margin": "md"}
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "15px",
                "backgroundColor": "#F5F5F5",
                "contents": [
                    {"type": "button", "action": {"type": "message", "label": "🙏 開始問事", "text": "問事"}, "style": "primary", "color": "#1a1a2e"}
                ]
            }
        }
    
    items = []
    for r in records:
        items.append({
            "type": "box",
            "layout": "horizontal",
            "paddingAll": "10px",
            "backgroundColor": "#F8F8F8",
            "cornerRadius": "8px",
            "margin": "sm",
            "contents": [
                {"type": "text", "text": r[1], "size": "sm", "flex": 3, "weight": "bold", "color": "#333333"},
                {"type": "text", "text": r[3][:10], "size": "xs", "color": "#888888", "flex": 2, "align": "end"}
            ]
        })
    
    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1a1a2e",
            "paddingAll": "15px",
            "contents": [
                {"type": "text", "text": "📜 占卜紀錄", "weight": "bold", "size": "lg", "color": "#FFFFFF", "align": "center"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "15px",
            "contents": items
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "15px",
            "backgroundColor": "#F5F5F5",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "button", "action": {"type": "message", "label": "🙏 問事占卜", "text": "問事"}, "style": "primary", "color": "#6B21A8", "flex": 1},
                        {"type": "button", "action": {"type": "message", "label": "🏠 回首頁", "text": "首頁"}, "style": "secondary", "flex": 1, "margin": "md"}
                    ]
                }
            ]
        }
    }

def create_daily_fortune_flex(fortune, is_premium=False):
    """每日運勢 Flex Message - 基於易經64卦"""
    
    body_contents = [
        # 卦象顯示
        {
            "type": "box",
            "layout": "horizontal",
            "paddingAll": "15px",
            "backgroundColor": fortune['overall']['color'] + "20",
            "cornerRadius": "12px",
            "contents": [
                {
                    "type": "box",
                    "layout": "vertical",
                    "flex": 1,
                    "contents": [
                        {"type": "text", "text": fortune.get('hexagram_symbol', '☯'), "size": "3xl", "align": "center", "color": fortune['overall']['color']},
                    ]
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "flex": 3,
                    "contents": [
                        {"type": "text", "text": fortune.get('hexagram_name', '今日卦象'), "size": "lg", "weight": "bold", "color": "#1a1a2e"},
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "margin": "sm",
                            "contents": [
                                {
                                    "type": "box",
                                    "layout": "vertical",
                                    "backgroundColor": fortune['overall']['color'],
                                    "cornerRadius": "12px",
                                    "paddingAll": "5px",
                                    "paddingStart": "12px",
                                    "paddingEnd": "12px",
                                    "contents": [
                                        {"type": "text", "text": fortune['overall']['level'], "size": "sm", "weight": "bold", "color": "#FFFFFF", "align": "center"}
                                    ]
                                },
                                {"type": "filler"}
                            ]
                        },
                        {"type": "text", "text": fortune['overall']['desc'], "size": "sm", "wrap": True, "margin": "md", "color": "#333333"}
                    ]
                }
            ]
        },
        {"type": "separator", "margin": "xl"},
        {
            "type": "box",
            "layout": "vertical",
            "margin": "xl",
            "contents": [
                {"type": "text", "text": "🎯 今日運勢速覽", "size": "md", "weight": "bold", "color": "#1a1a2e"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "md",
                    "paddingAll": "12px",
                    "backgroundColor": "#FFF5F5",
                    "cornerRadius": "8px",
                    "contents": [
                        {"type": "text", "text": f"💕 感情：{fortune['love']}", "size": "sm", "wrap": True, "color": "#333333"}
                    ]
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "sm",
                    "paddingAll": "12px",
                    "backgroundColor": "#F0FFF4",
                    "cornerRadius": "8px",
                    "contents": [
                        {"type": "text", "text": f"💼 事業：{fortune['career']}", "size": "sm", "wrap": True, "color": "#333333"}
                    ]
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "sm",
                    "paddingAll": "12px",
                    "backgroundColor": "#FFFFF0",
                    "cornerRadius": "8px",
                    "contents": [
                        {"type": "text", "text": f"💰 財運：{fortune['wealth']}", "size": "sm", "wrap": True, "color": "#333333"}
                    ]
                }
            ]
        },
        {"type": "separator", "margin": "xl"},
        {
            "type": "box",
            "layout": "horizontal",
            "margin": "xl",
            "contents": [
                {
                    "type": "box",
                    "layout": "vertical",
                    "flex": 1,
                    "contents": [
                        {"type": "text", "text": "🎨 幸運色", "size": "xs", "color": "#888888", "align": "center"},
                        {"type": "text", "text": fortune['lucky_color'], "size": "md", "weight": "bold", "color": "#333333", "align": "center", "margin": "sm"}
                    ]
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "flex": 1,
                    "contents": [
                        {"type": "text", "text": "🔢 幸運數", "size": "xs", "color": "#888888", "align": "center"},
                        {"type": "text", "text": str(fortune['lucky_number']), "size": "md", "weight": "bold", "color": "#333333", "align": "center", "margin": "sm"}
                    ]
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "flex": 1,
                    "contents": [
                        {"type": "text", "text": "🧭 幸運方位", "size": "xs", "color": "#888888", "align": "center"},
                        {"type": "text", "text": fortune['lucky_direction'], "size": "md", "weight": "bold", "color": "#333333", "align": "center", "margin": "sm"}
                    ]
                }
            ]
        },
        {"type": "separator", "margin": "xl"},
        {
            "type": "box",
            "layout": "vertical",
            "margin": "xl",
            "paddingAll": "12px",
            "backgroundColor": "#F0F8FF",
            "cornerRadius": "8px",
            "contents": [
                {"type": "text", "text": f"📿 卦象建議：{fortune['advice']}", "size": "sm", "wrap": True, "color": "#333333"}
            ]
        }
    ]
    
    # VIP 專屬：更詳細的時辰運勢提示
    if is_premium:
        body_contents.append({"type": "separator", "margin": "xl"})
        body_contents.append({
            "type": "box",
            "layout": "vertical",
            "margin": "xl",
            "paddingAll": "15px",
            "backgroundColor": "#F5F0FF",
            "cornerRadius": "12px",
            "contents": [
                {"type": "text", "text": "💎 VIP 專屬：今日時辰指南", "size": "md", "weight": "bold", "color": "#6B21A8"},
                {"type": "text", "text": "🌅 早上 6-9 點：最佳決策時段\n☀️ 中午 11-13 點：適合社交談判\n🌙 晚上 19-21 點：適合學習充電", "size": "sm", "wrap": True, "margin": "md", "color": "#333333", "lineSpacing": "5px"}
            ]
        })
    else:
        body_contents.append({"type": "separator", "margin": "xl"})
        body_contents.append({
            "type": "box",
            "layout": "vertical",
            "margin": "xl",
            "paddingAll": "12px",
            "backgroundColor": "#F0F0F0",
            "cornerRadius": "8px",
            "contents": [
                {"type": "text", "text": "💎 升級 VIP 解鎖更多", "size": "sm", "weight": "bold", "color": "#9333EA", "align": "center"},
                {"type": "text", "text": "時辰運勢指南 • 每日推送 • 無限占卜", "size": "xs", "color": "#888888", "align": "center", "margin": "sm"}
            ]
        })
    
    return {
        "type": "bubble",
        "size": "giga",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1a1a2e",
            "paddingAll": "15px",
            "contents": [
                {"type": "text", "text": "☀️ 今日運勢", "weight": "bold", "size": "lg", "color": "#FFFFFF", "align": "center"},
                {"type": "text", "text": f"{fortune['date']} 星期{fortune['weekday']}", "size": "sm", "color": "#CCCCCC", "align": "center", "margin": "sm"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "20px",
            "contents": body_contents
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "15px",
            "backgroundColor": "#F5F5F5",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "button", "action": {"type": "message", "label": "🙏 問事占卜", "text": "問事"}, "style": "primary", "color": "#6B21A8", "flex": 1},
                        {"type": "button", "action": {"type": "message", "label": "🏠 回首頁", "text": "首頁"}, "style": "secondary", "flex": 1, "margin": "md"}
                    ]
                },
                {"type": "text", "text": "運勢根據易經梅花易數計算 • 每日 00:00 更新", "size": "xs", "color": "#AAAAAA", "align": "center", "margin": "md"}
            ]
        }
    }

def create_push_setting_flex():
    """每日運勢推送設定 - 簡化版，直接選時間"""
    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#6B21A8",
            "paddingAll": "15px",
            "contents": [
                {"type": "text", "text": "📬 每日運勢推送", "weight": "bold", "size": "lg", "color": "#FFFFFF", "align": "center"},
                {"type": "text", "text": "VIP 專屬功能", "size": "xs", "color": "#E0E0E0", "align": "center", "margin": "sm"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "每天自動推送您的專屬運勢", "size": "md", "align": "center", "color": "#333333"},
                {"type": "text", "text": "請選擇推送時間（台灣時間）", "size": "sm", "color": "#888888", "align": "center", "margin": "md"},
                {"type": "separator", "margin": "lg"},
                {"type": "text", "text": "🌅 早上", "size": "sm", "weight": "bold", "color": "#6B21A8", "margin": "lg"},
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "sm",
                    "contents": [
                        {"type": "button", "action": {"type": "message", "label": "6點", "text": "推送時間:06:00"}, "style": "secondary", "height": "sm", "flex": 1},
                        {"type": "button", "action": {"type": "message", "label": "7點", "text": "推送時間:07:00"}, "style": "secondary", "height": "sm", "flex": 1, "margin": "sm"},
                        {"type": "button", "action": {"type": "message", "label": "8點", "text": "推送時間:08:00"}, "style": "primary", "color": "#6B21A8", "height": "sm", "flex": 1, "margin": "sm"},
                        {"type": "button", "action": {"type": "message", "label": "9點", "text": "推送時間:09:00"}, "style": "secondary", "height": "sm", "flex": 1, "margin": "sm"}
                    ]
                },
                {"type": "text", "text": "🌙 晚上", "size": "sm", "weight": "bold", "color": "#6B21A8", "margin": "lg"},
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "sm",
                    "contents": [
                        {"type": "button", "action": {"type": "message", "label": "20點", "text": "推送時間:20:00"}, "style": "secondary", "height": "sm", "flex": 1},
                        {"type": "button", "action": {"type": "message", "label": "21點", "text": "推送時間:21:00"}, "style": "secondary", "height": "sm", "flex": 1, "margin": "sm"},
                        {"type": "button", "action": {"type": "message", "label": "22點", "text": "推送時間:22:00"}, "style": "secondary", "height": "sm", "flex": 1, "margin": "sm"}
                    ]
                },
                {"type": "separator", "margin": "lg"},
                {"type": "button", "action": {"type": "message", "label": "❌ 不需要推送", "text": "推送:關閉"}, "style": "secondary", "height": "sm", "margin": "lg"}
            ]
        }
    }

def create_push_time_flex():
    """每日運勢推送設定 - 選擇時間（已整合到 create_push_setting_flex）"""
    return create_push_setting_flex()

def create_push_complete_flex(push_time):
    """推送設定完成"""
    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#228B22",
            "paddingAll": "15px",
            "contents": [
                {"type": "text", "text": "✅ 設定完成", "weight": "bold", "size": "lg", "color": "#FFFFFF", "align": "center"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "每日運勢推送已開啟！", "size": "lg", "weight": "bold", "align": "center", "color": "#1a1a2e"},
                {"type": "text", "text": f"每天 {push_time} 為您推送", "size": "md", "color": "#228B22", "align": "center", "margin": "md"},
                {"type": "separator", "margin": "xl"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "xl",
                    "paddingAll": "12px",
                    "backgroundColor": "#F0FFF0",
                    "cornerRadius": "8px",
                    "contents": [
                        {"type": "text", "text": "💡 輸入「推送設定」可隨時修改", "size": "xs", "color": "#228B22", "align": "center"}
                    ]
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "15px",
            "backgroundColor": "#F5F5F5",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "button", "action": {"type": "message", "label": "🏠 回首頁", "text": "首頁"}, "style": "primary", "color": "#1a1a2e", "flex": 1}
                    ]
                }
            ]
        }
    }

def create_push_status_flex(settings):
    """推送設定狀態"""
    if settings and settings['enabled']:
        status_text = f"✅ 已開啟（每天 {settings['time']}）"
        status_color = "#228B22"
    else:
        status_text = "❌ 未開啟"
        status_color = "#999999"
    
    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#B8860B",
            "paddingAll": "15px",
            "contents": [
                {"type": "text", "text": "📬 推送設定", "weight": "bold", "size": "lg", "color": "#FFFFFF", "align": "center"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "每日運勢推送狀態", "size": "md", "weight": "bold", "align": "center", "color": "#1a1a2e"},
                {"type": "text", "text": status_text, "size": "lg", "color": status_color, "align": "center", "margin": "md", "weight": "bold"},
                {"type": "separator", "margin": "xl"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "15px",
            "backgroundColor": "#F5F5F5",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "button", "action": {"type": "message", "label": "✅ 開啟/修改", "text": "推送:開啟"}, "style": "primary", "color": "#228B22", "flex": 1},
                        {"type": "button", "action": {"type": "message", "label": "❌ 關閉推送", "text": "推送:關閉"}, "style": "secondary", "flex": 1, "margin": "sm"}
                    ]
                }
            ]
        }
    }

# ============================================================
# LINE Bot 事件處理
# ============================================================
@app.route("/callback", methods=['POST'])
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
    user_id = event.source.user_id if hasattr(event.source, 'user_id') else None
    if user_id:
        get_user(user_id)
        # 開始用戶資料調查
        save_pending_profile(user_id, 'gender', None, None)
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[FlexMessage(alt_text="歡迎使用籟柏太極易占", contents=FlexContainer.from_dict(create_profile_gender_flex()))]
            )
        )

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    msg = event.message.text.strip()
    user_id = event.source.user_id if hasattr(event.source, 'user_id') else None
    
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        user = get_user(user_id)
        # VIP 判斷：is_premium=1 且未過期
        is_premium = False
        if user['is_premium'] == 1 and user['premium_expires_at']:
            try:
                expires_dt = datetime.fromisoformat(user['premium_expires_at'])
                now_dt = get_tw_now().replace(tzinfo=None)
                is_premium = expires_dt > now_dt
            except:
                is_premium = False
        user_profile = get_user_profile(user_id)
        
        # 檢查是否有待處理的問事
        pending = get_pending_status(user_id)
        
        # 檢查是否正在填寫用戶資料
        pending_profile = get_pending_profile(user_id)
        
        # 處理用戶資料輸入
        if msg.startswith('資料:'):
            parts = msg.split(':')
            if len(parts) >= 3:
                field = parts[1]
                value = parts[2]
                
                if field == '性別':
                    save_pending_profile(user_id, 'age', value, None)
                    api.reply_message(ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[FlexMessage(alt_text="年齡選擇", contents=FlexContainer.from_dict(create_profile_age_flex()))]
                    ))
                    return
                
                elif field == '年齡':
                    if pending_profile:
                        save_pending_profile(user_id, 'marital', pending_profile['gender'], value)
                    api.reply_message(ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[FlexMessage(alt_text="感情狀態選擇", contents=FlexContainer.from_dict(create_profile_marital_flex()))]
                    ))
                    return
                
                elif field == '婚姻':
                    if pending_profile:
                        # 轉換婚姻狀態值
                        marital_map = {'married': 'married', 'relationship': 'relationship', 'single': 'single', '不透露': 'single'}
                        marital_status = marital_map.get(value, 'single')
                        save_user_profile(user_id, pending_profile['gender'], pending_profile['age_range'], marital_status)
                        clear_pending_profile(user_id)
                    api.reply_message(ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[FlexMessage(alt_text="資料設定完成", contents=FlexContainer.from_dict(create_profile_complete_flex()))]
                    ))
                    return
        
        # 修改資料指令
        if msg in ['修改資料', '更新資料', '設定資料', '個人資料']:
            save_pending_profile(user_id, 'gender', None, None)
            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[FlexMessage(alt_text="性別選擇", contents=FlexContainer.from_dict(create_profile_gender_flex()))]
            ))
            return
        
        # 占卜指令 - 導向問事流程
        if msg in ['占卜', '卜卦', '問卦', '求卦', '占', '卜', '易占', '太極', '問事']:
            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[FlexMessage(alt_text="問事占卜", contents=FlexContainer.from_dict(create_ask_question_flex()))]
            ))
        
        # 問事分類選擇
        elif msg.startswith('問事:'):
            category_map = {
                '感情': 'love', '事業': 'career', '財運': 'wealth',
                '健康': 'health', '學業': 'study', '綜合': 'general'
            }
            cat_name = msg.replace('問事:', '')
            category = category_map.get(cat_name, 'general')
            save_pending_question(user_id, '__WAITING__', category)
            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[FlexMessage(alt_text=f"{cat_name}問事", contents=FlexContainer.from_dict(create_category_input_flex(category)))]
            ))
        
        # 快速問題按鈕點擊（格式：問題:分類:問題內容）
        elif msg.startswith('問題:'):
            parts = msg.split(':', 2)
            if len(parts) >= 3:
                category = parts[1]
                question = parts[2]
                
                can_do, remaining = can_divine(user_id)
                if not can_do:
                    api.reply_message(ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[FlexMessage(alt_text="今日次數已用完", contents=FlexContainer.from_dict(create_limit_reached_flex()))]
                    ))
                    return
                
                result = cast_yinyang_fish(user_id, question)
                increment_daily_usage(user_id)
                
                ai_interp = None
                if is_premium:
                    ai_interp = get_ai_interpretation(
                        result['hexagram']['name'],
                        result['hexagram']['code'],
                        question,
                        result['upper_trigram'],
                        result['lower_trigram'],
                        result['hexagram']
                    )
                
                save_divination_record(
                    user_id,
                    result['hexagram']['code'],
                    result['hexagram']['name'],
                    question,
                    category,
                    ai_interp,
                    result['crystal']['primary']['name'] if is_premium else None
                )
                
                _, remaining = can_divine(user_id)
                api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(
                        alt_text=f"占卜結果：{result['hexagram']['name']}",
                        contents=FlexContainer.from_dict(create_result_flex(result, remaining, is_premium, ai_interp, category, user_profile))
                    )]
                ))
        
        # 說明指令
        elif msg in ['說明', '幫助', 'help', '?', '？', '指令']:
            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[FlexMessage(alt_text="使用說明", contents=FlexContainer.from_dict(create_help_flex()))]
            ))
        
        # VIP 指令
        elif msg.upper() in ['VIP', '會員', '付費', '升級', '訂閱']:
            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[FlexMessage(alt_text="VIP 方案", contents=FlexContainer.from_dict(create_vip_flex()))]
            ))
        
        # VIP 狀態查詢（調試用）
        elif msg in ['VIP狀態', 'vip狀態', 'VIP状态']:
            user_data = get_user(user_id)
            expires = user_data.get('premium_expires_at', '未設定')
            is_vip = user_data.get('is_premium', 0)
            status_text = f"💎 VIP 狀態查詢\n\nis_premium: {is_vip}\n到期時間: {expires}\n\n"
            if is_vip == 1 and expires:
                try:
                    exp_dt = datetime.fromisoformat(expires)
                    now_dt = get_tw_now().replace(tzinfo=None)
                    if exp_dt > now_dt:
                        status_text += "✅ VIP 有效"
                    else:
                        status_text += "❌ VIP 已過期"
                except:
                    status_text += "⚠️ 日期格式異常"
            else:
                status_text += "❌ 非 VIP 會員"
            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=status_text)]
            ))
        
        # 管理員指令：設定 VIP（簡易版）
        elif msg in ['設定VIP', '設定vip', '啟用VIP', '啟用vip', 'setvip', 'SETVIP']:
            give_vip_bonus(user_id, 365)
            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="✅ VIP 已設定！\n有效期間：365 天")]
            ))
            return 'OK'
        
        # 管理員指令：設定 VIP（格式：管理員:VIP:天數）
        elif msg.startswith('管理員:VIP:') or msg.startswith('admin:vip:') or msg.startswith('管理員：VIP：') or msg.startswith('管理員:VIP：') or msg.startswith('管理員：VIP:'):
            # 統一替換中文冒號為英文冒號
            normalized_msg = msg.replace('：', ':')
            parts = normalized_msg.split(':')
            if len(parts) >= 3:
                try:
                    days = int(parts[2])
                    give_vip_bonus(user_id, days)
                    api.reply_message(ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=f"✅ VIP 已設定！\n有效期間：{days} 天")]
                    ))
                except:
                    api.reply_message(ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="❌ 格式錯誤，請使用：管理員:VIP:天數\n例如：管理員:VIP:365")]
                    ))
            return 'OK'
        
        # 次數查詢
        elif msg in ['次數', '剩餘', '額度']:
            _, remaining = can_divine(user_id)
            text = "💎 VIP 會員 - 無限占卜！" if remaining == -1 else f"📊 今日剩餘占卜次數：{remaining} / {FREE_DAILY_LIMIT}"
            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=text)]
            ))
        
        # 每日運勢
        elif msg in ['運勢', '今日運勢', '每日運勢', '今天運勢', '運氣']:
            fortune = get_daily_fortune(user_id, user_profile)
            push_settings = get_push_settings(user_id)
            
            # VIP 用戶第一次使用，詢問是否開啟推送
            if is_premium and push_settings is None:
                api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        FlexMessage(alt_text=f"今日運勢：{fortune['overall']['level']}", contents=FlexContainer.from_dict(create_daily_fortune_flex(fortune, is_premium))),
                        FlexMessage(alt_text="推送設定", contents=FlexContainer.from_dict(create_push_setting_flex()))
                    ]
                ))
            else:
                api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(alt_text=f"今日運勢：{fortune['overall']['level']}", contents=FlexContainer.from_dict(create_daily_fortune_flex(fortune, is_premium)))]
                ))
        
        # 簽到指令
        elif msg in ['簽到', '打卡', 'checkin']:
            status = get_check_in_status(user_id)
            if status['checked_today']:
                # 已簽到，顯示狀態
                api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(alt_text="今日已簽到", contents=FlexContainer.from_dict(create_check_in_flex(status)))]
                ))
            else:
                # 執行簽到
                result = do_check_in(user_id)
                status = get_check_in_status(user_id)
                api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(alt_text="簽到成功", contents=FlexContainer.from_dict(create_check_in_flex(status, result)))]
                ))
        
        # 推送設定指令（VIP 專屬）
        elif msg in ['推送設定', '推送', '通知設定']:
            if not is_premium:
                api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="📬 每日運勢推送是 VIP 專屬功能\n\n升級 VIP 即可享有：\n💎 每日自動推送運勢\n💎 無限次占卜\n💎 AI 深度解讀\n💎 水晶推薦\n\n輸入「VIP」了解詳情")]
                ))
            else:
                settings = get_push_settings(user_id)
                api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(alt_text="推送設定", contents=FlexContainer.from_dict(create_push_status_flex(settings)))]
                ))
        
        # 推送開啟（VIP 專屬）
        elif msg == '推送:開啟':
            if not is_premium:
                api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="📬 每日運勢推送是 VIP 專屬功能\n\n輸入「VIP」了解詳情")]
                ))
            else:
                api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(alt_text="選擇推送時間", contents=FlexContainer.from_dict(create_push_time_flex()))]
                ))
        
        # 推送關閉
        elif msg == '推送:關閉':
            save_push_settings(user_id, False)
            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="📬 每日運勢推送已關閉\n\n如需重新開啟，請輸入「推送設定」")]
            ))
        
        # 推送時間選擇（VIP 專屬）
        elif msg.startswith('推送時間:'):
            if not is_premium:
                api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="📬 每日運勢推送是 VIP 專屬功能\n\n輸入「VIP」了解詳情")]
                ))
            else:
                push_time = msg.replace('推送時間:', '')
                save_push_settings(user_id, True, push_time)
                api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(alt_text="設定完成", contents=FlexContainer.from_dict(create_push_complete_flex(push_time)))]
                ))
        
        # 首頁指令
        elif msg in ['首頁', '主頁', '回首頁', 'home', '主選單', '選單']:
            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[FlexMessage(alt_text="籟柏太極易占", contents=FlexContainer.from_dict(create_welcome_flex()))]
            ))
        
        # 紀錄查詢
        elif msg in ['紀錄', '歷史', '記錄']:
            records = get_user_history(user_id)
            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[FlexMessage(alt_text="占卜紀錄", contents=FlexContainer.from_dict(create_history_flex(records)))]
            ))
        
        # 處理問事輸入（已選擇分類，等待輸入問題）
        elif pending and pending['question'] == '__WAITING__':
            category = pending['category']
            question = msg
            
            # 清除並儲存完整問題
            conn = sqlite3.connect('yizhan.db')
            c = conn.cursor()
            c.execute('DELETE FROM pending_questions WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            
            can_do, remaining = can_divine(user_id)
            if not can_do:
                api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(alt_text="今日次數已用完", contents=FlexContainer.from_dict(create_limit_reached_flex()))]
                ))
                return
            
            result = cast_yinyang_fish(user_id, question)
            increment_daily_usage(user_id)
            
            ai_interp = None
            if is_premium:
                ai_interp = get_ai_interpretation(
                    result['hexagram']['name'],
                    result['hexagram']['code'],
                    question,
                    result['upper_trigram'],
                    result['lower_trigram'],
                    result['hexagram']
                )
            
            save_divination_record(
                user_id,
                result['hexagram']['code'],
                result['hexagram']['name'],
                question,
                category,
                ai_interp,
                result['crystal']['primary']['name'] if is_premium else None
            )
            
            _, remaining = can_divine(user_id)
            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[FlexMessage(
                    alt_text=f"占卜結果：{result['hexagram']['name']}",
                    contents=FlexContainer.from_dict(create_result_flex(result, remaining, is_premium, ai_interp, category, user_profile))
                )]
            ))
        
        # 其他訊息
        else:
            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="☯ 太極陰陽魚易占 ☯\n\n輸入「問事」開始問事占卜\n輸入「運勢」查看今日運勢\n輸入「簽到」每日簽到\n輸入「說明」查看使用方式\n輸入「VIP」了解進階功能\n\n🙏 心誠則靈")]
            ))

@app.route("/health", methods=['GET'])
def health_check():
    return {"status": "healthy", "service": "laibai-taiji-yizhan", "version": "5.8"}

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5003)), debug=True)
