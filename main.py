import time
import random
from flask import Flask, render_template, request, session, redirect, url_for

app = Flask(__name__)
# セッションの秘密鍵
app.config['SECRET_KEY'] = 'your-secret-key-final-penalty' 

# ---------------------------------
# 定数・設定
# ---------------------------------
TIME_ATTACK_QUESTIONS = 10    # 10問モードの問題数
TIME_LIMIT_MODE_SECONDS = 180 # 3分モードの時間 (3分 * 60秒)
PENALTY_TIME_SECONDS = 10     # TAモードでのペナルティ秒数

# 難易度と問題の範囲
DIFFICULTY_RANGES = {
    'start': (11, 1000),
    'sprint': (1001, 10000),
    'final': (10001, 50000)
}

# ---------------------------------
# ゲームのコアロジック
# ---------------------------------

def prime_factorization(n):
    """
    数nを素因数分解し、素因数のリストを返す (試し割り法)
    """
    factors = []
    while n % 2 == 0:
        factors.append(2)
        n //= 2
    i = 3
    while i * i <= n:
        if n % i == 0:
            factors.append(i)
            n //= i
        else:
            i += 2 
    if n > 1:
        factors.append(n)
    if not factors:
        return [1] 
    return factors

def generate_question(difficulty):
    """
    難易度に応じた問題（5の倍数を除いた奇数）を生成する
    """
    if difficulty not in DIFFICULTY_RANGES:
        difficulty = 'start' # デフォルト
    min_val, max_val = DIFFICULTY_RANGES[difficulty]
    while True:
        num = random.randint(min_val, max_val)
        if num % 2 != 0 and num % 5 != 0:
            return num

# ---------------------------------
# Webページのルーティング
# ---------------------------------

@app.route('/')
def index():
    """
    トップページ。難易度別の記録をすべて読み込む。
    """
    # 3分モードの記録 (x3)
    time_limit_scores = {
        'start': session.get('time_limit_max_score_start', 0),
        'sprint': session.get('time_limit_max_score_sprint', 0),
        'final': session.get('time_limit_max_score_final', 0),
    }
    
    # 10問TAモード スコア (x3)
    ta_scores = {
        'start': session.get('ta_max_score_start', 0),
        'sprint': session.get('ta_max_score_sprint', 0),
        'final': session.get('ta_max_score_final', 0),
    }
    
    # 10問TAモード タイム (x3)
    ta_times = {
        'start': session.get('ta_best_time_start', 9999),
        'sprint': session.get('ta_best_time_sprint', 9999),
        'final': session.get('ta_best_time_final', 9999),
    }
    
    return render_template(
        'index.html', 
        time_limit_scores=time_limit_scores,
        ta_scores=ta_scores,
        ta_times=ta_times
    )

@app.route('/start', methods=['POST'])
def start_game():
    """
    ゲーム開始。モードと難易度をセッションに保存。
    """
    session['difficulty'] = request.form['difficulty']
    session['mode'] = request.form['mode'] # 'time_attack' or '3_minutes'
    
    # 共通リセット
    session['streak'] = 0
    session['total_score'] = 0
    
    if session['mode'] == 'time_attack':
        # 10問モード用の初期化
        session['question_count'] = 1 
        session['ta_total_correct'] = 0 
        session['ta_start_time'] = time.time()
        session['ta_penalty_time'] = 0 # ペナルティタイム初期化
    
    elif session['mode'] == '3_minutes':
        # 3分モード用の初期化
        session['mode_end_time'] = time.time() + TIME_LIMIT_MODE_SECONDS
        session['time_limit_total_correct'] = 0 
    
    return redirect(url_for('show_question'))

@app.route('/question')
def show_question():
    """
    問題ページ。
    """
    difficulty = session.get('difficulty')
    mode = session.get('mode')
    
    if not difficulty: # セッション切れ
        return redirect(url_for('index'))
    
    # 3分モードの時間切れチェック
    time_remaining = 0
    if mode == '3_minutes':
        end_time = session.get('mode_end_time', 0)
        time_remaining = end_time - time.time()
        if time_remaining <= 0:
            return redirect(url_for('game_over'))
        
    question_num = generate_question(difficulty)
    session['start_time'] = time.time()
    session['question_num'] = question_num
    
    return render_template(
        'question.html',
        number=question_num,
        streak=session.get('streak', 0),
        total_score=session.get('total_score', 0),
        mode=mode,
        question_count=session.get('question_count', 0),
        total_questions=TIME_ATTACK_QUESTIONS,
        time_remaining=time_remaining
    )

