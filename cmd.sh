resources/bin/pd-ctl -u http://$PD -d region --jq=".regions[] | {id: .id, start: .start_key, end: .end_key, peer_stores: [.peers[].store_id], leader: .leader.store_id}"
resources/bin/pd-ctl -u http://$PD -d store --jq=".stores[].store | { id, address, state_name}"
resources/bin/pd-ctl -u http://$PD -d operator add transfer-peer 9 1 6


./resources/bin/proxy-ctl -pdaddr $PD getTableID
./resources/bin/proxy-ctl -pdaddr $PD createTable tableName tableID shardKey username
./resources/bin/proxy-ctl -pdaddr $PD setConfig tableID property1 value1 property2 value2 ...
./resources/bin/tikv-presplit --pd $PD --table-name $TABLENAME --shard-bits $SHARDBITS

