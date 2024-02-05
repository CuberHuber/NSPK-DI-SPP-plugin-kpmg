"""
Нагрузка плагина SPP

1/2 документ плагина
"""
import datetime
import itertools
import logging
import time

import dateutil.parser
from selenium.common import NoSuchElementException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from src.spp.types import SPP_document


class KPMG:
    """
    Класс парсера плагина SPP

    :warning Все необходимое для работы парсера должно находится внутри этого класса

    :_content_document: Это список объектов документа. При старте класса этот список должен обнулиться,
                        а затем по мере обработки источника - заполняться.


    """

    SOURCE_NAME = 'kpmg'
    _content_document: list[SPP_document]
    HOST = 'https://kpmg.com/xx/en/home/insights.html'

    # Здесь нужно указывать класс фильтра и значения, которые нужно выбрать
    FILTER = {
        'kpmg_filter_year': ['2024'], # , '2022', '2021'
        'kpmg_ind_path': [
            'Financial Services',
            'Infrastructure',
            'Professional and Business Services',
            'Regulatory Insight',
            'Retail',
            'Technology',
        ]
    }

    def __init__(self, webdriver: WebDriver, max_count_documents: int = 20, *args, **kwargs):
        """
        Конструктор класса парсера

        По умолчанию внего ничего не передается, но если требуется (например: driver селениума), то нужно будет
        заполнить конфигурацию
        """
        # Обнуление списка
        self._content_document = []

        self.driver = webdriver
        self.max_count_documents = max_count_documents

        # Логер должен подключаться так. Вся настройка лежит на платформе
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug(f"Parser class init completed")
        self.logger.info(f"Set source: {self.SOURCE_NAME}")
        ...

    def content(self) -> list[SPP_document]:
        """
        Главный метод парсера. Его будет вызывать платформа. Он вызывает метод _parse и возвращает список документов
        :return:
        :rtype:
        """
        self.logger.debug("Parse process start")
        self._parse()
        self.logger.debug("Parse process finished")
        return self._content_document

    def _parse(self):
        """
        Метод, занимающийся парсингом. Он добавляет в _content_document документы, которые получилось обработать
        :return:
        :rtype:
        """
        # HOST - это главная ссылка на источник, по которому будет "бегать" парсер
        self.logger.debug(F"Parser enter to {self.HOST}")

        # ========================================
        # Тут должен находится блок кода, отвечающий за парсинг конкретного источника
        # -
        self.driver.set_page_load_timeout(50)

        for value1, value2 in itertools.product(self.FILTER['kpmg_ind_path'], self.FILTER['kpmg_filter_year']):
            self._initial_access_source(self.HOST, 4)
            self._parse_filtered_page(value1, value2)
        # ---
        # ========================================

    def _initial_access_source(self, url: str, delay: int = 2):
        self.driver.get(url)
        time.sleep(delay)
        self._agree_cookie_pass()

    def _parse_filtered_page(self, ind_value, year_value):
        self._choice_target_tag_in_selection('kpmg_ind_path', ind_value)
        self._choice_target_tag_in_selection('kpmg_filter_year', year_value)
        time.sleep(2)

        try:
            for _ in range(2):
                # прокручиваем страницу до конца
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
        except Exception as e:
            print(e)

        # Список всех записей по классу.
        insights = self.driver.find_elements(By.CLASS_NAME, 'grid-tiles')
        print(insights)

        links = []

        for insight in insights:
            try:
                date = insight.find_element(By.CLASS_NAME, 'date-info').text
                web_link = insight.find_element(By.TAG_NAME, 'a').get_attribute('href')
                links.append((date, web_link))
            except Exception as e:
                self.logger.error(e)
                continue

        for index, (date, link) in enumerate(links):
            # Ограничение парсинга до установленного параметра self.max_count_documents
            if index >= self.max_count_documents:
                self.logger.debug(f'Max count documents reached ({self.max_count_documents})')
                break
            self._parse_insight(date, link)
            time.sleep(2)

    def _parse_insight(self, date, weblink):
        self._initial_access_source(weblink)

        try:
            text = None
            abstract = None

            try:
                pub_date: datetime.datetime = dateutil.parser.parse(date.split('\n')[-1])
            except Exception as e:
                self.logger.error(e)
                return

            try:
                banner_title = self.driver.find_element(By.CLASS_NAME, 'banner-title')
                title = banner_title.text
            except Exception as e:
                self.logger.error(e)
                return

            try:
                abstract = self.driver.find_element(By.CLASS_NAME, 'banner-description').text
            except Exception as e:
                self.logger.error(e)

            try:
                section = self.driver.find_element(By.XPATH, '//*[@id="page-content"]/section/div/div/div[4]/div/div[1]/section')
                text = section.text
            except Exception as e:
                self.logger.error(e)

            print(title, abstract, weblink)
            print(date.split('\n')[-1])
            print(text)

            document = SPP_document(
                None,
                title,
                abstract,
                text,
                weblink,
                None,
                {},
                pub_date,
                datetime.datetime.now()
            )
            self.logger.info(self._find_document_text_for_logger(document))
            self._content_document.append(document)

        except Exception as e:
            self.logger.error(e)

    def _agree_cookie_pass(self):
        """
        Метод прожимает кнопку agree на модальном окне
        """
        cookie_agree_xpath = '//*[@id="onetrust-accept-btn-handler"]'

        try:
            cookie_button = self.driver.find_element(By.XPATH, cookie_agree_xpath)
            if WebDriverWait(self.driver, 5).until(ec.element_to_be_clickable(cookie_button)):
                cookie_button.click()
                self.logger.debug(F"Parser pass cookie modal on page: {self.driver.current_url}")
        except NoSuchElementException as e:
            self.logger.debug(f'modal agree not found on page: {self.driver.current_url}')

    def _choice_target_tag_in_selection(self, classname: str, value: str):
        try:
            filter = self.driver.find_element(By.CLASS_NAME, classname)
            self.driver.execute_script("arguments[0].setAttribute('class','active')", filter)
            self.logger.debug(F"Open filter by class name: {classname}")
            options = filter.find_elements(By.CLASS_NAME, 'facetsCheckbox')
            for option in options:
                # print(option.text)
                # print(option.find_element(By.CLASS_NAME, 'facetBox').text, option.find_element(By.CLASS_NAME, 'facetBox').aria_role, option.find_element(By.CLASS_NAME, 'facetBox').get_attribute('value'), WebDriverWait(self.driver, 5).until(ec.element_to_be_clickable(option)))
                if option.find_element(By.CLASS_NAME, 'facetBox').get_attribute('value') == value and WebDriverWait(self.driver, 5).until(ec.element_to_be_clickable(option)):
                    self.driver.execute_script("arguments[0].click();", option)
                    self.logger.debug(F"Choice option '{value}' at filter by class name: {classname}")

        except Exception as e:
            self.logger.debug(f'{e}')

    @staticmethod
    def _find_document_text_for_logger(doc: SPP_document):
        """
        Единый для всех парсеров метод, который подготовит на основе SPP_document строку для логера
        :param doc: Документ, полученный парсером во время своей работы
        :type doc:
        :return: Строка для логера на основе документа
        :rtype:
        """
        return f"Find document | name: {doc.title} | link to web: {doc.web_link} | publication date: {doc.pub_date}"