@app.route('/check', methods=['POST'])
def check_answer():
    """
    回答チェック + スコア計算 + モード分岐
    """
    if 'question_num' not in session: 
        return redirect(url_for('index'))
        
    user_answer = request.form['answer'] 
    start_time = session.get('start_time', 0)
    number = session.get('question_num', 0)
    mode = session.get('mode')

    time_taken = time.time() - start_time
    factors = prime_factorization(number)
    
    correct_answer = 'prime' if len(factors) == 1 else 'composite'
    factor_str = f"{number} は素数です。" if correct_answer == 'prime' else f"{number} = " + " * ".join(map(str, factors))
    is_correct = (user_answer == correct_answer)
    
    # --- スコアとコンボの計算 (共通) ---
    score = 0
    bonus = ""
    
    if is_correct:
        session['streak'] += 1
        base_score = number 
        combo = session.get('streak', 0)
        
        if combo >= 10: 
            combo_multiplier, bonus = 2.0, "×2.0"
        elif combo >= 3: 
            combo_multiplier, bonus = 1.2, "×1.2"
        else: 
            combo_multiplier = 1.0
            
        score = int(base_score * combo_multiplier)
        
        if mode == 'time_attack':
            session['ta_total_correct'] = session.get('ta_total_correct', 0) + 1
        elif mode == '3_minutes':
            session['time_limit_total_correct'] = session.get('time_limit_total_correct', 0) + 1
        
    else: # 不正解
        session['streak'] = 0 
        
        # ペナルティ: 問題の数の半分を引く
        score = int(-number / 2) 
        
        if mode == 'time_attack':
            # 10問モードのタイムペナルティ
            session['ta_penalty_time'] = session.get('ta_penalty_time', 0) + PENALTY_TIME_SECONDS

    # 累計スコア更新 (0点未満にならないようにする)
    session['total_score'] = max(0, session.get('total_score', 0) + score)
    
    # --- モード分岐ロジック ---
    is_ta_complete = False 
    is_time_up = False     
    
    if mode == 'time_attack':
        current_q_count = session.get('question_count', 0)
        session['question_count'] = current_q_count + 1
        
        if current_q_count >= TIME_ATTACK_QUESTIONS:
            is_ta_complete = True
            # 最終タイム計算 (ペナルティ込み)
            base_time = time.time() - session.get('ta_start_time', 0)
            penalty_time = session.get('ta_penalty_time', 0)
            session['ta_total_time'] = base_time + penalty_time
            session['ta_base_time'] = base_time
            session['ta_total_penalty'] = penalty_time

    elif mode == '3_minutes':
        end_time = session.get('mode_end_time', 0)
        if time.time() >= end_time:
            is_time_up = True 

    return render_template(
        'result.html',
        number=number, is_correct=is_correct, factor_str=factor_str,
        time_taken=time_taken,
        streak=session.get('streak', 0), bonus=bonus,
        score=score, total_score=session.get('total_score', 0),
        mode=mode,
        question_count=session.get('question_count', 0), 
        total_questions=TIME_ATTACK_QUESTIONS,
        is_ta_complete=is_ta_complete, 
        is_time_up=is_time_up          
    )

@app.route('/ta_complete')
def ta_complete():
    """
    10問モード 完了ページ (難易度別)
    """
    if 'ta_total_time' not in session or 'difficulty' not in session:
        return redirect(url_for('index'))
        
    total_score = session.get('total_score', 0)
    total_time = session.get('ta_total_time', 0)
    total_correct = session.get('ta_total_correct', 0)
    difficulty = session.get('difficulty') 
    
    base_time = session.get('ta_base_time', total_time)
    total_penalty = session.get('ta_total_penalty', 0)
    
    is_new_highscore = False
    is_new_best_time = False
    
    # 難易度別の動的キー
    score_key = f"ta_max_score_{difficulty}"
    time_key = f"ta_best_time_{difficulty}"
    
    # ハイスコア更新
    if total_score > session.get(score_key, 0):
        session[score_key] = total_score
        is_new_highscore = True
        
    # ベストタイム更新 (全問正解時のみ)
    if total_correct == TIME_ATTACK_QUESTIONS and total_time < session.get(time_key, 9999):
        session[time_key] = total_time
        is_new_best_time = True
        
    return render_template(
        'ta_complete.html',
        total_score=total_score,
        total_time=total_time,
        total_correct=total_correct,
        total_questions=TIME_ATTACK_QUESTIONS,
        is_new_highscore=is_new_highscore,
        is_new_best_time=is_new_best_time,
        base_time=base_time,
        total_penalty=total_penalty
    )

@app.route('/game_over')
def game_over():
    """
    3分モード 終了ページ (難易D度別)
    """
    if 'mode_end_time' not in session or 'difficulty' not in session:
        return redirect(url_for('index'))
        
    total_score = session.get('total_score', 0)
    total_correct = session.get('time_limit_total_correct', 0)
    difficulty = session.get('difficulty')
    
    is_new_highscore = False
    
    # 難易度別の動的キー
    score_key = f"time_limit_max_score_{difficulty}" 

    if total_score > session.get(score_key, 0):
        session[score_key] = total_score
        is_new_highscore = True
        
    return render_template(
        'game_over.html',
        total_score=total_score,
        total_correct=total_correct,
        is_new_highscore=is_new_highscore
    )

# サーバー起動 (Renderデプロイ対応)
if __name__ == '__main__':
    # このファイルが直接実行された時だけ、開発用サーバーを起動
    # (gunicorn から呼ばれた時は、ここは実行されない)
    app.run(debug=False, host='0.0.0.0', port=5000)