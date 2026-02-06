# -*- coding: utf-8 -*-
"""
籟柏太極易占 - 時辰資料
"""

from datetime import datetime
import pytz

SHICHEN = {
    '子時': {'hours': (23, 1), 'element': '水', 'direction': '北', 'description': '夜深人靜，宜靜思'},
    '丑時': {'hours': (1, 3), 'element': '土', 'direction': '東北', 'description': '萬物休息，宜養精蓄銳'},
    '寅時': {'hours': (3, 5), 'element': '木', 'direction': '東北', 'description': '陽氣初生，新的開始'},
    '卯時': {'hours': (5, 7), 'element': '木', 'direction': '東', 'description': '日出東方，萬物甦醒'},
    '辰時': {'hours': (7, 9), 'element': '土', 'direction': '東南', 'description': '食時，一日之計'},
    '巳時': {'hours': (9, 11), 'element': '火', 'direction': '東南', 'description': '日正當中，精力充沛'},
    '午時': {'hours': (11, 13), 'element': '火', 'direction': '南', 'description': '日中，陽氣最盛'},
    '未時': {'hours': (13, 15), 'element': '土', 'direction': '西南', 'description': '日昃，宜休息'},
    '申時': {'hours': (15, 17), 'element': '金', 'direction': '西南', 'description': '哺時，事業運佳'},
    '酉時': {'hours': (17, 19), 'element': '金', 'direction': '西', 'description': '日入，宜社交'},
    '戌時': {'hours': (19, 21), 'element': '土', 'direction': '西北', 'description': '黃昏，宜放鬆'},
    '亥時': {'hours': (21, 23), 'element': '水', 'direction': '西北', 'description': '人定，宜沉思'},
}

WUXING_RELATIONS = {
    '金': {'生': '水', '被生': '土', '剋': '木', '被剋': '火'},
    '木': {'生': '火', '被生': '水', '剋': '土', '被剋': '金'},
    '水': {'生': '木', '被生': '金', '剋': '火', '被剋': '土'},
    '火': {'生': '土', '被生': '木', '剋': '金', '被剋': '水'},
    '土': {'生': '金', '被生': '火', '剋': '水', '被剋': '木'},
}

def get_current_shichen(tz_name='Asia/Taipei') -> dict:
    tz = pytz.timezone(tz_name)
    now = datetime.now(tz)
    hour = now.hour
    for name, info in SHICHEN.items():
        start, end = info['hours']
        if start > end:
            if hour >= start or hour < end:
                return {'name': name, **info, 'current_hour': hour}
        else:
            if start <= hour < end:
                return {'name': name, **info, 'current_hour': hour}
    return None

def get_shichen_bonus(shichen_element: str, hexagram_element: str) -> dict:
    if shichen_element == hexagram_element:
        return {'type': '比和', 'bonus': 10, 'description': f'時辰與卦象同屬{shichen_element}，運勢加強！'}
    relation = WUXING_RELATIONS.get(shichen_element, {})
    if relation.get('生') == hexagram_element:
        return {'type': '相生', 'bonus': 5, 'description': f'{shichen_element}生{hexagram_element}，事半功倍。'}
    if relation.get('被生') == hexagram_element:
        return {'type': '相生', 'bonus': 8, 'description': f'{hexagram_element}生{shichen_element}，運勢提升。'}
    if relation.get('剋') == hexagram_element:
        return {'type': '相剋', 'bonus': -5, 'description': f'{shichen_element}剋{hexagram_element}，宜謹慎。'}
    if relation.get('被剋') == hexagram_element:
        return {'type': '相剋', 'bonus': -8, 'description': f'{hexagram_element}剋{shichen_element}，建議擇時再行。'}
    return {'type': '無', 'bonus': 0, 'description': '時辰與卦象無特殊關係。'}

def format_shichen_tip(shichen: dict, hexagram_element: str) -> str:
    bonus = get_shichen_bonus(shichen['element'], hexagram_element)
    return f"""⏰ 時辰：{shichen['name']}（{shichen['element']}）
📍 方位：{shichen['direction']}
💫 {bonus['description']}"""
