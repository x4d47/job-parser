from abc import ABC, abstractmethod
from requests.exceptions import HTTPError, ConnectionError, Timeout, RequestException
from requests.adapters import HTTPAdapter
from requests import Response, Session
from urllib3.util import Retry

# local
from models import JobVacancy

TIMEOUT = 10.

class JobPlatform(ABC):
    def __init__(self):
        self.session = self.create_session()

    def create_session(self):
        session = Session()

        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "uk,en-US;q=0.9,en;q=0.8"
        })

        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods={'GET'},
        )

        adapter = HTTPAdapter(max_retries=retries)

        session.mount('http://', adapter)
        session.mount('https://', adapter)

        return session

    def fetch(self, url: str, timeout: float = TIMEOUT) -> Response | None:
        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            return response

        except Timeout:
            logger.warning("Request timeout (%ss) for '%s'", timeout, url)
        except ConnectionError:
            logger.warning("Connection error for '%s'", url)
        except HTTPError as http_err:
            logger.error("HTTP error occurred: %s", http_err)
        except RequestException as e:
            logger.error("Request exception: %s", e)
        except Exception as e:
            logger.exception("Exception: %s", e)
        
        return None

    @abstractmethod
    def search(self, query: str) -> list[JobVacancy] | None:
        pass
    
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self.session.close()
