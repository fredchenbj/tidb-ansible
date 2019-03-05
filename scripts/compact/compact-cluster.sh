#!/user/bin/env bash

# tikv_general_first
echo "compact tikv_general_first"
/ssd3/ChenFu/Git/tidb-ansible/resources/bin/tikv-ctl --pd 10.136.133.23:2379 compact-cluster -d kv --threads 1 1>>/tmp/compact.nohup 2>&1 

