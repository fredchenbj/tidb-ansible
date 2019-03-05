#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2016, Yidian Inc. All rights reserved.
# Author: yangjinfeng(yangjinfeng@yidian-inc.com).
#
import sys
import re
import os
import time
import json
import threading
import Queue
import httplib
import signal
import gzip
import shutil
import random
import copy
import traceback
import datetime
from multiprocessing import Process
from multiprocessing import Value
from multiprocessing import Queue
from Queue import Empty
import subprocess
import select
import inspect
import ctypes

class Snapshot:
    def __init__(self, values=list):
        self.values = values
        self.values.sort()
    def GetValue(self, quantile):
        if quantile >= 0.0 and quantile <= 1.0:
            if len(self.values) == 0:
                return 0.0
            else:
                pos = quantile * len(self.values) + 1
                if pos < 1.0:
                    return self.values[0]
                elif pos >= len(self.values):
                    return self.values[-1]
                else:
                    lower = self.values[int(pos) - 1]
                    upper = self.values[int(pos)]
                    return lower + (pos - int(pos)) * (upper - lower)

class Reservoir:
    def __init__(self, size=1028):
        self.count = 0
        self.size = size
        self.values = []

    def Size(self):
        return len(self.values)

    def NextInt(self, count):
        while True:
            bits = random.randint(0, 0xffffffffffffffff) & 9223372036854775807L
            val = bits % count
            if bits - val + count - 1L >= 0L:
                break
        return val

    def Update(self, value):
        self.count += 1
        if self.count < self.size:
            self.values.append(value)
        else:
            val = self.NextInt(self.count)
            if val < len(self.values):
                self.values[int(val)] = value

    def GetSnapshot(self):
        return Snapshot(copy.deepcopy(self.values))

