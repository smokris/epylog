#!/usr/bin/python -tt
import sys
import re

sys.path.insert(0, '../py/')
from epylog import Result, InternalModule

class notices_mod(InternalModule):
    def __init__(self, opts, logger):
        InternalModule.__init__(self)
        self.logger = logger
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
            rc('ypserv.*: refused connect'): self.ypserv,
            ##
            # Reboots
            #
            rc('kernel: Linux version'): self.linux_reboot,
            ##
            # SSHD notices
            #
            rc('sshd\[\S*: Did not receive identification'): self.sshd_scan,
            ##
            # VFS Errors left by cd-roms
            #
            rc('VFS: busy inodes on changed media'): self.busy_inodes
        }

        self.normal   = 0
        self.critical = 1
        
        self.ypserv_re = rc('from\s(.*):\d+\sto\sprocedure\s(\S+)')
        self.kernel_re = rc('Linux\sversion\s(\S*)')
        self.sshd_scan_re = rc('from\s(\S*)')
        
        self.report_wrap = '<table border="0" width="90%%">%s</table>\n'
        self.subreport_wrap = '<tr><th colspan="2" align="left"><h3>%s</h3></th></tr>\n'
        self.critical_title = '<font color="red">CRITICAL Notices</font>'
        self.normal_title = '<font color="blue">General Notices</font>'
        
        self.report_line = '<tr%s><td valign="top">%s:</td><td valign="top">%s</td></tr>\n'
        self.flip = ' bgcolor="#dddddd"'

    ##
    # Line matching routines
    #
    def gconf(self, linemap):
        urg = self.normal
        sys, msg, mult = self.get_smm(linemap)
        msg = 'Gconf locking errors'
        return Result((urg, sys, msg), mult)

    def fatalx(self, linemap):
        urg = self.critical
        sys, msg, mult = self.get_smm(linemap)
        msg = 'Fatal X errors'
        return Result((urg, sys, msg), mult)

    def sftp(self, linemap):
        urg = self.normal
        sys, msg, mult = self.get_smm(linemap)
        msg = 'SFTP activity'
        return Result((urg, sys, msg), mult)

    def floppy_misc(self, linemap):
        urg = self.normal
        sys, msg, mult = self.get_smm(linemap)
        msg = 'misc floppy errors'
        return Result((urg, sys, msg), mult)
    
    def ypserv(self, linemap):
        urg = self.critical
        sys, msg, mult = self.get_smm(linemap)
        mo = self.ypserv_re.search(msg)
        if not mo: return None
        fromip, proc = mo.groups()
        ypclient = self.gethost(fromip)
        msg = '%s denied from %s' % (proc, ypclient)
        return Result((urg, sys, msg), mult)

    def linux_reboot(self, linemap):
        urg = self.critical
        sys, msg, mult = self.get_smm(linemap)
        mo = self.kernel_re.search(msg)
        if not mo: return None
        kernel = mo.group(1)
        msg = 'rebooted with kernel %s' % kernel
        return Result((urg, sys, msg), mult)

    def sshd_scan(self, linemap):
        urg = self.critical
        sys, msg, mult = self.get_smm(linemap)
        mo = self.sshd_scan_re.search(msg)
        if not mo: return None
        rhost = mo.group(1)
        rhost = self.gethost(rhost)
        msg = 'sshd scan from %s' % rhost
        return Result((urg, sys, msg), mult)

    def busy_inodes(self, linemap):
        urg = self.normal
        sys, msg, mult = self.get_smm(linemap)
        msg = 'dirty CDROM mount'
        return Result((urg, sys, msg), mult)

    ##
    # FINALIZE!
    #
    def finalize(self, rs):
        report = ''
        reports = {}
        for urg in [self.critical, self.normal]:
            reports[urg] = ''
            flipr = ''
            for system in rs.get_distinct((urg,)):
                if flipr: flipr = ''
                else: flipr = self.flip
                mymap = rs.get_submap((urg, system,))
                messages = []
                for message in mymap.keys():
                    messages.append('%s(%d)' % (message[0], mymap[message]))
                reports[urg] += self.report_line % (flipr, system,
                                                    '<br>'.join(messages))
            
        if reports[self.critical]:
            report += self.subreport_wrap % self.critical_title
            report += reports[self.critical]

        if reports[self.normal]:
            report += self.subreport_wrap % self.normal_title
            report += reports[self.normal]

        report = self.report_wrap % report
        return report


if __name__ == '__main__':
    from epylog.helpers import ModuleTest
    ModuleTest(notices_mod, sys.argv)
