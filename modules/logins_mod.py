#!/usr/bin/python -tt
import sys
sys.path.insert(0, '../py/epylog/')
sys.path.insert(0, './py/')
import re
import string

from epylog import Result, ResultSet, InternalModule

class logins_mod(InternalModule):
    def __init__(self, opts, logger):
        InternalModule.__init__(self)
        self.logger = logger
        rc = re.compile

        self.ignore     = 0
        self.open       = 1
        self.failure    = 2
        self.root_open    = 11
        self.root_failure = 12
        
        self.regex_map = {
            ##
            # PAM reports
            #
            rc('\(pam_unix\)\S*:.*authentication\s*failure'): self.pam_failure,
            rc('\(pam_unix\)\S*:\ssession\sopened\sfor'): self.pam_open,
            rc('\(pam_unix\)\S*:\ssession\sclosed\sfor'): self.general_ignore,
            rc('\(pam_unix\)\S*:\sbad\susername'): self.pam_baduser,
            rc('\(pam_unix\)\S*:\sauth\scould\snot'): self.pam_chelper_failure,
            rc('\(pam_unix\)\S*:\scheck\spass;'): self.general_ignore,
            ##
            # XINETD reports
            #
            rc('xinetd\S*: START:'): self.xinetd_start,
            rc('xinetd\S*: EXIT:'): self.general_ignore,
            ##
            # SSH reports
            #
            rc('sshd\[\S*: Accepted'): self.sshd_open,
            rc('sshd\[\S*: Connection\sclosed'): self.general_ignore,
            rc('sshd\[\S*: Failed'): self.sshd_failure,
            ##
            # IMAPD and IPOP3D
            #
            rc('imapd\[\S*: Login\sfail'): self.imap_pop_failure,
            rc('imapd\[\S*: Authenticated\suser'): self.imap_pop_open,
            rc('imapd\[\S*: AUTHENTICATE'): self.general_ignore,
            rc('imapd\[\S*: Logout'): self.general_ignore,
            rc('ipop3d\[\S*: Login\sfail'): self.imap_pop_failure,
            rc('ipop3d\[\S*: Login\suser'): self.imap_pop_open,
            rc('ipop3d\[\S*: Auth\suser'): self.imap_pop_open,
            rc('ipop3d\[\S*: AUTHENTICATE'): self.general_ignore,
            rc('ipop3d\[\S*: Logout'): self.general_ignore,
            rc('ipop3d\[\S*: Killed'): self.general_ignore,
            rc('ipop3d\[\S*: Autologout'): self.general_ignore,
            ##
            # IMP
            #
            rc('IMP\[\S*: Login'): self.imp2_open,
            rc('IMP\[\S*: FAILED'): self.imp2_failure,
            rc('HORDE\[\S*\s*\[imp\] Login'): self.imp3_open,
            rc('HORDE\[\S*\s*\[imp\] FAILED'): self.imp3_failure,
            rc('HORDE\[\S*\s*\[imp\] Logout'): self.general_ignore
        }

        self.pam_service_re = rc('(\S+)\(pam_unix\)')
        self.pam_failure_re = rc('.*\slogname=(\S*).*\srhost=(\S*).*\suser=(\S*)')
        self.pam_open_re = rc('.*for user (\S+) by\s(\S*)\s*\(uid=(\S+)\)')
        self.pam_failure_more_re = rc('(\S+)\smore\sauthentication\sfailures')
        self.pam_baduser_re = rc('\sbad\susername\s\[(.*)\]')
        self.pam_chelper_re = rc('password\sfor\s\[(.*)\]')
        self.xinetd_start_re = rc('START:\s*(\S*)\s')
        self.sshd_open_re = rc('Accepted\s(\S*)\sfor\s(\S*)\sfrom\s(\S*)\sport\s\d*\s*[ruser]*\s*(\S*)\s*(\S*)$')
        self.sshd_fail_re = rc('Failed\s(\S*)\sfor.*\s(\S*)\sfrom\s(\S*)\sport\s\d*\s*(\S*)')
        self.imap_pop_fail_re = rc('auth=(.*)\shost=.*\[(\S*)\]')
        self.imap_pop_open_re = rc('user=(.*)\shost=.*\[(\S*)\]')
        self.imap_pop_service_re = rc('^(\S*)\[\d*\]:')
        self.imp2_open_re = rc('Login\s(\S*)\sto\s(\S*):\S*\sas\s(\S*)')
        self.imp2_fail_re = rc('FAILED\s(\S*)\sto\s(\S*):\S*\sas\s(\S*)')
        self.imp3_open_re = rc('success\sfor\s(\S*)\s\[(\S*)\]\sto\s\{(\S*):')
        self.imp3_fail_re = rc('LOGIN\s(\S*)\sto\s(\S*):\S*\sas\s(\S*)')
        
        self.sshd_methods = {'password': 'pw',
                             'publickey': 'pk',
                             'rhosts-rsa': 'rsa',
                             'rsa': 'rsa',
                             'none': 'none'}

        self.report_wrap = '<table width="90%%">%s</table>'
        self.subreport_wrap = '<tr><th align="left" colspan="3"><h3>%s</h3></th></tr>\n%s\n'

        self.root_failures_title = '<font color="red">ROOT FAILURES</font>'
        self.root_logins_title = '<font color="blue">ROOT Logins</font>'
        self.user_failures_title = '<font color="red">User Failures</font>'
        self.user_logins_title = '<font color="blue">User Logins</font>'

        self.flip = ' bgcolor="#dddddd"'

        self.line_rep = '<tr%s><td align="left" valign="top" width="15%%">%s</td><td align="right" valign="top" width="15%%">%s:</td><td width="70%%">%s</td></tr>\n'

    ##
    # LINE MATCHING ROUTINES
    #
    def general_ignore(self, linemap):
        restuple = (self.ignore, None, None, None)
        return Result(restuple, 1)

    def pam_failure(self, linemap):
        action = self.failure
        self.logger.put(5, 'pam_failure invoked')
        system, message, mult = self.get_smm(linemap)
        service = self._get_pam_service(message)
        if service == 'xscreensaver' or service == 'sshd':
            ##
            # xscreensaver always fail as root.
            # SSHD is better handled by sshd part itself.
            # Ignore these.
            #
            result = self.general_ignore(linemap)
            return result
        mo = self.pam_failure_re.search(message)
        if not mo:
            self.logger.put(3, 'Odd pam failure string: %s' % message)
            return None
        byuser, rhost, user = mo.groups()
        mo = self.pam_failure_more_re.search(message)
        if mo: mult += int(mo.group(1))
        else: mult += 1
        restuple = self._mk_restuple(action, system, service, user,
                                     byuser, rhost)
        return Result(restuple, mult)

    def pam_open(self, linemap):
        action = self.open
        system, message, mult = self.get_smm(linemap)
        service = self._get_pam_service(message)
        if service == 'sshd':
            ##
            # sshd_open will do a much better job.
            #
            result = self.general_ignore(linemap)
            return result
        mo = self.pam_open_re.search(message)
        if not mo:
            self.logger.put(3, 'Odd pam open string: %s' % message)
            return None
        user, byuser, byuid = mo.groups()
        if byuser == '': byuser = self.getuname(int(byuid))
        restuple = self._mk_restuple(action, system, service, user, byuser, '')
        return Result(restuple, mult)

    def pam_baduser(self, linemap):
        action = self.failure
        system, message, mult = self.get_smm(linemap)
        mo = self.pam_baduser_re.search(message)
        if not mo:
            self.logger.put(3, 'Odd pam bad user string: %s' % message)
            return None
        user = mo.group(1)
        service = self._get_pam_service(message)
        restuple = self._mk_restuple(action, system, service, user, '', '')
        return Result(restuple, mult)

    def pam_chelper_failure(self, linemap):
        action = self.failure
        system, message, mult = self.get_smm(linemap)
        mo = self.pam_chelper_re.search(message)
        if not mo:
            self.logger.put(3, 'Odd pam console helper string: %s' % message)
            return None
        user = mo.group(1)
        service = self._get_pam_service(message)
        restuple = self._mk_restuple(action, system, service, user, '', '')
        return Result(restuple, mult)

    def xinetd_start(self, linemap):
        action = self.open
        system, message, mult = self.get_smm(linemap)
        mo = self.xinetd_start_re.search(message)
        if not mo:
            self.logger.put(3, 'Odd xinetd start string: %s' % message)
            return None
        service = mo.group(1)
        restuple = self._mk_restuple(action, system, service, '', '', '')
        return Result(restuple, mult)

    def sshd_open(self, linemap):
        action = self.open
        system, message, mult = self.get_smm(linemap)
        mo = self.sshd_open_re.search(message)
        if not mo:
            self.logger.put(3, 'Odd sshd open string: %s' % message)
            return None
        method, user, rhost, ruser, service = mo.groups()
        method = self.sshd_methods.get(method, '??')
        rhost = self.gethost(rhost)
        if not service: service = 'ssh1'
        service = '%s(%s)' % (service, method)
        restuple = self._mk_restuple(action, system, service, user, '', rhost)
        return Result(restuple, mult)

    def sshd_failure(self, linemap):
        action = self.failure
        system, message, mult = self.get_smm(linemap)
        mo = self.sshd_fail_re.search(message)
        if not mo:
            self.logger.put(3, 'Odd sshd FAILURE string: %s' % message)
            return None
        method, user, rhost, ruser, service = mo.groups()
        method = self.sshd_methods.get(method, '??')
        rhost = self.gethost(rhost)
        if not service: service = 'ssh1'
        service = '%s(%s)' % (service, method)
        restuple = self._mk_restuple(action, system, service, user, '', rhost)
        return Result(restuple, mult)

    def imap_pop_failure(self, linemap):
        action = self.failure
        system, message, mult = self.get_smm(linemap)
        service = self._get_imap_pop_service(message)
        mo = self.imap_pop_fail_re.search(message)
        if not mo:
            self.logger.put(3, 'Odd imap FAILURE string: %s' % message)
            return None
        user, rhost = mo.groups()
        rhost = self.gethost(rhost)
        restuple = self._mk_restuple(action, system, service, user, '', rhost)
        return Result(restuple, mult)

    def imap_pop_open(self, linemap):
        action = self.open
        system, message, mult = self.get_smm(linemap)
        service = self._get_imap_pop_service(message)
        mo = self.imap_pop_open_re.search(message)
        if not mo:
            self.logger.put(3, 'Odd imap open string: %s' % message)
            return None
        user, rhost = mo.groups()
        rhost = self.gethost(rhost)
        restuple = self._mk_restuple(action, system, service, user, '', rhost)
        return Result(restuple, mult)

    def imp2_failure(self, linemap):
        action = self.failure
        system, message, mult = self.get_smm(linemap)
        mo = self.imp2_fail_re.search(message)
        if not mo:
            self.logger.put(3, 'Odd IMP failure string: %s' % message)
            return None
        rhost, system, user = mo.groups()
        rhost = self.gethost(rhost)
        service = 'IMP2'
        restuple = self._mk_restuple(action, system, service, user, '', rhost)
        return Result(restuple, mult)

    def imp2_open(self, linemap):
        action = self.open
        system, message, mult = self.get_smm(linemap)
        mo = self.imp2_open_re.search(message)
        if not mo:
            self.logger.put(3, 'Odd IMP open string: %s' % message)
            return None
        rhost, system, user = mo.groups()
        rhost = self.gethost(rhost)
        service = 'IMP2'
        restuple = self._mk_restuple(action, system, service, user, '', rhost)
        return Result(restuple, mult)

    def imp3_failure(self, linemap):
        action = self.failure
        system, message, mult = self.get_smm(linemap)
        mo = self.imp3_fail_re.search(message)
        if not mo:
            self.logger.put(3, 'Odd IMP failure string: %s' % message)
            return None
        rhost, system, user = mo.groups()
        rhost = self.gethost(rhost)
        service = 'IMP3'
        restuple = self._mk_restuple(action, system, service, user, '', rhost)
        return Result(restuple, mult)

    def imp3_open(self, linemap):
        action = self.open
        system, message, mult = self.get_smm(linemap)
        mo = self.imp3_open_re.search(message)
        if not mo:
            self.logger.put(3, 'Odd IMP open string: %s' % message)
            return None
        user, rhost, system = mo.groups()
        rhost = self.gethost(rhost)
        service = 'IMP3'
        restuple = self._mk_restuple(action, system, service, user, '', rhost)
        return Result(restuple, mult)


    ##
    # HELPER METHODS
    #
    def _mk_restuple(self, action, system, service, user, byuser, rhost):
        if user == '': user = 'unknown'
        if user == 'root' or user == 'ROOT':
            action += 10
            remote = self._mk_remote(byuser, rhost)
            restuple = (action, system, service, remote)
        else:
            restuple = (action, user, service, system)
        return restuple
    
    def _get_pam_service(self, str):
        service = 'unknown'
        mo = self.pam_service_re.search(str)
        if mo: service = mo.group(1)
        return service

    def _get_imap_pop_service(self, str):
        service = 'unknown'
        mo = self.imap_pop_service_re.search(str)
        if mo: service = mo.group(1)
        return service

    def _mk_remote(self, ruser, rhost):
        if ruser and rhost: ruhost = '%s@%s' % (ruser, rhost)
        elif ruser: ruhost = ruser
        elif rhost: ruhost = '@%s' % rhost
        else: ruhost = 'unknown'
        return ruhost

    ##
    # FINALIZE!!
    #
    def finalize(self, rs):
        logger = self.logger
        logger.put(5, '>logins_mod.finalize')
        ##
        # Prepare report
        #
        report = ''
        rep = {}
        for action in [self.root_failure, self.root_open,
                       self.failure, self.open]:
            logger.put(5, 'Processing action %d' % action)
            keys = rs.get_distinct((action,))
            keys.sort()
            rep[action] = ''
            flipper = ''
            for key in keys:
                logger.put(5, 'key=%s' % key)
                service_rep = []
                for service in rs.get_distinct((action, key)):
                    logger.put(5, 'service=%s' % service)
                    mymap = rs.get_submap((action, key, service))
                    key2s = []
                    for key2 in mymap.keys():
                        logger.put(5, 'key2=%s' % key2)
                        key2s.append('%s(%d)' % (key2[0], mymap[key2]))
                    service_rep.append([service, string.join(key2s, ', ')])
                blank = 0
                for svcrep in service_rep:
                    if blank: key = '&nbsp;'
                    else: blank = 1
                    if flipper: flipper = ''
                    else: flipper = self.flip
                    rep[action] += self.line_rep % (flipper, key,
                                                    svcrep[0], svcrep[1])
        
        if rep[self.root_failure]:
            report += self.subreport_wrap % (self.root_failures_title,
                                             rep[self.root_failure])
        if rep[self.root_open]:
            report += self.subreport_wrap % (self.root_logins_title,
                                             rep[self.root_open])
        if rep[self.failure]:
            report += self.subreport_wrap % (self.user_failures_title,
                                             rep[self.failure])
        if rep[self.open]:
            report += self.subreport_wrap % (self.user_logins_title,
                                             rep[self.open])

        report = self.report_wrap % report
        return report

