import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id
import sqlite3
import random
import datetime
import threading
import os
import sys
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# ==================== КОНФИГУРАЦИЯ ====================
TOKEN = "vk1.a.cgsYo5dMWn_d6c51WiuJZxjwDytf5grd5uhcyPWOC4ny5VNcDj1097PnVZfukL2jchzz9t1E4YFy1k9tdUlVgk_Z0WVoYYr-3N4GjWpsR0SFoatWE0bNef7uPMNex2e8L1Roh89F9ibEg7y5nnqoVbLruWDsCk2Q3prug_1iWrRdIkKOSkFzK_hcqvinmHpVEFos4AGzCTZJRGlE6tNVyA"
GROUP_ID = "235020203"
OWNER_ID = 1021905669

# Подключение к VK
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

# ==================== БАЗА ДАННЫХ ====================
conn = sqlite3.connect('lime_manager.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    coins INTEGER DEFAULT 500,
    warns INTEGER DEFAULT 0,
    last_bonus TEXT,
    join_date TEXT,
    nickname TEXT DEFAULT NULL
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS chat_settings (
    chat_id INTEGER PRIMARY KEY,
    bot_active INTEGER DEFAULT 0,
    timeout_active INTEGER DEFAULT 0,
    exclude_invited INTEGER DEFAULT 1,
    exclude_on_leave INTEGER DEFAULT 1,
    remove_rights_on_leave INTEGER DEFAULT 0,
    block_global_tags INTEGER DEFAULT 0,
    block_stickers INTEGER DEFAULT 0,
    block_invite_link INTEGER DEFAULT 0
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS admins (
    chat_id INTEGER,
    user_id INTEGER,
    role TEXT DEFAULT 'admin',
    granted_by INTEGER,
    granted_date TEXT,
    PRIMARY KEY (chat_id, user_id)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS punishments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER,
    user_id INTEGER,
    admin_id INTEGER,
    type TEXT,
    reason TEXT,
    date TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS duel_stats (
    user_id INTEGER PRIMARY KEY,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    draws INTEGER DEFAULT 0
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS nicknames (
    chat_id INTEGER,
    user_id INTEGER,
    nickname TEXT,
    set_by INTEGER,
    set_date TEXT,
    PRIMARY KEY (chat_id, user_id)
)
''')

conn.commit()
print("✅ База данных создана!")

# ==================== КЛАСС БОТА ====================
class LimeManagerBot:
    def __init__(self):
        self.active_duels = {}
        print("🤖 Бот LIME MANAGER запущен!")
        print(f"👑 Создатель: {OWNER_ID}")
    
    def send_message(self, chat_id, message):
        try:
            vk.messages.send(
                peer_id=chat_id,
                random_id=get_random_id(),
                message=message
            )
        except Exception as e:
            print(f"Ошибка отправки: {e}")
    
    def run(self):
        print("✅ Ожидание сообщений...")
        for event in longpoll.listen():
            try:
                if event.type == VkBotEventType.MESSAGE_NEW:
                    msg = event.object.message
                    chat_id = msg['peer_id']
                    user_id = msg['from_id']
                    text = msg['text'].strip()
                    
                    if text and user_id > 0:
                        self.send_message(chat_id, f"Привет! Ты написал: {text}")
                        print(f"Сообщение от {user_id}: {text}")
            
            except Exception as e:
                print(f"Ошибка: {e}")

# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    bot = LimeManagerBot()
    bot.run()
