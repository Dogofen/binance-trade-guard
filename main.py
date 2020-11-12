#!/usr/bin/python
from guard_bot import Bot
import sys

bot = Bot(sys.argv[1])
bot.trade_guard(sys.argv[2])
