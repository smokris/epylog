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
# @Author Konstantin Riabitsev <icon@phy.duke.edu>
# @version $Date$
#

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
            rc('VFS: busy inodes on changed media'): self.busy_inodes,
            ##
            # Generic CD-ROM errors
            #
            rc('kernel: cdrom: This disc doesn'): self.cdrom_misc,
            ##
            # Most indicative of dirty floppy mounts
            #
            rc('attempt to access beyond end of device'): self.dirty_mount,
            rc('rw=\d+, want=\d+, limit=\d+'): self.dirty_mount,
            rc('Directory sread .* failed'): self.dirty_mount
        }

        self.normal   = 0
        self.critical = 1
        
        self.ypserv_re = rc('from\s(.*):\d+\sto\sprocedure\s(\S+)')
        self.kernel_re = rc('Linux\sversion\s(\S*)')
        self.sshd_scan_re = rc('from\s(\S*)')
        
        self.report_wrap = '<table border="0" width="100%%" rules="cols" cellpadding="2">%s</table>\n'
        self.subreport_wrap = '<tr><th colspan="2" align="left"><h3>%s</h3></th></tr>\n'
        self.critical_title = '<font color="red">CRITICAL Notices</font>'
        self.normal_title = '<font color="blue">General Notices</font>'
        
        self.report_line = '<tr><td valign="top">%s</td><td valign="top" width="90%%">%s</td></tr>\n'

    ##
    # Line matching routines
    #
    def gconf(self, linemap):
        urg = self.normal
        sys, msg, mult = self.get_smm(linemap)
        msg = 'Gconf locking errors'
        return {(urg, sys, msg): mult}

    def fatalx(self, linemap):
        urg = self.critical
        sys, msg, mult = self.get_smm(linemap)
        msg = 'Fatal X errors'
        return {(urg, sys, msg): mult}

    def sftp(self, linemap):
        urg = self.normal
        sys, msg, mult = self.get_smm(linemap)
        msg = 'SFTP activity'
        return {(urg, sys, msg): mult}

    def dirty_mount(self, linemap):
        urg = self.normal
        sys, msg, mult = self.get_smm(linemap)
        msg = 'dirty floppy mount [non-indicative]'
        return {(urg, sys, msg): mult}

    def floppy_misc(self, linemap):
        urg = self.normal
        sys, msg, mult = self.get_smm(linemap)
        msg = 'misc floppy errors'
        return {(urg, sys, msg): mult}

    def cdrom_misc(self, linemap):
        urg = self.normal
        sys, msg, mult = self.get_smm(linemap)
        msg = 'misc CDROM errors'
        return {(urg, sys, msg): mult}
    
    def ypserv(self, linemap):
        urg = self.normal
        sys, msg, mult = self.get_smm(linemap)
        mo = self.ypserv_re.search(msg)
        if not mo: return None
        fromip, proc = mo.groups()
        ypclient = self.gethost(fromip)
        msg = '%s denied from %s' % (proc, ypclient)
        return {(urg, sys, msg): mult}

    def linux_reboot(self, linemap):
        urg = self.critical
        sys, msg, mult = self.get_smm(linemap)
        mo = self.kernel_re.search(msg)
        if not mo: return None
        kernel = mo.group(1)
        msg = 'rebooted with kernel %s' % kernel
        return {(urg, sys, msg): mult}

    def sshd_scan(self, linemap):
        urg = self.critical
        sys, msg, mult = self.get_smm(linemap)
        mo = self.sshd_scan_re.search(msg)
        if not mo: return None
        rhost = mo.group(1)
        rhost = self.gethost(rhost)
        msg = 'sshd scan from %s' % rhost
        return {(urg, sys, msg): mult}

    def busy_inodes(self, linemap):
        urg = self.normal
        sys, msg, mult = self.get_smm(linemap)
        msg = 'dirty CDROM mount'
        return {(urg, sys, msg): mult}

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
                mymap = rs.get_submap((urg, system,))
                messages = []
                for message in mymap.keys():
                    messages.append('%s(%d)' % (message[0], mymap[message]))
                reports[urg] += self.report_line % (system,
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