class GZipper:
    def __init__(self, the_log_path, retain_days):
        self.log_path = the_log_path
        self.retain_days = retain_days
        self.pattern2 = re.compile(r'.*gz$')
        self.pattern1 = re.compile(r'^morpheus.*\.log\.INFO\.(.*?)\.(.*)')

    def GZip(self):
        candidate_files = os.listdir(self.log_path)
        files = []
        for f in candidate_files:
            match_result1 = self.pattern1.match(f)
            match_result2 = self.pattern2.match(f)
            #print "process file: " + f
            if match_result1:
                #print "match_result1: " + f
                date_time = match_result1.group(1)
                t = time.strptime(date_time, "%Y%m%d-%H%M%S")
                if match_result2:
                    if time.mktime(t) < time.time() - self.retain_days*6*3600:
                        #print "remove file: " + f
                        os.remove(self.log_path + os.sep + f)
                    #else:
                        #print "reserve file: " + f
                else:
                    the_date = time.strftime("%Y%m%d", t)
                    files.append([f, time.mktime(t), the_date])

        if len(files) < 2:
            return # no new file generated

        current_file = ""
        t = 0.0
        for f in files:
            if f[1] > t:
                t = f[1]
                current_file = f[0]
        today = time.strftime("%Y%m%d")
        print "current_file: " + current_file
        for f in files:
            if f[0] != current_file: # do not zip the current log file
                with open(self.log_path + os.sep + f[0], "rb") as f_in, gzip.open(self.log_path + os.sep + f[0] + ".gz", "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
 
                os.unlink(self.log_path + os.sep + f[0])

# get json string from a blocking queue, and send it to the tsdb server
class TSDBSender:
    def __init__(self, the_monitor_server, the_log_path):
        self.monitor_server = the_monitor_server
        self.log_path = the_log_path
        self.deque = Queue()
        self.deque_mutex = threading.Lock()


class StatisticData:
    def __init__(self, length):
        self.get_reservior = Reservoir(length)
        self.set_cnt = 0
        self.set_row_cnt = 0
        self.input_load = 0
        self.get_cnt = 0
        self.row_cnt = 0
        self.out_cnt = 0
        self.ret_err_cnt = 0
        self.output_load = 0
        self.get_time_cost = 0
        self.set_time_cost = 0
        self.qps = 0
        self.ups = 0
        self.eps = 0
        self.input_load = 0
        self.output_load = 0
        
# monitor the performance log file
class PerformanceMonitor:
    def BuildMetric(self, metric, timestamp, value):
        result = {}
        result["metric"] = "morpheus_" + self.service_name + "_" + metric
        result["timestamp"] = timestamp
        result["tags"] = {"host": self.host + "_" + self.port}
        result["value"] = value
        return result

    def BuildMetricWithTable(self, metric, timestamp, value, table):
        result = {}
        result["metric"] = "morpheus_" + self.service_name + "_" + metric
        result["timestamp"] = timestamp
        result["tags"] = {"host": self.host + "_" + self.port, "table": table}
        result["value"] = value
        return result

    def __init__(self, the_service_name, the_log_path, the_host, the_port):
        self.service_name = the_service_name
        self.host = the_host
        self.port = the_port
        self.log_path = the_log_path
        self.buffer = []
        self.buffer_mutex = threading.Lock()
        self.stop_cond = threading.Condition()

    # just get one line of performance log, and put it into the buffer
    def MorpheusTailLogFile(self, log_file):
        #global buffer, buffer_mutex
        global log_processor_stop
        f = subprocess.Popen(['tail','-F',log_file], stdout=subprocess.PIPE)
        while log_processor_stop.value != 1:
            try:
                n = 0;
                count = 0
                while log_processor_stop.value != 1:
                    lines = f.stdout.readlines(1)

                    for i in range(0, len(lines)):
                        line = lines[i]
                        if line.find("table=default") >= 0 or line.find("table=_status_") >=0:
                            continue
                        if line == '':
                            count += 1
                            if count < 100:
                                time.sleep(0.01)
                                continue
                            else:
                                break
                        count = 0
                        item = {}
                        n += 1;
                        if n % 1000000 == 1: 
                            print "[NOW: " + time.strftime("%Y-%m-%d %H:%M:%S") + "] line: " + line
                            print "buffer.size: %d" % len(self.buffer)
                        try:
                            uinits=re.split(" +", line, 5);
                            if len(uinits) > 5:
                              operation=uinits[4].lower()
                              sub_uinits = uinits[5].split(" ");
                              if operation == "[get]":
                                  item["type"] = "get"
                                  item["table"] = re.split("=|,", sub_uinits[0])[1]
                                  #print "table: " + item["table"]
                                  item["row_cnt"] = long(re.split("=|,", sub_uinits[1])[1])
                                  item["out_cnt"] = long(re.split("=|,", sub_uinits[2])[1]);
                                  item["data_size"] = long(re.split("=|,", sub_uinits[3])[1]);
                                  item["ret"] = long(re.split("=|,", sub_uinits[4])[1]);
                                  item["time"] = long(round(float(re.split("=|,|µ", sub_uinits[5])[1])));
                              elif operation == "[put]" or operation =="[update]":
                                  item["type"] = "set"
                                  item["table"] = re.split("=|,", sub_uinits[0])[1]
                                  item["row_cnt"] = long(re.split("=|,", sub_uinits[1])[1])
                                  item["data_size"] = long(re.split("=|,", sub_uinits[3])[1]);
                                  item["ret"] = long(re.split("=|,", sub_uinits[4])[1]);
                                  item["time"] = long(round(float(re.split("=|,|µ", sub_uinits[5])[1])));
                              elif operation == "[readtotalcost]":
                                  item["type"] = "readtotal"
                                  item["time"] = long(re.split("=", sub_uinits[0])[1]);
                              elif operation == "[readtaskcost]":
                                  item["type"] = "readtask"
                                  item["time"] = long(re.split("=", sub_uinits[0])[1]);
               
                            if item:
                                self.buffer_mutex.acquire()
                                self.buffer.append(item)
                                self.buffer_mutex.release()
                        except:
                            print traceback.print_exc()
                            #print "process line failed. line: %s" % line
                            pass

            except:
                print traceback.print_exc()
                print 'process log file: ', log_file, 'failed'


    def NotifyStop(self):
        try:
            self.stop_cond.acquire() 
            self.stop_cond.notify()
        finally:
            self.stop_cond.release() 

    # get all performance logs from buffer every 60 seconds, and compute the qps, average latency, ups, hit rate and so on,
    # then give the json string to TSDBSender to send to the tsdb server
    def MorpheusSummarize(self):
        global log_processor_stop
        while True:
            try:
                self.stop_cond.acquire() 
                self.stop_cond.wait(60) 
            finally:
                self.stop_cond.release() 
            if log_processor_stop.value == 1:
                return

            now = long(time.time())

            self.buffer_mutex.acquire()
            exchanged_buffer = self.buffer
            self.buffer = []
            self.buffer_mutex.release()

            data_map = {}

            #get_reservior = Reservoir(len(exchanged_buffer))
            readtotal_reservior = Reservoir(len(exchanged_buffer))
            readtask_reservior = Reservoir(len(exchanged_buffer))
            readtotal_count = 0
            readtask_count = 0
            #set_cnt = 0
            #set_row_cnt = 0
            #input_load = 0
            #get_cnt = 0
            #row_cnt = 0
            #out_cnt = 0
            #ret_err_cnt = 0
            #output_load = 0
            readtotal_time_cost = 0
            readtask_time_cost = 0
            #get_time_cost = 0
            #set_time_cost = 0

            print("item length: %d" % (len(exchanged_buffer)))
            length = len(exchanged_buffer)
            try:
                for item in exchanged_buffer:
                    if item["type"] == "get":
                        table = item["table"]
                        #print "table 1: " + table
                        if table not in data_map:
                            data = StatisticData(length)
                            data_map[table] = data
                        else:
                            data = data_map[table]
                        data.row_cnt += item["row_cnt"]
                        data.out_cnt += item["out_cnt"]
                        data.output_load += item["data_size"]
                        data.get_time_cost += item["time"]
                        data.get_cnt += 1
                        data.get_reservior.Update(item["time"])
                        if item["ret"] != 0:
                          data.ret_err_cnt += 1
                    elif item["type"] == "set":
                        table = item["table"]
                        if table not in data_map:
                            data = StatisticData(length)
                            data_map[table] = data
                        else:
                            data = data_map[table]
                        data.set_cnt += 1
                        data.set_row_cnt += item["row_cnt"]
                        data.input_load += item["data_size"]
                        data.set_time_cost += item["time"]
                        if item["ret"] != 0:
                          data.ret_err_cnt += 1
                    elif item["type"] == "readtotal":
                        readtotal_count += 1
                        readtotal_time_cost += item["time"]
                        readtotal_reservior.Update(item["time"])
                    elif item["type"] == "readtask":
                        readtask_count += 1
                        readtask_time_cost += item["time"]
                        readtask_reservior.Update(item["time"])
                #qps = float(get_cnt) / 60.0
                #ups = float(set_row_cnt) / 60.0
                #eps = float(ret_err_cnt) / 60.0
                #input_load = float(input_load) / 60.0
                #output_load = float(output_load) / 60.0
                #print("get: %d set: %d set_row: %d" % (get_cnt, set_cnt, set_row_cnt))
               
                print "data_map size: " + str(len(data_map))
                for table in data_map:
                    #print "table: " + table
                    data = data_map[table]

                    data.qps = float(data.get_cnt) / 60.0
                    data.ups = float(data.set_row_cnt) / 60.0
                    data.eps = float(data.ret_err_cnt) / 60.0
                    data.input_load = float(data.input_load) / 60.0
                    data.output_load = float(data.output_load) / 60.0

                    if data.row_cnt > 0:
                        data.hit_rate = "%.2f" % ((float(data.out_cnt) / float(data.row_cnt)) * 100.0) # in percent
                    else:
                        data.hit_rate = "0.00"
                    if data.get_cnt > 0:
                        data.get_latency = data.get_time_cost / data.get_cnt # in microseconds
                    else:
                        data.get_latency = 0
                    if data.set_cnt > 0:
                        data.set_latency = data.set_time_cost / data.set_cnt # in microseconds
                    else:
                        data.set_latency = 0

                    #print("qps: %d ups: %d" % (qps, ups))

                    request_body = []
                    request_body.append(self.BuildMetricWithTable("qps", now, float("%.2f" % data.qps), table))
                    request_body.append(self.BuildMetricWithTable("output_load", now, data.output_load, table))
                    request_body.append(self.BuildMetricWithTable("input_load", now, data.input_load, table))
                    request_body.append(self.BuildMetricWithTable("hit_rate", now, float(data.hit_rate), table))
                    request_body.append(self.BuildMetricWithTable("ups", now, float("%.2f" % data.ups), table))
                    request_body.append(self.BuildMetricWithTable("eps", now, float("%.2f" % data.eps), table))
                    request_body.append(self.BuildMetricWithTable("update_latency", now, data.set_latency, table))
                    request_body.append(self.BuildMetricWithTable("get_latency", now, data.get_latency, table))
                    get_snapshot = data.get_reservior.GetSnapshot()
                    request_body.append(self.BuildMetricWithTable("get_p99latency", now, get_snapshot.GetValue(0.99), table))
                    request_body.append(self.BuildMetricWithTable("get_p999latency", now, get_snapshot.GetValue(0.999), table))

                    try:
                        str_request_body = json.dumps(request_body)
                        #print "body: " + str_request_body
                        SendToTSDB(str_request_body);
                    except SystemExit:
                        raise
                    except:
                        print traceback.print_exc()
                        print 'json serialize failed'

                if readtotal_count > 0:
                    readtotal_latency = readtotal_time_cost / readtotal_count
                else:
                    readtotal_latency = 0
                if readtask_count > 0:
                    readtask_latency = readtask_time_cost / readtask_count
                else:
                    readtask_latency = 0

                request_body = []
                request_body.append(self.BuildMetric("read_total_latency", now, readtotal_latency))
                readtotal_snapshot = readtotal_reservior.GetSnapshot()
                request_body.append(self.BuildMetric("read_total_p99latency", now, readtotal_snapshot.GetValue(0.99)))
                request_body.append(self.BuildMetric("read_total_p999latency", now, readtotal_snapshot.GetValue(0.999)))
                request_body.append(self.BuildMetric("read_task_latency", now, readtask_latency))
                readtask_snapshot = readtask_reservior.GetSnapshot()
                request_body.append(self.BuildMetric("read_task_p99latency", now, readtask_snapshot.GetValue(0.99)))
                request_body.append(self.BuildMetric("read_task_p999latency", now, readtask_snapshot.GetValue(0.999)))

            except:
                print traceback.print_exc()

            try:
                str_request_body = json.dumps(request_body)
                SendToTSDB(str_request_body);
            except SystemExit:
                raise
            except:
                print traceback.print_exc()
                print 'json serialize failed'

# monitor the rocksdb log file
class RocksDBLogMonitor:
    def __init__(self, the_service_name, the_log_path, the_host, the_port, the_tsdb_sender):
        self.service_name = the_service_name
        self.host = the_host
        self.port = the_port
        self.log_path = the_log_path
        self.tsdb_sender = the_tsdb_sender
        self.pattern_for_cumulative_compaction = re.compile(r'Cumulative compaction: (.*)')
        self.pattern_for_interval_compaction = re.compile(r'Interval compaction: (.*)')
        self.pattern_for_compaction_started = re.compile(r'.*EVENT_LOG_v1 (.*compaction_started.*)')
        self.pattern_for_compaction_finished = re.compile(r'.*EVENT_LOG_v1 (.*compaction_finished.*)')
        self.pattern_for_flush_started = re.compile(r'.*EVENT_LOG_v1 (.*flush_started.*)')
        self.pattern_for_flush_finished = re.compile(r'.*EVENT_LOG_v1 (.*flush_finished.*)')

    def ProcessCompactionSummary(self, log_file, line):
        match_result = self.pattern_for_cumulative_compaction.match(line)
        if match_result:
            self.DoProcessCompactionSummary(log_file, match_result.group(1), 'cumulative')
        else:
            match_result = self.pattern_for_interval_compaction.match(line)
            if match_result:
                self.DoProcessCompactionSummary(log_file, match_result.group(1), 'interval')

    def DoProcessCompactionSummary(self, log_file, summary, summary_type):
        summary_fields = summary.split(', ')
        if len(summary_fields) != 5:
            return False
        write_bytes = summary_fields[0].split()
        write_byte = float(write_bytes[0])
        if write_bytes[1] == 'GB':
            write_byte = long(write_byte * 1024L * 1024 * 1024)
        elif write_bytes[1] == 'MB':
            write_byte = long(write_byte * 1024L * 1024)
        elif write_bytes[1] == 'KB':
            write_byte = long(write_byte * 1024L)

        write_rates = summary_fields[1].split()
        write_rate = float(write_rates[0])
        if write_rates[1] == 'MB/s':
            write_rate = long(write_rate * 1024L * 1024)
        elif write_rates[1] == 'KB/s':
            write_rate = long(write_rate * 1024L)
        elif write_rates[1] == 'GB/s':
            write_rate = long(write_rate * 1024L * 1024 * 1024)

        read_bytes = summary_fields[2].split()
        read_byte = float(read_bytes[0])
        if read_bytes[1] == 'GB':
            read_byte = long(read_byte * 1024L * 1024 * 1024)
        elif read_bytes[1] == 'MB':
            read_byte = long(read_byte * 1024L * 1024)
        elif read_bytes[1] == 'KB':
            read_byte = long(read_byte * 1024L)

        read_rates = summary_fields[3].split()
        read_rate = float(read_rates[0])
        if read_rates[1] == 'MB/s':
            read_rate = long(read_rate * 1024L * 1024)
        elif read_rates[1] == 'KB/s':
            read_rate = long(read_rate * 1024L)
        elif read_rates[1] == 'GB/s':
            read_rate = long(read_rate * 1024L * 1024 * 1024)

        time_costs = summary_fields[4].split()
        time_cost = float(time_costs[0])
        time_cost = long(time_cost * 1000000L)  # us

        request_body = [{}, {}]
        request_body[0]["timestamp"] = time.time()
        request_body[1]["timestamp"] = time.time()
        request_body[0]["metric"] = "morpheus_" + self.service_name + "_rocksdb_log_" + summary_type + "_compaction_rate_summary"
        request_body[1]["metric"] = "morpheus_" + self.service_name + "_rocksdb_log_" + summary_type + "_compaction_rate_summary"
        request_body[0]["value"] = write_rate
        request_body[1]["value"] = read_rate
        request_body[0]["tags"] = {"type": "write", "host": self.host + "_" + self.port}
        request_body[1]["tags"] = {"type": "read", "host": self.host + "_" + self.port}
        try:
            str_request_body = json.dumps(request_body)
            SendToTSDB(str_request_body)
        except SystemExit:
            raise
        except:
            print 'json serialize failed'

        return True

    def ProcessCompactionEvent(self, log_file, line, jobs):
        match_result = self.pattern_for_compaction_started.match(line)
        if match_result:
            self.ProcessCompactionStarted(log_file, match_result.group(1), jobs)
        else:
            match_result = self.pattern_for_compaction_finished.match(line)
            if match_result:
                self.ProcessCompactionFinished(log_file, match_result.group(1), jobs)

    def ProcessCompactionStarted(self, log_file, str_event, jobs):
        try:
            json_event = json.loads(str_event)
            job_nr = json_event["job"]
            time_micros = json_event["time_micros"]
            input_data_size = json_event["input_data_size"]
            if job_nr in jobs:
                return True
            jobs[job_nr] = [time_micros, input_data_size, str_event]
            return True
        except SystemExit:
            raise
        except:
            print "started except"
            return False

    def ProcessCompactionFinished(self, log_file, str_event, jobs):
        try:
            json_event = json.loads(str_event)
            job_nr = json_event["job"]
            time_micros = json_event["time_micros"]
            if job_nr not in jobs:
                return True
            time_cost = time_micros - jobs[job_nr][0]
            request_body = {}
            request_body["metric"] = "morpheus_" + self.service_name + "_rocksdb_log"
            request_body["timestamp"] = jobs[job_nr][0] / 1000000
            request_body["value"] = time_cost / 1000.0
            request_body["tags"] = {"type": 'compaction',
                                    "host": self.host + "_" + self.port}
            jobs.pop(job_nr)
            try:
                str_request_body = json.dumps(request_body)
                SendToTSDB(str_request_body)
            except SystemExit:
                raise
            except:
                print 'json serialize failed'
                return True
        except SystemExit:
            raise
        except:
            print "finished except"
            return False

    def ProcessFlushEvent(self, log_file, line, jobs):
        match_result = self.pattern_for_flush_started.match(line)
        if match_result:
            self.ProcessFlushStarted(log_file, match_result.group(1), jobs)
        else:
            match_result = self.pattern_for_flush_finished.match(line)
            if match_result:
                self.ProcessFlushFinished(log_file, match_result.group(1), jobs)

    def ProcessFlushStarted(self, log_file, str_event, jobs):
        try:
            json_event = json.loads(str_event)
            job_nr = json_event["job"]
            time_micros = json_event["time_micros"]
            num_memtables = json_event["num_memtables"]
            if job_nr in jobs:
                return True
            jobs[job_nr] = [time_micros, num_memtables, str_event]
            return True
        except SystemExit:
            raise
        except:
            return False

    def ProcessFlushFinished(self, log_file, str_event, jobs):
        try:
            json_event = json.loads(str_event)
            job_nr = json_event["job"]
            time_micros = json_event["time_micros"]
            if job_nr not in jobs:
                return True
            time_cost = time_micros - jobs[job_nr][0]
            request_body = {}
            request_body["metric"] = "morpheus_" + self.service_name + "_rocksdb_log"
            request_body["timestamp"] = jobs[job_nr][0] / 1000000
            request_body["value"] = time_cost / 1000.0
            request_body["tags"] = {"type": 'flush',
                                    "host": self.host + "_" + self.port}
            try:
                str_request_body = json.dumps(request_body)
                SendToTSDB(str_request_body)
            except SystemExit:
                raise
            except:
                print 'json serialize failed'
                return True
            return True
        except SystemExit:
            raise
        except:
            return False

    def ProcessEachLogFile(self, log_file):
        while True:
            jobs = {}
            with open(log_file, "a+") as fd:
                try:
                    fd.seek(0, os.SEEK_END)
                    count = 0
                    while True:
                        line = fd.readline()
                        if line == '':
                            count += 1
                            if count < 360000:
                                time.sleep(0.01)
                                continue
                            else:
                                break
                        count = 0
                        if self.ProcessCompactionEvent(log_file, line, jobs) or \
                                self.ProcessFlushEvent(log_file, line, jobs) or \
                                self.ProcessCompactionSummary(log_file, line):
                            continue
                except SystemExit:
                    raise
                except:
                    print 'process log file: ', log_file, 'failed'

def SendToTSDBWrapper(tsdb_sender):
    tsdb_sender.Send()

def SummarizeWrapper(performance_monitor):
    print "Summarize start"
    try:
        performance_monitor.MorpheusSummarize()
    except:
        pass
    print "Summarize exit"

def TailLogFileWrapper(performance_monitor, file_path):
    performance_monitor.MorpheusTailLogFile(file_path)

def ProcessEachLogFileWrapper(rocksdb_log_monitor, log_file):
    #print "ProcessEachLogFile start"
    try:
        rocksdb_log_monitor.ProcessEachLogFile(log_file)
    except:
        pass
    #print "ProcessEachLogFile exit"

def GZipProcess(log_path, retain_days):
    gzipper = GZipper(log_path, int(retain_days))
    gzipper_thread = threading.Thread(target=GZipWrapper, args=(gzipper,))
    gzipper_thread.start()
    while gzip_stop.value != 1:
        time.sleep(1)
    stop_thread(gzipper_thread);
    gzipper_thread.join()

def GZipWrapper(gzipper):
    print "Gzip start"
    try:
      while True:
          gzipper.GZip()
          time.sleep(60)
    except:
        pass
    print "Gzip exit"


tsdb_sender_queue = Queue(100000000)
log_processor_stop = Value('B', 0)
sender_stop = Value('B', 0)
gzip_stop = Value('B', 0)
threads = []

def SendToTSDB(metrics_json):
    global tsdb_sender_queue
    tsdb_sender_queue.put(metrics_json)

def ExitWrapper(signum, frame):
    Exit()

def Exit():
    print "Exit"
    log_processor_stop.value = 1
    sender_stop.value = 1
    gzip_stop.value = 1
    #stop_thread(gzipper_thread)
    for t in threads:
        stop_thread(t);

def stop_thread(thread):
    _async_raise(thread.ident, SystemExit)

def _async_raise(tid, exctype):
    """raises the exception, performs cleanup if needed"""
    tid = ctypes.c_long(tid)
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("invalid thread id")
    elif res != 1:
        # """if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"""
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")

def Main(service_name, log_path, retain_days, host, port):
    pid = os.getpid()
    with open(log_path + "/monitor.pid", 'w') as pid_fd:
        print >> pid_fd, pid

    global threads
    processes = []

    signal.signal(signal.SIGINT, ExitWrapper)
    signal.signal(signal.SIGTERM, ExitWrapper)

    try:
        # monitor performance log file
        pattern_for_log_file = re.compile(r'^proxy.log$')
        files = os.listdir(log_path)
        for f in files:
            match_result = pattern_for_log_file.match(f)
            if match_result:
                p = Process(target=MorpheusTailLogFileProcess, args=(service_name, host, port, log_path, log_path + os.sep + f))
                processes.append(p)
                break

        ## processes.append(Process(target=GZipProcess, args=(log_path, retain_days)))

        monitor_server="metrics-server.ha.in.yidian.com:4242"
        processes.append(Process(target=TSDBSenderProcess, args=(monitor_server, log_path)))

        # start all process
        for p in processes:
            original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
            p.daemon = True    # When a process exits, it attempts to terminate all of its daemonic child processes.
            p.start()
            signal.signal(signal.SIGINT, original_sigint_handler)

        # ------------ start threads ---------------------------
    
        ## monitor_server="metrics-server.ha.in.yidian.com:4242"
        ## tsdb_sender = TSDBSender(monitor_server, log_path)
    
       # rocksdb_log_monitor = RocksDBLogMonitor(service_name, log_path, host, port, tsdb_sender)
       # # monitor rocksdb log file
       # pattern_for_rocksdb_log_file = re.compile(r'ssd.*_LOG')
       # pattern_for_metadb_rocksdb_log_file = re.compile(r'.*meta.*')
       # files = os.listdir(log_path)
       # for f in files:
       #     match_result = pattern_for_rocksdb_log_file.match(f)
       #     if match_result:
       #         match_result = pattern_for_metadb_rocksdb_log_file.match(f)
       #         if not match_result:
       #             t = threading.Thread(target=ProcessEachLogFileWrapper,
       #                                  args=(rocksdb_log_monitor, log_path + os.sep + f,))
       #             threads.append(t)
    
       # # start all threads
       # for t in threads:
       #     #t.setDaemon(True)
       #     t.start()

        # wait until all process finished
        for p in processes:
            p.join()

    except KeyboardInterrupt:
        print("force stop")
        Exit()
        for p in processes:
            p.join()

def ClearQueue(queue):
    while not queue.empty():
        queue.get(True, 1)

def MorpheusTailLogFileProcess(service_name, host, port, log_path, log_file):
    print "MorpheusTailLogFile start"
    global log_processor_stop
    performance_monitor = PerformanceMonitor(service_name, log_path, host, port);

    summarize_thread = threading.Thread(target=SummarizeWrapper, args=(performance_monitor,))
    summarize_thread.start();

    performance_monitor.MorpheusTailLogFile(log_file)

    performance_monitor.NotifyStop()

    summarize_thread.join();
    print "MorpheusTailLogFile exit"

def TSDBSenderProcess(monitor_server, log_path):
    global tsdb_sender_queue, sender_stop
    print "TSDBSender start"
    try:
        while sender_stop.value != 1:
            try:
                str_request_body = tsdb_sender_queue.get(True, 1)
                #print str_request_body
                success = True
                try:
                    tsdb_handler = httplib.HTTPConnection(monitor_server, timeout=5)
                    request_headers = {"Content-type": "application/json"}
                    tsdb_handler.request("POST", "/api/put?details", str_request_body, request_headers)
                    status = tsdb_handler.getresponse().status
                    if status < 200 or status >= 300:
                        print 'send to tsdb failed, status is: ' + status
                        success = False
                except:
                    print 'send to tsdb failed'
                    success = False
                finally:
                    tsdb_handler.close()
                    if not success:
                        tsdb_sender_queue.put(str_request_body)
                    else:
                        with open(log_path + os.sep + 'monitor.log', 'a+') as log_fd:
                            print >> log_fd, time.strftime("%Y-%m-%d/%H:%M:%S"), str_request_body
            except Empty:
                pass
    except KeyboardInterrupt:
        pass
    ClearQueue(tsdb_sender_queue)
    print "TSDBSender exit"


if __name__ == "__main__":
    if len(sys.argv) < 6:
        print "usage: python monitor.py service_name log_path retain_days host port"
        exit(1)

    print "start"
    Main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
