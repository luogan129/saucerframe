#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Copyright (c) saucerman (https://saucer-man.com)
See the file 'LICENSE' for copying permission
"""

import gevent
import sys
import threading
import time
import traceback
from lib.core.data import conf,paths,th
from lib.core.common import outputscreen
from lib.core.enums import POC_RESULT_STATUS
from lib.utils.console import getTerminalSize

def initEngine():
    # init control parameter
    th.result = []
    th.thread_mode = True if conf.engine_mode == "multi_threaded" else False
    th.thread_count = th.thread_num = conf.thread_num
    th.module_name = conf.module_name
    th.module_path = conf.module_path 
    th.module_obj = conf.module_obj 
    th.target = conf.target
    th.no_output = conf.no_output 
    th.output_path = conf.output_path 
    th.scan_count = th.found_count = 0 
    th.is_continue = True 
    th.console_width = getTerminalSize()[0] - 2
    th.start_time = time.time()
    msg = '[+] Set the number of thread: %d' % th.thread_num 
    outputscreen.success(msg) 

def setThreadLock(): 
    # set thread lock 
    th.output_screen_lock = threading.Lock()
    th.found_count_lock = threading.Lock()
    th.scan_count_lock = threading.Lock()
    th.thread_count_lock = threading.Lock()
    th.file_lock = threading.Lock() 
    th.load_lock = threading.Lock() 

def scan():
    while True:
        if th.thread_mode: th.load_lock.acquire()
        if th.target.qsize() > 0 and th.is_continue: 
            payload = str(th.target.get(timeout=1.0))
            if th.thread_mode: th.load_lock.release() 
        else:
            if th.thread_mode:th.load_lock.release() 
            break
        try:
            status = th.module_obj.poc(payload) 
            resultHandler(status, payload) 
        except Exception:
            th.errmsg = traceback.format_exc()
            th.is_continue = False
        # set scanned count + 1
        changeScanCount(1) 
    # set running thread -1
    changeThreadCount(-1) # 

def run():
    initEngine()
    if th.thread_mode:
        # set lock for multi_threaded mode   
        setThreadLock() 
        outputscreen.success('[+] Set working way Multi-Threaded mode')
        for i in range(th.thread_num): 
            t = threading.Thread(target=scan, name=str(i))
            t.setDaemon(True)
            t.start()
        # It can quit with Ctrl-C
        while th.thread_count > 0 and th.is_continue:
                time.sleep(0.01)

    # Coroutine mode
    else:
        outputscreen.success('[+] Set working way Coroutine mode')
        #while th.target.qsize() > 0 and th.is_continue:
        gevent.joinall([gevent.spawn(scan) for i in range(0, th.thread_num)])


    # save result to output file
    if not th.no_output:
        output2file(th.result) 
    printProgress()
    if 'errmsg' in th:
        outputscreen.error(th.errmsg)

def resultHandler(status, payload):
    if th.thread_mode: th.output_screen_lock.acquire()
    sys.stdout.write(payload + " "*(th.console_width-len(payload)) + "\r")
    sys.stdout.flush()
    if th.thread_mode: th.output_screen_lock.release()
    if not status or status is POC_RESULT_STATUS.FAIL:
        return 
    # try again 
    elif status is POC_RESULT_STATUS.RETRAY:
        changeScanCount(-1) 
        th.target.put(payload) 
        return
    # vulnerable
    elif status is True or status is POC_RESULT_STATUS.SUCCESS:
        msg = '[+] ' + payload
        if th.thread_mode: th.output_screen_lock.acquire()
        outputscreen.info(msg) # 成功了
        if th.thread_mode: th.output_screen_lock.release()
        th.result.append(payload)
    else:
        msg = str(status)
        if th.thread_mode: th.output_screen_lock.acquire()
        outputscreen.info(msg)
        if th.thread_mode: th.output_screen_lock.release()
        th.result.append(msg)

    # get found number of payload +1
    changeFoundCount(1) 

    # if result list is too large, save it to file and empty list
    if len(th.result) > 5000:
        if not th.no_output:
            output2file(th.result) 
            th.result = []

def changeScanCount(num): 
    if th.thread_mode: th.scan_count_lock.acquire()
    th.scan_count += num
    if th.thread_mode: th.scan_count_lock.release()

def output2file(msg): 
    if th.thread_mode: th.file_lock.acquire()
    f = open(th.output_path, 'a')
    for res in msg:
        f.write(res + '\n')
    f.close()
    if th.thread_mode: th.file_lock.release()

def changeFoundCount(num):
    if th.thread_mode: th.found_count_lock.acquire()
    th.found_count += num
    if th.thread_mode: th.found_count_lock.release()

def changeThreadCount(num): 
    if th.thread_mode: th.thread_count_lock.acquire()
    th.thread_count += num
    if th.thread_mode: th.thread_count_lock.release()

def printProgress(): 
    msg = '%s found | %s remaining | %s scanned in %.2f seconds' % (
        th.found_count, th.target.qsize(), th.scan_count, time.time() - th.start_time)
    out = '\r' + ' ' * (th.console_width - len(msg)) + msg
    outputscreen.blue(out)