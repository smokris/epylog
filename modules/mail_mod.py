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

class mail_mod(InternalModule):
    def __init__(self, opts, logger):
        InternalModule.__init__(self)
        self.logger = logger
        rc = re.compile
        postfix_map = {
            rc('postfix/smtpd\[\d+\]:\s\S*:'): self.postfix_smtpd,
            rc('postfix/nqmgr\[\d+\]:\s\S*:'): self.postfix_nqmgr,
            rc('postfix/local\[\d+\]:\s\S*:'): self.postfix_local,
            rc('postfix/smtp\[\d+\]:\s\S*:\sto='): self.postfix_smtp
            }

        sendmail_map = {
            rc('sendmail\['): self.sendmail
            }

        do_postfix = int(opts.get('enable_postfix', '0'))
        do_sendmail = int(opts.get('enable_sendmail', '1'))

        self.regex_map = {}
        if do_postfix: self.regex_map.update(postfix_map)
        if do_sendmail: self.regex_map.update(sendmail_map)
        
        self.toplim = int(opts.get('top_report_limit', '5'))

        self.postfix_ident_re = rc('\[\d+\]:\s*([A-Z0-9]*):')
        self.postfix_smtpd_re = rc('client=\S*\[(\S*)\]')
        self.postfix_nqmgr_re = rc('from=(\S*),.*size=(\d*)')
        self.postfix_local_re = rc('to=(\S*),.*status=(\S*)\s\((.*)\)')
        self.postfix_smtp_re  = rc('to=(\S*),.*status=(\S*)')

        self.sendmail_ident_re = rc('sendmail\[\d+\]:\s(.*?):')
        self.sendmail_fromline_re = rc('from=(.*?),.*size=(\d+),.*relay=(.*)')
        self.sendmail_ctladdr_re = rc('to=(\"\|.*?),\sctladdr=(.*?),.*stat=(\w+)')
        self.sendmail_toline_re = rc('to=(.*?),.*stat=(\w+)')
        self.sendmail_from_re = rc('(<.*?>)')
        self.sendmail_relay_re = rc('(.*?)\s\[(\S*)\]')

        self.procmail_re = rc('/procmail')

        self.bounce   = 0
        self.success  = 1
        self.warning  = 2
        self.procmail = 3

        self.report_wrap = '<table border="0" width="100%%" rules="cols" cellpadding="2">%s</table>'
        self.subreport_wrap = '<tr><th colspan="2" align="left"><h3><font color="blue">%s</font></h3></th></tr>\n'
        
        self.report_line = '<tr><td valign="top" align="right">%s</td><td valign="top" width="90%%">%s</td></tr>\n'

    ##
    # Line-matching routines
    #
    def postfix_smtpd(self, linemap):
        sys, msg, mult = self.get_smm(linemap)
        id = self._get_postfix_id(msg)
        self.logger.put(5, 'id=%s' % id)
        try:
            client = self.postfix_smtpd_re.search(msg).group(1)
            client = self.gethost(client)
        except: client = None
        self.logger.put(5, 'client=%s' % client)
        restuple = self._mk_restuple(sys, id, client=client)
        return {restuple: mult}

    def postfix_nqmgr(self, linemap):
        sys, msg, mult = self.get_smm(linemap)
        id = self._get_postfix_id(msg)
        self.logger.put(5, 'id=%s' % id)
        try: sender, size = self.postfix_nqmgr_re.search(msg).groups()
        except: sender, size = (None, 0)
        size = int(size)
        self.logger.put(5, 'sender=%s, size=%d' % (sender, size))
        restuple = self._mk_restuple(sys, id, sender=sender, size=size)
        return {restuple: mult}

    def postfix_local(self, linemap):
        sys, msg, mult = self.get_smm(linemap)
        id = self._get_postfix_id(msg)
        self.logger.put(5, 'id=%s' % id)
        try: to, status, comment = self.postfix_local_re.search(msg).groups()
        except:
            self.logger.put(5, 'Odd postfix/local line: %s' % msg)
            return None
        self.logger.put(5, 'to=%s, status=%s, comment=%s' %
                        (to, status, comment))
        if status == 'sent': status = self.success
        elif status == 'bounced': status = self.bounce
        else: status = self.warning
        if self.procmail_re.search(comment): extra = self.procmail
        else: extra = None
        restuple = self._mk_restuple(sys, id, to=to, status=status,
                                     extra=extra)
        return {restuple: mult}

    def postfix_smtp(self, linemap):
        sys, msg, mult = self.get_smm(linemap)
        id = self._get_postfix_id(msg)
        self.logger.put(5, 'id=%s' % id)
        try: to, status = self.postfix_smtp_re.search(msg).groups()
        except:
            self.logger.put(5, 'Odd postfix/smtp line: %s' % msg)
            return None
        self.logger.put(5, 'to=%s, status=%s' % (to, status))
        if status == 'sent': status = self.success
        elif status == 'bounced': status = self.bounce
        else: status = self.warning
        restuple = self._mk_restuple(sys, id, to=to, status=status)
        return {restuple: mult}

    def sendmail(self, linemap):
        sys, msg, mult = self.get_smm(linemap)
        id = self._get_sendmail_id(msg)
        mo = self.sendmail_fromline_re.search(msg)
        if mo:
            sender, size, client = mo.groups()
            sender = self._fix_sendmail_address(sender)
            size = int(size)
            client = self._fix_sendmail_relay(client)
            restuple = self._mk_restuple(sys, id, client=client, sender=sender,
                                         size=size)
            return {restuple: mult}
        mo = self.sendmail_ctladdr_re.search(msg)
        if mo:
            command, to, status = mo.groups()
            extra = None
            if self.procmail_re.search(command): extra = self.procmail
            to = self._fix_sendmail_address(to)
            if status == 'Sent': status = self.success
            elif status == 'Deferred': status = self.warning
            restuple = self._mk_restuple(sys, id, to=to, status=status,
                                         extra=extra)
            return {restuple: mult}
        mo = self.sendmail_toline_re.search(msg)
        if mo:
            to, status = mo.groups()
            to = self._fix_sendmail_address(to)
            if status == 'Sent': status = self.success
            elif status == 'Deferred': status = self.warning
            restuple = self._mk_restuple(sys, id, to=to, status=status)
            return {restuple: mult}
        return None

    ##
    # HElpers
    #

    def _mk_restuple(self, sys, id, client=None, sender=None, to=None,
                     size=0, status=None, extra=None):
        return (sys, id, client, sender, to, size, status, extra)

    def _get_postfix_id(self, str):
        try: id = self.postfix_ident_re.search(str).group(1)
        except: id = 'unknown'
        return id

    def _get_sendmail_id(self, str):
        try: id = self.sendmail_ident_re.search(str).group(1)
        except: id = 'unknown'
        return id

    def _fix_address(self, address):
        if address == '<>': address = '<mailer-daemon>'
        address = self.htmlsafe(address)
        return address

    def _fix_sendmail_relay(self, str):
        try:
            host, ip = self.sendmail_relay_re.search(str).groups()
            str = self.gethost(ip)
        except: pass
        return str

    def _fix_sendmail_address(self, str):
        try: str = self.sendmail_from_re.search(str).group(1)
        except: pass
        return str
    
    def _get_top_report(self, rs, descr):
        toprep = self.subreport_wrap % (descr % self.toplim)
        toplist = rs.get_top(self.toplim)
        for count, member in toplist:
            key = self._fix_address(member[0])
            toprep += self.report_line % (str(count), key)
        return toprep
    
    def finalize(self, rs):
        ##
        # Go through the results and make sense out of them
        #
        msgdict = {}
        while 1:
            try: msgtup, mult = rs.popitem()
            except: break
            system, id, client, sender, rcpt, size, status, extra = msgtup
            if system is None or (id is None or id is 'unknown'): continue
            key = (system, id)
            try: msglist = msgdict[key]
            except KeyError: msglist = [[], [], [], [], [], []]
            if client is not None: msglist[0].append(client)
            if sender is not None: msglist[1].append(sender)
            if rcpt is not None: msglist[2].append(rcpt)
            if size is not None: msglist[3].append(size)
            if status is not None: msglist[4].append(status)
            if extra is not None: msglist[5].append(extra)
            msgdict[key] = msglist
        ##
        # Do some real calculations now that we have the results collapsed.
        #
        yrs = Result() # Systems
        crs = Result() # Clients (Connecting Relays)
        srs = Result() # Senders
        rrs = Result() # Recipients
        totalmsgs = 0
        totalsize = 0
        warnings = 0
        successes = 0
        bounces = 0
        procmailed = 0
        while 1:
            try: key, val = msgdict.popitem()
            except: break
            system, id = key
            yrs.add_result({(system,): 1})
            totalmsgs += 1
            clients, senders, rcpts, sizes, stati, extras = val
            for client in clients: crs.add_result({(client,): 1})
            for sender in senders: srs.add_result({(sender,): 1})
            for rcpt in rcpts: rrs.add_result({(rcpt,): 1})
            for size in sizes: totalsize += size
            for status in stati:
                if status == self.warning: warnings += 1
                elif status == self.success: successes += 1
                elif status == self.bounce: bounces += 1
            for extra in extras:
                if extra == self.procmail: procmailed += 1
        rep = self.subreport_wrap % 'General Mail Report'
        rep += self.report_line % (totalmsgs, 'Total Messages Processed')
        rep += self.report_line % (successes, 'Total Successful Deliveries')
        rep += self.report_line % (warnings, 'Total Warnings Issued')
        rep += self.report_line % (bounces, 'Total Bounced Messages')
        if procmailed:
            rep += self.report_line % (procmailed, 'Processed by Procmail')
        size, unit = self.mk_size_unit(totalsize)
        rep += self.report_line % ('%d %s' % (size, unit),
                                   'Total Transferred Size')

        if yrs: rep += self._get_top_report(yrs, 'Top %d active systems')
        if crs: rep += self._get_top_report(crs, 'Top %d connecting hosts')
        if srs: rep += self._get_top_report(srs, 'Top %d senders')
        if rrs: rep += self._get_top_report(rrs, 'Top %d recipients')
        
        report = self.report_wrap % rep
        
        return report

if __name__ == '__main__':
    from epylog.helpers import ModuleTest
    ModuleTest(mail_mod, sys.argv)
