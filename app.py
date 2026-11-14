import os
import random
import logging
from datetime import date
from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole
from dotenv import load_dotenv

load_dotenv()

# ТВОЙ КЛЮЧ (ОБЯЗАТЕЛЬНО ПЕРЕВЫПУСТИ ЕГО ПОСЛЕ ЭТОГО!)
HARDCODED_KEY = "MDFhMWM2MTAtNjU3NS03MGU1LWFiMjUtNTY5MmMxZGYwODM1OmE3NGY3M2MzLWM5NjgtNGYxNS04NmI1LTUxNjE3ZjUxZWQwMA=="
app = Flask(__name__)
app.secret_key = "greenowl_secret_key_2026"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///greenowl.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    exp = db.Column(db.Integer, default=0)
    coins = db.Column(db.Integer, default=100)
    level = db.Column(db.Integer, default=1)
    nft = db.Column(db.String(500), default="")
    pass_claimed = db.Column(db.String(500), default="")

with app.app_context():
    db.create_all()

try:
    client = GigaChat(base_url="https://api.giga.chat/v1", credentials=HARDCODED_KEY, scope="GIGACHAT_API_PERS", verify_ssl_certs=False, model="GigaChat-3-Ultra")
except Exception as e:
    client = None

EASY_WORDS = {'food': [('apple', 'яблоко'), ('water', 'вода'), ('tea', 'чай'), ('milk', 'молоко'), ('fish', 'рыба'), ('cheese', 'сыр'), ('bread', 'хлеб')], 'animals': [('cat', 'кот'), ('dog', 'собака'), ('bird', 'птица'), ('fox', 'лиса')]}
MEDIUM_WORDS = {'food': [('meat', 'мясо'), ('coffee', 'кофе'), ('pineapple', 'ананас')], 'animals': [('horse', 'лошадь'), ('bear', 'медведь'), ('wolf', 'волк')]}
HARD_WORDS = {'food': [('refrigerator', 'холодильник'), ('ingredients', 'ингредиенты')], 'animals': [('kangaroo', 'кенгуру'), ('butterfly', 'бабочка'), ('crocodile', 'крокодил')]}
ALL_TOPICS = ['food', 'animals']

def get_words_for_difficulty(topic, diff):
    if topic == 'general':
        base = []
        for t in ALL_TOPICS:
            if diff == 'easy': base.extend(EASY_WORDS.get(t, []))
            elif diff == 'medium': base.extend(MEDIUM_WORDS.get(t, []))
            else: base.extend(HARD_WORDS.get(t, []))
        return list(set(base))
    if diff == 'easy': return EASY_WORDS.get(topic, [])
    elif diff == 'medium': return MEDIUM_WORDS.get(topic, [])
    else: return HARD_WORDS.get(topic, [])

DIFFICULTY_COUNTS = {'easy': 4, 'medium': 5, 'hard': 6}
EXP_GAIN = {'easy': 10, 'medium': 20, 'hard': 30}
COIN_GAIN = {'easy': 5, 'medium': 10, 'hard': 15}

SENTENCES = [
    {'ru': 'Я люблю читать интересные книги.', 'correct': 'I like to read interesting books', 'words': ['interesting', 'I', 'read', 'like', 'to', 'books']},
    {'ru': 'Она обычно ходит в школу пешком.', 'correct': 'she usually goes to school on foot', 'words': ['goes', 'she', 'on', 'school', 'usually', 'to', 'foot']},
]

PHRASES = [
    {'en': 'How are you?', 'ru': 'Как дела?', 'cat': 'Приветствия'},
    {'en': 'What is your name?', 'ru': 'Как тебя зовут?', 'cat': 'Приветствия'},
    {'en': 'Can I have the menu, please?', 'ru': 'Можно мне меню?', 'cat': 'В кафе'},
    {'en': 'How much does it cost?', 'ru': 'Сколько это стоит?', 'cat': 'В кафе'},
]

NFT_PRICES = {'owl': 500, 'cat': 700, 'crown': 1000, 'rocket': 1500, 'diamond': 3000, 'heart': 2000, 'star': 2500, 'ghost': 4000}

