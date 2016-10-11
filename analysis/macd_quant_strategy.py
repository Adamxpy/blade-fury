#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import datetime
import logging
import argparse

from mongoengine import Q
from pandas import DataFrame

from logger import setup_logging
from models import StockInfo, QuantResult as QR, StockDailyTrading as SDT


step = 100  # 一次从数据库取出打股票数量
ema_volume = 150


def check_duplicate(qr):
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


def quant_stock(stock_number, stock_name, **kwargs):
    sdt_li = SDT.objects(Q(stock_number=stock_number) & Q(today_closing_price__ne=0.0) &
                         Q(date__lte=kwargs['date'])).order_by('-date')[:ema_volume]

    trading_data = []
    qr_date = kwargs['date']
    standard_total_stock = sdt_li[0].total_stock
    if not standard_total_stock:
        standard_total_stock = sdt_li[1].total_stock

    for s in sdt_li:
        if s.date != qr_date:
            total_stock = s.total_stock
            if total_stock != standard_total_stock:
                s.today_closing_price = s.today_closing_price * total_stock / standard_total_stock

        trading_data.append({'date': s.date, 'price': s.today_closing_price, 'total_stock': s.total_stock})
    trading_data.reverse()
    sorted(trading_data, key=lambda data: data['date'])

    df = DataFrame(trading_data).set_index(['date'])
    df['short_ema'] = df['price'].ewm(span=kwargs['short_ema']).mean()
    df['long_ema'] = df['price'].ewm(span=kwargs['long_ema']).mean()
    df['dif'] = df['short_ema'] - df['long_ema']
    df['dea'] = df['dif'].ewm(span=kwargs['dif_ema']).mean()
    df['macd'] = df['dif'] - df['dea']

    today_macd = df.iloc[-1]
    yestoday_macd = df.iloc[-2]

    if yestoday_macd['macd'] < 0 < today_macd['macd']:
        strategy_direction = 'long'
        strategy_name = 'macd_long_%s_%s_%s' % (kwargs['short_ema'], kwargs['long_ema'], kwargs['dif_ema'])

        qr = QR(
            stock_number=stock_number, stock_name=stock_name, date=today_macd.name,
            strategy_direction=strategy_direction, strategy_name=strategy_name, init_price=today_macd['price']
        )

        if not check_duplicate(qr):
            qr.save()


def start_quant_analysis(**kwargs):
    if not SDT.objects(date=kwargs['date']):
        print 'Not a Trading Day'
        return

    stock_count = StockInfo.objects().count()
    skip = 0

    while skip < stock_count:
        try:
            stocks = StockInfo.objects().skip(skip).limit(step)
        except Exception, e:
            logging.error('Error when query StockInfo:' + str(e))
            stocks = []

        for s in stocks:
            if s.account_firm and u'瑞华会计师' in s.account_firm:
                # 过滤瑞华的客户
                continue

            try:
                quant_stock(s.stock_number, s.stock_name, **kwargs)
            except Exception, e:
                logging.error('Error when macd quant %s:%s' % (s.stock_number, e))

        skip += step


def setup_argparse():
    parser = argparse.ArgumentParser(description=u'根据长短均线的金叉来选股')
    parser.add_argument(u'-s', action=u'store', dest='short_ema', required=True, help=u'短期指数加权均线数')
    parser.add_argument(u'-l', action=u'store', dest='long_ema', required=True, help=u'长期指数加权均线数')
    parser.add_argument(u'-d', action=u'store', dest='dif_ema', required=True, help=u'dif指数加权均线数')
    parser.add_argument(u'-t', action=u'store', dest='qr_date', required=False, help=u'计算策略的日期')

    args = parser.parse_args()

    if args.qr_date:
        try:
            qr_date = datetime.datetime.strptime(args.qr_date, '%Y-%m-%d')
        except Exception, e:
            print 'Wrong date form'
            raise e
    else:
        qr_date = datetime.date.today()

    return int(args.short_ema), int(args.long_ema), int(args.dif_ema), qr_date


if __name__ == '__main__':
    setup_logging(__file__, logging.WARNING)
    short_ema, long_ema, dif_ema, date = setup_argparse()
    start_quant_analysis(short_ema=short_ema, long_ema=long_ema, dif_ema=dif_ema, date=date)
