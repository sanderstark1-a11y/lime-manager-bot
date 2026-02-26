import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id
import sqlite3
import random
import datetime
import time
import threading
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
import re

# ==================== КОНФИГУРАЦИЯ ====================
TOKEN = "vk1.a.cgsYo5dMWn_d6c51WiuJZxjwDytf5grd5uhcyPWOC4ny5VNcDj1097PnVZfukL2jchzz9t1E4YFy1k9tdUlVgk_Z0WVoYYr-3N4GjWpsR0SFoatWE0bNef7uPMNex2e8L1Roh89F9ibEg7y5nnqoVbLruWDsCk2Q3prug_1iWrRdIkKOSkFzK_hcqvinmHpVEFos4AGzCTZJRGlE6tNVyA"
GROUP_ID = "235020203"
OWNER_ID = 1021905669  # Твой ID ВКонтакте

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
print("✅ База данных успешно создана!")

# ==================== КЛАССЫ ====================
@dataclass
class User:
    user_id: int
    first_name: str
    last_name: str
    username: str = ""
    coins: int = 500
    warns: int = 0

class ChatManager:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self._init_settings()
    
    def _init_settings(self):
        cursor.execute('INSERT OR IGNORE INTO chat_settings (chat_id) VALUES (?)', (self.chat_id,))
        conn.commit()
    
    def get_setting(self, key):
        cursor.execute(f'SELECT {key} FROM chat_settings WHERE chat_id = ?', (self.chat_id,))
        result = cursor.fetchone()
        return result[0] if result else 0
    
    def set_setting(self, key, value):
        cursor.execute(f'UPDATE chat_settings SET {key} = ? WHERE chat_id = ?', (int(value), self.chat_id))
        conn.commit()
    
    def is_bot_active(self):
        return self.get_setting('bot_active') == 1
    
    def is_timeout(self):
        return self.get_setting('timeout_active') == 1

