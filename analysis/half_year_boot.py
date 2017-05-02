#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import logging
import argparse

from mongoengine import Q
from pandas import DataFrame

from logger import setup_logging
from models import QuantResult as QR, StockDailyTrading as SDT
from analysis.technical_analysis_util import calculate_ma, format_trading_data, check_duplicate_strategy
from analysis.technical_analysis_util import start_quant_analysis, collect_stock_daily_trading, display_quant


query_step = 100  # 一次从数据库中取出的数据量
half_num = 120
inspect_start = -30
inspect_end = -1


def quant_stock(stock_number, stock_name, **kwargs):
    short_ma = kwargs['short_ma']
    long_ma = kwargs['long_ma']
    qr_date = kwargs['qr_date']
    real_time = kwargs.get('real_time', False)
    if short_ma <= long_ma:
        strategy_direction = 'long'
        quant_count = long_ma + 5
    else:
        strategy_direction = 'short'
        quant_count = short_ma + 5
    if quant_count < half_num:
        quant_count += half_num
    strategy_name = 'halfboot_%s_%s_%s' % (strategy_direction, short_ma, long_ma)

    sdt = SDT.objects(Q(stock_number=stock_number) & Q(today_closing_price__ne=0.0) &
                      Q(date__lte=qr_date)).order_by('-date')[:quant_count]
    if len(sdt) < quant_count:
        # trading data not enough
        return

    if real_time:
        today_sdt = SDT.objects(date=kwargs['qr_date'])
        if kwargs['qr_date'] == datetime.date.today() and not today_sdt:
            today_trading = kwargs.get('today_trading', {})
            if not today_trading.get(stock_number):
                return

            sdt = list(sdt)
            sdt.insert(0, today_trading.get(stock_number))
    trading_data = format_trading_data(sdt)
    if not trading_data:
        return

    df = calculate_ma(DataFrame(trading_data), short_ma, long_ma)
    df['half_ma'] = df['close_price'].rolling(window=half_num, center=False).mean()
    df['price_half_diff'] = df['close_price'] - df['half_ma']
    today_ma = df.iloc[-1]
    yestoday_ma = df.iloc[-2]

    if today_ma['close_price'] < today_ma['half_ma']:
        # 过滤当日价格低于半年线的
        return
    inspect_period = df['price_half_diff'].iloc[inspect_start: inspect_end]
    if inspect_period.max() < 0:
        return

    if today_ma['diff_ma'] > 0 > yestoday_ma['diff_ma']:
        qr = QR(
            stock_number=stock_number, stock_name=stock_name, date=today_ma.name,
            strategy_direction=strategy_direction, strategy_name=strategy_name,
            init_price=today_ma['close_price']
        )
        if real_time:
            return qr
        if not check_duplicate_strategy(qr):
            qr.save()
            return qr
    return ''


def setup_argparse():
    parser = argparse.ArgumentParser(description=u'根据长短均线的金叉来选股')
    parser.add_argument(u'-s', action=u'store', dest='short_ma', required=True, help=u'短期均线数')
    parser.add_argument(u'-l', action=u'store', dest='long_ma', required=True, help=u'长期均线数')
    parser.add_argument(u'-t', action=u'store', dest='qr_date', required=False, help=u'计算均线的日期')
    parser.add_argument(u'-r', action=u'store_true', dest='real_time', required=False, help=u'是否实时计算')

    args = parser.parse_args()
    if args.qr_date:
        try:
            qr_date = datetime.datetime.strptime(args.qr_date, '%Y-%m-%d')
        except Exception, e:
            print 'Wrong date form'
            raise e
    else:
        qr_date = datetime.date.today()

    return int(args.short_ma), int(args.long_ma), qr_date, args.real_time


if __name__ == '__main__':
    setup_logging(__file__, logging.WARNING)
    short_ma, long_ma, qr_date, real_time = setup_argparse()
    today_trading = {}
    if real_time:
        today_trading = collect_stock_daily_trading()

    real_time_res = start_quant_analysis(short_ma=short_ma, long_ma=long_ma, qr_date=qr_date, quant_stock=quant_stock,
                                         real_time=real_time, today_trading=today_trading)
    if real_time_res and real_time:
        display_quant(real_time_res)
