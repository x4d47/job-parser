from dataclasses import dataclass
from typing import Self
from enum import Enum
import re

class Currency(Enum):
    UAH = "₴"
    USD = "$"
    EUR = "€"
    PLN = "zł"

    @classmethod
    def from_str(cls, string: str) -> Self | None:
        patterns: dict[Currency, str] = {
            cls.UAH: r'(грн|uah|₴)',
            cls.USD: r'(usd|\$)',
            cls.EUR: r'(eur|€)',
            cls.PLN: r'(pln|zł)'
        }

        for currency, pattern in patterns.items():
            if re.search(pattern, string, re.IGNORECASE):
                return currency
        
        return None
    
    def __str__(self):
        return self.value

class JobPlatformType(Enum):
    WORKUA = "Work.ua"

    def __str__(self):
        return self.value

@dataclass(frozen=True)
class JobVacancy:
    title: str
    company: str
    salary_min: int | None
    salary_max: int | None
    currency: Currency | None
    description: str
    job_platform: JobPlatformType
    link: str
    is_remote: bool = False

    def format_salary(self) -> str:
        if (self.salary_min is not None) and (self.salary_max is not None):
            return f"{self.salary_min} — {self.salary_max} {self.currency}"
        elif self.salary_min is not None:
            return f"від {self.salary_min} {self.currency}"
        
        return "Не вказано"
    
    def __str__(self) -> str:
        salary = self.format_salary()

        return (
            f"Назва вакансії: {self.title}\n"
            f"Назва компанії: {self.company}\n"
            f"Зарплата: {salary}\n"
            f"Віддалено: {"Так" if self.is_remote else "Ні"}\n"
            f"Опис: {self.description[:100]}...\n"
            f"Платформа: {self.job_platform}\n"
            f"Посилання: {self.link}"
        )