if __name__ == '__main__':
    def mklinemap(system, message):
        linemap = {'line': 'line',
                   'stamp': 0,
                   'system': system,
                   'message': message,
                   'multiplier': 1}
        return linemap                   
    
    from epylog import Logger
    logger = Logger(5)
    opts = {}
    epymod = logins_mod(opts, logger)
    testlines = [
        ['ruser open', 'sshd[30260]: Accepted rhosts-rsa for jcd from 152.3.182.36 port 32901 ruser jcd'],
        ['simple open', 'sshd[316]: Accepted password for shwetket from 152.3.25.84 port 47030'],
        ['imap login', 'imapd[16091]: Authenticated user=djcecile host=login2.phy.duke.edu [152.3.182.75]'],
        ['imap failure', 'imapd[16035]: Login failed user=AryaBhatta auth=AryaBhatta host=login1.phy.duke.edu [152.3.182.74]'],
        ['pop3 login', 'ipop3d[5613]: Login user=shke host=momentum.chem.duke.edu [152.3.169.5] nmsgs=144/144'],
        ['pop3 failure', 'ipop3d[804]: Login failed user=leluo auth=leluo host=res-152-16-222-235.dorm.duke.edu [152.16.222.235]'],
        ['IMP2 open', 'IMP[15435]: Login 152.3.182.140 to mail.phy.duke.edu:993 as kinast'],
        ['IMP2 failure', 'IMP[15398]: FAILED 152.3.182.140 to mail.phy.duke.edu:993 as kinast'],
        ['IMP3 open', 'HORDE[27127]: [imp] Login success for wjs [208.61.133.234] to {mail-wj.acpub.duke.edu:993} [on line 64 of "/usr/share/horde/imp/redirect.php"]'],
        ['IMP3 failure', 'HORDE[27126]: [imp] FAILED LOGIN 208.61.133.234 to mail.cs.duke.edu:993[imap/ssl/novalidate-cert] as wjs [on line 270 of "/usr/share/horde/imp/lib/IMP.php"]']
        ]
    for descr, line in testlines:
        linemap = mklinemap(descr, line)
        for regex in epymod.regex_map.keys():
            if regex.search(line):
                handler = epymod.regex_map[regex]
                result = handler(linemap)
                print result.result
