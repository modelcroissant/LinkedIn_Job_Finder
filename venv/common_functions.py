from selenium import webdriver
from selenium.webdriver.firefox.options import Options
import PySimpleGUI as sg
import sqlite3

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

# Browser spool up
def start_new_browser(firefox_profile_path):
    # Specify the path to the Firefox profile directory
    firefox_profile_path = firefox_profile_path

    # Create a Firefox profile
    firefox_profile = webdriver.FirefoxProfile(firefox_profile_path)

    # Create Firefox options and set the profile
    firefox_options = Options()
    firefox_options.profile = firefox_profile
    firefox_options.add_argument("--headless")

    # Initialize the Firefox WebDriver with the specified profile
    browser = webdriver.Firefox(options=firefox_options)
    return browser

# Function to load the last saved URL from the file
def load_url_from_file():
    try:
        with open("current_url.txt", "r") as file:
            return file.read().strip()
    except FileNotFoundError:
        return None
    
# Create the results table if it doesn't exist.   
def create_results_table(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER UNIQUE,
            applied INTEGER DEFAULT 0,
            external_link INTEGER DEFAULT 0
        )
    ''')
    conn.commit()

def create_questions_table(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT UNIQUE,
            answer TEXT
        )
    ''')
    conn.commit()

# Create new table to keep global parameters
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

# Create new database connection
def new_db_connection():
    db_path = 'linkedin_jobs.db'
    conn = sqlite3.connect(db_path)
    return conn

# Insert results into the database.
def insert_results(conn, results):
    cursor = conn.cursor()

    for i in results:
        try:
            cursor.execute('INSERT INTO results (job_id) VALUES (?)', (int(i),))
        except sqlite3.IntegrityError as e:
            # Handle the integrity error as needed (print, log, etc.)
            print(f"job already in the DB: IntegrityError: {e}")

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
    db_param = None
    try:
        cursor.execute('SELECT value, alternative FROM global_parameters WHERE param = ? LIMIT 1', (param,))
        db_param = cursor.fetchone()
    except Exception as e:
        print(f"{e}")

    results = []

    if db_param:
        results = list(db_param)

    return results

# Insert results into the database.
def get_total_jobs(conn):
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM results')
    return int(cursor.fetchone()[0])

def get_total_jobs_applied(conn):
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM results WHERE applied = 1')
    return int(cursor.fetchone()[0])