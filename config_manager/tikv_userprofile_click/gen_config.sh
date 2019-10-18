#!/bin/bash

# id=1;
# cat /tmp/host.list | while read ip n; do 
# 	for j in $(seq 1 $n); do 
# 		port=$[20160+i];
# 		echo -e "TiKV$id-$j ansible_host=$ip deploy_dir=/ssd$j/tikv/pioneer/tikv-server tikv_port=$port labels=\\\"host=$ip\\\"ABCXYZ\c";
# 	done;
# 	id=$[id+1];
# done > .tikv.config

tikv_config=$(cat .tikv.config)

sed -e "s#zhangjizhiyanzhangzheshoufabueyi.*#$tikv_config#g" \
	-e "s/ABCXYZ/\n/g" \
	-e "s/ = EMPTYEMPTYEMPTY//g" inventory.ini.new > inventory.ini
