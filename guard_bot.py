from binance.client import Client
import datetime
import configparser
from botlogger import Logger
import numpy as np
from time import sleep


class Bot(object):
    TIME  = 0
    OPEN  = 1
    HIGH  = 2
    LOW   = 3
    CLOSE = 4
    TREND = 'UP'

    API_KEY = ''
    API_SECRET = ''

    current_stop = {}
    price_round = 0
    min_points_list = []
    data_dict = {
        'timestamp': [],
        'close':[],
        'low':[]
    }


    def __init__(self, symbol):
        self.logger = Logger().init_logger()
        config = configparser.ConfigParser()
        config.read('conf.ini')
        self.API_KEY = config['API_KEYS']['api_key']
        self.API_SECRET = config['API_KEYS']['api_secret']
        self.client = Client(self.API_KEY, self.API_SECRET)
        self.symbol = symbol
        order = self.client.get_all_orders(symbol=self.symbol)[-1]
        self.current_stop = {
            'orderId': order['orderId'],
            'price': float(order['stopPrice'])
        }
        p = float(self.client.get_symbol_info(symbol=self.symbol)['filters'][2]['minQty'])
        while p != 1:
            p = p * 10
            self.price_round = self.price_round + 1
        self.logger.info("bot started guarding, current stop: {}, price round: {}".format(self.current_stop, self.price_round))

    def get_historical_data(self, time_interval):
        startDay = (datetime.datetime.now()).strftime('%Y-%m-%d')
        return self.client.get_historical_klines(self.symbol, time_interval, startDay)

    def data_dict_init(self, historical_data):
        self.data_dict['timestamp'].append(datetime.datetime.fromtimestamp(historical_data[-2][self.TIME] / 1e3).strftime("%d/%m/%Y, %H:%M:%S"))
        self.data_dict['close'].append(float(historical_data[-2][self.CLOSE]))
        self.data_dict['low'].append(float(historical_data[-2][self.LOW]))
        self.data_dict['timestamp'].append(datetime.datetime.fromtimestamp(historical_data[-1][self.TIME] / 1e3).strftime("%d/%m/%Y, %H:%M:%S"))
        self.data_dict['close'].append(float(historical_data[-1][self.CLOSE]))
        self.data_dict['low'].append(float(historical_data[-1][self.LOW]))
        self.logger.info("data dictionary has initiated {}".format(self.data_dict))
        self.min_points_list.append(
            [
                self.data_dict['timestamp'][-1],
                self.data_dict['low'][-1]
            ]
        )

    def populate_data_dict(self, historical_data):
        if self.data_dict['timestamp'][-1] == datetime.datetime.fromtimestamp(historical_data[-2][self.TIME] / 1e3).strftime("%d/%m/%Y, %H:%M:%S"):
            return
        self.data_dict['timestamp'].append(datetime.datetime.fromtimestamp(historical_data[-2][self.TIME] / 1e3).strftime("%d/%m/%Y, %H:%M:%S"))
        self.data_dict['close'].append(float(historical_data[-2][self.CLOSE]))
        self.data_dict['low'].append(float(historical_data[-2][self.LOW]))

    def validate_min_list(self):
        mp_list = []
        if len(self.min_points_list) < 2:
            return
        for mp in self.min_points_list:
            mp_list.append(mp[1])
        diff = np.diff(mp_list)
        if diff[-1] < 0:
            self.logger.warning("the minimum list has lost it's validity with a new lower low")

    def create_min_list(self):
        diff_array = np.diff(self.data_dict['close'])
        if float(diff_array[-1]) > 0 and self.TREND == 'DOWN':
            self.TREND = 'UP'
            if self.min_points_list[-1][1] > self.data_dict['low'][-2]:
                self.min_points_list.pop()
            if self.data_dict['low'][-2] < self.data_dict['low'][-1]:
                self.min_points_list.append(
                    [
                        self.data_dict['timestamp'][-2],
                        self.data_dict['low'][-2]
                    ]
                )
            else:
                self.min_points_list.append(
                    [
                        self.data_dict['timestamp'][-1],
                        self.data_dict['low'][-1]
                    ]
                )
            self.logger.info("list of minimums is: {}".format(self.min_points_list))
        if float(diff_array[-1]) < 0 and self.TREND == 'UP':
            self.TREND = 'DOWN'
        print("diff: {} trend:{}".format(diff_array[-1], self.TREND))
        sleep(3)

    def wait_for_data(self, time_interval):
        time = datetime.datetime.now().strftime("%M")
        if 'h' in time_interval:
            while time != '00':
                time = datetime.datetime.now().strftime("%M")
                sleep(5)
            return
        interval = int(time_interval.replace('m',''))
        while int(time) % interval != 0:
                time = datetime.datetime.now().strftime("%M")
                sleep(5)

    def change_stop_limit(self, stop):
        self.client.cancel_order(orderId=self.current_stop['orderId'], symbol=self.symbol)
        quantity = float(self.client.get_asset_balance(asset=self.symbol.replace('USDT',''))['free'])
        quantity = round(quantity, self.price_round)
        order = self.client.create_order(type="STOP_LOSS_LIMIT", side="SELL",price=stop, stopPrice=stop, quantity=quantity, symbol=self.symbol, timeInForce='GTC')
        self.current_stop = {
            'orderId': order['orderId'],
            'price': stop
        }
        self.logger.info("stop has changed: {}".format(self.current_stop))

    def is_new_stop(self):
        mp_list = []
        diff_abs_list = []
        if len(self.min_points_list) < 3:
            return False
        for mp in self.min_points_list:
            mp_list.append(mp[1])
        diff = np.diff(mp_list)
        for d in diff:
            diff_abs_list.append(d/abs(d))
        if diff_abs_list[-1] + diff_abs_list[-2] == 2:
            if self.min_points_list[-3][1] > self.current_stop['price']:
                return True
        return False

    def trade_guard(self, time_interval):
        historical_data = self.get_historical_data(time_interval)
        self.data_dict_init(historical_data)

        while True:
            self.wait_for_data(time_interval)
            historical_data = self.get_historical_data(time_interval)
            self.populate_data_dict(historical_data)
            self.create_min_list()
            if self.is_new_stop():
                self.change_stop_limit(self.min_points_list[-3][1])

