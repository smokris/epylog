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
from xml.dom.minidom import parse
import os

sys.path.insert(0, '../py/')
from epylog import InternalModule

def getTextVal(node):
    """
    getTextVal(node):
        The node is an element node containing text nodes. This function
        will concatenate the text nodes together and return them as one
        string. Any non-text nodes will be ignored.
    """
    val = ''
    for childnode in node.childNodes:
        if childnode.nodeType == childnode.TEXT_NODE:
            val = val + childnode.data
    return val

class notices_mod(InternalModule):
    def __init__(self, opts, logger):
        InternalModule.__init__(self)
        self.logger = logger
        self.critical = 1
        self.normal = 0
        self.regex_map = {}
        self.regex_dict = {}
        n_dist = opts.get('notice_dist', '/etc/epylog/notice_dist.xml')
        n_loc = opts.get('notice_local', '/etc/epylog/notice_local.xml')

        self.entities = {
            re.compile('&lt;'): '<',
            re.compile('&gt;'): '>',
            re.compile('&quot;'): '"',
            re.compile('&amp;'): '&'}

        enables = opts.get('enable', 'ALL')
        if not enables: return
        enlist = []
        for en in enables.split(','): enlist.append(en.strip())
        
        notice_dict = self._parse_notices(n_dist, n_loc, enlist)
        if not notice_dict: return
        self._digest_notice_dict(notice_dict)

        self.ip_re = re.compile('\d+.\d+.\d+.\d+')

        self.report_wrap = '<table border="0" width="100%%" rules="cols" cellpadding="2">%s</table>\n'
        self.subreport_wrap = '<tr><th colspan="2" align="left"><h3>%s</h3></th></tr>\n'
        self.critical_title = '<font color="red">CRITICAL Notices</font>'
        self.normal_title = '<font color="blue">General Notices</font>'
        
        self.report_line = '<tr><td valign="top">%s</td><td valign="top" width="90%%">%s</td></tr>\n'

    ##
    # Line matching routines
    #
    def handle_notice(self, linemap):
        sys, msg, mult = self.get_smm(linemap)
        regex = linemap['regex']
        crit, report = self.regex_dict[regex]
        mo = regex.search(msg)
        groups = mo.groups()
        if groups:
            groups = self._resolver(groups)
            try: report = report % groups
            except: pass
        return {(crit, sys, report): mult}
    
    ##
    # Helper methods
    #
    def _resolver(self, groups):
        ret = []
        for member in groups:
            if self.ip_re.search(member): member = self.gethost(member)
            ret.append(member)
        return tuple(ret)

    def _deent(self, str):
        for regex in self.entities.keys():
            str = re.sub(regex, self.entities[regex], str)
        return str
    
    def _parse_notices(self, dist, loc, enlist):
        logger = self.logger
        notice_dict = {}
        try:
            doc = parse(dist)
            temp_dict = self._get_notice_dict(doc)
            if enlist[0] == 'ALL': notice_dict = temp_dict
            else:
                for en in enlist:
                    if en in temp_dict: notice_dict[en] = temp_dict[en]
            del doc
        except Exception, e:
            logger.put(0, 'Could not read/parse notices file %s: %s' %
                       (dist, e))
            return
        if os.access(loc, os.R_OK):
            try:
                doc = parse(loc)
                local_dict = self._get_notice_dict(doc)
                if local_dict: notice_dict.update(local_dict)
                del doc
            except Exception, e:
                logger.put(0, 'Exception while parsing %s: %s' % (loc, e))
                pass
        return notice_dict

    def _digest_notice_dict(self, notice_dict):
        for regexes, crit, report in notice_dict.values():
            for regex in regexes:
                self.regex_dict[regex] = (crit, report)
                self.regex_map[regex] = self.handle_notice
    
    def _get_notice_dict(self, doc):
        logger = self.logger
        notice_dict = {}
        for node in doc.getElementsByTagName('notice'):
            id = node.getAttribute('id')
            crit = self.normal
            try:
                if node.getAttribute('critical') == 'yes': crit = self.critical
            except: pass
            regexes = []
            for cnode in node.childNodes:
                val = getTextVal(cnode)
                val = self._deent(val)
                if cnode.nodeName == 'regex':
                    try:
                        regex = re.compile(val)
                        regexes.append(regex)
                    except:
                        logger.put(0, 'Bad regex for "%s": %s' % (id, val))
                elif cnode.nodeName == 'report':
                    report = val
            notice_dict[id] = (regexes, crit, report)
        return notice_dict

    ##
    # FINALIZE!
    #
    def finalize(self, rs):
        report = ''
        reports = {}
        for urg in [self.critical, self.normal]:
            reports[urg] = ''
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
