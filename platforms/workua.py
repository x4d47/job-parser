from requests.exceptions import HTTPError, ConnectionError, Timeout, RequestException
from html_to_markdown import convert as to_markdown
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import logging
import re

# local
from models import JobPlatformType, JobVacancy
from base_platform import JobPlatform

logger = logging.getLogger(__name__)

class WorkUAPlatform(JobPlatform):
    @staticmethod
    def parse_salary(salary: str) -> tuple[int | None, int | None, str | None]:
        without_spaces = re.sub(r'\s+', '', salary)
        numbers = re.findall(r'\d+', without_spaces)

        salary_min = int(numbers[0]) if len(numbers) >= 1 else None
        salary_max = int(numbers[1]) if len(numbers) >= 2 else None

        currency_pattern = r'(грн|uah|usd|\$|eur|€|pln|zł)'
        currency_match = re.search(currency_pattern, salary, re.IGNORECASE)
        
        currency = currency_match.group().lower() if currency_match else "грн"

        if (salary_min is None) and (salary_max is None):
            currency = None

        return salary_min, salary_max, currency

    def parse_job_page(self, page_content: bytes, link: str) -> JobVacancy:
        soup = BeautifulSoup(page_content, 'html.parser')

        # Title

        if not (title_tag := soup.find('h1', id='h1-name')):
            return None

        if not (title := title_tag.text):
            return None

        if not (metadata_block := soup.find('ul', class_='list-unstyled sm:mt-xl mt-lg mb-0')):
            return None

        # Salary and currency

        salary_min, salary_max, currency = None, None, None

        if salary_icon := metadata_block.find('span', class_='glyphicon-hryvnia-fill'):
            if salary_tag := salary_icon.find_next_sibling('span', class_='strong-500'):
                if salary := salary_tag.text:
                    salary_min, salary_max, currency = self.parse_salary(salary)

        # Company

        if not (company_icon := metadata_block.find('span', class_='glyphicon-company')):
            return None

        if not (a_tag := company_icon.find_next_sibling('a')):
            return None

        if not (company_tag := a_tag.find('span', class_='strong-500')):
            return None

        if not (company := company_tag.text):
            return None

        # Is remote

        is_remote = True if metadata_block.find('span', class_='glyphicon-remote') else False

        # Description

        if not (description_block := soup.find('div', id='job-description')):
            return None

        # to do: check for errors!
        description_dict = to_markdown(str(description_block))

        description = description_dict['content']

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

    def extract_job_links(self, page_content: bytes) -> list[str]:
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

    # parses only first page
    def search(self, query: str) -> list[JobVacancy] | None:
        base_url = "https://www.work.ua/jobs/?search="
        
        url = f"{base_url}{quote_plus(query)}"

        if (response := self.fetch(url)) is None:
            return None

        links = self.extract_job_links(response.content)

        vacancies: list[JobVacancy] = []

        for link in links:
            if (response := self.fetch(link)) is None:
                logger.warning("Failed to fetch job page: %s. Skipping", link)
                continue

            vacancy = self.parse_job_page(response.content, link)

            if vacancy is None:
                logger.warning("Failed to parse job page: %s. Skipping", link)
                continue

            vacancies.append(vacancy)

        return vacancies
