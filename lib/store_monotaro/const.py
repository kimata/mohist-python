#!/usr/bin/env python3
# -*- coding: utf-8 -*-

HIST_URL = (
    "https://www.monotaro.com/monotaroMain.py?func=monotaro.orderHistory.showListServlet.ShowListServlet"
)

HIST_URL_BY_MONTH = (
    "https://www.monotaro.com/monotaroMain.py"
    + "?func=monotaro.orderHistory.showListServlet.ShowListServlet&targetMonth={year}-{month}"
)

DETAIL_URL_BY_LINK_NO = (
    "https://www.monotaro.com/monotaroMain.py"
    + "?func=monotaro.orderHistory.showReadServlet.ShowReadServlet&recvOrderNo={link_no}"
)


ORDER_COUNT_PER_PAGE = 20
