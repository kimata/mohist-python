#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
モノタロウから購入履歴を収集します．

Usage:
  crawler.py [-c CONFIG]

Options:
  -c CONFIG     : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
"""

import logging
import random
import re
import datetime
import time
import traceback

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

import store_monotaro.const
import store_monotaro.handle

import local_lib.captcha
import local_lib.selenium_util

STATUS_MONTH_COUNT = "[collect] Count of month"
STATUS_MONTH_ORDER = "[collect] Order of month"
STATUS_ORDER_ITEM_ALL = "[collect] All orders"

LOGIN_RETRY_COUNT = 2
FETCH_RETRY_COUNT = 3


def wait_for_loading(handle, xpath='//div[@id="globalMenu"]', sec=1):
    driver, wait = store_monotaro.handle.get_selenium_driver(handle)

    wait.until(EC.visibility_of_all_elements_located((By.XPATH, xpath)))
    time.sleep(sec)


def parse_month(month_text):
    return datetime.datetime.strptime(month_text, "%Y-%m")


def parse_datetime(datetime_text):
    return datetime.datetime.strptime(datetime_text, "%Y/%m/%d %H:%M:%S")


def gen_hist_url(date):
    return store_monotaro.const.HIST_URL_BY_MONTH.format(year=date.year, month=date.month)


def gen_detail_url(order_info):
    return store_monotaro.const.DETAIL_URL_BY_LINK_NO.format(link_no=order_info["link_no"])


def gen_month_str(date):
    return date.strftime("%Y年 %m月")


def visit_url(handle, url, xpath='//div[@id="globalMenu"]'):
    driver, wait = store_monotaro.handle.get_selenium_driver(handle)

    driver.get(url)
    wait_for_loading(handle, xpath)


def save_thumbnail(handle, item, thumb_url):
    driver, wait = store_monotaro.handle.get_selenium_driver(handle)

    with local_lib.selenium_util.browser_tab(driver, thumb_url):
        png_data = driver.find_element(By.XPATH, "//img").screenshot_as_png

        with open(store_monotaro.handle.get_thumb_path(handle, item), "wb") as f:
            f.write(png_data)


def fetch_item_detail(handle, item):
    driver, wait = store_monotaro.handle.get_selenium_driver(handle)

    with local_lib.selenium_util.browser_tab(driver, item["url"]):
        wait_for_loading(handle)

        item["name"] = driver.find_element(By.XPATH, '//h1[contains(@class, "ProductName")]').text

        breadcrumb_list = driver.find_elements(By.XPATH, '//ul[contains(@class, "BreadCrumbs")]/li')
        category = list(map(lambda x: x.text, breadcrumb_list))

        if len(category) > 1:
            category.pop(0)

        item["category"] = category


def parse_item(handle, item_xpath, col_list):
    driver, wait = store_monotaro.handle.get_selenium_driver(handle)

    title = driver.find_element(
        By.XPATH,
        item_xpath
        + '/td[{index}]//table[contains(@class, "orderHistory_item")]/tbody/tr/td/a'.format(
            index=col_list.index("商品名") + 1
        ),
    )

    name = title.text
    url = title.get_attribute("href")

    item_id_text = title.get_attribute("data-analytics-tag")
    item_id = item_id_text.split(",")[0]

    if local_lib.selenium_util.xpath_exists(
        driver,
        item_xpath
        + '/td[{index}]/strong[contains(@class, "cancel")]'.format(index=col_list.index("注文状況") + 1),
    ):
        return {"name": name, "cancel": True}

    count = int(
        driver.find_element(By.XPATH, item_xpath + "/td[{index}]".format(index=col_list.index("数量") + 1)).text
    )
    price_text = driver.find_element(
        By.XPATH, item_xpath + "/td[{index}]".format(index=col_list.index("金額(税抜)") + 1)
    ).text
    price = int(re.match(r".*?(\d{1,3}(?:,\d{3})*)", price_text).group(1).replace(",", ""))

    tax_text = driver.find_element(
        By.XPATH, item_xpath + "/td[{index}]".format(index=col_list.index("消費税") + 1)
    ).text
    tax = int(re.match(r"(\d+)", tax_text).group(1)) / 100

    # NOTE: 税込価格に変換する
    price = round(price * (1 + tax))

    thumb_url = driver.find_element(
        By.XPATH,
        item_xpath
        + '/td[{index}]//td[contains(@class, "productimage")]//img'.format(index=col_list.index("商品名") + 1),
    ).get_attribute("src")

    item = {
        "name": name,
        "count": count,
        "price": price,
        "tax": tax,
        "url": url,
        "id": item_id,
    }

    save_thumbnail(handle, item, thumb_url)

    fetch_item_detail(handle, item)

    return item


def parse_order(handle, order_info):
    ITEM_XPATH = '//table[contains(@class, "oderHistory_product") and contains(@data-ee-list-name, "orderhistory_datail")]/tbody/tr'

    driver, wait = store_monotaro.handle.get_selenium_driver(handle)

    logging.info(
        "Parse order: {date} - {no} ({link_no})".format(
            date=order_info["date"].strftime("%Y-%m-%d"), no=order_info["no"], link_no=order_info["link_no"]
        )
    )

    col_elem_list = driver.find_elements(By.XPATH, ITEM_XPATH + "[1]/th")
    col_list = list(map(lambda x: x.text, col_elem_list))

    date_text = driver.find_element(
        By.XPATH, '//div[contains(@id, "oderHistory")]//p[contains(@class, "detail_guide")]/strong'
    ).text
    date = parse_datetime(date_text)

    no_text = driver.find_element(
        By.XPATH, '//div[contains(@id, "oderHistory")]//p[contains(@class, "detail_guide")]'
    ).text.split("\n")[2]

    no = re.match(r"注文書番号：(\d+)", no_text).group(1)

    item_base = {
        "date": date,
        "no": no,
        "link_no": order_info["link_no"],
    }

    for i in range(1, len(driver.find_elements(By.XPATH, ITEM_XPATH))):
        item_xpath = "(" + ITEM_XPATH + ")[{index}]".format(index=i + 1)

        if abs(len(driver.find_elements(By.XPATH, item_xpath + "/td")) - len(col_list)) > 1:
            break

        item = parse_item(handle, item_xpath, col_list)
        item |= item_base

        if "cancel" not in item:
            logging.info("{name} {price:,}円".format(name=item["name"], price=item["price"]))
            store_monotaro.handle.record_item(handle, item)
        else:
            logging.info("{name} キャンセルされました".format(name=item["name"]))

    return True


def fetch_order_item_list_by_order_info(handle, order_info):
    visit_url(handle, gen_detail_url(order_info))
    keep_logged_on(handle)

    if not parse_order(handle, order_info):
        logging.warning(
            "Failed to parse order of {no} ({link_no})".format(
                no=order_info["no"], link_no=order_info["link_no"]
            )
        )
        time.sleep(1)
        return False

    return True


def fetch_order_item_list_by_month_impl(handle, month):
    ORDER_XPATH = '//div[contains(@class, "orderHistory_list_box")]'

    driver, wait = store_monotaro.handle.get_selenium_driver(handle)

    store_monotaro.handle.set_status(
        handle,
        "注文履歴を解析しています... {month}".format(month=gen_month_str(month)),
    )

    visit_url(handle, gen_hist_url(month))
    keep_logged_on(handle)

    logging.info("Check order of {month}".format(month=gen_month_str(month)))
    logging.info("URL: {url}".format(url=driver.current_url))

    order_list = []
    for i in range(len(driver.find_elements(By.XPATH, ORDER_XPATH))):
        order_xpath = "(" + ORDER_XPATH + ")[{index}]".format(index=i + 1)

        date_text = driver.find_element(
            By.XPATH, order_xpath + '//p[contains(@class, "detail_guide")]/strong'
        ).text
        date = parse_datetime(date_text)

        total_price_text = driver.find_element(
            By.XPATH, order_xpath + '//p[contains(@class, "detail_guide")]/span[contains(@class, "price")]'
        ).text
        total_price = int(re.match(r".*?(\d{1,3}(?:,\d{3})*)", total_price_text).group(1).replace(",", ""))

        no = driver.find_element(
            By.XPATH,
            order_xpath + '//div[contains(@class, "DeteilItem")]/span[contains(@class, "DeteilItem__Text")]',
        ).text

        link_no = driver.find_element(
            By.XPATH,
            order_xpath + '//div[contains(@class, "OrderStatusArea")]/a[contains(@class, "Button")]',
        ).get_attribute("data-ee-recv-order-no")

        order_list.append(
            {
                "date": date,
                "total_price": total_price,
                "no": no,
                "link_no": link_no,
            }
        )

    for order_info in order_list:
        if order_info["link_no"] is None:
            logging.info(
                "Canceled order: {date} - {no} [cached]".format(
                    date=order_info["date"].strftime("%Y-%m-%d"), no=order_info["no"]
                )
            )
            continue

        if not store_monotaro.handle.get_order_stat(handle, order_info["no"]):
            fetch_order_item_list_by_order_info(handle, order_info)
        else:
            logging.info(
                "Done order: {date} - {no} [cached]".format(
                    date=order_info["date"].strftime("%Y-%m-%d"), no=order_info["no"]
                )
            )

        store_monotaro.handle.get_progress_bar(handle, STATUS_ORDER_ITEM_ALL).update()


def fetch_order_item_list_by_month(handle, month):
    visit_url(handle, gen_hist_url(month))

    keep_logged_on(handle)

    month_list = store_monotaro.handle.get_month_list(handle)

    logging.info(
        "Check order of {month} ({year_index}/{total_year})".format(
            month=gen_month_str(month), year_index=month_list.index(month) + 1, total_year=len(month_list)
        )
    )

    fetch_order_item_list_by_month_impl(handle, month)

    store_monotaro.handle.set_month_checked(handle, month)
    store_monotaro.handle.store_order_info(handle)


def fetch_month_list(handle):
    driver, wait = store_monotaro.handle.get_selenium_driver(handle)

    visit_url(handle, store_monotaro.const.HIST_URL)

    keep_logged_on(handle)

    month_list = list(
        map(
            lambda elem: parse_month(re.match(r".*?(\d{4}-\d{2})", elem.get_attribute("href")).group(1)),
            driver.find_elements(By.XPATH, '//div[contains(@class, "oder_date")]/a'),
        )
    )
    month_list += list(
        map(
            lambda elem: parse_month(elem.get_attribute("value")),
            driver.find_elements(By.XPATH, '//select[@name="targetMonthCmb"]/option[contains(@value, "20")]'),
        )
    )

    month_list = list(sorted(month_list))

    store_monotaro.handle.set_month_list(handle, month_list)

    return month_list


def fetch_order_count_by_month(handle, month):
    driver, wait = store_monotaro.handle.get_selenium_driver(handle)

    store_monotaro.handle.set_status(
        handle,
        "注文件数を調べています... {month}年".format(month=gen_month_str(month)),
    )

    visit_url(handle, gen_hist_url(month))

    return len(driver.find_elements(By.XPATH, '//div[contains(@class, "orderHistory_list_box")]'))


def fetch_order_count(handle):
    month_list = store_monotaro.handle.get_month_list(handle)

    logging.info("Collect order count")

    store_monotaro.handle.set_progress_bar(handle, STATUS_MONTH_COUNT, len(month_list))

    total_count = 0
    for month in month_list:
        if month >= store_monotaro.handle.get_cache_last_modified(handle).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        ):
            count = fetch_order_count_by_month(handle, month)
            store_monotaro.handle.set_order_count(handle, month, count)
            logging.info("{month}: {count:4,} orders".format(month=gen_month_str(month), count=count))
        else:
            count = store_monotaro.handle.get_order_count(handle, month)
            logging.info(
                "{month}: {count:4,} orders [cached]".format(month=gen_month_str(month), count=count)
            )

        total_count += count

        store_monotaro.handle.get_progress_bar(handle, STATUS_MONTH_COUNT).update()

    logging.info("Total order is {total_count:,}".format(total_count=total_count))

    store_monotaro.handle.get_progress_bar(handle, STATUS_MONTH_COUNT).update()
    store_monotaro.handle.store_order_info(handle)


def fetch_order_item_list_all_year(handle):
    driver, wait = store_monotaro.handle.get_selenium_driver(handle)

    month_list = fetch_month_list(handle)

    fetch_order_count(handle)

    store_monotaro.handle.set_progress_bar(
        handle, STATUS_ORDER_ITEM_ALL, store_monotaro.handle.get_total_order_count(handle)
    )
    store_monotaro.handle.set_progress_bar(handle, STATUS_MONTH_ORDER, len(month_list))

    for month in month_list:
        if (
            month
            >= store_monotaro.handle.get_cache_last_modified(handle).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
        ) or (not store_monotaro.handle.get_month_checked(handle, month)):
            fetch_order_item_list_by_month(handle, month)
        else:
            logging.info("Done order of {month} [cached]".format(month=gen_month_str(month)))
            store_monotaro.handle.get_progress_bar(handle, STATUS_ORDER_ITEM_ALL).update(
                store_monotaro.handle.get_order_count(handle, month)
            )
        store_monotaro.handle.get_progress_bar(handle, STATUS_MONTH_ORDER).update()

    store_monotaro.handle.get_progress_bar(handle, STATUS_MONTH_ORDER).update()
    store_monotaro.handle.get_progress_bar(handle, STATUS_ORDER_ITEM_ALL).update()


def fetch_order_item_list(handle):
    store_monotaro.handle.set_status(handle, "巡回ロボットの準備をします...")
    driver, wait = store_monotaro.handle.get_selenium_driver(handle)

    store_monotaro.handle.set_status(handle, "注文履歴の収集を開始します...")

    try:
        fetch_order_item_list_all_year(handle)
    except:
        local_lib.selenium_util.dump_page(
            driver,
            int(random.random() * 100),
            store_monotaro.handle.get_debug_dir_path(handle),
        )
        raise

    store_monotaro.handle.set_status(handle, "注文履歴の収集が完了しました．")


def execute_login(handle):
    driver, wait = store_monotaro.handle.get_selenium_driver(handle)

    driver.find_element(By.XPATH, '//input[@name="userId"]').clear()
    driver.find_element(By.XPATH, '//input[@name="userId"]').send_keys(
        store_monotaro.handle.get_login_user(handle)
    )

    driver.find_element(By.XPATH, '//input[@name="password"]').clear()
    driver.find_element(By.XPATH, '//input[@name="password"]').send_keys(
        store_monotaro.handle.get_login_pass(handle)
    )

    local_lib.selenium_util.click_xpath(
        driver, '//button[contains(@class, "Button") and contains(text(), "ログイン")]'
    )

    time.sleep(2)


def keep_logged_on(handle):
    driver, wait = store_monotaro.handle.get_selenium_driver(handle)

    wait_for_loading(handle)

    if not local_lib.selenium_util.xpath_exists(driver, '//h1[contains(@class, "LoginTitle")]'):
        return

    logging.info("Try to login")

    for i in range(LOGIN_RETRY_COUNT):
        if i != 0:
            logging.info("Retry to login")

        execute_login(handle)

        wait_for_loading(handle)

        if not local_lib.selenium_util.xpath_exists(
            driver,
            '//h1[contains(@class, "LoginTitle")]',
        ):
            return

        logging.warning("Failed to login")

        local_lib.selenium_util.dump_page(
            driver,
            int(random.random() * 100),
            store_monotaro.handle.get_debug_dir_path(handle),
        )

    logging.error("Give up to login")
    raise Exception("ログインに失敗しました．")


if __name__ == "__main__":
    from docopt import docopt

    import local_lib.logger
    import local_lib.config

    args = docopt(__doc__)

    local_lib.logger.init("test", level=logging.INFO)

    config = local_lib.config.load(args["-c"])
    handle = store_monotaro.handle.create(config)

    driver, wait = store_monotaro.handle.get_selenium_driver(handle)

    try:
        fetch_order_item_list(handle)
    except:
        driver, wait = store_monotaro.handle.get_selenium_driver(handle)
        logging.error(traceback.format_exc())

        local_lib.selenium_util.dump_page(
            driver,
            int(random.random() * 100),
            store_monotaro.handle.get_debug_dir_path(handle),
        )
