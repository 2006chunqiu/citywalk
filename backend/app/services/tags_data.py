"""兴趣标签与分类码映射。

开发阶段先用常量；正式实现应改为读取 tag_mapping 表（可热更新，不用发版），
见 PRD FR-02-03。
"""
TAGS = [
    {"tagId": "art", "name": "文艺", "desc": "书店、画廊、独立咖啡馆",
     "typecodes": ["140400", "140300", "050500"], "keywords": ["书店", "画廊", "独立咖啡"]},
    {"tagId": "park", "name": "公园绿地", "desc": "绿道、湿地、湖滨草坪",
     "typecodes": ["110100", "110200"], "keywords": ["绿道", "湿地", "湖滨"]},
    {"tagId": "history", "name": "历史建筑", "desc": "旧址、故居、里份、老建筑",
     "typecodes": ["110200", "140200"], "keywords": ["旧址", "故居", "里份"]},
    {"tagId": "food", "name": "美食小吃", "desc": "热干面、豆皮、过早、夜市",
     "typecodes": ["050100", "050300", "050700"], "keywords": ["热干面", "豆皮", "小吃"]},
    {"tagId": "river", "name": "江景滨江", "desc": "江滩、码头、轮渡、观景平台",
     "typecodes": ["110200"], "keywords": ["江滩", "码头", "轮渡"]},
    {"tagId": "local", "name": "市井烟火", "desc": "菜市场、老街、便民市场",
     "typecodes": ["120000", "070000"], "keywords": ["菜市场", "老街", "里份"]},
    {"tagId": "photo", "name": "拍照出片", "desc": "网红、打卡、天台、涂鸦",
     "typecodes": [], "keywords": ["打卡", "天台", "涂鸦"]},
    {"tagId": "family", "name": "亲子友好", "desc": "亲子、儿童、游乐、科普",
     "typecodes": ["110100", "140500", "140100"], "keywords": ["亲子", "儿童", "科普"]},
]

TAG_INDEX = {t["tagId"]: t for t in TAGS}
