from time import sleep
from common_functions import start_new_browser, show_options, get_user_input, new_db_connection
from selenium.webdriver.support.ui import Select

def process_results(status_queue, firefox):
    # analytics parameters
    jobs_done,jobs_started,jobs_not_available, external_jobs = 0, 0, 0, 0

    # start new browser
    browser = start_new_browser(firefox) 
    # new db connection
    conn = new_db_connection()

    try:
        # Retrieve the latest results from the database
        cursor = conn.cursor()
        cursor.execute('SELECT job_id FROM results WHERE applied = 0 AND external_link = 0 ORDER BY id DESC')
        rows = cursor.fetchall()

        apply_button = """document.querySelector('.jobs-apply-button').click();"""
        submit_button = """document.querySelector('.jobs-easy-apply-footer__info + div button:nth-last-child(1)').click();"""
        status_queue.put({"Title": "Proccessing Results Process","Status":"Running...","stats": {"total jobs processed" : 0,"total jobs started":0,"total jobs not available":0,"total jobs with external links" : 0}})

        for row in rows:
            job_id = row[0]
            # Process the job_id as needed
            browser.get(f'https://www.linkedin.com/jobs/view/{job_id}')
            jobs_started += 1
            sleep(3)
            if browser.execute_script("var button = document.querySelector('.jobs-apply-button'); return button !== null && button.getAttribute('disabled') === null && button.getAttribute('aria-label').includes('Easy');"):
                browser.execute_script(apply_button)
            elif browser.execute_script("var button = document.querySelector('.jobs-apply-button'); return button !== null && button.getAttribute('disabled') === null && !button.getAttribute('aria-label').includes('Easy');"):
                cursor.execute(f'UPDATE results SET external_link = 1 WHERE job_id = {job_id}')
                conn.commit()
                external_jobs += 1
                continue
            else:
                cursor.execute(f'UPDATE results SET applied = 1 WHERE job_id = {job_id}')
                conn.commit()
                jobs_not_available += 1
                continue
            
            for _ in range(10):
                sleep(2)
                # Check if the target class is visible
                if browser.execute_script("return document.querySelector('div[aria-labelledby=\"post-apply-modal\"') === null;") and browser.execute_script("return document.querySelector('div[data-test-form-element-error-messages=\"\"]') === null;"):
                    browser.execute_script(submit_button)
                    continue
                elif browser.execute_script("return document.querySelector('div[data-test-form-element-error-messages=\"\"]') !== null;"):
                    # Get error field question
                    if browser.execute_script("return document.querySelector('div[data-test-form-element-error-messages=\"\"]').parentElement.previousElementSibling.type === \"fieldset\""):
                        choices = browser.execute_script("""
                                                        var choices = [];
                                                        var elements = Array.from(document.querySelector('div[data-test-form-element-error-messages]').parentElement.previousElementSibling.children); 
                                                        elements.forEach(function(element) {
                                                            var identifier = element;
                                                            var innerText = element.innerText.trim();
                                                            choices.push(innerText);
                                                        });
                                                        return choices;
                                                        """)
                        form_question = choices[0].split('\n')[0]
                        choices.pop(0)
                        cursor.execute(f"SELECT answer FROM questions WHERE question = ? LIMIT 1", (form_question,))
                        db_question = cursor.fetchone()
                        
                        if db_question:
                            user_result = db_question[0]
                        else:
                            user_result = show_options(form_question,choices)
                            
                            cursor.execute('INSERT INTO questions (question, answer) VALUES (?, ?)', (form_question, user_result))
                            conn.commit()

                        browser.execute_script("""
                                                var choices = [];
                                                var elements = Array.from(document.querySelector('div[data-test-form-element-error-messages]').parentElement.previousElementSibling.children); 
                                                elements.forEach(function(element) {
                                                    if(element.innerText.trim() === "{user_result}"){
                                                        var event = new Event("change");
                                                        element.firstChild.nextSibling.dispatchEvent(event);
                                                    }
                                                });
                                                """.replace("{user_result}",user_result))

                        continue
                    elif browser.execute_script("return document.querySelector('div[data-test-form-element-error-messages=\"\"]').parentElement.previousElementSibling.type === \"select-one\""):
                        dropdown = browser.execute_script("return document.querySelector('div[data-test-form-element-error-messages=\"\"]').parentElement.previousElementSibling")
                        options = browser.execute_script("""
                                                        var choices = [];
                                                        var elements = Array.from(document.querySelector('div[data-test-form-element-error-messages]').parentElement.previousElementSibling.children); 
                                                        elements.forEach(function(element) {
                                                            var identifier = element;
                                                            var innerText = element.innerText.trim();
                                                            choices.push(innerText);
                                                        });
                                                        return choices;
                                                        """)
                        dropdown_question = browser.execute_script("return document.querySelector('div[data-test-form-element-error-messages]').parentElement.parentElement.querySelector(\"label\").innerText;").split('\n')[0]
                        options.pop(0)
                        cursor.execute(f"SELECT answer FROM questions WHERE question = ? LIMIT 1", (dropdown_question,))
                        db_question = cursor.fetchone()
                        
                        if db_question:
                            user_result = db_question[0]
                        else:
                            user_result = show_options(dropdown_question,options)
                            
                            cursor.execute('INSERT INTO questions (question, answer) VALUES (?, ?)', (dropdown_question, user_result))
                            conn.commit()

                        Select(dropdown).select_by_visible_text(user_result)

                        continue    
                    else:
                        user_question = browser.execute_script("return document.querySelector('div[data-test-form-element-error-messages]').parentElement.previousElementSibling.children[0].innerText.trim();")
                        cursor.execute(f"SELECT answer FROM questions WHERE question = ? LIMIT 1", (user_question,))
                        db_question = cursor.fetchone()
                        
                        if db_question:
                            user_answer = db_question[0]
                        else:
                            user_answer = get_user_input(user_question)
                            
                            cursor.execute('INSERT INTO questions (question, answer) VALUES (?, ?)', (user_question, user_answer))
                            conn.commit()
                        
                        browser.execute_script("return document.querySelector('div[data-test-form-element-error-messages]').parentElement.previousElementSibling.children[0].children[1];").send_keys(user_answer)
                
                else:
                    cursor.execute(f'UPDATE results SET applied = 1 WHERE job_id = {job_id}')
                    conn.commit()
                    jobs_done += 1
                    break
            status_queue.put({"Title": "Proccessing Results Process","Status":"Running...","stats": {"total jobs processed" : jobs_done,"total jobs started":jobs_started,"total jobs not available":jobs_not_available,"total jobs with external links" : external_jobs}})
        
        browser.quit()
        conn.close()
        status_queue.put({"Title": "Proccessing Results Process","Status":"Finished Succesfully","stats": {"total jobs processed" : jobs_done,"total jobs started":jobs_started,"total jobs not available":jobs_not_available,"total jobs with external links" : external_jobs}})

    except Exception as e:
        browser.quit()
        conn.close()
        print("error in collect_results_script.py", str(e))
        status_queue.put({"Title": "error","Status":str(e),"stats": {"total jobs processed" : jobs_done,"total jobs started":jobs_started,"total jobs not available":jobs_not_available,"total jobs with external links" : external_jobs}})
    