#!/bin/bash
## ./resources/bin/tikv-presplit --pd $PD --table-name "meta" --shard-bits 0
## ./resources/bin/tikv-presplit --pd $PD --table-name "6D657461" --shard-bits 0
if [ $# -lt 1 ];
then
	>&2 echo "usage $0 <pd> <table-name> <shard-bits(0~7)> [username]"
	exit 1
fi

PD=$1
TABLENAME=$2

if [ "$3" -gt 7 ] || [ "$3" -lt 0 ];
then 
	echo "shard-bits should between 0 and 7"
	exit 1
fi 
SHARDBITS=$3
USERNAME="TiKV"

if [ $# -gt 3 ];
then
	USERNAME=$4
fi

## ./resources/bin/proxy-ctl -pdaddr $PD createTable "test" 4 "cf"
## ./resources/bin/tikv-presplit --pd $PD --table-name "test" --shard-bits 4
./resources/bin/proxy-ctl -pdaddr $PD createTable $TABLENAME $SHARDBITS $USERNAME && ./resources/bin/tikv-presplit --pd $PD --table-name $TABLENAME --shard-bits $SHARDBITS