PASS_REWARDS = {}
for i in range(2, 41):
    if i % 10 == 0: PASS_REWARDS[i] = {'coins': i * 50, 'item': f'Эксклюзивная рамка {i//10}'}
    elif i % 5 == 0: PASS_REWARDS[i] = {'coins': i * 50, 'item': f'Эксклюзивный скин {i//5}'}
    else: PASS_REWARDS[i] = {'coins': i * 50, 'item': 'Монеты'}

def get_user():
    username = session.get('username', 'guest')
    user = User.query.filter_by(username=username).first()
    if not user:
        user = User(username=username)
        db.session.add(user)
        db.session.commit()
    return user

@app.route('/')
def index(): return render_template('index.html')

@app.route('/check_auth')
def check_auth():
    if 'username' in session: return jsonify({'auth': True, 'name': session['username']})
    return jsonify({'auth': False})

@app.route('/set_name', methods=['POST'])
def set_name():
    name = (request.get_json() or {}).get('name', '').strip()[:15]
    if not name: return jsonify({'status': 'error', 'message': 'Введи имя!'})
    existing = User.query.filter_by(username=name).first()
    if existing: return jsonify({'status': 'error', 'message': '❌ Имя занято!'})
    session['username'] = name
    user = User(username=name)
    db.session.add(user)
    db.session.commit()
    return jsonify({'status': 'ok'})

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('username', None)
    return jsonify({'status': 'ok'})

import json

@app.route('/ask', methods=['POST'])
def ask():
    if not client: return jsonify({'reply': '⚠️ GigaChat не инициализирован.'})
    try:
        word = (request.get_json() or {}).get('message', '').strip()
        
        # ПРОСИМ ИИ ВЫДАТЬ СТРОГО JSON (это исключает любой лишний текст)
        prompt = f"Ты англо-русский словарь. Пользователь ввел слово: '{word}'. Ответь строго в формате JSON без лишних символов: {{\"translation\": \"перевод на русский\", \"sentence\": \"одно короткое предложение на английском с этим словом\"}}"
        
        chat = Chat(messages=[Messages(role=MessagesRole.USER, content=prompt)])
        reply_text = client.chat(chat).choices[0].message.content
        
        # Очищаем ответ от возможных маркеров Markdown (```json ... ```)
        reply_text = reply_text.replace("```json", "").replace("```", "").strip()
        
        # Парсим JSON
        data = json.loads(reply_text)
        translation = data.get('translation', 'Перевод не найден')
        sentence = data.get('sentence', 'Предложение не найдено')
        
        # Форматируем красивый ответ
        formatted_reply = f"<b>Перевод:</b> {translation}<br><br><b>Предложение:</b> {sentence}"
        return jsonify({'reply': formatted_reply})
        
    except Exception as e:
        return jsonify({'reply': f'⚠️ Ошибка: {str(e)}'})
@app.route('/get_stats')
def get_stats():
    user = get_user()
    return jsonify({
        'level': user.level, 'exp': user.exp, 'coins': user.coins,
        'nft': user.nft.split(",") if user.nft else [],
        'pass_claimed': user.pass_claimed.split(",") if user.pass_claimed else []
    })

@app.route('/get_word', methods=['POST'])
def get_word():
    data = request.get_json() or {}
    topic = data.get('topic', 'general')
    diff = data.get('difficulty', 'easy')
    words_list = get_words_for_difficulty(topic, diff)
    if not words_list: return jsonify({'error': 'Нет слов'}), 400
    
    word = random.choice(words_list)
    count = DIFFICULTY_COUNTS[diff]
    
    all_other_words = []
    for t in ALL_TOPICS:
        for w in get_words_for_difficulty(t, diff):
            if w[1] != word[1] and w[1] not in all_other_words: all_other_words.append(w[1])
            
    if len(all_other_words) < count - 1:
        for t in ALL_TOPICS:
            for w in EASY_WORDS.get(t, []) + MEDIUM_WORDS.get(t, []) + HARD_WORDS.get(t, []):
                if w[1] != word[1] and w[1] not in all_other_words: all_other_words.append(w[1])

    distractors = random.sample(all_other_words, min(count - 1, len(all_other_words)))
    options = [word[1]] + distractors
    random.shuffle(options)
    
    session['current_answer'] = word[1]
    return jsonify({'en': word[0], 'options': options})

