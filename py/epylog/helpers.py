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
sys.path.insert(0, './py/')

import epylog
import getopt

class ModuleTest:
    def __init__(self, epyclass, args):
        logger = epylog.Logger(5)
        cmdargs = args[1:]
        if not cmdargs: self._usage(args[0])
        infile = None
        repfile = None
        filtfile = None
        opts = {}
        try:
            gopts, cmds = getopt.getopt(cmdargs, 'i:r:f:o:', [])
            for o, a in gopts:
                if o == '-i': infile  = a
                if o == '-r': repfile  = a
                if o == '-f': filtfile = a
                if o == '-o':
                    pairs = a.split(',')
                    for pair in pairs:
                        pair.strip()
                        key, value = pair.split(':')
                        key = key.strip()
                        value = value.strip()
                        opts[key] = value
        except getopt.error, e: self._usage(args[0])
        if opts:
            logger.put(5, 'Additional opts follow')
            logger.put(5, opts)
        logger.put(5, 'Instantiating the module')
        epymod = epyclass(opts, logger)
        if input is None: self._usage(args[0])
        logger.put(5, 'Trying to open file %s for reading' % infile)
        try: infh = open(infile)
        except Exception, e:
            msg = "ERROR trying to open file %s: %s" % (infile, e)
            self._die(msg)
        if filtfile is not None:
            logger.put(5, 'Trying to open %s for writing' % filtfile)
            try: filtfh = open(filtfile, 'w')
            except Exception, e:
                msg = "ERROR trying to open file %s: %s" % (filtfile, e)
                self._die(msg)
        monthmap = epylog.log.mkmonthmap()
        rs = epylog.Result()
        while 1:
            line = infh.readline()
            if not line: break
            line = line.strip()
            linemap = self._mk_linemap(line, monthmap)
            msg = linemap['message']
            for regex in epymod.regex_map.keys():
                if regex.search(msg):
                    handler = epymod.regex_map[regex]
                    logger.put(5, '%s -> %s' % (handler.__name__, msg))
                    result = handler(linemap)
                    if result is not None:
                        rs.add_result(result)
                        if filtfile is not None:
                            filtfh.write('%s\n' % line)
                        break
        infh.close()
        if filtfile is not None: filtfh.close()
        if not rs.is_empty():
            logger.put(5, 'Finalizing')
            report = epymod.finalize(rs)
            if repfile is not None:
                logger.put(5, 'Trying to write report to %s' % repfile)
                repfh = open(repfile, 'w')
                repfh.write(report)
                repfh.close()
                logger.put(5, 'Report written to %s' % repfile)
            else:
                logger.put(5, 'Report follows:')
                print report
        else:
            logger.put(5, 'No results for this run')
        logger.put(5, 'Done')

    def _mk_linemap(self, line, monthmap):
        try:
            stamp, sys, msg = epylog.log.get_stamp_sys_msg(line, monthmap)
        except ValueError, e:
            msg = 'Invalid syslog line: %s' % line
            self._die(msg)
        linemap = {'line': line,
                   'stamp': stamp,
                   'system': sys,
                   'message': msg,
                   'multiplier': 1}
        return linemap

    def _die(self, message):
        print 'FATAL ERROR: %s' % message
        sys.exit(1)
    
    def _mklinemap(self, system, message):
        linemap = {'line': 'line',
                   'stamp': 0,
                   'system': system,
                   'message': message,
                   'multiplier': 1}
        return linemap                   

    def _usage(self, name):
        print '''Usage:
    %s -i testcase [-r report] [-f filter] [-o EXTRAOPTS]
        If -r is omitted, the report is printed to stdout
        If -f is omitted, filtered lines are not shown
            
        EXTRAOPTS:
        Extra options should be submitted in this matter:
        -o "option: value, option2: value, option3: value"
        ''' % name
        sys.exit(1)

if __name__ == '__main__':
    print "See module documentation on how to use the helper"
