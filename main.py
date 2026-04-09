import logging

# local
from platforms.workua import WorkUAPlatform

def main():
    logging.basicConfig(
        filename='app.log',
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    search_query = "junior python backend developer"

    with WorkUAPlatform() as work_ua:
        results = work_ua.search(search_query)

    for job in results:
        print(job)
        print("----------------\n")

if __name__ == '__main__':
    main()
