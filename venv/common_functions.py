from selenium import webdriver
from selenium.webdriver.firefox.options import Options
import PySimpleGUI as sg
import sqlite3
import re
from datasketch import MinHash, MinHashLSH
from fuzzywuzzy import fuzz

def show_options(question, options): 
    layout = [[sg.Text(question)],
            [sg.Combo(options, size=(20, len(options)), key='-COMBO-', enable_events=True)],
            [sg.Button('OK')]]

    window = sg.Window('Choose an option', layout)
    window.finalize()
    window.bring_to_front()

    while True:
        event, values = window.read()

        if event in (sg.WIN_CLOSED, 'OK'):
            break

    window.close()

    return values['-COMBO-']

def get_user_input(prompt):
    layout = [[sg.Text(prompt)],
            [sg.InputText(key='-INPUT-', size=(40, 5))],
            [sg.Button('OK')]]

    window = sg.Window('Enter Text', layout)
    window.finalize()
    window.bring_to_front()

    while True:
        event, values = window.read()

        if event in (sg.WIN_CLOSED, 'OK'):
            break

    window.close()

    return values['-INPUT-']

def normalise_question(question):
    cleaned_question = re.sub(r'[^\w\s]', '', question.lower().strip('?'))
    cleaned_question = re.sub(r'\s+', ' ', cleaned_question)
    return cleaned_question

def start_new_browser(firefox_profile_path):
    firefox_profile_path = firefox_profile_path
    firefox_profile = webdriver.FirefoxProfile(firefox_profile_path)
    firefox_options = Options()
    firefox_options.profile = firefox_profile
    #firefox_options.add_argument("--headless")

    browser = webdriver.Firefox(options=firefox_options)
    return browser

def load_url_from_db(conn):
    cursor = conn.cursor()
    cursor.execute('SELECT url FROM searches')
    return cursor.fetchall()
      
def create_results_table(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER UNIQUE,
            applied INTEGER DEFAULT 0,
            external_link INTEGER DEFAULT 0,
            needs_user_input INTEGER DEFAULT 0       
        )
    ''')
    conn.commit()

def create_questions_table(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT UNIQUE,
            answer TEXT,
            input_type TEXT
        )
    ''')
    conn.commit()

def create_app_parameters(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_parameters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            param TEXT UNIQUE,
            value TEXT,
            alternative TEXT       
        )
    ''')
    conn.commit()

def create_searches_table(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE      
        )
    ''')
    conn.commit()

def new_db_connection():
    db_path = 'linkedin_jobs.db'
    conn = sqlite3.connect(db_path)
    return conn

def insert_results(conn, results):
    cursor = conn.cursor()

    for i in results:
        try:
            cursor.execute('INSERT INTO results (job_id) VALUES (?)', (int(i),))
        except sqlite3.IntegrityError as e:
            pass

    conn.commit()

def insert_app_parameters(conn,params: list[list]):
    cursor = conn.cursor()

    for i in params:
        try:
            cursor.execute('INSERT INTO global_parameters (param,value,alternative) VALUES (?,?,?)', (i[0],i[1],i[2]))
        except sqlite3.IntegrityError as e:
            print(f"parameter already in the DB: IntegrityError: {e}\nTrying to update")
            cursor.execute('UPDATE global_parameters SET value = ? WHERE param = ?', (i[1],i[0]))

    conn.commit()

def get_app_parameters(conn, param: str):
    cursor = conn.cursor()
    cursor.execute('SELECT value, alternative FROM global_parameters WHERE param = ? LIMIT 1', (param,))
    return cursor.fetchone()[0]

def get_total_jobs(conn):
    cursor = conn.cursor()   
    cursor.execute('SELECT COUNT(*) FROM results')
    return int(cursor.fetchone()[0])

def get_total_jobs_applied(conn):
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM results WHERE applied = 1')
    return int(cursor.fetchone()[0])

def insert_url(conn, result):
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO searches (url) VALUES (?)', (result,))
        conn.commit()
    except sqlite3.IntegrityError as e:
        pass

# TODO create an small algo to handle fuzzymatching and hash table logic for incoming questions
#def get_answer(question):