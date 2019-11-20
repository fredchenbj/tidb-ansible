resources/bin/pd-ctl -u $PD -d region --jq=".regions[] | {id: .id, start: .start_key, end: .end_key, peer_stores: [.peers[].store_id], leader: .leader.store_id}"
resources/bin/pd-ctl -u $PD -d store --jq=".stores[].store | { id, address, state_name}"
resources/bin/pd-ctl -u $PD -d operator add transfer-peer 9 1 6


./resources/bin/proxy-ctl -pdaddr $PD getTableID
./resources/bin/proxy-ctl -pdaddr $PD createTable tableName tableID shardKey username
./resources/bin/proxy-ctl -pdaddr $PD setConfig tableID property1 value1 property2 value2 ...
./resources/bin/tikv-presplit --pd $PD --table-id tableID --shard-bits $SHARDBITS

resources/bin/pd-ctl -u $PD -d store --jq=".stores[]| { id: .store.id, adress: .store.address, state: .store.state_name, leader_w: .status.leader_weight, region_w: .status.region_weight }"

## tikv_userprofile_new
PD=http://10.120.167.23:2379
## tikv_common_two
PD=http://10.136.163.3:2379

resources/bin/tikv-ctl --pd http://10.136.163.2:2379 compact-table -t 22DD0000 -s 2 -n 1
