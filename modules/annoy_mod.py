#!/usr/bin/python -tt

import re
import string
import epylog

class annoy_mod(epylog.module.PythonModule):
    def __init__(self, logger):
        epylog.module.PythonModule.__init__(self)
        self.logger = logger
        self.athreads = 50
        rc = re.compile
        self.regex_map = {
            ##
            # GConf, the bane of all existence
            #
            rc('gconfd.*: Failed to get lock.*Failed to create'): self.gconf,
            rc('gconfd.*: Error releasing lockfile'): self.gconf,
            rc('gconfd.*: .* Could not lock temporary file'): self.gconf,
            rc('gconfd.*: .* another process has the lock'): self.gconf,
            ##
            # Look for fatal X errors. These usually occur when
            # someone logs out, but if they repeat a lot, then it's
            # something that should be looked at.
            #
            rc('Fatal X error'): self.fatalx,
            ##
            # Look for sftp activity.
            #
            rc('sftp-server.*:'): self.sftp,
            rc('subsystem request for sftp'): self.sftp,
            ##
            # Look for misc floppy errors (vmware likes to leave those).
            #
            rc('floppy0:|\(floppy\)'): self.floppy_misc,
            ##
            # Look for ypserv errors
            #
            rc('ypserv.*: refused connect'): self.ypserv
        }
        self.ypserv_re = rc('from\s(.*):\d+\sto\sprocedure\s(\S+)')

    def gconf(self, stamp, system, message):
        msg = 'Gconf locking errors'
        return [system, msg]

    def fatalx(self, stamp, system, message):
        msg = 'Fatal X errors'
        return [system, msg]

    def sftp(self, stamp, system, message):
        msg = 'SFTP activity'
        return [system, msg]

    def floppy_misc(self, stamp, system, message):
        msg = 'misc floppy errors'
        return [system, msg]
    
    def ypserv(self, stamp, system, message):
        mo = self.ypserv_re.search(message)
        if mo:
            fromip, proc = mo.groups()
            ypclient = self.gethost(fromip)
            msg = '%s denied from %s' % (proc, ypclient)
            return [system, msg]
        return None            

    def finalize(self, resultset):
        logger = self.logger
        logger.put(5, '>annoy_mod.finalize')
        if len(resultset):
            report = self.__get_report(resultset)
        else:
            report = ''
        logger.put(5, '<annoy_mod.finalize')
        return report

    def __get_report(self, resultset):
        hosts = {}
        for system, message in resultset:
            try:
                hosts[system][message] += 1
            except KeyError:
                hosts[system] = {message: 1}
        report =  '<table border="0">'
        repline = '<tr><td>%s:</td><td>%s</td></tr>'
        for system in hosts.keys():
            messages = []
            for message in hosts[system].keys():
                messages.append('%s(%d)' % (message, hosts[system][message]))
            report += repline % (system, string.join(messages, ', '))
        report += '</table>'
        return report
