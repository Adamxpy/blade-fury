#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import logging
import argparse

from mongoengine import Q
from pandas import DataFrame

from logger import setup_logging
from models import QuantResult as QR, StockDailyTrading as SDT
from analysis.technical_analysis_util import format_trading_data, check_duplicate_strategy, collect_stock_daily_trading
from analysis.technical_analysis_util import calculate_macd, calculate_ma, start_quant_analysis, display_quant


step = 100  # 一次从数据库取出打股票数量
ema_volume = 150
year_num = 250


def quant_stock(stock_number, stock_name, **kwargs):
    real_time = kwargs.get('real_time', False)
    sdt = SDT.objects(Q(stock_number=stock_number) & Q(today_closing_price__ne=0.0) &
                      Q(date__lte=kwargs['qr_date'])).order_by('-date')[:year_num+10]
    if len(sdt) < year_num:
        return
    if float(sdt[0].increase_rate.replace('%', '')) > 9:
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
    df = calculate_macd(DataFrame(trading_data), kwargs['short_ema'], kwargs['long_ema'], kwargs['dif_ema'])
    df = calculate_ma(df, kwargs['short_ma'], kwargs['long_ma'])
    df['year_ma'] = df['close_price'].rolling(window=year_num, center=False).mean()
    today_analysis = df.iloc[-1]
    yestoday_analysis = df.iloc[-2]

    if today_analysis['close_price'] < today_analysis['year_ma']:
        return ''

    if short_ma <= long_ma:
        strategy_direction = 'long'
    else:
        strategy_direction = 'short'
    strategy_name = 'ma_macd_%s_%s_%s' % (strategy_direction, short_ma, long_ma)

    if today_analysis['diff_ma'] > 0 > yestoday_analysis['diff_ma']:
        qr = ''
        if strategy_direction == 'long':
            if today_analysis['macd'] > 0 > today_analysis['dif'] and today_analysis['dea'] < 0:
                qr = QR(
                    stock_number=stock_number, stock_name=stock_name, date=today_analysis.name,
                    strategy_direction=strategy_direction, strategy_name=strategy_name,
                    init_price=today_analysis['close_price']
                )
        elif strategy_direction == 'short':
            if today_analysis['macd'] < 0 < today_analysis['dif'] and today_analysis['dea'] > 0:
                qr = QR(
                    stock_number=stock_number, stock_name=stock_name, date=today_analysis.name,
                    strategy_direction=strategy_direction, strategy_name=strategy_name,
                    init_price=today_analysis['close_price']
                )

        if isinstance(qr, QR):
            if real_time:
                return qr
            if not check_duplicate_strategy(qr):
                qr.save()
                return qr
    return ''


def setup_argparse():
    parser = argparse.ArgumentParser(description=u'根据ma_macd来选股')
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
    short_ema = 12
    long_ema = 26
    dif_ema = 9
    short_ma, long_ma, qr_date, real_time = setup_argparse()
    today_trading = {}
    if real_time:
        today_trading = collect_stock_daily_trading()
    real_time_res = start_quant_analysis(short_ma=short_ma, long_ma=long_ma, short_ema=short_ema, long_ema=long_ema,
                                         dif_ema=dif_ema, qr_date=qr_date, quant_stock=quant_stock, real_time=real_time,
                                         today_trading=today_trading)

    if real_time_res and real_time:
        display_quant(real_time_res)
