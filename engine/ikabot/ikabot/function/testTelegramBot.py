#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import sys

from ikabot.helpers.botComm import sendToBot
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import enter, read
from ikabot.helpers.decorators import configurator


@configurator
def testTelegramBot(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    input = read(msg="Enter the massage you wish to see: ")
    msg = "Test message: {}".format(input)
    sendToBot(session, msg)
    enter()


from ikabot.helpers.botComm import native_notification_ready, native_notification_test
from ikabot.helpers.decorators import task


def prepare_native_test(session):
    if not native_notification_ready(session, "telegram"):
        raise ValueError("Notification provider not configured")
    return {}


@task("testTelegramBot", prepare=prepare_native_test, report_error=False)
def native_test(session):
    native_notification_test(session, "telegram")
