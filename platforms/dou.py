from html_to_markdown import convert as to_markdown
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import logging
import re

# local
from models import Currency, JobPlatformType, JobVacancy
from .base_platform import JobPlatform

logger = logging.getLogger(__name__)

class DOUPlatform(JobPlatform):
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

    @staticmethod
    def extract_job_links(page_content: bytes) -> list[str]:
        soup = BeautifulSoup(page_content, 'html.parser')

        link_tags = soup.select('div#vacancyListId > ul > li > div.title > a.vt')

        links = []

        for link_tag in link_tags:
            if link := link_tag.get('href'):
                links.append(link)

        return links

    def parse_job_page(self, page_content: bytes, link: str) -> JobVacancy | None:
        soup = BeautifulSoup(page_content, 'html.parser')

        vacancy_container = soup.find('div', class_='b-vacancy')

        # Company

        company_tag = vacancy_container.select_one('.b-compinfo .l-n a:first-of-type')

        if not (company_tag and company_tag.text):
            logger.debug("Company not found for: %s", link)
            return None

        company = company_tag.text

        # Title

        title_tag = vacancy_container.find('h1', class_='g-h2')

        if not (title_tag and title_tag.text):
            logger.debug("Title not found for: %s", link)
            return None
        
        title = title_tag.text

        # Is remote

        if not (location_tag := vacancy_container.find('span', class_="place bi bi-geo-alt-fill")):
            logger.debug("Location tag not found for: %s", link)
            return None

        if not (location := location_tag.get_text(strip=True)):
            logger.debug("Location tag is empty for: %s", link)
            return None
        
        is_remote = bool(location.lower() == "віддалено")

        # Salary

        salary_tag = vacancy_container.find('span', class_="salary")

        salary_min, salary_max, currency = None, None, None

        if salary_tag and salary_tag.text:
            salary_min, salary_max, currency = self.parse_salary(salary_tag.text)
        
        # Description

        if not (description_block := vacancy_container.find('div', class_='b-typo vacancy-section')):
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
            job_platform=JobPlatformType.DOU,
            currency=currency,
            is_remote=is_remote
        )

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

    def search(self, query: str) -> list[JobVacancy]:
        base_url: str = "https://jobs.dou.ua/vacancies/?search="

        if (search_response := self.fetch(f"{base_url}{quote_plus(query)}")) is None:
            return None
        
        # First page
        vacancies: list[JobVacancy] = self.process_search_page(search_response.content)
        
        # Remaining pages (not sure if there is pagination)
        # ...

        # Return only unique vacancies
        return list(dict.fromkeys(vacancies))
