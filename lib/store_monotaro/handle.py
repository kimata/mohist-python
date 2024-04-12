#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pathlib
import enlighten
import datetime
import functools

from selenium.webdriver.support.wait import WebDriverWait
import openpyxl.styles

import local_lib.serializer
import local_lib.selenium_util

AGENT_NAME = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"


def create(config):
    handle = {
        "progress_manager": enlighten.get_manager(),
        "progress_bar": {},
        "config": config,
    }

    load_order_info(handle)

    prepare_directory(handle)

    return handle


def get_login_user(handle):
    return handle["config"]["login"]["user"]


def get_login_pass(handle):
    return handle["config"]["login"]["pass"]


def prepare_directory(handle):
    get_selenium_data_dir_path(handle).mkdir(parents=True, exist_ok=True)
    get_debug_dir_path(handle).mkdir(parents=True, exist_ok=True)
    get_thumb_dir_path(handle).mkdir(parents=True, exist_ok=True)
    get_caceh_file_path(handle).parent.mkdir(parents=True, exist_ok=True)
    get_excel_file_path(handle).parent.mkdir(parents=True, exist_ok=True)


def get_excel_font(handle):
    font_config = handle["config"]["output"]["excel"]["font"]
    return openpyxl.styles.Font(name=font_config["name"], size=font_config["size"])


def get_caceh_file_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["data"]["cache"]["order"])


def get_excel_file_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["output"]["excel"]["table"])


def get_thumb_dir_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["data"]["cache"]["thumb"])


def get_selenium_data_dir_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["data"]["selenium"])


def get_debug_dir_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["data"]["debug"])


def get_selenium_driver(handle):
    if "selenium" in handle:
        return (handle["selenium"]["driver"], handle["selenium"]["wait"])
    else:
        driver = local_lib.selenium_util.create_driver(
            "Mohist", get_selenium_data_dir_path(handle), AGENT_NAME
        )
        wait = WebDriverWait(driver, 5)

        local_lib.selenium_util.clear_cache(driver)

        handle["selenium"] = {
            "driver": driver,
            "wait": wait,
        }

        return (driver, wait)


def record_item(handle, item):
    handle["order"]["item_list"].append(item)
    handle["order"]["order_no_stat"][item["no"]] = True


def get_order_stat(handle, no):
    return no in handle["order"]["order_no_stat"]


def get_item_list(handle):
    return sorted(handle["order"]["item_list"], key=lambda x: x["date"], reverse=True)


def set_month_list(handle, month_list):
    handle["order"]["month_list"] = month_list


def get_month_list(handle):
    return handle["order"]["month_list"]


def set_order_count(handle, month, order_count):
    handle["order"]["month_count"][month.strftime("%Y-%m")] = order_count


def get_order_count(handle, month):
    return handle["order"]["month_count"][month.strftime("%Y-%m")]


def get_total_order_count(handle):
    return functools.reduce(lambda a, b: a + b, handle["order"]["month_count"].values())


def set_month_checked(handle, month):
    handle["order"]["month_stat"][month.strftime("%Y-%m")] = True
    store_order_info(handle)


def get_month_checked(handle, month):
    return month.strftime("%Y-%m") in handle["order"]["month_stat"]


def get_thumb_path(handle, item):
    return get_thumb_dir_path(handle) / (item["id"] + ".png")


def get_cache_last_modified(handle):
    return handle["order"]["last_modified"]


def set_progress_bar(handle, desc, total):
    BAR_FORMAT = (
        "{desc:31s}{desc_pad}{percentage:3.0f}% |{bar}| {count:5d} / {total:5d} "
        + "[{elapsed}<{eta}, {rate:6.2f}{unit_pad}{unit}/s]"
    )
    COUNTER_FORMAT = (
        "{desc:30s}{desc_pad}{count:5d} {unit}{unit_pad}[{elapsed}, {rate:6.2f}{unit_pad}{unit}/s]{fill}"
    )

    handle["progress_bar"][desc] = handle["progress_manager"].counter(
        total=total, desc=desc, bar_format=BAR_FORMAT, counter_format=COUNTER_FORMAT
    )


def set_status(handle, status):
    if "status" not in handle:
        handle["status"] = handle["progress_manager"].status_bar(
            status_format="Merhist{fill}{status}{fill}{elapsed}",
            color="bold_bright_white_on_lightslategray",
            justify=enlighten.Justify.CENTER,
            status=status,
        )
    else:
        handle["status"].update(status=status, force=True)


def finish(handle):
    if "selenium" in handle:
        handle["selenium"]["driver"].quit()
        handle.pop("selenium")

    handle["progress_manager"].stop()


def store_order_info(handle):
    handle["order"]["last_modified"] = datetime.datetime.now()

    local_lib.serializer.store(get_caceh_file_path(handle), handle["order"])


def load_order_info(handle):
    handle["order"] = local_lib.serializer.load(
        get_caceh_file_path(handle),
        {
            "month_list": [],
            "month_count": {},
            "month_stat": {},
            "item_list": [],
            "order_no_stat": {},
            "last_modified": datetime.datetime(1994, 7, 5),
        },
    )


#     # NOTE: 再開した時には巡回すべきなので削除しておく
#     for time_filter in [
#         datetime.datetime.now().year,
#         get_cache_last_modified(handle).year,
#     ]:
#         if time_filter in handle["order"]["page_stat"]:
#             del handle["order"]["page_stat"][time_filter]


def get_progress_bar(handle, desc):
    return handle["progress_bar"][desc]
