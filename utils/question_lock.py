# -*- coding: utf-8 -*-
"""
籟柏太極易占 - 問事鎖定機制
"""

import hashlib
import re
from datetime import datetime
import pytz

SYNONYMS = {
    '老公': '伴侶', '老婆': '伴侶', '男友': '伴侶', '女友': '伴侶',
    '男朋友': '伴侶', '女朋友': '伴侶', '對象': '伴侶', '另一半': '伴侶',
    '工作': '事業', '職場': '事業', '公司': '事業', '上班': '事業',
    '老闆': '主管', '上司': '主管', '領導': '主管',
    '錢': '財', '財運': '財', '財富': '財',
    '股票': '投資', '基金': '投資', '理財': '投資',
    '好嗎': '', '好不好': '', '可以嗎': '', '會嗎': '', '嗎': '',
    '請問': '', '想問': '', '想知道': '',
}

def normalize_question(question: str) -> str:
    if not question:
        return ''
    text = question.lower()
    text = re.sub(r'[，。！？、；：""''「」【】（）\(\)\[\]\{\}\s]+', '', text)
    for old, new in SYNONYMS.items():
        text = text.replace(old, new)
    return text

def generate_question_hash(user_id: str, question: str, date_str: str = None) -> str:
    if date_str is None:
        tz = pytz.timezone('Asia/Taipei')
        date_str = datetime.now(tz).strftime('%Y-%m-%d')
    normalized = normalize_question(question)
    combined = f"{user_id}:{normalized}:{date_str}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()

def get_question_category(question: str) -> str:
    text = question.lower()
    if any(kw in text for kw in ['感情', '伴侶', '喜歡', '愛', '結婚', '婚姻', '桃花', '告白', '分手']):
        return 'love'
    if any(kw in text for kw in ['工作', '事業', '職場', '公司', '升遷', '面試', '離職']):
        return 'career'
    if any(kw in text for kw in ['錢', '財', '投資', '股票', '賺', '收入', '創業', '生意']):
        return 'wealth'
    if any(kw in text for kw in ['健康', '身體', '生病', '手術', '看病', '懷孕']):
        return 'health'
    if any(kw in text for kw in ['考試', '學業', '讀書', '學校', '成績', '證照']):
        return 'study'
    if any(kw in text for kw in ['買房', '搬家', '租房', '房子', '置產']):
        return 'property'
    if any(kw in text for kw in ['合作', '合夥', '談判', '簽約']):
        return 'cooperation'
    return 'other'

class QuestionLock:
    def __init__(self, db_connection):
        self.conn = db_connection

    def check_lock(self, user_id: str, question: str) -> dict:
        question_hash = generate_question_hash(user_id, question)
        cursor = self.conn.execute(
            'SELECT hexagram_code, lock_date FROM question_locks WHERE user_id = ? AND question_hash = ?',
            (user_id, question_hash))
        row = cursor.fetchone()
        if row:
            return {'locked': True, 'hexagram_code': row[0], 'lock_date': row[1]}
        return {'locked': False}

    def create_lock(self, user_id: str, question: str, hexagram_code: str) -> bool:
        tz = pytz.timezone('Asia/Taipei')
        date_str = datetime.now(tz).strftime('%Y-%m-%d')
        question_hash = generate_question_hash(user_id, question, date_str)
        try:
            self.conn.execute(
                'INSERT OR REPLACE INTO question_locks (user_id, question_hash, lock_date, hexagram_code) VALUES (?, ?, ?, ?)',
                (user_id, question_hash, date_str, hexagram_code))
            self.conn.commit()
            return True
        except:
            return False
