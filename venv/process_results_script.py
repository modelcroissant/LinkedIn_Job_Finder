from time import sleep
from common_functions import start_new_browser, show_options, get_user_input, new_db_connection, normalise_question
from selenium.webdriver.support.ui import Select

def process_results(status_queue, firefox):
    browser = start_new_browser(firefox) 
    conn = new_db_connection()
    cursor = conn.cursor()
    jobs_done,jobs_started,jobs_not_available, external_jobs = 0, 0, 0, 0
    sqlite_job_script = "SELECT job_id FROM results WHERE applied = 0 AND external_link = 0 AND needs_user_input = 0 ORDER BY id DESC"
    apply_button = """document.querySelector('.jobs-apply-button').click();"""
    submit_button = """document.querySelector('.jobs-easy-apply-footer__info + div button:nth-last-child(1)').click();"""
    save_for_later: bool = cursor.execute("SELECT COUNT(*) FROM results WHERE applied = 0 AND external_link = 0").fetchone()[0] > 0
    easy_apply_btn_js = """var button = document.querySelector('.jobs-apply-button'); return button !== null && button.getAttribute('disabled') === null && button.getAttribute('aria-label').includes('Easy');"""
    external_apply_btn_js = """var button = document.querySelector('.jobs-apply-button'); return button !== null && button.getAttribute('disabled') === null && !button.getAttribute('aria-label').includes('Easy');"""
    post_apply_modal_js = """return document.querySelector('div[aria-labelledby=\"post-apply-modal\"') === null;"""
    error_message_js = """return document.querySelector('div[data-test-form-element-error-messages=\"\"]') === null;"""
    fieldset_js = """return document.querySelector('div[data-test-form-element-error-messages=\"\"]').parentElement.previousElementSibling.type === \"fieldset\""""
    fieldset_choices_js = """var choices = [];var elements = Array.from(document.querySelector('div[data-test-form-element-error-messages]').parentElement.previousElementSibling.children); elements.forEach(function(element) {var identifier = element;var innerText = element.innerText.trim();choices.push(innerText);});return choices;"""
    fieldset_answer_js = """var choices = [];var elements = Array.from(document.querySelector('div[data-test-form-element-error-messages]').parentElement.previousElementSibling.children); elements.forEach(function(element) {if(element.innerText.trim() === "{user_result}"){var event = new Event("change");element.firstChild.nextSibling.dispatchEvent(event);}});"""
    select_js = """return document.querySelector('div[data-test-form-element-error-messages=\"\"]').parentElement.previousElementSibling.type === \"select-one\""""
    select_element_js = """return document.querySelector('div[data-test-form-element-error-messages=\"\"]').parentElement.previousElementSibling"""
    select_question_js = """return document.querySelector('div[data-test-form-element-error-messages]').parentElement.parentElement.querySelector(\"label\").innerText;"""
    select_options_js = """var choices = [];var elements = Array.from(document.querySelector('div[data-test-form-element-error-messages]').parentElement.previousElementSibling.children); elements.forEach(function(element) {var identifier = element;var innerText = element.innerText.trim();choices.push(innerText);});return choices;"""
    input_js = """return document.querySelector('div[data-test-form-element-error-messages]').parentElement.previousElementSibling.children[0].innerText.trim();"""
    input_element_js = """return document.querySelector('div[data-test-form-element-error-messages]').parentElement.previousElementSibling.children[0].children[1];"""
    

    # quick and dirty DB questions table clean

    cursor.execute(f"SELECT question FROM questions")
    db_question = cursor.fetchall()

    try:
        cursor.execute(sqlite_job_script)
        rows = cursor.fetchall()
        status_queue.put({"Title": "Proccessing Results Process","Status":"Running...","stats": {"total jobs processed" : 0,"total jobs started":0,"total jobs not available":0,"total jobs with external links" : 0}})

        for row in rows:
            jobs_started += 1
            job_id = row[0]
            browser.get(f'https://www.linkedin.com/jobs/view/{job_id}')
            sleep(5)
            
            if browser.execute_script(easy_apply_btn_js):
                browser.execute_script(apply_button)
            
            elif browser.execute_script(external_apply_btn_js):
                external_jobs += 1
                cursor.execute(f'UPDATE results SET external_link = 1 WHERE job_id = {job_id}')
                conn.commit()
                continue
            
            else:
                cursor.execute(f'UPDATE results SET applied = 1 WHERE job_id = {job_id}')
                conn.commit()
                jobs_not_available += 1
                continue
            # TODO implement input_type in the questions Table to match incoming questions and avoid type errors
            for _ in range(20):
                sleep(2)
                if browser.execute_script(post_apply_modal_js) and browser.execute_script(error_message_js):
                    browser.execute_script(submit_button)
                    continue
            
                elif not browser.execute_script(error_message_js):
                    if browser.execute_script(fieldset_js):
                        choices = browser.execute_script(fieldset_choices_js)
                        form_question = normalise_question(choices[0].split('\n')[0])
                        choices.pop(0)
                        
                        # TODO implement Fuzzy Matching instead of direct match
                        cursor.execute(f"SELECT answer FROM questions WHERE question = ? LIMIT 1", (form_question,))
                        db_question = cursor.fetchone()
                        
                        if db_question:
                            user_result = db_question[0]
                        elif not save_for_later:
                            user_result = show_options(form_question,choices)        
                            cursor.execute('INSERT INTO questions (question, answer) VALUES (?, ?)', (form_question, user_result))
                            conn.commit()
                        else:
                            cursor.execute(f'UPDATE results SET needs_user_input = 1 WHERE job_id = {job_id}')
                            conn.commit()
                            break
                        
                        try:
                            browser.execute_script(fieldset_answer_js.replace("{user_result}",user_result))
                        except:
                            print(f"Fieldset error in job: {job_id}")
                            pass

                        continue

                    elif browser.execute_script(select_js):
                        dropdown = browser.execute_script(select_element_js)
                        options = browser.execute_script(select_options_js)
                        dropdown_question = normalise_question(browser.execute_script(select_question_js).split('\n')[0])
                        options.pop(0)

                        # TODO implement Fuzzy Matching instead of direct match
                        cursor.execute(f"SELECT answer FROM questions WHERE question = ? LIMIT 1", (dropdown_question,))
                        db_question = cursor.fetchone()
                        
                        if db_question:
                            user_result = db_question[0]
                        elif not save_for_later:
                            user_result = show_options(dropdown_question,options)
                            cursor.execute('INSERT INTO questions (question, answer) VALUES (?, ?)', (dropdown_question, user_result))
                            conn.commit()
                        else:
                            cursor.execute(f'UPDATE results SET needs_user_input = 1 WHERE job_id = {job_id}')
                            conn.commit()
                            break
                        
                        # TODO no visible text from DB results can be selected casuing an error
                        try:
                            Select(dropdown).select_by_visible_text(user_result)
                        except:
                            print(f"Select error in job: {job_id}")
                            pass
                        
                        continue    

                    else:
                        user_question = normalise_question(browser.execute_script(input_js))

                        # TODO implement Fuzzy Matching instead of direct match
                        cursor.execute(f"SELECT answer FROM questions WHERE question = ? LIMIT 1", (user_question,))
                        db_question = cursor.fetchone()
                        
                        if db_question:
                            user_answer = db_question[0]
                        elif not save_for_later:
                            user_answer = get_user_input(user_question)
                            cursor.execute('INSERT INTO questions (question, answer) VALUES (?, ?)', (user_question, user_answer))
                            conn.commit()
                        else:
                            cursor.execute(f'UPDATE results SET needs_user_input = 1 WHERE job_id = {job_id}')
                            conn.commit()
                            break
                        
                        # TODO - LinkedIn uses some inputs as dropdowns which will need to be handled  
                        # for now this try catch block should handle the errors gracefully 
                        # maybe use select_question_js logic to find elements cleaner 
                        try:
                            browser.execute_script(input_element_js).send_keys(user_answer)
                        except:
                            print(f"Input error in job: {job_id}")
                            break

                        # TODO - LinkedIn checkbox logic
                else:
                    cursor.execute(f'UPDATE results SET applied = 1 WHERE job_id = {job_id}')
                    conn.commit()
                    jobs_done += 1
                    break

            cursor.execute('SELECT job_id FROM results WHERE applied = 0 AND external_link = 0 ORDER BY id DESC')
            rows = cursor.fetchall()
            status_queue.put({"Title": "Proccessing Results Process","Status":"Running...","stats": {"total jobs processed" : jobs_done,"total jobs started":jobs_started,"total jobs not available":jobs_not_available,"total jobs with external links" : external_jobs}})
        
        browser.quit()
        conn.close()
        status_queue.put({"Title": "Proccessing Results Process","Status":"Finished Succesfully","stats": {"total jobs processed" : jobs_done,"total jobs started":jobs_started,"total jobs not available":jobs_not_available,"total jobs with external links" : external_jobs}})

    except Exception as e:
        browser.quit()
        conn.close()
        print("error in collect_results_script.py", str(e))
        status_queue.put({"Title": "error","Status":str(e),"stats": {"total jobs processed" : jobs_done,"total jobs started":jobs_started,"total jobs not available":jobs_not_available,"total jobs with external links" : external_jobs}})
    

# local testing
#if __name__ == "__main__":
#    process_results({}, r"C:\Users\dmitr\AppData\Roaming\Mozilla\Firefox\Profiles\mfq6ieob.default-release")