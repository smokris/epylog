#!/usr/bin/python -tt
"""
Description will eventually go here.
"""
##
# Copyright (C) 2003 by Duke University
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.
#
# $Id$
#
# @Author Konstantin Ryabitsev <icon@linux.duke.edu>
# @version $Date$
#

import sys
import re

##
# This is for testing purposes, so you can invoke this from the
# modules directory. See also the testing notes at the end of the
# file.
#
sys.path.insert(0, '../py/')
from epylog import Result, InternalModule

class packets_mod(InternalModule):
    def __init__(self, opts, logger):
        InternalModule.__init__(self)
        self.logger = logger
        rc = re.compile
        iptables_map = {
            rc('IN=\S*\sOUT=\S*\sMAC=\S*\sSRC=\S*\sDST=\S*\s'): self.iptables
            }
        ipchains_map = {
            rc('Packet\slog:\s.*PROTO.*'): self.ipchains
            }
        ipfilter_map = {
            rc('ipmon\[\d+\]:'): self.ipfilter
            }

        self.regex_map = {}
        if opts.get('enable_iptables', '1') == '1':
            self.regex_map.update(iptables_map)
        if opts.get('enable_ipchains', '0') == '1':
            self.regex_map.update(ipchains_map)
        if opts.get('enable_ipfilter', '0') == '1':
            self.regex_map.update(ipfilter_map)
        self.sortby = opts.get('sortby', 'packets')

        self.comment_line_re = rc('^\s*#')
        self.empty_line_re = rc('^\s*$')
        self.iptables_logtype_re = rc(':\s.*?(\S+?):*\sIN=')
        self.iptables_re = rc('SRC=(\S*)\s.*PROTO=(\S*)\s.*DPT=(\S*)')
        self.ipchains_re = rc('\slog:\s\S+\s(\S*).*\sPROTO=(\d+)\s(\S*):\d*\s\S*:(\d+)')
        self.ipfilter_re = rc('ipmon\[\d+\]:.*\s(\S+),\d+\s->\s\S+,(\d+)\sPR\s(\S+)')
        self.etc_services_re = rc('^(\S*)\s+(\S*)')
        self.trojan_list_re = rc('^(\S*)\s+(.*)')
        self.etc_protocols_re = rc('^(\S*)\s+(\S*)')

        svcdict = self._parse_etc_services()

        trojans = opts.get('trojan_list', '')
        self.systems_collapse = int(opts.get('systems_collapse', '10'))
        self.ports_collapse = int(opts.get('ports_collapse', '10'))

        self.trojan_warning_wrap = '<font color="red">%s</font>'
        if trojans: svcdict = self._parse_trojan_list(trojans, svcdict)
        self.svcdict = svcdict

        self.protodict = self._parse_etc_protocols()

        self.collapsed_ports_rep = '<font color="red">[%d&nbsp;ports]</font>'
        self.collapsed_hosts_rep = '<font color="red">[%d&nbsp;hosts]</font>'

        self.report_wrap = '<table width="100%%" rules="cols" cellpadding="2">%s</table>'
        self.subreport_wrap = '<tr><th align="left" colspan="5"><h3><font color="red">%s</font></h3></th></tr>\n%s\n'

        self.line_rep = '<tr%s><td valign="top" width="5%%">%d</td><td valign="top" width="50%%">%s</td><td valign="top" width="15%%">%s</td><td valign="top" width="15%%">%s</td><td valign="top" width="15%%">%s</td></tr>\n'
        self.flip = ' bgcolor="#dddddd"'

    def _parse_etc_protocols(self):
        try: fh = open('/etc/protocols', 'r')
        except:
            self.logger.put(0, 'Could not open /etc/protocols for reading!')
            return {}
        protodict = {}
        while 1:
            line = fh.readline()
            if not line: break
            if (self.comment_line_re.search(line)
                or self.empty_line_re.search(line)): continue
            try: proto, num = self.etc_protocols_re.search(line).groups()
            except: continue
            protodict[num] = proto
        return protodict
        
    def _parse_etc_services(self):
        try: fh = open('/etc/services', 'r')
        except:
            self.logger.put(0, 'Could not open /etc/services for reading!')
            return {}
        svcdict = {}
        while 1:
            line = fh.readline()
            if not line: break
            if (self.comment_line_re.search(line)
                or self.empty_line_re.search(line)): continue
            try: service, pproto = self.etc_services_re.search(line).groups()
            except: continue
            svcdict[pproto] = service
        return svcdict

    def _parse_trojan_list(self, fileloc, svcdict):
        try: fh = open(fileloc, 'r')
        except:
            self.logger.put(0, 'Could not open %s for reading!' % fileloc)
            return svcdict
        while 1:
            line = fh.readline()
            if not line: break
            if (self.comment_line_re.search(line)
                or self.empty_line_re.search(line)): continue
            try: pproto, trojan = self.trojan_list_re.search(line).groups()
            except: continue
            if pproto not in svcdict:
                svcdict[pproto] = self.trojan_warning_wrap % trojan
        return svcdict

    ##
    # Line-matching routines
    #
    def iptables(self, linemap):
        sys, msg, mult = self.get_smm(linemap)
        ##
        # See if it's prepended with a logtype string of sorts.
        #
        try: logtype = self.iptables_logtype_re.search(msg).group(1)
        except: logtype = 'LOGGED'
        try: src, proto, dpt = self.iptables_re.search(msg).groups()
        except:
            self.logger.put(3, 'Unknown iptables entry: %s' % msg)
            return None
        source = self.gethost(src)
        port = '%s/%s' % (dpt, proto.lower())
        return {(source, sys, port, logtype): mult}

    def ipchains(self, linemap):
        sys, msg, mult = self.get_smm(linemap)
        try: logtype, proto, src, dpt = self.ipchains_re.search(msg).groups()
        except:
            self.logger.put(3, 'Unknown ipchains entry: %s' % msg)
            return None
        source = self.gethost(src)
        port = '%s/%s' % (dpt, self.protodict.get(proto, '??'))
        return {(source, sys, port, logtype): mult}

    def ipfilter(self, linemap):
        sys, msg, mult = self.get_smm(linemap)
        try: src, dpt, proto = self.ipfilter_re.search(msg).groups()
        except:
            self.logger.put(3, 'Unknown ipfilter entry: %s' % msg)
            return None
        source = self.gethost(src)
        port = '%s/%s' % (dpt, proto.lower())
        return {(source, sys, port, 'LOGGED'): mult}


    def _mk_port(self, port):
        try: desc = '%s&nbsp;(%s)' % (self.svcdict[port], port)
        except KeyError: desc = port
        return desc

    def _addfin(self, fin, packets, source, system, port, rawport, logtype):
        if self.sortby == 'packets':
            fin.append((packets, source, system, port, rawport, logtype))
        elif self.sortby == 'source':
            fin.append((source, packets, system, port, rawport, logtype))
        elif self.sortby == 'system':
            fin.append((system, packets, source, port, rawport, logtype))
        elif self.sortby == 'port':
            fin.append((rawport, packets, source, system, port, logtype))
    
    ##
    # Finalize!
    #
    def finalize(self, rs):
        logger = self.logger
        fin = []
        for source in rs.get_distinct(()):
            dstrs = Result(rs.get_submap((source,)))
            systems = dstrs.get_distinct(())
            if len(systems) >= self.systems_collapse:
                ##
                # result will look like so:
                # 655 | source | [ 25 systems ] | [ 2 ] | [ 2 ports ] | lst
                # or
                # 655 | source | [ 25 systems ] | DROP | 22/tcp | ssh
                #
                ports = []
                logtypes = []
                packets = 0
                for system in systems:
                    submap = dstrs.get_submap((system,))
                    while 1:
                        try: entry, mult = submap.popitem()
                        except KeyError: break
                        port, logtype = entry
                        if port not in ports: ports.append(port)
                        if logtype not in logtypes: logtypes.append(logtype)
                        packets += mult
                rawport = port
                if len(ports) > 1:
                    port = self.collapsed_ports_rep % len(ports)
                    rawport = -1
                else: port = ports[0]
                if len(logtypes) > 1: logtype = '[%d]' % len(logtypes)
                else: logtype = logtypes[0]
                system = self.collapsed_hosts_rep % len(systems)
                self._addfin(fin, packets, source, system, port, rawport,
                             logtype)
            else:
                for system in systems:
                    logger.put(2, 'Processing system %s' % system)
                    ports = dstrs.get_distinct((system,))
                    if len(ports) > self.ports_collapse:
                        ##
                        # Result will look like so:
                        # 655 | source | system | DROP | [ 5 ports ] | lst
                        #
                        logtypes = []
                        packets = 0
                        sysrs = Result(dstrs.get_submap((system,)))
                        portmap = dstrs.get_submap((system,))
                        while 1:
                            try: entry, mult = portmap.popitem()
                            except KeyError: break
                            port, logtype = entry
                            logger.put(2, 'Processing port %s' % port)
                            if logtype not in logtypes:
                                logtypes.append(logtype)
                            packets += mult
                        if len(logtypes) > 1:
                            logtype = '[%d]' % len(logtypes)
                        else: logtype = logtypes[0]
                        port = self.collapsed_ports_rep % len(ports)
                        self._addfin(fin, packets, source, system, port, -1,
                                     logtype)
                    else:
                        for port in ports:
                            submap = dstrs.get_submap((system, port))
                            while 1:
                                try: entry, packets = submap.popitem()
                                except KeyError: break
                                logtype = entry[0]
                                self._addfin(fin, packets, source, system,
                                             port, port, logtype)
        report = ''
        flipper = ''
        fin.sort()
        if self.sortby == 'packets':
            fin.reverse()
        for entry in fin:
            if flipper: flipper = ''
            else: flipper = self.flip
            if self.sortby == 'packets':
                packets, source, system, port, rawport, logtype = entry
            elif self.sortby == 'source':
                source, packets, system, port, rawport, logtype = entry
            elif self.sortby == 'system':
                system, packets, source, port, rawport, logtype = entry
            elif self.sortby == 'port':
                rawport, packets, source, system, port, logtype = entry
            port = self._mk_port(port)
            report += self.line_rep % (flipper, packets, source, system,
                                       logtype, port)

        report = self.subreport_wrap % ('Firewall Violations', report)
        report = self.report_wrap % report
                
        return report

if __name__ == '__main__':
    from epylog.helpers import ModuleTest
    ModuleTest(packets_mod, sys.argv)
