#!/usr/bin/python -tt
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
        self.regex_map = {
            rc('IN=\S*\sOUT=\S*\sMAC=\S*\sSRC=\S*\sDST=\S*\s'): self.iptables,
            rc('kernel:\sPacket\slog:\s'): self.ipchains
        }

        self.comment_line_re = rc('^\s*#')
        self.empty_line_re = rc('^\s*$')
        self.iptables_logtype_re = rc('iptables:\s*(\S*)')
        self.iptables_re = rc('SRC=(\S*)\s.*PROTO=(\S*)\s.*DPT=(\S*)')
        self.ipchains_re = rc('\slog:\s\S+\s(\S*).*\sPROTO=(\d+)\s(\S*):\d*\s\S*:(\d+)')
        self.etc_services_re = rc('^(\S*)\s+(\S*)')
        self.trojan_list_re = rc('^(\S*)\s+(\S*)')
        self.etc_protocols_re = rc('^(\S*)\s+(\S*)')

        svcdict = self._parse_etc_services()

        trojans = opts.get('trojan_list', '')
        self.systems_collapse = int(opts.get('systems_collapse', '10'))
        self.ports_collapse = int(opts.get('ports_collapse', '10'))
        
        if trojans: svcdict = self._parse_trojan_list(trojans, svcdict)
        self.svcdict = svcdict

        self.protodict = self._parse_etc_protocols()

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
            if pproto not in svcdict: svcdict[pproto] = trojan
        return svcdict
            

    ##
    # Line-matching routines
    #
    def iptables(self, linemap):
        sys, msg, mult = self.get_smm(linemap)
        ##
        # See if it's prepended with "iptables: LOGTYPE"
        #
        try: logtype = self.iptables_logtype_re.search(msg).group(1)
        except: logtype = 'LOGGED'
        try: src, proto, dpt = self.iptables_re.search(msg).groups()
        except:
            self.logger.put(3, 'Unknown iptables entry: %s' % msg)
            return None
        source = self.gethost(src)
        port = '%s/%s' % (dpt, proto.lower())
        port = self._mk_port(port)
        return {(source, sys, port, logtype): mult}

    def ipchains(self, linemap):
        sys, msg, mult = self.get_smm(linemap)
        try: logtype, proto, src, dpt = self.ipchains_re.search(msg).groups()
        except:
            self.logger.put(3, 'Unknown ipchains entry: %s' % msg)
            return None
        source = self.gethost(src)
        port = '%s/%s' % (dpt, self.protodict.get(int(proto), '??'))
        port = self._mk_port(port)
        return {(source, sys, port, logtype): mult}


    def _mk_port(self, port):
        try: desc = '%s&nbsp;(%s)' % (self.svcdict[port], port)
        except KeyError: desc = port
        return desc
    
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
                if len(ports) > 1: port = '[%d&nbsp;ports]' % len(ports)
                else: port = ports[0]
                if len(logtypes) > 1: logtype = '[%d]' % len(logtypes)
                else: logtype = logtypes[0]
                system = '[%d&nbsp;systems]' % len(systems)
                fin.append((packets, source, system, port, logtype))
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
                        port = '[%d&nbsp;ports]' % len(ports)
                        fin.append((packets, source, system, port, logtype))
                    else:
                        for port in ports:
                            submap = dstrs.get_submap((system, port))
                            while 1:
                                try: entry, packets = submap.popitem()
                                except KeyError: break
                                logtype = entry[0]
                                fin.append((packets, source, system, port,
                                            logtype))
        report = ''
        flipper = ''
        fin.sort()
        fin.reverse()
        for entry in fin:
            if flipper: flipper = ''
            else: flipper = self.flip
            packets, source, system, port, logtype = entry
            report += self.line_rep % (flipper, packets, source, system,
                                       logtype, port)

        report = self.subreport_wrap % ('Firewall Violations', report)
        report = self.report_wrap % report
                
        return report

if __name__ == '__main__':
    from epylog.helpers import ModuleTest
    ModuleTest(packets_mod, sys.argv)
