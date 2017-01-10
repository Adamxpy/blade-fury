#!/usr/bin/env python
# -*- coding: utf-8 -*-


from pandas import DataFrame


def format_trading_data(sdt):
    trading_data = []
    standard_total_stock = sdt[1].total_stock if sdt[1].total_stock else sdt[2].total_stock
    if not standard_total_stock:
        return trading_data

    for i in sdt:
        if not i.total_stock:
            price = i.today_closing_price
        else:
            if standard_total_stock == i.total_stock:
                price = i.today_closing_price
            else:
                price = i.today_closing_price * i.total_stock / standard_total_stock
        trading_data.append({'date': i.date, 'price': price})
    trading_data = sorted(trading_data, key=lambda x: x['date'], reverse=False)
    return trading_data


def calculate_macd(df, short_ema, long_ema, dif_ema):
    if isinstance(df, DataFrame):
        df = df.set_index(['date'])
        df['short_ema'] = df['price'].ewm(span=short_ema).mean()
        df['long_ema'] = df['price'].ewm(span=long_ema).mean()
        df['dif'] = df['short_ema'] - df['long_ema']
        df['dea'] = df['dif'].ewm(span=dif_ema).mean()
        df['macd'] = df['dif'] - df['dea']
        return df
    else:
        raise Exception('df type is wrong')


def calculate_ma(df, short_ma, long_ma):
    if isinstance(df, DataFrame):
        df = df.set_index(['date'])
        df['short_ma'] = df['price'].rolling(window=short_ma, center=False).mean()
        df['long_ma'] = df['price'].rolling(window=long_ma, center=False).mean()
        df['diff_ma'] = df['short_ma'] - df['long_ma']
        return df
    else:
        raise Exception('df type is wrong')
