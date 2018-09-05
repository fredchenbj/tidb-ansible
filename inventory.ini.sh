## TiDB Cluster Part
[tidb_servers]

[tikv_proxys]
10.120.195.4

[tikv_servers]
TiKV1-1 ansible_host=10.120.195.1 deploy_dir=/ssd1/deploy tikv_port=20171 labels="host=tikv1,disk=ssd"
TiKV1-2 ansible_host=10.120.195.1 deploy_dir=/ssd2/deploy tikv_port=20172 labels="host=tikv1,disk=ssd"
TiKV1-3 ansible_host=10.120.195.1 deploy_dir=/ssd3/deploy tikv_port=20173 labels="host=tikv1,disk=ssd"
TiKV1-4 ansible_host=10.120.195.1 deploy_dir=/ssd4/deploy tikv_port=20174 labels="host=tikv1,disk=ssd"
TiKV2-1 ansible_host=10.120.195.2 deploy_dir=/ssd1/deploy tikv_port=20171 labels="host=tikv2,disk=ssd"
TiKV2-2 ansible_host=10.120.195.2 deploy_dir=/ssd2/deploy tikv_port=20172 labels="host=tikv2,disk=ssd"
TiKV2-3 ansible_host=10.120.195.2 deploy_dir=/ssd3/deploy tikv_port=20173 labels="host=tikv2,disk=ssd"
TiKV2-4 ansible_host=10.120.195.2 deploy_dir=/ssd4/deploy tikv_port=20174 labels="host=tikv2,disk=ssd"
TiKV3-1 ansible_host=10.120.195.3 deploy_dir=/ssd1/deploy tikv_port=20171 labels="host=tikv3,disk=ssd"
TiKV3-2 ansible_host=10.120.195.3 deploy_dir=/ssd2/deploy tikv_port=20172 labels="host=tikv3,disk=ssd"
TiKV3-3 ansible_host=10.120.195.3 deploy_dir=/ssd3/deploy tikv_port=20173 labels="host=tikv3,disk=ssd"
TiKV3-4 ansible_host=10.120.195.3 deploy_dir=/ssd4/deploy tikv_port=20174 labels="host=tikv3,disk=ssd"


[pd_servers]
10.120.195.1
10.120.195.2
10.120.195.3

[spark_master]

[spark_slaves]

## Monitoring Part
# prometheus and pushgateway servers
[monitoring_servers]
10.120.195.4

[grafana_servers]
10.120.195.4

# node_exporter and blackbox_exporter servers
[monitored_servers]
10.120.195.1
10.120.195.2
10.120.195.3
10.120.195.4

[alertmanager_servers]
10.120.195.4

[kafka_exporter_servers]

## Binlog Part
# [pump_servers:children]
# tidb_servers

[drainer_servers]

## Group variables
[pd_servers:vars]
# location_labels = ["zone","rack","host"]
location_labels = ["host", "disk"]

## Global variables
[all:vars]
deploy_dir = /home/worker/deploy

## Connection
# ssh via normal user
ansible_user = worker

cluster_name = test-cluster

tidb_version = latest

# process supervision, [systemd, supervise]
process_supervision = systemd

# timezone of deployment region
timezone = Asia/Shanghai
set_timezone = True

enable_firewalld = False
# check NTP service
enable_ntpd = True
set_hostname = False
# CPU, memory and disk performance will not be checked when dev_mode = True
dev_mode = True

## binlog trigger
enable_binlog = False
# zookeeper address of kafka cluster for binlog, example:
# zookeeper_addrs = "192.168.0.11:2181,192.168.0.12:2181,192.168.0.13:2181"
zookeeper_addrs = ""
# kafka cluster address for monitoring, example:
# kafka_addrs = "192.168.0.11:9092,192.168.0.12:9092,192.168.0.13:9092"
kafka_addrs = ""

# store slow query log into seperate file
enable_slow_query_log = False

# enable TLS authentication in the TiDB cluster
enable_tls = False

# KV mode
deploy_without_tidb = True

# Optional: Set if you already have a alertmanager server.
# Format: alertmanager_host:alertmanager_port
alertmanager_target = ""

grafana_admin_user = "admin"
grafana_admin_password = "admin"


### Collect diagnosis
collect_log_recent_hours = 2

enable_bandwidth_limit = True
# default: 10Mb/s, unit: Kbit/s
collect_bandwidth_limit = 2500