@app.route('/save_progress', methods=['POST'])
def save_progress():
    try:
        correct = session.pop('current_answer', None)
        data = request.get_json() or {}
        diff = data.get('difficulty', 'easy')
        selected = data.get('answer')
        
        if not correct or selected is None: return jsonify({'error': 'no active question'}), 400

        is_correct = (selected == correct)
        user = get_user()
        earned_exp = 0
        earned_coins = 0
        
        if is_correct:
            earned_exp = EXP_GAIN[diff]
            earned_coins = COIN_GAIN[diff]
            user.exp += earned_exp
            user.coins += earned_coins
        user.level = user.exp // 100 + 1
        db.session.commit()
        
        return jsonify({'correct': is_correct, 'answer': correct, 'earned_exp': earned_exp, 'earned_coins': earned_coins, 'exp': user.exp, 'coins': user.coins, 'level': user.level})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/get_sentence')
def get_sentence():
    s = random.choice(SENTENCES)
    shuffled = s['words'][:]
    random.shuffle(shuffled)
    return jsonify({'words': shuffled, 'correct': s['correct'], 'ru': s['ru']})

@app.route('/check_sentence', methods=['POST'])
def check_sentence():
    try:
        data = request.get_json() or {}
        user_answer = ' '.join(data.get('answer', []))
        correct = data.get('correct', '')
        clean_user = user_answer.lower().replace('.', '').replace(',', '').strip()
        clean_correct = correct.lower().replace('.', '').replace(',', '').strip()
        
        is_ok = clean_user == clean_correct
        user = get_user()
        earned_exp = 0
        earned_coins = 0
        
        if is_ok:
            earned_exp = 20
            earned_coins = 10
            user.exp += earned_exp
            user.coins += earned_coins
        user.level = user.exp // 100 + 1
        db.session.commit()
        return jsonify({'correct': is_ok, 'earned_exp': earned_exp, 'earned_coins': earned_coins, 'level': user.level})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/get_phrase')
def get_phrase(): return jsonify(random.choice(PHRASES))

@app.route('/claim_pass', methods=['POST'])
def claim_pass():
    level = int((request.get_json() or {}).get('level', 0))
    user = get_user()
    if level > user.level: return jsonify({'status': 'error', 'message': 'Ты еще не достиг этого уровня!'})
    claimed = user.pass_claimed.split(",") if user.pass_claimed else []
    if str(level) in claimed: return jsonify({'status': 'error', 'message': 'Ты уже забрал эту награду!'})
    
    reward = PASS_REWARDS.get(level)
    if not reward: return jsonify({'status': 'error', 'message': 'Награда не найдена'})
    
    user.coins += reward['coins']
    user.pass_claimed = user.pass_claimed + "," + str(level) if user.pass_claimed else str(level)
    db.session.commit()
    return jsonify({'status': 'ok', 'message': f"✅ Получено: +{reward['coins']}💰 и {reward['item']}"})

@app.route('/buy_nft', methods=['POST'])
def buy_nft():
    nft_id = (request.get_json() or {}).get('nft_id')
    if nft_id not in NFT_PRICES: return jsonify({'status': 'error', 'message': '❌ Подарок не найден'})
    user = get_user()
    owned = user.nft.split(",") if user.nft else []
    if nft_id in owned: return jsonify({'status': 'error', 'message': '⚠️ У тебя уже есть этот подарок'})
    if user.coins < NFT_PRICES[nft_id]: return jsonify({'status': 'error', 'message': f'❌ Нужно {NFT_PRICES[nft_id]}💰'})
    user.coins -= NFT_PRICES[nft_id]
    user.nft = user.nft + "," + nft_id if user.nft else nft_id
    db.session.commit()
    return jsonify({'status': 'ok', 'message': f'✅ Куплено! Остаток: {user.coins}💰'})

@app.route('/leaderboard')
def leaderboard():
    top = User.query.order_by(User.exp.desc()).limit(10).all()
    return jsonify([{'name': u.username, 'exp': u.exp, 'level': u.level, 'gift': u.nft.split(",")[0] if u.nft else None} for u in top])

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)