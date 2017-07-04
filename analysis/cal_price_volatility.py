#!/usr/bin/env python
# -*- coding: utf-8 -*-


import datetime
import argparse
import logging

import pandas as pd
from pandas import DataFrame
from mongoengine import Q

from logger import setup_logging
from models import StockInfo, StockDailyTrading as SDT


display_count = 100


def fetch_stock_price(stock_number, date):
    sdt = SDT.objects(Q(stock_number=stock_number) & Q(date=date))

    if sdt:
        return sdt.first().today_closing_price
    else:
        return


def start_calculate(start_date, end_date):
    if not isinstance(start_date, datetime.datetime) or not isinstance(end_date, datetime.datetime):
        return

    stock_info = StockInfo.objects()
    price_volatility = list()
    for i in stock_info:
        start_price = fetch_stock_price(i.stock_number, start_date)
        end_price = fetch_stock_price(i.stock_number, end_date)

        if not start_price or not end_price:
            continue

        price_diff = end_price - start_price
        if price_diff < 0:
            continue

        price_volatility.append({
            'stock_number': i.stock_number,
            'stock_name': i.stock_name,
            'start_price': start_price,
            'end_price': end_price,
            'increase_rate': round(price_diff/start_price, 4)
        })

    price_volatility = sorted(price_volatility, key=lambda x: x['increase_rate'], reverse=True)
    count = len(price_volatility)

    print '------------------%s--------------------' % count
    df = DataFrame(price_volatility[:display_count]).set_index(['stock_number']).reindex(columns=['stock_name', 'start_price',
                                                                      'end_price', 'increase_rate'])
    pd.set_option('display.max_rows', display_count + 10)
    print df
    pd.reset_option('display.max_rows')



def setup_argparse():
    parser = argparse.ArgumentParser(description=u'计算价格变化并排行')
    parser.add_argument(u'-s', action=u'store', dest='start_date', required=True, help=u'开始时间')
    parser.add_argument(u'-e', action=u'store', dest='end_date', required=True, help=u'结束时间')

    args = parser.parse_args()
    try:
        start_date = datetime.datetime.strptime(args.start_date, '%Y-%m-%d')
        end_date = datetime.datetime.strptime(args.end_date, '%Y-%m-%d')
    except Exception as e:
        print 'Wrong date form'
        raise e

    return start_date, end_date


if __name__ == '__main__':
    setup_logging(__file__, logging.WARNING)
    start_date, end_date = setup_argparse()
    start_calculate(start_date, end_date)

