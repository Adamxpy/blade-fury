#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging

import numpy as np
import talib as ta
from pandas import DataFrame
from models import QuantResult as QR, StockDailyTrading as SDT, StockInfo
from mongoengine import Q


query_step = 100


def format_trading_data(sdt):
    trading_data = []
    standard_total_stock = sdt[1].total_stock if sdt[1].total_stock else sdt[2].total_stock
    if not standard_total_stock:
        return trading_data

    for i in sdt:
        if not i.total_stock:
            close_price = i.today_closing_price
            high_price = i.today_highest_price
            low_price = i.today_lowest_price
        else:
            if standard_total_stock == i.total_stock:
                close_price = i.today_closing_price
                high_price = i.today_highest_price
                low_price = i.today_lowest_price
            else:
                close_price = i.today_closing_price * i.total_stock / standard_total_stock
                high_price = i.today_highest_price * i.total_stock / standard_total_stock
                low_price = i.today_lowest_price * i.total_stock / standard_total_stock
        trading_data.append({'date': i.date, 'close_price': close_price, 'high_price': high_price,
                             'low_price': low_price, 'quantity_relative_ratio': i.quantity_relative_ratio})
    trading_data = sorted(trading_data, key=lambda x: x['date'], reverse=False)
    return trading_data


def calculate_macd(df, short_ema, long_ema, dif_ema):
    if isinstance(df, DataFrame):
        if df.index.name != 'date':
            df = df.set_index(['date'])
        df['short_ema'] = df['close_price'].ewm(span=short_ema).mean()
        df['long_ema'] = df['close_price'].ewm(span=long_ema).mean()
        df['dif'] = df['short_ema'] - df['long_ema']
        df['dea'] = df['dif'].ewm(span=dif_ema).mean()
        df['macd'] = df['dif'] - df['dea']
        return df
    else:
        raise Exception('df type is wrong')


def calculate_ma(df, short_ma, long_ma):
    if isinstance(df, DataFrame):
        if df.index.name != 'date':
            df = df.set_index(['date'])
        df['short_ma'] = df['close_price'].rolling(window=short_ma, center=False).mean()
        df['long_ma'] = df['close_price'].rolling(window=long_ma, center=False).mean()
        df['diff_ma'] = df['short_ma'] - df['long_ma']
        return df
    else:
        raise Exception('df type is wrong')


def calculate_kdj(df, fastk_period=9):
    if isinstance(df, DataFrame):
        if df.index.name != 'date':
            df = df.set_index(['date'])
        df['k'], df['d'] = ta.STOCH(np.array(df['high_price']), np.array(df['low_price']), np.array(df['close_price']),
                                    fastk_period=fastk_period, slowk_period=3, slowk_matype=0, slowd_period=3,
                                    slowd_matype=0)
        df['k_d_dif'] = df['k'] - df['d']
        return df
    else:
        raise Exception('df type is wrong')


def check_duplicate_strategy(qr):
    if isinstance(qr, QR):
        try:
            cursor = QR.objects(Q(stock_number=qr.stock_number) & Q(strategy_name=qr.strategy_name) &
                                Q(date=qr.date))
        except Exception, e:
            logging.error('Error when check dupliate %s strategy %s date %s: %s' % (qr.stock_number, qr.strategy_name,
                                                                                    qr.date, e))
        if cursor:
            return True
        else:
            return False


def start_quant_analysis(**kwargs):
    if not kwargs.get('qr_date') or not kwargs.get('quant_stock'):
        print 'no qr_date or quant_stock function'
        return

    if not SDT.objects(date=kwargs['qr_date']):
        print 'Not a Trading Date'
        return

    try:
        all_stocks = StockInfo.objects()
    except Exception, e:
        logging.error('Error when query StockInfo:' + str(e))
        raise e

    stocks_count = all_stocks.count()
    skip = 0

    while skip < stocks_count:
        try:
            stocks = StockInfo.objects().skip(skip).limit(query_step)
        except Exception, e:
            logging.error('Error when query skip %s  StockInfo:%s' % (skip, e))
            stocks = []

        for i in stocks:
            if i.account_firm and u'瑞华会计师' in i.account_firm:
                # 过滤瑞华的客户
                continue

            try:
                kwargs['quant_stock'](i.stock_number, i.stock_name, **kwargs)
            except Exception, e:
                logging.error('Error when quant %s ma strategy: %s' % (i.stock_number, e))
        skip += query_step
