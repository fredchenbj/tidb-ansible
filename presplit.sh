#!/bin/bash

if [ $# -lt 1 ];
then
    >&2 echo "usage $0 <pd> <table-name> <shard-bits> [username]"
	exit 1
fi

PD=$1
TABLENAME=$2
SHARDBITS=$3
USERNAME="TiKV"

if [ $# -gt 3 ];
then
	USERNAME=$4
fi

./resourse/bin/proxy-ctl -pdaddr $PD createTable $TABLENAME $SHARDBITS $USERNAME

./resourse/bin/tikv-presplit --pd $PD --table-name $TABLENAME --shard-bits $SHARDBITS
