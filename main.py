from sqlmodel import Session, SQLModel, create_engine, select
import logging

# local
from platforms.workua import WorkUAPlatform
from platforms.dou import DOUPlatform
from models import JobVacancy

def main():
    logging.basicConfig(
        filename='app.log',
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    db_engine = create_engine("sqlite:///database.db")

    SQLModel.metadata.create_all(db_engine)

    search_query = "junior python"

    # with WorkUAPlatform() as work_ua:
    #     results = work_ua.search(search_query)

    with DOUPlatform() as dou:
        results = dou.search(search_query)

    if not results:
        return

    with Session(db_engine) as db_session:
        result_links = [job.link for job in results]

        stored_links = set(
            db_session.exec(
                select(JobVacancy.link).where(JobVacancy.link.in_(result_links))
            ).all()
        )

        for job in results:
            if job.link not in stored_links:
                db_session.add(job)
        
        db_session.commit()

if __name__ == '__main__':
    main()
