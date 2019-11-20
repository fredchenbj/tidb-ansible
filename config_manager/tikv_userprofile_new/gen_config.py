import os
import sys
import configparser

metaconfig = configparser.ConfigParser()
metaconfigfile = "meta.ini"
metaconfig.read(metaconfigfile)

config = configparser.ConfigParser()
configfile = "inventory.ini.template"
config.read(configfile)

pd_baseport = int(metaconfig.get('common', 'pd_baseport'))
tikv_baseport = int(metaconfig.get('common', 'tikv_baseport'))
tikv_status_baseport = int(metaconfig.get('common', 'tikv_status_baseport'))
proxy_baseport = int(metaconfig.get('common', 'proxy_baseport'))
node_exporter_baseport = int(metaconfig.get('common', 'node_exporter_baseport'))
black_exporter_baseport = node_exporter_baseport + 15

prometheus_baseport = int(metaconfig.get('common', 'prometheus_baseport'))
pushgateway_baseport = prometheus_baseport + 1
grafana_baseport = int(metaconfig.get('common', 'grafana_baseport'))
alertmanager_baseport = int(metaconfig.get('common', 'alertmanager_baseport'))

offset_unit = int(metaconfig.get('common', 'offset_unit'))


name = metaconfig.get('cluster', 'name')
offset = int(metaconfig.get('cluster', 'offset'))

config.set('pd_servers:vars', 'pd_client_port', str(pd_baseport + offset_unit * offset))
config.set('pd_servers:vars', 'pd_peer_port', str(pd_baseport + 1 + offset_unit * offset))

config.set('proxy_servers:vars', 'proxy_port', str(proxy_baseport + offset_unit * offset))
config.set('grafana_servers:vars', 'grafana_port', str(grafana_baseport + offset_unit * offset))

config.set('alertmanager_servers:vars', 'alertmanager_port', str(alertmanager_baseport + offset_unit * offset))
config.set('alertmanager_servers:vars', 'alertmanager_cluster_port', str(alertmanager_baseport + 1 + offset_unit * offset))

config.set('monitoring_servers:vars', 'prometheus_port', str(prometheus_baseport + offset_unit * offset))
config.set('monitoring_servers:vars', 'pushgateway_port', str(prometheus_baseport + 1 + offset_unit * offset))

config.set('monitored_servers:vars', 'node_exporter_port', str(node_exporter_baseport + offset_unit * offset))
config.set('monitored_servers:vars', 'blackbox_exporter_port', str(node_exporter_baseport + 15 + offset_unit * offset))

config.set('all:vars', 'deploy_dir', "/home/worker/tikv/{0}".format(name))
config.set('all:vars', 'cluster_name', name)

hostlist = metaconfig.options('hosts')
# print hostlist

empty_string = "EMPTYEMPTYEMPTY"
length = len(hostlist)

for i in hostlist[0:3]:
	config.set('pd_servers', i, empty_string)
for i in hostlist:
	config.set('proxy_servers', i, empty_string)
	config.set('monitored_servers', i, empty_string)
	
config.set('monitoring_servers', hostlist[0], empty_string)
config.set('alertmanager_servers', hostlist[1], empty_string)
config.set('grafana_servers', hostlist[length-offset-1], empty_string)

id = 1
tikv_strings = ""
for host in hostlist:
	ssd_num = int(metaconfig.get('hosts', host))
	for ssd_id in range(1, ssd_num+1):
		tikv_strings = "{6}TiKV{0}-{1} ansible_host={2} deploy_dir=/ssd{1}/tikv/{3} tikv_port={4} tikv_status_port={5} labels=\"host={2}\"ABCXYZ".format(id, ssd_id, host, name, tikv_baseport + ssd_id, tikv_status_baseport + ssd_id, tikv_strings)
	
	id = id + 1

file = '.tikv.config'
if os.path.exists(file):
	os.remove(file)
with open(file, 'w') as fd:
	fd.write(tikv_strings)
	fd.close()

host_file = "host.ini"
inventory_file = "inventory.ini.new"

with open(inventory_file, 'w') as configfile:
	config.write(configfile)
	configfile.close()
with open(host_file, 'w') as hostconfigfile:
	hostconfigfile.write('[servers]\n')
	for host in hostlist:
		hostconfigfile.write('{0}\n'.format(host))
	hostconfigfile.write('\n')
	hostconfigfile.write('[all:vars]\n')
	hostconfigfile.write('username = worker\n')
	hostconfigfile.write('ntp_server = ntpc1-1.yidian.com\n')

os.system('sh gen_config.sh')
os.remove(inventory_file)
os.remove(file)
