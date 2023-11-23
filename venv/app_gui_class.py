import PySimpleGUI as sg
import os
from multiprocessing import Manager, Process
from threading import Thread
from common_functions import insert_url,insert_app_parameters, get_app_parameters, new_db_connection,create_results_table,create_questions_table,create_app_parameters,get_total_jobs,get_total_jobs_applied,create_searches_table,get_user_input
from master_script import master_script
import queue

class AppGUI:
    def __init__(self, start_flag, shutdown_event, collect_stats_queue):
        self.start_flag = start_flag
        self.shutdown_event = shutdown_event
        self.collect_stats_queue = collect_stats_queue
        self.conn = new_db_connection()
        self.browser = get_app_parameters(self.conn, "firefox_selected_user_profile")

        create_results_table(self.conn)
        create_questions_table(self.conn)
        create_app_parameters(self.conn)
        create_searches_table(self.conn)
        insert_app_parameters(self.conn, [["collect_results_script", False , None]])

        # TODO Make GUI more presentable with auto sizing the window
        # and have some conditional logic for other windows like start/running/init/options
        # add options for running all processes or individual
        # add the ability to clean the db
        # remove applied for jobs or completly wipe the db or wipe certain tables
        # add flags for showing browser windows or not

        self.layout = [
            [sg.Text('Welcome to LinkedIn Job Helper',font=('Arial Bold', 16))],
            [sg.Text('', font=('Arial Bold', 1), justification='center', expand_x=True)],
            [sg.Text('Current Firefox profile being used:'),sg.Text(str(self.browser.split("\\")[-1]), key="firefox")],
            [sg.Button('Change Firefox Profile', key='configure_profile')],
            [sg.Button('Add LinkedIn Search link', key='add_search_urls')],
            [sg.Text('', font=('Arial Bold', 1), justification='center', expand_x=True)],
            [sg.Text('Total jobs in the db'),sg.Text(str(get_total_jobs(self.conn)), key="get_total_jobs")],
            [sg.Text('Total jobs applied for:'),sg.Text(str(get_total_jobs_applied(self.conn)),key="get_total_jobs_applied")],
            [sg.Text('', font=('Arial Bold', 1), justification='center', expand_x=True)],
            [sg.ProgressBar(100, orientation='h', expand_x=True, size=(20, 20),  key='-PBAR-')],
            [sg.Text('Processor Status:'),sg.Text('idle', key="processor_status"),sg.Text('Finder Status:'),sg.Text('idle', key="finder_status")],
            [sg.Text('', font=('Arial Bold', 1), justification='center', expand_x=True)],
            [sg.Text('Total Jobs Found:'),sg.Text('', key="jobs_found")],
            [sg.Text('Total Jobs Processed:'),sg.Text('', key="jobs_processed")],
            [sg.Text('Total External Jobs:'),sg.Text('', key="external_jobs")],
            [sg.Text('Total Jobs Skipped:'),sg.Text('', key="skipped_jobs")],
            [sg.Button('Start'),sg.Button('Exit')]
        ]
        self.window = sg.Window('LinkedIn Job Helper', self.layout, finalize=True, size=(450, 450))

    @staticmethod
    def _get_available_profiles():
        profiles_path = os.path.expandvars(r'%AppData%\Mozilla\Firefox\Profiles')
        return [d for d in os.listdir(profiles_path) if os.path.isdir(os.path.join(profiles_path, d))]

    @staticmethod
    def _get_default_profile(available_profiles):
        for profile in available_profiles:
            if 'default' in profile.lower():
                return profile
        return None

    @staticmethod
    def get_firefox_profile_path(self):
        db_params = get_app_parameters(self.conn, "firefox_selected_user_profile")
        available_profiles = AppGUI._get_available_profiles()
        default_profile = AppGUI._get_default_profile(available_profiles)

        if db_params:
            self.browser = db_params
            default_profile = db_params

        layout = [
            [sg.Text('Select your Firefox profile')],
            [sg.DropDown(available_profiles, key='firefox_profile_path', size=(100, 50), default_value=default_profile.split("\\")[-1])],
            [sg.Button('OK')]
        ]

        window = sg.Window('Configuration', layout, size=(400, 250))

        while True:
            event, values = window.read()

            if event == sg.WIN_CLOSED:
                window.close()
                insert_app_parameters(self.conn, [["firefox_selected_user_profile", default_profile, None]])
                break

            if event == 'OK':
                user_input = values['firefox_profile_path']
                window.close()
                self.browser = os.path.join(os.path.expandvars(r'%AppData%\Mozilla\Firefox\Profiles'), user_input)
                self.window['firefox'].update(self.browser.split("\\")[-1])
                insert_app_parameters(self.conn, [["firefox_selected_user_profile", os.path.join(os.path.expandvars(r'%AppData%\Mozilla\Firefox\Profiles'), user_input), default_profile]])
                break
    
    @staticmethod
    def run_dashboard(self):
        while not self.shutdown_event.is_set():
            try:
                for _ in range(self.collect_stats_queue.qsize()):
                    data = self.collect_stats_queue.get_nowait()
                    self.format_stats(data)

            except queue.Empty:
                pass

            event, values = self.window.read(timeout=100)

            if event in (sg.WIN_CLOSED, 'Exit'):
                break

    def format_stats(self, *stats_list):
        for stats in stats_list:
            if stats['Title'] == "Collecting Results Process":
                self.window["finder_status"].update(stats['Status'])
                for key, value in stats['stats'].items():
                    self.window['jobs_found'].update(value)
            
            elif stats['Title'] == "Proccessing Results Process":
                self.window["processor_status"].update(stats['Status'])
                for key, value in stats['stats'].items():
                    if key == 'total jobs processed': 
                        self.window['jobs_processed'].update(value)
                    elif key == "total jobs not available":
                        self.window['skipped_jobs'].update(value)
                    elif key == "total jobs with external links":
                        self.window['external_jobs'].update(value)

        self.window['-PBAR-'].update((get_total_jobs_applied(self.conn)/get_total_jobs(self.conn))*100)
        self.window['get_total_jobs'].update(get_total_jobs(self.conn))
        self.window['get_total_jobs_applied'].update(get_total_jobs_applied(self.conn))

    def run(self):
        thread_started = False
        
        while not self.shutdown_event.is_set():
            event, values = self.window.read(timeout=100)
            if event in (sg.WIN_CLOSED, 'Exit'):
                self.shutdown_event.set()
                break

            if event == 'configure_profile':
                self.get_firefox_profile_path(self)

            if event == 'add_search_urls':
                url = get_user_input("Add LinkedIn Search URL you would like to search")
                insert_url(self.conn, url)

            elif event == 'Start':
                if get_app_parameters(self.conn, "firefox_selected_user_profile"):
                   self.start_flag.value = True
                else:
                    sg.popup('Need a firefox profile to start')

            if self.start_flag.value and not thread_started:
                thread_started = True
                self.window['-PBAR-'].update((get_total_jobs_applied(self.conn)/get_total_jobs(self.conn))*100)
                self.window["finder_status"].update('spooling up')
                self.window["processor_status"].update('spooling up')

                thread = Thread(target=master_script, args=((self.start_flag, self.shutdown_event, self.collect_stats_queue, self.browser),))
                thread.daemon = True
                thread.start()
                self.run_dashboard(self)

        self.window['-PBAR-'].update(max=100)
        self.conn.close()
        self.window.close()

def main():
    with Manager() as manager:
        start_flag = manager.Value('b', False)
        shutdown_event = manager.Event()

        collect_stats_queue = manager.Queue()
        gui_process = AppGUI(start_flag, shutdown_event, collect_stats_queue)
        gui_process.run()

if __name__ == "__main__":
    main()