from sqlmodel import Session, SQLModel, create_engine, select
import logging

# local
from platforms.workua import WorkUAPlatform
from platforms.dou import DOUPlatform
from models import JobVacancy
from exceptions import PlatformInitError

def main():
    logging.basicConfig(
        filename='app.log',
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logger = logging.getLogger(__name__)

    db_engine = create_engine("sqlite:///database.db")

    SQLModel.metadata.create_all(db_engine)

    search_query = "python"

    # with WorkUAPlatform() as work_ua:
    #     vacancies = work_ua.search(search_query)

    vacancies = []

    try:
        with DOUPlatform() as dou:
            vacancies.extend(dou.search(search_query))
    except PlatformInitError as e:
        logger.error("Platform init error: %s", e)
    except Exception as e:
        logger.exception("Unexpected exception (DOU platform): %s", e)

    if not vacancies:
        return

    with Session(db_engine) as db_session:
        vacancy_links = [job.link for job in vacancies]

        stored_links = set(
            db_session.exec(
                select(JobVacancy.link).where(JobVacancy.link.in_(vacancy_links))
            ).all()
        )

        for job in vacancies:
            if job.link not in stored_links:
                db_session.add(job)
        
        db_session.commit()

if __name__ == '__main__':
    main()
