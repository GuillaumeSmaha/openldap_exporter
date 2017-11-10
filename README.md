# Prometheus OpenLDAP Exporter

Export metrics from your [OpenLDAP](http://www.openldap.org/) servers
to your [Prometheus](http://prometheus.io) monitoring system.

## Prerequisites

You'll need a working OpenLDAP server, and a working Prometheus
server.  Setup and installation of those is left as an exercise to the
reader.

The exporter service is developed and tested using Python 2 and Python 3.
The dependencies [ldap3](https://github.com/cannatag/ldap3) and
[Twisted](http://twistedmatrix.com/trac/) are required.

## How it Works

The OpenLDAP exporter opens up a new LDAP connection to each OpenLDAP
server each time Prometheus scrapes the exporter. LDAP objects with
the ```structuralObjectClass```/```objectClass```  of ```monitorCounterObject``` or
```monitoredObject``` under the ```cn=Monitor``` base are searched
for. Any objects that are found that have data that can be converted
to a floating point number are exported as metrics with the object's
distinguished name as a label.

See the [OpenLDAP Manual](http://www.openldap.org/doc/admin24/monitoringslapd.html) for
more information on how OpenLDAP exposes performance metrics.


## Installation

```bash
git clone https://github.com/GuillaumeSmaha/openldap_exporter.git
cd openldap_exporter
virtualenv --python=/usr/bin/python2 /opt/openldap_exporter #or python3
/opt/openldap_exporter/bin/pip install --requirement requirements.txt
cp openldap_exporter.py /opt/openldap_exporter
cp openldap_exporter.yml /opt/openldap_exporter
vi /opt/openldap_exporter/openldap_exporter.yml
# edit configuration file
cp openldap_exporter.service /etc/systemd/system
systemctl daemon-reload
systemctl enable openldap_exporter
systemctl start openldap_exporter
```

## Configuration

### OpenLDAP

The OpenLDAP configuration needs to be modified to allow querying the
monitoring database over a remote connection. The following command should be run
on the OpenLDAP server:

```
# ldapmodify -Y EXTERNAL -H ldapi:// <<EOF
dn: olcDatabase={1}monitor,cn=config
changetype: modify
replace: olcAccess
olcAccess: to * by dn.base="gidNumber=0+uidNumber=0,cn=peercred,cn=external,cn=auth" read by dn.base="cn=Manager,dc=example,dc=com" read by * none
-
EOF
```

Replace ```cn=Manager,dc=example,dc=com``` with the distinguished name
of the user that you want to read the metrics with.

Consult the OpenLDAP manual for more information on configuring
OpenLDAP access lists.

### Exporter

The exporter is configured using command line options:

```
usage: openldap_exporter [-h] --config CONFIG

Prometheus OpenLDAP exporter

optional arguments:
  -h, --help       show this help message and exit
  --config CONFIG  configuration file
```

The configuration file is a YAML formatted file that looks like this:

```---
server_port: 9142
clients:
  - server_uri: ldap://127.0.0.1:389
    name: "MyLDAP"
    bind_dn: cn=monitor,dc=nodomain
    bind_pw: monitor
  - server_uri: ldap://172.17.0.3:389
    bind_dn: cn=monitor,dc=example,dc=org
    bind_pw: monitor
  - server_uri: ldaps://192.168.121.251:1636
    bind_dn: cn=directory manager,o=gluu
    bind_pw: ljHbH4vCrwNq
    validate_certs: False
  - server_uri: ldap://127.0.0.2:220
    name: "NoLdapServer"
    bind_dn: cn=monitor,dc=example,dc=org
    bind_pw: monitor

```

The options available for each client are:

 - **name**: Name to return in metrics result. By default, it's equal to **server_uri** parameter
 - **server_uri**: URI for the OpenLDAP server
 - **bind_dn**: A DN to bind with. If this is omitted, we'll try a SASL bind with the EXTERNAL mechanism. If this is blank, we'll use an anonymous bind.
 - **bind\_pw**: The password to use with I(bind_dn)
 - **start\_tls**: If true, we'll use the START_TLS LDAP extension.
 - **validate_certs**: If C(no), SSL certificates will not be validated. This should only be used on sites using self-signed certificates.
 - **timeout_connect**: Timeout in seconds for the connect operation
 - **timeout_receive**: Timeout in seconds for the receive operation


### Prometheus

Add a job to your Promethus configuration that looks like the following:

```
scrape_configs:
  - job_name: 'openldap'
    scrape_interval: 30s
    scrape_timeout: 10s
    target_groups:
      - targets:
        - 'localhost:9142'
```

## Example Output

```
openldap_up{server="MyLDAP"} 1
openldap_monitor_counter_object{server="MyLDAP",dn="cn=Max File Descriptors,cn=Connections,cn=Monitor"} 1024.0
openldap_monitor_counter_object{server="MyLDAP",dn="cn=Total,cn=Connections,cn=Monitor"} 1106.0
openldap_monitor_counter_object{server="MyLDAP",dn="cn=Current,cn=Connections,cn=Monitor"} 1.0
openldap_monitor_counter_object{server="MyLDAP",dn="cn=Bytes,cn=Statistics,cn=Monitor"} 6039246.0
openldap_monitor_counter_object{server="MyLDAP",dn="cn=PDU,cn=Statistics,cn=Monitor"} 3078.0
openldap_monitor_counter_object{server="MyLDAP",dn="cn=Entries,cn=Statistics,cn=Monitor"} 2746.0
openldap_monitor_counter_object{server="MyLDAP",dn="cn=Referrals,cn=Statistics,cn=Monitor"} 0.0
openldap_monitor_counter_object{server="MyLDAP",dn="cn=Read,cn=Waiters,cn=Monitor"} 1.0
openldap_monitor_counter_object{server="MyLDAP",dn="cn=Write,cn=Waiters,cn=Monitor"} 0.0
openldap_monitored_object{server="MyLDAP",dn="cn=Max,cn=Threads,cn=Monitor"} 16.0
openldap_monitored_object{server="MyLDAP",dn="cn=Max Pending,cn=Threads,cn=Monitor"} 0.0
openldap_monitored_object{server="MyLDAP",dn="cn=Open,cn=Threads,cn=Monitor"} 2.0
openldap_monitored_object{server="MyLDAP",dn="cn=Starting,cn=Threads,cn=Monitor"} 0.0
openldap_monitored_object{server="MyLDAP",dn="cn=Active,cn=Threads,cn=Monitor"} 1.0
openldap_monitored_object{server="MyLDAP",dn="cn=Pending,cn=Threads,cn=Monitor"} 0.0
openldap_monitored_object{server="MyLDAP",dn="cn=Backload,cn=Threads,cn=Monitor"} 1.0
openldap_monitored_object{server="MyLDAP",dn="cn=Uptime,cn=Time,cn=Monitor"} 270216.0
openldap_up{server="ldap://172.17.0.3:389"} 1
openldap_monitor_counter_object{server="ldap://172.17.0.3:389",dn="cn=Max File Descriptors,cn=Connections,cn=Monitor"} 1024.0
openldap_monitor_counter_object{server="ldap://172.17.0.3:389",dn="cn=Total,cn=Connections,cn=Monitor"} 1018.0
openldap_monitor_counter_object{server="ldap://172.17.0.3:389",dn="cn=Current,cn=Connections,cn=Monitor"} 1.0
openldap_monitor_counter_object{server="ldap://172.17.0.3:389",dn="cn=Bytes,cn=Statistics,cn=Monitor"} 3135565.0
openldap_monitor_counter_object{server="ldap://172.17.0.3:389",dn="cn=PDU,cn=Statistics,cn=Monitor"} 717.0
openldap_monitor_counter_object{server="ldap://172.17.0.3:389",dn="cn=Entries,cn=Statistics,cn=Monitor"} 648.0
openldap_monitor_counter_object{server="ldap://172.17.0.3:389",dn="cn=Referrals,cn=Statistics,cn=Monitor"} 0.0
openldap_monitor_counter_object{server="ldap://172.17.0.3:389",dn="cn=Read,cn=Waiters,cn=Monitor"} 1.0
openldap_monitor_counter_object{server="ldap://172.17.0.3:389",dn="cn=Write,cn=Waiters,cn=Monitor"} 0.0
openldap_monitored_object{server="ldap://172.17.0.3:389",dn="cn=Max,cn=Threads,cn=Monitor"} 16.0
openldap_monitored_object{server="ldap://172.17.0.3:389",dn="cn=Max Pending,cn=Threads,cn=Monitor"} 0.0
openldap_monitored_object{server="ldap://172.17.0.3:389",dn="cn=Open,cn=Threads,cn=Monitor"} 2.0
openldap_monitored_object{server="ldap://172.17.0.3:389",dn="cn=Starting,cn=Threads,cn=Monitor"} 0.0
openldap_monitored_object{server="ldap://172.17.0.3:389",dn="cn=Active,cn=Threads,cn=Monitor"} 1.0
openldap_monitored_object{server="ldap://172.17.0.3:389",dn="cn=Pending,cn=Threads,cn=Monitor"} 0.0
openldap_monitored_object{server="ldap://172.17.0.3:389",dn="cn=Backload,cn=Threads,cn=Monitor"} 1.0
openldap_monitored_object{server="ldap://172.17.0.3:389",dn="cn=Uptime,cn=Time,cn=Monitor"} 3459.0
openldap_up{server="ldaps://192.168.121.251:1636"} 1
openldap_monitor_counter_object{server="ldaps://192.168.121.251:1636",dn="cn=Max File Descriptors,cn=Connections,cn=Monitor"} 1024.0
openldap_monitor_counter_object{server="ldaps://192.168.121.251:1636",dn="cn=Total,cn=Connections,cn=Monitor"} 1024.0
openldap_monitor_counter_object{server="ldaps://192.168.121.251:1636",dn="cn=Current,cn=Connections,cn=Monitor"} 9.0
openldap_monitor_counter_object{server="ldaps://192.168.121.251:1636",dn="cn=Bytes,cn=Statistics,cn=Monitor"} 4786044.0
openldap_monitor_counter_object{server="ldaps://192.168.121.251:1636",dn="cn=PDU,cn=Statistics,cn=Monitor"} 5480.0
openldap_monitor_counter_object{server="ldaps://192.168.121.251:1636",dn="cn=Entries,cn=Statistics,cn=Monitor"} 4327.0
openldap_monitor_counter_object{server="ldaps://192.168.121.251:1636",dn="cn=Referrals,cn=Statistics,cn=Monitor"} 0.0
openldap_monitor_counter_object{server="ldaps://192.168.121.251:1636",dn="cn=Read,cn=Waiters,cn=Monitor"} 9.0
openldap_monitor_counter_object{server="ldaps://192.168.121.251:1636",dn="cn=Write,cn=Waiters,cn=Monitor"} 0.0
openldap_monitored_object{server="ldaps://192.168.121.251:1636",dn="cn=Max,cn=Threads,cn=Monitor"} 16.0
openldap_monitored_object{server="ldaps://192.168.121.251:1636",dn="cn=Max Pending,cn=Threads,cn=Monitor"} 0.0
openldap_monitored_object{server="ldaps://192.168.121.251:1636",dn="cn=Open,cn=Threads,cn=Monitor"} 3.0
openldap_monitored_object{server="ldaps://192.168.121.251:1636",dn="cn=Starting,cn=Threads,cn=Monitor"} 0.0
openldap_monitored_object{server="ldaps://192.168.121.251:1636",dn="cn=Active,cn=Threads,cn=Monitor"} 1.0
openldap_monitored_object{server="ldaps://192.168.121.251:1636",dn="cn=Pending,cn=Threads,cn=Monitor"} 0.0
openldap_monitored_object{server="ldaps://192.168.121.251:1636",dn="cn=Backload,cn=Threads,cn=Monitor"} 1.0
openldap_monitored_object{server="ldaps://192.168.121.251:1636",dn="cn=Uptime,cn=Time,cn=Monitor"} 3264.0
openldap_up{server="NoLdapServer"} 0
```
