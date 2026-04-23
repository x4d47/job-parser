from html_to_markdown import convert as to_markdown
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import logging
import re

# local
from models import Currency, JobPlatformType, JobVacancy
from .base_platform import JobPlatform

logger = logging.getLogger(__name__)

class WorkUAPlatform(JobPlatform):
    @staticmethod
    def get_pages_count(page_content: bytes) -> int:
        soup = BeautifulSoup(page_content, 'html.parser')

        if not (pagination_ul := soup.find('ul', class_='pagination pagination-small visible-xs-block')):
            return 1

        pages_span = pagination_ul.find('span', class_='text-default')
        if not pages_span or not pages_span.text:
            return 1

        words = pages_span.text.split()
        if words:
            try:
                return int(words[-1])
            except ValueError:
                pass
        
        return 1

    @staticmethod
    def extract_job_links(page_content: bytes) -> list[str]:
        soup = BeautifulSoup(page_content, 'html.parser')

        job_cards = soup.find_all('div', class_='job-link')

        links = []

        for card in job_cards:
            if not (a_tag := card.find('a', tabindex='-1')):
                continue

            if not (href := a_tag.get('href')):
                continue

            links.append(f"https://www.work.ua{href}")

        return links

    @staticmethod
    def parse_salary(salary: str) -> tuple[int | None, int | None, Currency | None]:
        without_spaces = re.sub(r'\s+', '', salary)
        numbers = re.findall(r'\d+', without_spaces)

        salary_min = int(numbers[0]) if len(numbers) >= 1 else None
        salary_max = int(numbers[1]) if len(numbers) >= 2 else None

        if (salary_min is None) and (salary_max is None):
            currency = None
        else:
            currency = Currency.from_str(salary)

        return salary_min, salary_max, currency

    def process_search_page(self, page_content: bytes) -> list[JobVacancy]:
        vacancies: list[JobVacancy] = []

        links: list[str] = self.extract_job_links(page_content)

        for link in links:
            if (response := self.fetch(link)) is None:
                logger.warning("Failed to fetch job page: %s. Skipping", link)
                continue

            vacancy: JobVacancy = self.parse_job_page(response.content, link)

            if vacancy is None:
                logger.warning("Failed to parse job page: %s. Skipping", link)
                continue

            vacancies.append(vacancy)
        
        return vacancies

    def parse_job_page(self, page_content: bytes, link: str) -> JobVacancy | None:
        soup = BeautifulSoup(page_content, 'html.parser')

        # Title

        if not (title_tag := soup.find('h1', id='h1-name')):
            logger.debug("Title tag not found for: %s", link)
            return None

        if not (title := title_tag.text):
            logger.debug("Title tag is empty for: %s", link)
            return None

        # Metadata block

        if not (metadata_block := soup.find('ul', class_='list-unstyled sm:mt-xl mt-lg mb-0')):
            logger.debug("Metadata block not found for: %s", link)
            return None

        # Salary and currency

        salary_tag = metadata_block.select_one('span.glyphicon-hryvnia-fill + span.strong-500')
        
        salary_min, salary_max, currency = None, None, None

        if salary_tag and salary_tag.text:
            salary_min, salary_max, currency = self.parse_salary(salary_tag.text)

        # Company

        company_tag = metadata_block.select_one('span.glyphicon-company + a > span')

        if not (company_tag and company_tag.text):
            logger.debug("Company not found for: %s", link)
            return None

        company = company_tag.text

        # Is remote

        is_remote = bool(metadata_block.find('span', class_='glyphicon-remote'))

        # Description

        if not (description_block := soup.find('div', id='job-description')):
            logger.debug("Description block not found for: %s", link)
            return None

        description_dict = to_markdown(str(description_block))
        description = description_dict.get('content')

        if not description:
            logger.debug("Description is empty for: %s", link)
            return None

        # Final result
        return JobVacancy(
            title=title,
            company=company,
            salary_min=salary_min,
            salary_max=salary_max,
            description=description,
            link=link,
            job_platform=JobPlatformType.WORKUA,
            currency=currency,
            is_remote=is_remote
        )

    def search(self, query: str) -> list[JobVacancy]:
        base_url: str = "https://www.work.ua/jobs/?search="

        if (search_response := self.fetch(f"{base_url}{quote_plus(query)}")) is None:
            return None

        # After redirect `/jobs/?search=python+backend` changes to `/jobs-python+backend/`
        # We have to use this new url
        new_location = search_response.url

        page_base_url: str = f"{new_location}?page="

        pages_count: int = self.get_pages_count(search_response.content)

        # First page
        vacancies: list[JobVacancy] = self.process_search_page(search_response.content)

        # Remaining pages
        for page in range(2, pages_count + 1):
            if (search_response := self.fetch(f"{page_base_url}{page}")) is None:
                break

            vacancies.extend(self.process_search_page(search_response.content))

        return list(dict.fromkeys(vacancies))
