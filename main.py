import logging

# local
from platforms.workua import WorkUAPlatform
from platforms.dou import DOUPlatform

def main():
    logging.basicConfig(
        filename='app.log',
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    search_query = "junior python"

    # with WorkUAPlatform() as work_ua:
    #     results = work_ua.search(search_query)

    with DOUPlatform() as dou:
        results = dou.search(search_query)

    if not results:
        return

    for job in results:
        print(job)
        print("\n----------------\n")

if __name__ == '__main__':
    main()
