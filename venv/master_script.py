from multiprocessing import Process, Manager
from collect_results_script import collect_results
from process_results_script import process_results
from common_functions import create_results_table, create_questions_table, new_db_connection, create_app_parameters
from time import sleep

def master_script(args):
    start_flag, shutdown_event, collect_stats_queue, browser = args

    while start_flag.value:
        # Create a multiprocessing Queue for live statistics
        process_stats_queue = Manager().Queue()

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