class UserManager:
    @staticmethod
    def get_user(user_id):
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return cursor.fetchone()
    
    @staticmethod
    def create_user(user_id, first_name, last_name, username=''):
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, join_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
    
    @staticmethod
    def add_coins(user_id, amount):
        cursor.execute('UPDATE users SET coins = coins + ? WHERE user_id = ?', (amount, user_id))
        conn.commit()
    
    @staticmethod
    def remove_coins(user_id, amount):
        cursor.execute('UPDATE users SET coins = coins - ? WHERE user_id = ?', (amount, user_id))
        conn.commit()
    
    @staticmethod
    def get_coins(user_id):
        cursor.execute('SELECT coins FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 500
    
    @staticmethod
    def add_warn(user_id, chat_id, admin_id, reason=''):
        cursor.execute('UPDATE users SET warns = warns + 1 WHERE user_id = ?', (user_id,))
        cursor.execute('''
            INSERT INTO punishments (chat_id, user_id, admin_id, type, reason, date)
            VALUES (?, ?, ?, 'warn', ?, ?)
        ''', (chat_id, user_id, admin_id, reason, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        
        cursor.execute('SELECT warns FROM users WHERE user_id = ?', (user_id,))
        warns = cursor.fetchone()
        if warns and warns[0] >= 3:
            return True
        return False
    
    @staticmethod
    def remove_warn(user_id):
        cursor.execute('UPDATE users SET warns = warns - 1 WHERE user_id = ? AND warns > 0', (user_id,))
        conn.commit()
    
    @staticmethod
    def get_warns(user_id):
        cursor.execute('SELECT warns FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0
    
    @staticmethod
    def set_nickname(chat_id, user_id, nickname, set_by):
        cursor.execute('''
            INSERT OR REPLACE INTO nicknames (chat_id, user_id, nickname, set_by, set_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (chat_id, user_id, nickname, set_by, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
    
    @staticmethod
    def get_nickname(chat_id, user_id):
        cursor.execute('SELECT nickname FROM nicknames WHERE chat_id = ? AND user_id = ?', (chat_id, user_id))
        result = cursor.fetchone()
        return result[0] if result else None
    
    @staticmethod
    def remove_nickname(chat_id, user_id):
        cursor.execute('DELETE FROM nicknames WHERE chat_id = ? AND user_id = ?', (chat_id, user_id))
        conn.commit()
    
    @staticmethod
    def get_all_nicknames(chat_id):
        cursor.execute('''
            SELECT user_id, nickname, set_by, set_date 
            FROM nicknames 
            WHERE chat_id = ?
            ORDER BY set_date DESC
        ''', (chat_id,))
        return cursor.fetchall()

class RoleManager:
    @staticmethod
    def get_user_role(chat_id, user_id):
        if user_id == OWNER_ID:
            return 'owner'
        
        cursor.execute('SELECT role FROM admins WHERE chat_id = ? AND user_id = ?', (chat_id, user_id))
        result = cursor.fetchone()
        return result[0] if result else 'user'
    
    @staticmethod
    def add_admin(chat_id, user_id, granted_by, role='admin'):
        cursor.execute('''
            INSERT OR REPLACE INTO admins (chat_id, user_id, role, granted_by, granted_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (chat_id, user_id, role, granted_by, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
    
    @staticmethod
    def remove_admin(chat_id, user_id):
        cursor.execute('DELETE FROM admins WHERE chat_id = ? AND user_id = ?', (chat_id, user_id))
        conn.commit()
    
    @staticmethod
    def is_admin(chat_id, user_id):
        return RoleManager.get_user_role(chat_id, user_id) in ['admin', 'owner']
    
    @staticmethod
    def is_owner(chat_id, user_id):
        return user_id == OWNER_ID or RoleManager.get_user_role(chat_id, user_id) == 'owner'
    
    @staticmethod
    def can_target(chat_id, admin_id, target_id):
        # Админ не может наказывать создателя
        if target_id == OWNER_ID:
            return False
        # Админ не может наказывать другого админа (кроме создателя)
        if RoleManager.is_admin(chat_id, target_id) and not RoleManager.is_owner(chat_id, admin_id):
            return False
        return True

# ==================== ИГРЫ ====================
class GameManager:
    @staticmethod
    def rock_paper_scissors(choice1, choice2):
        rules = {
            'камень': {'камень': 'ничья', 'ножницы': 'победа', 'бумага': 'поражение'},
            'ножницы': {'камень': 'поражение', 'ножницы': 'ничья', 'бумага': 'победа'},
            'бумага': {'камень': 'победа', 'ножницы': 'поражение', 'бумага': 'ничья'}
        }
        return rules[choice1][choice2]
    
    @staticmethod
    def process_duel(chat_id, user1_id, user2_id, bet):
        coins1 = UserManager.get_coins(user1_id)
        coins2 = UserManager.get_coins(user2_id)
        
        if coins1 < bet or coins2 < bet:
            return None, "У одного из участников недостаточно монет!"
        
        winner = random.choice([user1_id, user2_id])
        loser = user2_id if winner == user1_id else user1_id
        
        UserManager.remove_coins(loser, bet)
        UserManager.add_coins(winner, bet)
        
        cursor.execute('INSERT OR IGNORE INTO duel_stats (user_id) VALUES (?)', (winner,))
        cursor.execute('INSERT OR IGNORE INTO duel_stats (user_id) VALUES (?)', (loser,))
        cursor.execute('UPDATE duel_stats SET wins = wins + 1 WHERE user_id = ?', (winner,))
        cursor.execute('UPDATE duel_stats SET losses = losses + 1 WHERE user_id = ?', (loser,))
        conn.commit()
        
        return winner, None
    
    @staticmethod
    def eight_ball():
        answers = [
            "Да", "Нет", "Возможно", "Конечно", "Никогда", 
            "Скорее всего", "Вряд ли", "Без сомнения", 
            "Спроси позже", "Лучше не знать", "Да, но будь осторожен",
            "Нет, это плохая идея", "Мой ответ - да", "Мой ответ - нет",
            "Звёзды говорят да", "Звёзды говорят нет", "Я не уверен",
            "Это точно", "Это маловероятно", "Решай сам"
        ]
        return random.choice(answers)

# ==================== ОСНОВНОЙ БОТ ====================
class LimeManagerBot:
    def __init__(self):
        self.active_duels = {}
        self.timeout_chats = set()
    
    def send_message(self, chat_id, message, attachment=None):
        try:
            vk.messages.send(
                peer_id=chat_id,
                random_id=get_random_id(),
                message=message,
                attachment=attachment
            )
        except Exception as e:
            print(f"Ошибка отправки сообщения: {e}")
    
    def check_permission(self, chat_id, user_id, required_role):
        role = RoleManager.get_user_role(chat_id, user_id)
        roles_order = {'user': 0, 'admin': 1, 'owner': 2}
        return roles_order[role] >= roles_order[required_role]
    
    def get_role_emoji(self, chat_id, user_id):
        role = RoleManager.get_user_role(chat_id, user_id)
        if role == 'owner':
            return '👑'
        elif role == 'admin':
            return '🛡️'
        else:
            return '👤'
    
    def handle_message(self, event):
        try:
            msg = event.object.message
            chat_id = msg['peer_id']
            user_id = msg['from_id']
            text = msg['text'].strip()
            
            if not text or user_id < 0:
                return
            
            try:
                user_info = vk.users.get(user_ids=user_id, fields='first_name,last_name')[0]
                first_name = user_info['first_name']
                last_name = user_info['last_name']
            except:
                first_name = "Пользователь"
                last_name = ""
            
            UserManager.create_user(user_id, first_name, last_name)
            
            chat_manager = ChatManager(chat_id)
            
            if chat_manager.is_timeout() and not self.check_permission(chat_id, user_id, 'admin'):
                try:
                    vk.messages.delete(
                        message_ids=msg['id'],
                        delete_for_all=1
                    )
                except:
                    pass
                return
            
            if not chat_manager.is_bot_active():
                if text.lower() == '/start':
                    if self.check_permission(chat_id, user_id, 'admin'):
                        chat_manager.set_setting('bot_active', 1)
                        self.send_message(chat_id, f"✅ Бот LIME MANAGER успешно запущен!\n👤 Администратор: {first_name}\n💬 Чат готов к работе!\n\nℹ️ Используйте /help для списка команд.")
                    else:
                        self.send_message(chat_id, f"❌ {first_name}, запустить бота может только администратор или создатель!")
                return
            
            self.process_command(chat_id, user_id, text, first_name, msg)
            
        except Exception as e:
            print(f"Ошибка в handle_message: {e}")
    
    def process_command(self, chat_id, user_id, text, first_name, msg):
        try:
            args = text.split()
            command = args[0].lower()
            
            # ========== КОМАНДЫ УЧАСТНИКА ==========
            if command == '/help':
                role = RoleManager.get_user_role(chat_id, user_id)
                help_text = "🌟 LIME MANAGER - Помощь 🌟\n\n"
                
                help_text += "👤 Команды участника:\n"
                help_text += "• /stats – 📊 Твоя статистика\n"
                help_text += "• /help – 📋 Это меню\n"
                help_text += "• /duel [@user] [сумма] – ⚔️ Сразиться с участником\n"
                help_text += "• /game [камень/ножницы/бумага] – 🎮 Игра с ботом\n"
                help_text += "• /id – 🆔 Информация о профиле\n"
                help_text += "• /bonus – 🎁 Ежедневный бонус (500 монет)\n"
                help_text += "• /transfer [@user] [сумма] – 💸 Передать монеты\n"
                help_text += "• /top – 🏆 Топ игроков по монетам\n"
                help_text += "• /8ball [вопрос] – 🎱 Ответ на вопрос\n\n"
                
                if role in ['admin', 'owner']:
                    help_text += "👮 Команды администратора:\n"
                    help_text += "• /kick [@user] – 👢 Исключить участника\n"
                    help_text += "• /check [@user] – 🔍 Проверить наказания\n"
                    help_text += "• /ban [@user] – 🔨 Забанить\n"
                    help_text += "• /unban [@user] – 🔓 Разбанить\n"
                    help_text += "• /timeout – 🔇 Включить тишину\n"
                    help_text += "• /untimeout – 🔊 Выключить тишину\n"
                    help_text += "• /warn [@user] [причина] – ⚠️ Выдать предупреждение\n"
                    help_text += "• /unwarn [@user] – ✅ Снять предупреждение\n"
                    help_text += "• /setnick [@user] [ник] – 📝 Установить ник\n"
                    help_text += "• /rnick [@user] – 🗑️ Удалить ник\n"
                    help_text += "• /nlist – 📋 Список ников\n\n"
                
                if role == 'owner':
                    help_text += "👑 Команды создателя:\n"
                    help_text += "• /giveowner [@user] – 👑 Передать создателя\n"
                    help_text += "• /giveadm [@user] – 🛡️ Дать администратора\n"
                    help_text += "• /settings – ⚙️ Настройки беседы\n"
                
                self.send_message(chat_id, help_text)
            
            elif command == '/stats':
                user_data = UserManager.get_user(user_id)
                if user_data:
                    coins = user_data[4]
                    warns = user_data[5]
                    last_bonus = user_data[6]
                    nickname = UserManager.get_nickname(chat_id, user_id)
                    
                    role_emoji = self.get_role_emoji(chat_id, user_id)
                    role_name = RoleManager.get_user_role(chat_id, user_id)
                    role_text = f"{role_emoji} {role_name.capitalize()}"
                    
                    cursor.execute('SELECT wins, losses, draws FROM duel_stats WHERE user_id = ?', (user_id,))
                    duel_stats = cursor.fetchone()
                    if not duel_stats:
                        duel_stats = (0, 0, 0)
                    
                    stats_text = f"📊 Статистика {first_name}\n"
                    if nickname:
                        stats_text += f"📝 Ник: {nickname}\n"
                    stats_text += f"👑 Должность: {role_text}\n"
                    stats_text += f"💰 Монеты: {coins}\n"
                    stats_text += f"⚠️ Предупреждения: {warns}/3\n"
                    stats_text += f"⚔️ Дуэли: Побед: {duel_stats[0]} | Поражений: {duel_stats[1]}\n"
                    stats_text += f"🎮 Ничьи: {duel_stats[2]}\n"
                    stats_text += f"📅 Последний бонус: {last_bonus or 'Никогда'}"
                    
                    self.send_message(chat_id, stats_text)
            
            elif command == '/8ball':
                if len(args) < 2:
                    self.send_message(chat_id, "❌ Задай вопрос! Например: /8ball Сегодня будет дождь?")
                    return
                
                question = ' '.join(args[1:])
                answer = GameManager.eight_ball()
                
                ball_text = f"🎱 Вопрос: {question}\n"
                ball_text += f"💬 Ответ: {answer}"
                
                self.send_message(chat_id, ball_text)
            
            elif command == '/id':
                try:
                    user_info = vk.users.get(user_ids=user_id, fields='last_seen')[0]
                    last_seen = user_info.get('last_seen', {}).get('time', 0)
                    if last_seen:
                        last_seen_str = datetime.datetime.fromtimestamp(last_seen).strftime('%d.%m.%Y %H:%M')
                    else:
                        last_seen_str = 'недавно'
                    
                    id_text = f"🆔 Информация о профиле\n\n"
                    id_text += f"👤 Имя: {first_name}\n"
                    id_text += f"🔢 ID: {user_id}\n"
                    id_text += f"🕒 Последняя активность: {last_seen_str}"
                    
                    self.send_message(chat_id, id_text)
                except:
                    self.send_message(chat_id, f"🆔 Ваш ID: {user_id}")
            
            elif command == '/bonus':
                user_data = UserManager.get_user(user_id)
                if user_data:
                    last_bonus = user_data[6]
                    
                    if last_bonus:
                        try:
                            last_bonus_date = datetime.datetime.strptime(last_bonus, '%Y-%m-%d %H:%M:%S')
                            now = datetime.datetime.now()
                            if (now - last_bonus_date).days < 1:
                                next_bonus = last_bonus_date + datetime.timedelta(days=1)
                                time_left = next_bonus - now
                                hours = time_left.seconds // 3600
                                minutes = (time_left.seconds % 3600) // 60
                                self.send_message(chat_id, f"❌ {first_name}, следующий бонус будет доступен через {hours}ч {minutes}мин!")
                                return
                        except:
                            pass
                    
                    UserManager.add_coins(user_id, 500)
                    cursor.execute('UPDATE users SET last_bonus = ? WHERE user_id = ?', 
                                 (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id))
                    conn.commit()
                    self.send_message(chat_id, f"🎁 +500 монет!\n💰 Баланс: {UserManager.get_coins(user_id)} монет")
            
            elif command == '/top':
                cursor.execute('SELECT user_id, coins FROM users ORDER BY coins DESC LIMIT 10')
                top_users = cursor.fetchall()
                
                if top_users:
                    top_text = "🏆 ТОП-10 БОГАЧЕЙ 🏆\n\n"
                    for i, (uid, coins) in enumerate(top_users, 1):
                        try:
                            user_info = vk.users.get(user_ids=uid)[0]
                            name = user_info['first_name']
                            nickname = UserManager.get_nickname(chat_id, uid)
                            if nickname:
                                name = f"{name} ({nickname})"
                        except:
                            name = f"Пользователь {uid}"
                        top_text += f"{i}. {name} – {coins} 💰\n"
                    
                    self.send_message(chat_id, top_text)
                else:
                    self.send_message(chat_id, "📊 Пока нет данных для топа")
            
            elif command == '/game':
                if len(args) < 2:
                    self.send_message(chat_id, "❌ Использование: /game [камень/ножницы/бумага]")
                    return
                
                user_choice = args[1].lower()
                if user_choice not in ['камень', 'ножницы', 'бумага']:
                    self.send_message(chat_id, "❌ Выберите: камень, ножницы или бумага")
                    return
                
                bot_choice = random.choice(['камень', 'ножницы', 'бумага'])
                result = GameManager.rock_paper_scissors(user_choice, bot_choice)
                
                game_text = f"🎮 Игра: {first_name} vs Бот\n"
                game_text += f"👤 Ваш выбор: {user_choice}\n"
                game_text += f"🤖 Выбор бота: {bot_choice}\n\n"
                
                if result == 'победа':
                    game_text += "✅ Вы выиграли! +50 монет"
                    UserManager.add_coins(user_id, 50)
                elif result == 'поражение':
                    game_text += "❌ Вы проиграли! -20 монет"
                    UserManager.remove_coins(user_id, 20)
                else:
                    game_text += "🤝 Ничья!"
                
                self.send_message(chat_id, game_text)
            
            elif command == '/duel':
                if len(args) < 3:
                    self.send_message(chat_id, "❌ Использование: /duel [@user] [сумма]")
                    return
                
                try:
                    target_id = self.extract_user_id(args[1])
                    if not target_id:
                        self.send_message(chat_id, "❌ Пользователь не найден!")
                        return
                    
                    bet = int(args[2])
                    
                    if target_id == user_id:
                        self.send_message(chat_id, "❌ Нельзя дуэлировать с самим собой!")
                        return
                    
                    if bet < 10:
                        self.send_message(chat_id, "❌ Минимальная ставка: 10 монет")
                        return
                    
                    if chat_id in self.active_duels:
                        self.send_message(chat_id, "❌ В этом чате уже идет дуэль!")
                        return
                    
                    if UserManager.get_coins(user_id) < bet:
                        self.send_message(chat_id, f"❌ {first_name}, у вас недостаточно монет!")
                        return
                    
                    try:
                        target_info = vk.users.get(user_ids=target_id)[0]
                        target_name = target_info['first_name']
                    except:
                        target_name = f"Пользователь {target_id}"
                    
                    self.active_duels[chat_id] = {
                        'user1': user_id,
                        'user2': target_id,
                        'bet': bet,
                        'status': 'waiting'
                    }
                    
                    self.send_message(chat_id, f"⚔️ {first_name} вызывает {target_name} на дуэль!\n💰 Ставка: {bet} монет\n\n{target_name}, напишите /accept чтобы принять вызов!")
                    
                    threading.Timer(60.0, self.duel_timeout, args=[chat_id]).start()
                except ValueError:
                    self.send_message(chat_id, "❌ Сумма должна быть числом!")
                except Exception as e:
                    self.send_message(chat_id, f"❌ Ошибка: {e}")
            
            elif command == '/accept':
                if chat_id not in self.active_duels:
                    self.send_message(chat_id, "❌ Нет активных дуэлей!")
                    return
                
                duel = self.active_duels[chat_id]
                if user_id != duel['user2']:
                    self.send_message(chat_id, "❌ Это не ваш вызов!")
                    return
                
                winner, error = GameManager.process_duel(chat_id, duel['user1'], duel['user2'], duel['bet'])
                if error:
                    self.send_message(chat_id, error)
                else:
                    try:
                        winner_info = vk.users.get(user_ids=winner)[0]
                        loser_id = duel['user1'] if winner == duel['user2'] else duel['user2']
                        loser_info = vk.users.get(user_ids=loser_id)[0]
                        
                        self.send_message(chat_id, f"⚔️ Дуэль завершена!\n\n🏆 Победитель: {winner_info['first_name']}\n💔 Проигравший: {loser_info['first_name']}\n💰 Выигрыш: {duel['bet']} монет")
                    except:
                        self.send_message(chat_id, f"⚔️ Дуэль завершена!\n\n🏆 Победитель одержал победу!\n💰 Выигрыш: {duel['bet']} монет")
                
                del self.active_duels[chat_id]
            
            elif command == '/transfer':
                if len(args) < 3:
                    self.send_message(chat_id, "❌ Использование: /transfer [@user] [сумма]")
                    return
                
                try:
                    target_id = self.extract_user_id(args[1])
                    if not target_id:
                        self.send_message(chat_id, "❌ Пользователь не найден!")
                        return
                    
                    amount = int(args[2])
                    
                    if amount <= 0:
                        self.send_message(chat_id, "❌ Сумма должна быть положительной!")
                        return
                    
                    if UserManager.get_coins(user_id) < amount:
                        self.send_message(chat_id, f"❌ {first_name}, у вас недостаточно монет!")
                        return
                    
                    if target_id == user_id:
                        self.send_message(chat_id, "❌ Нельзя перевести монеты самому себе!")
                        return
                    
                    UserManager.remove_coins(user_id, amount)
                    UserManager.add_coins(target_id, amount)
                    
                    try:
                        target_info = vk.users.get(user_ids=target_id)[0]
                        target_name = target_info['first_name']
                    except:
                        target_name = f"Пользователь {target_id}"
                    
                    self.send_message(chat_id, f"✅ {first_name} перевел {amount} монет пользователю {target_name}!\n💰 Ваш баланс: {UserManager.get_coins(user_id)}")
                except ValueError:
                    self.send_message(chat_id, "❌ Сумма должна быть числом!")
            
            # ========== КОМАНДЫ АДМИНИСТРАТОРА ==========
            elif command in ['/kick', '/ban', '/warn', '/unwarn', '/check', '/timeout', '/untimeout', '/setnick', '/rnick', '/nlist']:
                if not self.check_permission(chat_id, user_id, 'admin'):
                    self.send_message(chat_id, f"❌ {first_name}, у вас нет прав администратора!")
                    return
                
                if command in ['/kick', '/ban', '/warn', '/unwarn', '/check', '/setnick', '/rnick']:
                    if len(args) < 2:
                        self.send_message(chat_id, f"❌ Использование: {command} [@user]")
                        return
                    
                    target_id = self.extract_user_id(args[1])
                    if not target_id:
                        self.send_message(chat_id, "❌ Пользователь не найден!")
                        return
                    
                    # Проверка можно ли воздействовать на цель
                    if not RoleManager.can_target(chat_id, user_id, target_id):
                        self.send_message(chat_id, "❌ Вы не можете использовать эту команду на создателя или другого администратора!")
                        return
                
                if command == '/kick':
                    try:
                        vk.messages.removeChatUser(
                            chat_id=chat_id - 2000000000,
                            user_id=target_id
                        )
                        
                        cursor.execute('''
                            INSERT INTO punishments (chat_id, user_id, admin_id, type, date)
                            VALUES (?, ?, ?, 'kick', ?)
                        ''', (chat_id, target_id, user_id, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                        conn.commit()
                        
                        self.send_message(chat_id, f"👢 {first_name} исключил пользователя из беседы")
                    except Exception as e:
                        self.send_message(chat_id, f"❌ Не удалось исключить пользователя: {e}")
                
                elif command == '/ban':
                    try:
                        vk.messages.removeChatUser(
                            chat_id=chat_id - 2000000000,
                            user_id=target_id
                        )
                        
                        cursor.execute('''
                            INSERT INTO punishments (chat_id, user_id, admin_id, type, date)
                            VALUES (?, ?, ?, 'ban', ?)
                        ''', (chat_id, target_id, user_id, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                        conn.commit()
                        
                        self.send_message(chat_id, f"🔨 {first_name} забанил пользователя в беседе")
                    except Exception as e:
                        self.send_message(chat_id, f"❌ Не удалось забанить пользователя: {e}")
                
                elif command == '/warn':
                    reason = ' '.join(args[2:]) if len(args) > 2 else 'Без причины'
                    
                    need_kick = UserManager.add_warn(target_id, chat_id, user_id, reason)
                    
                    try:
                        target_info = vk.users.get(user_ids=target_id)[0]
                        target_name = target_info['first_name']
                    except:
                        target_name = f"Пользователь {target_id}"
                    
                    warns = UserManager.get_warns(target_id)
                    
                    warn_text = f"⚠️ {target_name} получил предупреждение от {first_name}\n"
                    warn_text += f"📋 Причина: {reason}\n"
                    warn_text += f"⚠️ Предупреждений: {warns}/3"
                    
                    self.send_message(chat_id, warn_text)
                    
                    if need_kick:
                        try:
                            vk.messages.removeChatUser(
                                chat_id=chat_id - 2000000000,
                                user_id=target_id
                            )
                            self.send_message(chat_id, f"👢 {target_name} исключен за 3 предупреждения!")
                        except:
                            pass
                
                elif command == '/unwarn':
                    UserManager.remove_warn(target_id)
                    
                    try:
                        target_info = vk.users.get(user_ids=target_id)[0]
                        target_name = target_info['first_name']
                    except:
                        target_name = f"Пользователь {target_id}"
                    
                    warns = UserManager.get_warns(target_id)
                    
                    self.send_message(chat_id, f"✅ Снято предупреждение с {target_name}\n⚠️ Текущие предупреждения: {warns}/3")
                
                elif command == '/check':
                    cursor.execute('''
                        SELECT type, admin_id, reason, date FROM punishments 
                        WHERE chat_id = ? AND user_id = ? 
                        ORDER BY date DESC LIMIT 10
                    ''', (chat_id, target_id))
                    punishments = cursor.fetchall()
                    
                    try:
                        target_info = vk.users.get(user_ids=target_id)[0]
                        target_name = target_info['first_name']
                    except:
                        target_name = f"Пользователь {target_id}"
                    
                    if not punishments:
                        self.send_message(chat_id, f"✅ У {target_name} нет нарушений")
                        return
                    
                    check_text = f"🔍 История нарушений: {target_name}\n\n"
                    for p in punishments:
                        p_type, admin_id, reason, date = p
                        try:
                            admin_info = vk.users.get(user_ids=admin_id)[0]
                            admin_name = admin_info['first_name']
                        except:
                            admin_name = f"Админ {admin_id}"
                        
                        type_emoji = {'warn': '⚠️', 'kick': '👢', 'ban': '🔨'}.get(p_type, '📌')
                        check_text += f"{type_emoji} {p_type.upper()}\n"
                        check_text += f"👮 Админ: {admin_name}\n"
                        check_text += f"📋 Причина: {reason}\n"
                        check_text += f"🕒 {date}\n\n"
                    
                    self.send_message(chat_id, check_text)
                
                elif command == '/setnick':
                    if len(args) < 3:
                        self.send_message(chat_id, "❌ Использование: /setnick [@user] [ник]")
                        return
                    
                    nickname = ' '.join(args[2:])
                    if len(nickname) > 30:
                        self.send_message(chat_id, "❌ Ник слишком длинный! Максимум 30 символов")
                        return
                    
                    UserManager.set_nickname(chat_id, target_id, nickname, user_id)
                    
                    try:
                        target_info = vk.users.get(user_ids=target_id)[0]
                        target_name = target_info['first_name']
                    except:
                        target_name = f"Пользователь {target_id}"
                    
                    self.send_message(chat_id, f"✅ Установлен ник для {target_name}: {nickname}")
                
                elif command == '/rnick':
                    UserManager.remove_nickname(chat_id, target_id)
                    
                    try:
                        target_info = vk.users.get(user_ids=target_id)[0]
                        target_name = target_info['first_name']
                    except:
                        target_name = f"Пользователь {target_id}"
                    
                    self.send_message(chat_id, f"🗑️ Ник удален у {target_name}")
                
                elif command == '/nlist':
                    nicknames = UserManager.get_all_nicknames(chat_id)
                    
                    if not nicknames:
                        self.send_message(chat_id, "📋 Список ников пуст")
                        return
                    
                    list_text = "📋 СПИСОК НИКОВ\n\n"
                    for uid, nick, set_by, date in nicknames[:20]:  # Показываем только последние 20
                        try:
                            user_info = vk.users.get(user_ids=uid)[0]
                            user_name = user_info['first_name']
                            
                            set_by_info = vk.users.get(user_ids=set_by)[0]
                            set_by_name = set_by_info['first_name']
                        except:
                            user_name = f"Пользователь {uid}"
                            set_by_name = f"Админ {set_by}"
                        
                        list_text += f"👤 {user_name} → {nick}\n"
                        list_text += f"   👮 Установил: {set_by_name}\n"
                        list_text += f"   🕒 {date[:10]}\n\n"
                    
                    self.send_message(chat_id, list_text)
                
                elif command == '/timeout':
                    ChatManager(chat_id).set_setting('timeout_active', 1)
                    self.send_message(chat_id, f"🔇 Тишина в чате включена!\n👮 Активировал: {first_name}\n✋ Писать могут только администраторы")
                
                elif command == '/untimeout':
                    ChatManager(chat_id).set_setting('timeout_active', 0)
                    self.send_message(chat_id, f"🔊 Тишина отключена!\n👮 Активировал: {first_name}\n💬 Теперь все могут писать")
            
            # ========== КОМАНДЫ СОЗДАТЕЛЯ ==========
            elif command in ['/giveowner', '/giveadm', '/settings']:
                if not self.check_permission(chat_id, user_id, 'owner'):
                    self.send_message(chat_id, f"❌ {first_name}, это команда только для создателя!")
                    return
                
                if command == '/giveowner':
                    if len(args) < 2:
                        self.send_message(chat_id, "❌ Использование: /giveowner [@user]")
                        return
                    
                    target_id = self.extract_user_id(args[1])
                    if not target_id:
                        self.send_message(chat_id, "❌ Пользователь не найден!")
                        return
                    
                    RoleManager.add_admin(chat_id, target_id, user_id, 'owner')
                    
                    try:
                        target_info = vk.users.get(user_ids=target_id)[0]
                        target_name = target_info['first_name']
                    except:
                        target_name = f"Пользователь {target_id}"
                    
                    self.send_message(chat_id, f"👑 {target_name} теперь создатель беседы!")
                
                elif command == '/giveadm':
                    if len(args) < 2:
                        self.send_message(chat_id, "❌ Использование: /giveadm [@user]")
                        return
                    
                    target_id = self.extract_user_id(args[1])
                    if not target_id:
                        self.send_message(chat_id, "❌ Пользователь не найден!")
                        return
                    
                    RoleManager.add_admin(chat_id, target_id, user_id, 'admin')
                    
                    try:
                        target_info = vk.users.get(user_ids=target_id)[0]
                        target_name = target_info['first_name']
                    except:
                        target_name = f"Пользователь {target_id}"
                    
                    self.send_message(chat_id, f"🛡️ {target_name} теперь администратор беседы!")
                
                elif command == '/settings':
                    chat_manager = ChatManager(chat_id)
                    settings_text = "⚙️ НАСТРОЙКИ БЕСЕДЫ ⚙️\n\n"
                    settings_text += f"1️⃣ Исключать приглашенных без прав: {'✅ Вкл' if chat_manager.get_setting('exclude_invited') else '❌ Выкл'}\n"
                    settings_text += f"2️⃣ Исключать при выходе: {'✅ Вкл' if chat_manager.get_setting('exclude_on_leave') else '❌ Выкл'}\n"
                    settings_text += f"3️⃣ Удалять права при выходе: {'✅ Вкл' if chat_manager.get_setting('remove_rights_on_leave') else '❌ Выкл'}\n"
                    settings_text += f"4️⃣ Запретить глобальные теги: {'✅ Вкл' if chat_manager.get_setting('block_global_tags') else '❌ Выкл'}\n"
                    settings_text += f"5️⃣ Запретить стикеры: {'✅ Вкл' if chat_manager.get_setting('block_stickers') else '❌ Выкл'}\n"
                    settings_text += f"6️⃣ Запретить вход по ссылке: {'✅ Вкл' if chat_manager.get_setting('block_invite_link') else '❌ Выкл'}\n\n"
                    settings_text += "📝 Для изменения: /set [номер] [вкл/выкл]"
                    
                    self.send_message(chat_id, settings_text)
            
            elif command == '/set':
                if not self.check_permission(chat_id, user_id, 'owner'):
                    return
                
                if len(args) < 3:
                    self.send_message(chat_id, "❌ Использование: /set [номер] [вкл/выкл]")
                    return
                
                try:
                    setting_num = int(args[1])
                    value = args[2].lower() == 'вкл'
                    
                    settings_map = {
                        1: 'exclude_invited',
                        2: 'exclude_on_leave',
                        3: 'remove_rights_on_leave',
                        4: 'block_global_tags',
                        5: 'block_stickers',
                        6: 'block_invite_link'
                    }
                    
                    if setting_num in settings_map:
                        ChatManager(chat_id).set_setting(settings_map[setting_num], value)
                        self.send_message(chat_id, f"✅ Настройка {setting_num} изменена на {'✅ Вкл' if value else '❌ Выкл'}")
                    else:
                        self.send_message(chat_id, "❌ Неверный номер настройки! (1-6)")
                except ValueError:
                    self.send_message(chat_id, "❌ Номер настройки должен быть числом!")
        
        except Exception as e:
            print(f"Ошибка в process_command: {e}")
    
    def extract_user_id(self, mention):
        try:
            if not mention:
                return None
            
            mention = str(mention)
            
            if mention.startswith('[id') and '|' in mention:
                return int(mention.split('|')[0].replace('[id', ''))
            elif mention.startswith('@') and mention[1:].isdigit():
                return int(mention[1:])
            elif mention.isdigit():
                return int(mention)
            else:
                try:
                    users = vk.users.get(user_ids=mention)
                    if users:
                        return users[0]['id']
                except:
                    pass
        except:
            pass
        return None
    
    def duel_timeout(self, chat_id):
        if chat_id in self.active_duels:
            del self.active_duels[chat_id]
            self.send_message(chat_id, "⏰ Время на принятие дуэли истекло!")
    
    def handle_new_member(self, event):
        try:
            chat_id = event.chat_id + 2000000000
            user_id = event.obj['message']['action']['member_id']
            
            if user_id > 0:
                try:
                    user_info = vk.users.get(user_ids=user_id)[0]
                    first_name = user_info['first_name']
                except:
                    first_name = "Новый участник"
                
                self.send_message(chat_id, f"🌟 Добро пожаловать в LIME MOBILE! 🌟\n👋 {first_name}, рады видеть тебя в нашей беседе!\n\n📌 Не забудь ознакомиться с правилами и использовать /help для списка команд.")
        except Exception as e:
            print(f"Ошибка в handle_new_member: {e}")
    
    def handle_leave_member(self, event):
        try:
            chat_id = event.chat_id + 2000000000
            user_id = event.obj['message']['action']['member_id']
            
            if ChatManager(chat_id).get_setting('exclude_on_leave'):
                cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
                conn.commit()
        except Exception as e:
            print(f"Ошибка в handle_leave_member: {e}")
    
    def run(self):
        print("🤖 Бот LIME MANAGER запущен!")
        print(f"👑 Создатель: {OWNER_ID}")
        print("✅ Ожидание сообщений...")
        
        for event in longpoll.listen():
            try:
                if event.type == VkBotEventType.MESSAGE_NEW:
                    self.handle_message(event)
                
                elif event.type == VkBotEventType.MESSAGE_EVENT:
                    pass
                
                elif event.type == VkBotEventType.GROUP_JOIN:
                    pass
                
                elif event.type == VkBotEventType.MESSAGE_TYPING_STATE:
                    pass
                
                if hasattr(event, 'obj') and event.obj and 'message' in event.obj:
                    if 'action' in event.obj['message']:
                        action = event.obj['message']['action']
                        if action['type'] == 'chat_invite_user':
                            if action['member_id'] != -int(GROUP_ID):
                                self.handle_new_member(event)
                        elif action['type'] == 'chat_kick_user':
                            self.handle_leave_member(event)
            
            except Exception as e:
                print(f"Ошибка в основном цикле: {e}")

# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    bot = LimeManagerBot()
    bot.run()
