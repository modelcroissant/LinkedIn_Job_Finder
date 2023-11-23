from multiprocessing import Process
from collect_results_script import collect_results
from process_results_script import process_results
from common_functions import new_db_connection, get_app_parameters
from time import sleep

def master_script(args):
    start_flag, shutdown_event, collect_stats_queue, browser = args
    conn = new_db_connection()
    run_collecting = get_app_parameters(conn, "firefox_selected_user_profile")
    run_processing = get_app_parameters(conn, "firefox_selected_user_profile")

    while start_flag.value:
        # Create processes for collecting, processing results, and running the dashboard
        collect_process = Process(target=collect_results, args=(collect_stats_queue, browser))
        process_process = Process(target=process_results, args=(collect_stats_queue, browser))

        # Start all processes
        collect_process.start()
        process_process.start()

        # Wait for all processes to finish
        collect_process.join()
        process_process.join()

        sleep(1)

    shutdown_event.set()