#!/usr/bin/python -tt
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

        self.top = int(opts.get('report_top', '10'))
        sort_by = opts.get('sort_by', 'most spammed')
        if sort_by == 'most spammed': self.sort = 'spammed'
        else: self.sort = 'messages'

        self.spamd_re = rc('\s\((.*?)/.*for (\S*?):.*in (\S*).*, (\d+) bytes')

        self.report_wrap = '<table border="0" width="100%%" rules="cols" cellpadding="2">%s</table>\n'
        self.subreport_wrap = '<tr><th colspan="4" align="left"><h3>%s</h3></th></tr>\n'
        self.total_title = '<font color="blue">Total stats</font>'
        self.users_title = '<font color="blue">Top %d ranking users</font>' % self.top
        
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

    def _mk_score(self, msgs, score, score1, score2, score3):
        avg_score = float(score/msgs)
        ret = '%.1f (%d/%d/%d)' % (avg_score, score1, score2, score3)
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
        t_score_lt5 = 0
        t_score_510 = 0
        t_score_gt10 = 0
        t_secs = 0
        t_size = 0
        urs = Result()
        for user in users:
            submap = rs.get_submap((user,))
            msgs = 0
            score_t = 0
            score_lt5 = 0 # from <0 till 5
            score_510 = 0 # from 5 till 10
            score_gt10 = 0 # 10 and more
            secs = 0
            size = 0
            while 1:
                try: entry, mult = submap.popitem()
                except KeyError: break
                msgs += mult
                score, sec, bytes = entry
                score_t += score * mult
                if score < 5: score_lt5 += mult
                elif score >= 5 and score <= 10: score_510 += mult
                else: score_gt10 += mult
                secs += sec * mult
                size += bytes * mult
            if msgs == 0: continue
            t_msgs += msgs
            t_score_t += score_t
            t_score_lt5 += score_lt5
            t_score_510 += score_510
            t_score_gt10 += score_gt10
            t_secs += secs
            t_size += size
            if self.sort == 'spammed': ctr = float(score/msgs)
            else: ctr = msgs
            urs.add_result({(user, msgs, score_t, score_lt5, score_510,
                            score_gt10, secs, size): ctr})

        report = ''
        report += self.subreport_wrap % self.total_title
        score = self._mk_score(t_msgs, t_score_t, t_score_lt5, t_score_510,
                               t_score_gt10)
        time = '%d %s' % self._mk_time_unit(t_secs)
        size = '%d %s' % self.mk_size_unit(t_size)
        user = '%d&nbsp;users/%d&nbsp;msgs' % (len(users), t_msgs)
        report += self.report_line % (self.flip, user, size, time, score)
        report += self.subreport_wrap % self.users_title
        flipper = ''
        for avg, entry in urs.get_top(self.top):
            if flipper: flipper = ''
            else: flipper = self.flip
            user, msgs, score_t, score1, score2, score3, secs, size = entry
            score = self._mk_score(msgs, score_t, score1, score2, score3)
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
