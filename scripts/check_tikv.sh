#!/bin/bash
/home/worker/tidb-ansible/resources/bin/pd-ctl store -d -u http://10.120.195.1:2379 | egrep '(id|address|state_name)' | awk '{if(NR%3!=0)ORS=" "; else ORS="\n"}1' | sed 's/^[ \t]*//g'
