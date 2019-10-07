resources/bin/pd-ctl -u http://$PD -d region --jq=".regions[] | {id: .id, start: .start_key, end: .end_key, peer_stores: [.peers[].store_id], leader: .leader.store_id}"
resources/bin/pd-ctl -u http://$PD -d store --jq=".stores[].store | { id, address, state_name}"
resources/bin/pd-ctl -u http://$PD -d operator add transfer-peer 9 1 6
