#!/usr/bin/python -tt

import re
import epylog
import string
from epylog.module import Result

class logins_mod(epylog.module.PythonModule):
    def __init__(self, opts, logger):
        epylog.module.PythonModule.__init__(self)
        self.logger = logger
        rc = re.compile

        self.failure = 0
        self.open    = 1
        self.close   = 2
        self.notice  = 3
        self.ignore  = 4
        
        self.regex_map = {
            rc('\(pam_unix\)\S*:.*authentication\s*failure'): self.pam_failure,
            rc('\(pam_unix\)\S*:\ssession\sopened\sfor'): self.pam_open,
            rc('\(pam_unix\)\S*:\ssession\sclosed\sfor'): self.pam_closed
        }

        self.pam_service_re = rc('(\S+)\(pam_unix\)')
        self.pam_failure_re = rc('.*\slogname=(\S*).*\srhost=(\S*).*\suser=(\S*)')
        self.pam_open_re = rc('.*for user (\S+) by\s(\S*)\s*\(uid=(\S+)\)')
        self.pam_failure_more_re = rc('(\S+)\smore\sauthentication\sfailures')


        self.root_failure_wrap = '<h4>ROOT Login FAILURES</h4><table border="0">%s</table>\n'
        self.root_success_wrap = '<h4>ROOT Logins</h4><table border="0">%s</table>\n'
        self.user_failure_wrap = '<h4>User Login FAILURES</h4><table border="0">%s</table>\n'
        self.user_success_wrap = '<h4>User Logins</h4><table border="0">%s</table>\n'

        self.line1_rep = '<tr bgcolor="%s"><td align="left" valign="top" rowspan="%d">%s:</td><td align="right" valign="top">%s:</td><td>%s</td></tr>\n'
        self.line2_rep = '<tr><td align="right" valign="top">%s:</td><td>%s</td></tr>\n'

    def pam_failure(self, stamp, system, message, multiplier):
        action = self.failure
        mo = self.pam_failure_re.search(message)
        if not mo:
            self.logger.put(3, 'Odd pam failure string: %s' % message)
            return None
        byuser, rhost, user = mo.groups()
        service = self._get_pam_service(message)
        mo = self.pam_failure_more_re.search(message)
        if mo: multiplier += int(mo.group(1))
        else: multiplier += 1
        restuple = (action, system, service, user, byuser, rhost)
        return Result(restuple, multiplier)

    def pam_open(self, stamp, system, message, multiplier):
        action = self.open
        mo = self.pam_open_re.search(message)
        if not mo:
            self.logger.put(3, 'Odd pam open string: %s' % message)
            return None
        user, byuser, byuid = mo.groups()
        service = self._get_pam_service(message)
        if byuser == '':
            byuser = self.getuname(int(byuid))
        rhost = ''
        restuple = (action, system, service, user, byuser, rhost)
        return Result(restuple, multiplier)

    def pam_closed(self, stamp, system, message, multiplier):
        action = self.close
        ##
        # We are ignoring these at the moment
        #
        restuple = (action, None, None, None, None, None)
        return Result(restuple, multiplier)
    
    def _get_pam_service(self, str):
        service = 'unknown'
        mo = self.pam_service_re.search(str)
        if mo:
            service = mo.group(1)
        return service

    def _mk_remote(self, ruser, rhost):
        if ruser and rhost: ruhost = '%s@%s' % (ruser, rhost)
        elif ruser: ruhost = ruser
        elif rhost: ruhost = '@%s' % rhost
        else: ruhost = 'unknown'
        return ruhost
        
    def finalize(self, rs):
        logger = self.logger
        logger.put(5, '>logins_mod.finalize')
        rrs = epylog.module.ResultSet()
        urs = epylog.module.ResultSet()
        nrs = epylog.module.ResultSet()
        ##
        # Get all failures and opens
        #
        for action in [self.open, self.failure]:
            for system in rs.get_distinct((action,)):
                mymap = rs.get_submap((action, system))
                for key in mymap.keys():
                    service, user, byuser, rhost = key
                    if user == 'root' or user == 'ROOT':
                        if (service == 'xscreensaver' and
                            action == self.failure): continue
                        remote = self._mk_remote(byuser, rhost)
                        restuple = (action, system, service, remote)
                        rrs.add(Result(restuple, mymap[key]))
                    else:
                        restuple = (action, user, service, system)
                        urs.add(Result(restuple, mymap[key]))
        ##
        # Get all notices
        #
        for system in rs.get_distinct((self.notice,)):
            pass

        ##
        # Prepare report
        #
        report = ''
        ##
        # ROOT Logins and failures
        #
        sysrep = {}
        for action in [self.failure, self.open]:
            systems = rrs.get_distinct((action,))
            systems.sort()
            sysrep[action] = ''
            color = 'whitesmoke'
            flipper = ''
            for system in systems:
                if flipper: flipper = ''
                else: flipper = color
                service_rep = []
                for service in rrs.get_distinct((action, system)):
                    mymap = rrs.get_submap((action, system, service))
                    remotes = []
                    for remote in mymap.keys():
                        remotes.append('%s(%d)' % (remote[0], mymap[remote]))
                    service_rep.append([service, string.join(remotes, ', ')])
                first = 1
                for svcrep in service_rep:
                    if first:
                        sysrep[action] += (self.line1_rep %
                                           (flipper, len(service_rep), system,
                                            svcrep[0], svcrep[1]))
                        first = 0
                    else:
                        sysrep[action] += self.line2_rep%(svcrep[0], svcrep[1])
                    
        if sysrep[self.failure]:
            report += self.root_failure_wrap % sysrep[self.failure]
        if sysrep[self.open]:
            report += self.root_success_wrap % sysrep[self.open]

        ##
        # User Logins and failures
        #
        userrep = {}
        for action in [self.failure, self.open]:
            users = urs.get_distinct((action,))
            users.sort()
            userrep[action] = ''
            color = 'whitesmoke'
            flipper = ''
            for user in users:
                if flipper: flipper = ''
                else: flipper = color
                service_rep = []
                for service in urs.get_distinct((action, user)):
                    mymap = urs.get_submap((action, user, service))
                    systems = []
                    for system in mymap.keys():
                        systems.append('%s(%d)' % (system[0], mymap[system]))
                    service_rep.append([service, string.join(systems, ', ')])
                first = 1
                for svcrep in service_rep:
                    if first:
                        userrep[action] += self.line1_rep % (flipper,
                                                             len(service_rep),
                                                             user, svcrep[0],
                                                             svcrep[1])
                        first = 0
                    else:
                        userrep[action] += self.line2_rep % (svcrep[0],
                                                             svcrep[1])
        if userrep[self.failure]:
            report += self.user_failure_wrap % userrep[self.failure]
        if userrep[self.open]:
            report += self.user_success_wrap % userrep[self.open]
        
        return report
