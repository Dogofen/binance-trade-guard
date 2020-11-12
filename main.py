#!/usr/bin/python
import time
from guard_bot import Bot
import sys

bot = Bot(sys.argv[1])
bot.trade_guard(sys.argv[2])
