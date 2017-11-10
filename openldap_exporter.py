# -*- mode: python; coding: utf-8 -*-

import argparse
import sys
import yaml
import ssl

from twisted.internet import reactor
from twisted.internet.endpoints import serverFromString
from twisted.logger import Logger
from twisted.logger import globalLogBeginner
from twisted.logger import textFileLogObserver
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET
from twisted.web.server import Site
try:
    import ldap3
    from ldap3.core.exceptions import LDAPException

    HAS_LDAP3 = True
except ImportError:
    HAS_LDAP3 = False


__version__ = "1.0.0"

OPENLDAP_MONITOR_BASEDN = 'cn=Monitor'
OPENLDAP_MONITOR_FILTER = '(|({}=monitorCounterObject)({}=monitoredObject))'



class LdapEntries(object):
    def __init__(self, client):
        self._client = client
        self._server_uri = client.get('server_uri')
        self._bind_dn = client.get('bind_dn')
        self._bind_pw = client.get('bind_pw')
        self._start_tls = client.get('start_tls', False)
        self._validate_certs = client.get('validate_certs', True)
        self._timeout_connect = client.get('timeout_connect', 1)
        self._timeout_receive = client.get('timeout_receive', 1)

        self._connection = None

    def search_entry_by_dn(self, dn):
        """ Search with the dn and return it """
        if not self._connection:
            return None

        result = self._connection.search(
            dn,
            '',
            get_operational_attributes=True,
            search_scope=ldap3.SUBTREE,
            attributes=ldap3.ALL_ATTRIBUTES)

        if result:
            return self._connection.response

        return None

    def search_entries(self, search_base, search_filter):
        """ Search with the search_filter and return an array of entries """
        if not self._connection:
            return None

        result = self._connection.search(
            search_base,
            search_filter,
            get_operational_attributes=True,
            search_scope=ldap3.SUBTREE,
            attributes=ldap3.ALL_ATTRIBUTES)

        if result:
            return self._connection.response

        return None

    def close(self):
        if self._connection:
            self._connection.unbind()
            self._connection = None

    def connect(self):
        if self._connection:
            return self._connection

        if self._start_tls or self._server_uri.lower().startswith('ldaps://'):
            self._start_tls = True
            tls = None
            if self._validate_certs:
                tls = ldap3.Tls(validate=ssl.CERT_OPTIONAL)
            else:
                tls = ldap3.Tls(validate=ssl.CERT_NONE)

            try:
                server = ldap3.Server(self._server_uri, tls=tls, use_ssl=True, connect_timeout=self._timeout_connect)
            except LDAPException as e:
                raise LDAPException("Invalid parameter for LDAP server.", str(e))
        else:
            server = ldap3.Server(self._server_uri, connect_timeout=self._timeout_connect)

        try:
            if self._bind_dn:
                connection = ldap3.Connection(
                    server,
                    auto_bind=False,
                    receive_timeout=self._timeout_receive,
                    user=self._bind_dn,
                    password=self._bind_pw)
            else:
                connection = ldap3.Connection(
                    server,
                    auto_bind=False,
                    receive_timeout=self._timeout_receive,
                    authentication=ldap3.SASL,
                    sasl_mechanism='EXTERNAL',
                    sasl_credentials='')

            if self._start_tls:
                try:
                    connection.start_tls()
                except LDAPException as e:
                    raise LDAPException("Cannot start TLS.", str(e))

            connection.bind()

        except LDAPException as e:
            raise LDAPException("Cannot bind to the server.", str(e))

        self._connection = connection
        return connection


class OpenldapClient():
    log = Logger()
    isLeaf = True

    def __init__(self, client):
        self._client = client
        self._name = client.get('name', client.get('server_uri', ''))
        self._ldap = LdapEntries(client)
        self._object_class = client.get('object_class', 'structuralObjectClass')

    def get_html_content(self):
        server_label = 'server="{}"'.format(self._name)
        try:
            self._ldap.connect()
            entries = self._ldap.search_entries(OPENLDAP_MONITOR_BASEDN, OPENLDAP_MONITOR_FILTER.format(self._object_class, self._object_class))
            self._ldap.close()
        except LDAPException as e:
            return "openldap_up{{{}}} 0\n".format(server_label)

        if not entries:
            return "openldap_up{{{}}} 0\n".format(server_label)


        content = "openldap_up{{{}}} 1\n".format(server_label)

        for entry in entries:
            attrs = entry.get('attributes', {})
            if 'monitorCounterObject' in attrs['objectClass']:
                if 'monitorCounter' in attrs and len(attrs['monitorCounter']) == 1:
                    try:
                        label = 'dn="{}"'.format(entry['dn'])
                        value = float(attrs['monitorCounter'].pop())
                        content += "openldap_monitor_counter_object{{{},{}}} {}\n".format(server_label, label, value)
                    except ValueError:
                        pass

        for entry in entries:
            attrs = entry.get('attributes', {})
            if 'monitoredObject' in attrs['objectClass']:
                if 'monitoredInfo' in attrs and len(attrs['monitoredInfo']) == 1:
                    try:
                        label = 'dn="{}"'.format(entry['dn'])
                        value = float(attrs['monitoredInfo'].pop())
                        content += "openldap_monitored_object{{{},{}}} {}\n".format(server_label, label, value)
                    except ValueError:
                        pass

        return content

class MetricsPage(Resource):
    log = Logger()
    isLeaf = True

    def __init__(self, clients):
        self._clients = []
        Resource.__init__(self)
        for client in clients:
            self._clients.append(OpenldapClient(client))

    def render_GET(self, request):
        request.setHeader('Content-Type', 'text/plain; charset=utf-8; version=' + __version__)
        for client in self._clients:
            request.write(client.get_html_content().encode('utf-8'))
        request.finish()
        return NOT_DONE_YET

class QuietSite(Site):
    noisy = False

class RootPage(Resource):
    isLeaf = False

    def render_GET(self, request):
        request.setHeader('Content-Type', 'text/plain; charset=utf-8')
        return 'OK\n'.encode('utf-8')



def main():
    if not HAS_LDAP3:
        raise RuntimeError("Missing required 'ldap' module (pip install ldap3).")

    parser = argparse.ArgumentParser(prog='openldap_exporter', description='Prometheus OpenLDAP exporter')
    parser.add_argument('--config', type=argparse.FileType('r'), help='configuration file', required=True)
    arguments = parser.parse_args()

    configs = yaml.load(arguments.config)
    arguments.config.close()

    output = textFileLogObserver(sys.stderr, timeFormat='')
    globalLogBeginner.beginLoggingTo([output])

    # Setup web client
    metrics = MetricsPage(configs['clients'])
    root = RootPage()
    root.putChild(b'metrics', metrics)
    site = QuietSite(root)
    endpoint = serverFromString(reactor, "tcp:port=" + str(configs['server_port']))
    endpoint.listen(site)

    reactor.run()

if __name__ == '__main__':
      main()
