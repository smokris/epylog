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

##
# This is for testing purposes, so you can invoke this from the
# modules directory. See also the testing notes at the end of the
# file.
#
sys.path.insert(0, '../py/')
from epylog import InternalModule, Result

class spamd_mod(InternalModule):
    def __init__(self, opts, logger):
        InternalModule.__init__(self)
        self.logger = logger
        rc = re.compile
        self.regex_map = {
            rc('spamd\[\d+\]: clean message'): self.spamd,
            rc('spamd\[\d+\]: identified spam'): self.spamd
        }

        ##
        # Pass special data to the weeder
        #
        self.special = {
            'weed': [
                rc('spamd\[.*: info:'),
                rc('spamd\[.*: processing message'),
                rc('spamd\[.*: checking message'),
                rc('spamd\[.*: connection from'),
                rc('spamd\[.*: Creating default_prefs')
                ],
            'notice': {
                rc('spamd\[.*: hit max-children limit \((\d+)\)'):
                    (0, 'spamd: max-children limit of %s reached')
            }
        }
        
        self.top = int(opts.get('report_top', '10'))
        self.thold = int(opts.get('spam_threshold', '5'))
        sort_by = opts.get('sort_by', 'most spammed')
        if sort_by == 'most spammed': self.sort = 'spammed'
        else: self.sort = 'messages'

        self.spamd_re = rc('\s\((.*?)/.*for (\S*?):.*in (\S*).*, (\d+) bytes')

        self.report_wrap = '<table border="0" width="100%%" rules="cols" cellpadding="2">%s</table>\n'
        self.subreport_wrap = '<tr><th colspan="4" align="left"><h3>%s</h3></th></tr>\n'
        self.total_title = '<font color="blue">Total stats</font>'
        self.users_title = '<font color="blue">Top %d ranking users</font>' % self.top
        self.score_rep = '%.1f (%d/%d)'
        self.report_line = '<tr%s><td valign="top">%s</td><td valign="top">%s</td><td valign="top">%s</td><td valign="top">%s</td></tr>\n'
        self.flip = ' bgcolor="#dddddd"'

    ##
    # Line-matching routines
    #
    def spamd(self, linemap):
        sys, msg, mult = self.get_smm(linemap)
        try:
            score, user, sec, size = self.spamd_re.search(msg).groups()
        except:
            logger.put(0, 'Odd spamd line: %s' % msg)
            return None
        score = float(score)
        sec = float(sec)
        size = int(size)
        return {(user, score, sec, size): mult}

    def _mk_score(self, msgs, score, score1, score2):
        avg_score = float(score/msgs)
        ret = self.score_rep % (avg_score, score1, score2)
        return ret

    def _mk_time_unit(self, secs):
        mins = int(secs/60)
        if mins:
            hrs = int(mins/60)
            if hrs:
                days = int(hrs/24)
                if days: return (days, 'd')
                return (hrs, 'hr')
            return (mins, 'min')
        return (secs, 'sec')

    def finalize(self, rs):
        user_rep = ''
        users = rs.get_distinct(())
        t_msgs = 0
        t_score_t = 0
        t_thold_lt = 0
        t_thold_gt = 0
        t_secs = 0
        t_size = 0
        urs = Result()
        for user in users:
            submap = rs.get_submap((user,))
            msgs = 0
            score_t = 0
            thold_lt = 0
            thold_gt = 0
            secs = 0
            size = 0
            while 1:
                try: entry, mult = submap.popitem()
                except KeyError: break
                msgs += mult
                score, sec, bytes = entry
                score_t += score * mult
                if score < self.thold: thold_lt += mult
                else: thold_gt += mult
                secs += sec * mult
                size += bytes * mult
            if msgs == 0: continue
            t_msgs += msgs
            t_score_t += score_t
            t_thold_lt += thold_lt
            t_thold_gt += thold_gt
            t_secs += secs
            t_size += size
            if self.sort == 'spammed': ctr = float(score/msgs)
            else: ctr = msgs
            urs.add_result({(user, msgs, score_t, thold_lt, thold_gt,
                             secs, size): ctr})

        report = ''
        report += self.subreport_wrap % self.total_title
        score = self._mk_score(t_msgs, t_score_t, t_thold_lt, t_thold_gt)
        time = '%d %s' % self._mk_time_unit(t_secs)
        size = '%d %s' % self.mk_size_unit(t_size)
        user = '%d&nbsp;users/%d&nbsp;msgs' % (len(users), t_msgs)
        report += self.report_line % (self.flip, user, size, time, score)
        report += self.subreport_wrap % self.users_title
        flipper = ''
        for avg, entry in urs.get_top(self.top):
            if flipper: flipper = ''
            else: flipper = self.flip
            user, msgs, score_t, thold_lt, thold_gt, secs, size = entry
            score = self._mk_score(msgs, score_t, thold_lt, thold_gt)
            time = '%d %s' % self._mk_time_unit(secs)
            size = '%d %s' % self.mk_size_unit(size)
            report += self.report_line % (flipper, user, size, time, score)
        report = self.report_wrap % report
        return report

##
# This is useful when testing your module out.
# Invoke without command-line parameters to learn about the proper
# invocation.
#
if __name__ == '__main__':
    from epylog.helpers import ModuleTest
    ModuleTest(spamd_mod, sys.argv)
