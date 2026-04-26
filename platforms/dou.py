from html_to_markdown import convert as to_markdown
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from requests import Response, Session
import logging
import re

# local
from models import Currency, JobPlatformType, JobVacancy
from exceptions import PlatformInitError
from .base_platform import JobPlatform

logger = logging.getLogger(__name__)

class DOUPlatform(JobPlatform):
    def _create_session(self) -> Session:
        session: Session = super()._create_session()

        url = "https://jobs.dou.ua/"

        session.headers.update({
            "Referer": url
        })

        try:
            response = session.get(url)
            response.raise_for_status()

        except Exception as e:
            session.close()
            raise PlatformInitError(f"DOU init error: {e}")

        self._csrf_token: str | None = response.cookies.get('csrftoken')

        if not self._csrf_token:
            raise PlatformInitError("Failed to get CSRF token for DOU")

        return session

    @staticmethod
    def _get_total_vacancies(page_content: bytes, link: str) -> int | None:
        soup = BeautifulSoup(page_content, 'html.parser')
        
        header_tag = soup.select_one('.b-vacancies-head .b-inner-page-header > h1')

        if not (header_tag and header_tag.text):
            logger.debug("Header tag or text not found for: %s", link)
            return None

        if not (regex_result := re.search(r'\d+', header_tag.text)):
            logger.debug("Number of total vacancies not found for: %s", link)
            return None

        return int(regex_result.group())
        
    @staticmethod
    def _parse_salary(salary: str) -> tuple[int | None, int | None, Currency | None]:
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
    def _extract_job_links(page_content: bytes, from_xhr: bool) -> list[str]:
        soup = BeautifulSoup(page_content, 'html.parser')

        if from_xhr:
            link_tags = soup.select('li > div.title > a.vt')
        else:
            link_tags = soup.select('div#vacancyListId > ul > li > div.title > a.vt')

        links = []

        for link_tag in link_tags:
            if link := link_tag.get('href'):
                links.append(link)

        return links

    def _parse_job_page(self, page_content: bytes, link: str) -> JobVacancy | None:
        soup = BeautifulSoup(page_content, 'html.parser')

        if not (vacancy_container := soup.find('div', class_='b-vacancy')):
            logger.debug("Vacancy container not found for: %s", link)
            return None

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

        is_remote = False

        if not (location_tag := vacancy_container.find('span', class_="place bi bi-geo-alt-fill")):
            logger.debug("Location tag not found for: %s", link)

        elif not (location := location_tag.get_text(strip=True)):
            logger.debug("Location tag is empty for: %s", link)
        
        else:
            is_remote = "віддалено" in location.lower()

        # Salary

        salary_tag = vacancy_container.find('span', class_="salary")

        salary_min, salary_max, currency = None, None, None

        if salary_tag and salary_tag.text:
            salary_min, salary_max, currency = self._parse_salary(salary_tag.text)
        
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

    def _process_search_page(self, page_content: bytes, from_xhr: bool = False) -> list[JobVacancy]:
        vacancies: list[JobVacancy] = []

        links: list[str] = self._extract_job_links(page_content, from_xhr)

        for link in links:
            if (response := self.get(link)) is None:
                logger.warning("Failed to fetch job page: %s. Skipping", link)
                continue

            vacancy: JobVacancy | None = self._parse_job_page(response.content, link)

            if vacancy is None:
                logger.warning("Failed to parse job page: %s. Skipping", link)
                continue

            vacancies.append(vacancy)
        
        return vacancies

    def _load_vacancies(self, loaded_vacancies_count: int) -> tuple[bytes, int, bool] | tuple[None, None, None]:
        url = "https://jobs.dou.ua/vacancies/xhr-load/?search=python"

        payload = {
            "csrfmiddlewaretoken": self._csrf_token,
            "count": f"{loaded_vacancies_count}"
        }

        response: Response | None = self.post(url, data=payload)

        if not response:
            logger.warning("No response received from the server.")
            return (None, None, None)

        try:
            r = response.json()

            vacancies: bytes = r['html'].encode('utf-8')
            amount: int = r['num']
            is_last: bool = r['last']

            return (vacancies, amount, is_last)

        except Exception as e:
            logger.warning("Failed to parse vacancies response: %s", e)
            return (None, None, None)

    def search(self, query: str) -> list[JobVacancy]:
        base_url: str = "https://jobs.dou.ua/vacancies/?search="
        query_url: str = f"{base_url}{quote_plus(query)}"

        if (search_response := self.get(query_url)) is None:
            logger.warning("Failed to fetch search page: %s", query_url)
            return []

        total_vacancies: int | None = self._get_total_vacancies(search_response.content, query_url)

        if total_vacancies is None:
            logger.warning("Failed to get total vacancies number for: %s", query_url)
            return []

        # First page
        vacancies: list[JobVacancy] = self._process_search_page(search_response.content)

        # Remaining pages (XHR pagination)
        if total_vacancies > 20:
            loaded_vacancies_count = 20
            is_last = False

            while not is_last:
                vacancies_html, amount, is_last = self._load_vacancies(loaded_vacancies_count)

                if (vacancies_html is None) or (amount is None) or (is_last is None):
                    break
                
                vacancies.extend(self._process_search_page(vacancies_html, from_xhr=True))
                loaded_vacancies_count += amount

        # Return only unique vacancies
        return list(dict.fromkeys(vacancies))
