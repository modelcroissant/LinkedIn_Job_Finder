from time import sleep
from common_functions import load_url_from_file, insert_results, start_new_browser, new_db_connection

def collect_results(status_queue, firefox):
    # start new browser
    browser = start_new_browser(firefox)
    # new db connection
    conn = new_db_connection()

    # Open LinkedIn jobs page or last known position
    last_saved_url = load_url_from_file()

    if last_saved_url:
        browser.get(last_saved_url)
    else:
        browser.get(r'https://www.linkedin.com/jobs/search/?location=London%2C%20England%2C%20United%20Kingdom&f_TPR=r86400&origin=JOB_SEARCH_PAGE_JOB_FILTER&refresh=false')

    status_queue.put({"Title": "Collecting Results Process","Status":"Running...","stats": {"total jobs found" : 0}})
    # Scroll to the end of search results to load all of the "below the fold" job listings
    try:
        scrollToBottom = "var element = document.querySelector('.jobs-search-results-list'), scrollHeight = element.scrollHeight+300, step = 50, scrollInterval = setInterval(function() {element.scrollTop += step; (element.scrollTop >= scrollHeight - element.clientHeight) && clearInterval(scrollInterval);}, 10);"
        sleep(5)
        browser.execute_script(scrollToBottom)
        sleep(5)
    except Exception as e:
        print(f"JavascriptException in collect_results_script.py: {e}")

    # Get total number of pages
    pagination_links = """
    var pages = [];
    return parseInt(document.querySelector('.jobs-search-results-list__pagination li:last-child').getAttribute('data-test-pagination-page-btn'));
    """

    # Get all jobs links
    links = []
    js_links_script = """
    var links = [];
    document.querySelectorAll('.scaffold-layout__list-container li a').forEach(function(link) {
        var cleanedLink = link.href.split('?')[0].split('/view/')[1].replace('/','');
        links.push(cleanedLink);
    });
    return links;
    """

    # js to load next page of results
    next_page = """
    var nextLi = document.querySelector('.jobs-search-results-list__pagination li button[aria-label="Page {{nextPage}}"]');;
    var secondToLastLi = document.querySelector('.jobs-search-results-list__pagination li:nth-last-child(2)'); 
    if(!nextLi){
        if (secondToLastLi) {
            var nextPageButton = secondToLastLi.querySelector('button[aria-label="Page {{nextPage}}"]');
            if (nextPageButton) {
                nextPageButton.click();
            }
        }else {return false}
    }else{
        nextLi.click()
    }
    """

    try:
        for i in range(1,browser.execute_script(pagination_links)):
            links += browser.execute_script(js_links_script)
            if browser.execute_script(next_page.replace('{{nextPage}}',str(i+1))) is not False:
                sleep(3)
                browser.execute_script(scrollToBottom)
                sleep(4)

                # analytics
                status_queue.put({"Title": "Collecting Results Process","Status":"Runnning...","stats": {"total jobs found" : len(links)}})
                
                continue
    except Exception as e:
        insert_results(conn, links)
        browser.quit()
        conn.close()
        print("error in collect_results_script.py", str(e))
        status_queue.put({"Title": "error","Status":str(e),"stats": {"total jobs found" : len(links)}})

    insert_results(conn, links)
    browser.quit()
    conn.close()
    status_queue.put({"Title": "Collecting Results Process","Status":"Successfully Finished!","stats": {"total jobs found" : len(links)}})
