#!/usr/bin/python -tt
"""
This module watches Dovecot, recording information about logins, disconnects,
and the like. Output gives a high-level view of all the disconnects and login
failures.
"""

import sys
import re

##
# This is for testing purposes, so you can invoke this from the
# modules directory. See also the testing notes at the end of the
# file.
#
sys.path.insert(0, '../py/')
from epylog import InternalModule

class dovecot_mod(InternalModule):

    def __init__(self, opts, logger):
        """
        Sets up the module, naturally.
        """
        InternalModule.__init__(self)
        self.logger = logger

        # For this mod, we'll use 5 as the default log level for general debug
        # statements and the like
        logger.put(5, 'Mod instantiated!');

        self.regex_map = {
            re.compile(r'imap-login', re.I)                                : self.imap_login,
            re.compile(r'pop[3s]?-login', re.I)                         : self.pop_login,
            re.compile(r'disconnected:?\s(?:for)?\sinactivity', re.I)    : self.inactivity,
            re.compile(r'disconnected:\sinternal\serror', re.I)         : self.internal_err,
            re.compile(r'auth\sfail(?:ed)?', re.I)                         : self.auth_fail,
            re.compile(r'disconnected:\slog(?:ged)?\sout', re.I)        : self.logout,
            re.compile(r'no\sauth\sattempt', re.I)                         : self.no_auth_atmt,
            re.compile(r'disconnected\sby\sserver', re.I)                 : self.sever_disc,
            re.compile(r'(?:too\smany)?\s?invalid\simap', re.I)         : self.invalid_imap,
            re.compile(r'(?:disallowed)?\s?plaintext\sauth', re.I)         : self.disallow_ptxt,
            re.compile(r'\seof\s', re.I)                                : self.unex_eof,
            re.compile(r'\((?P<user>\w*)\):\sconnection\sclosed', re.I)    : self.imap_close,
            re.compile(r'\((?P<user>\w*)\):\sdisconnected:\sdisconnected\s(?:in\sidle)?', re.I) : self.disc_idle,
            re.compile(r'disconnected\sin\sappend', re.I)                : self.fail_append,
            re.compile(r'director:\serror', re.I)                        : self.direc_error
        }

        # Useful strings for formatting the output
        self.report_table = '<table width="100%%" cellpadding="2">%s</table>'
        self.report_line = '<tr><td id="msg" width="90%%">%s</td><td id="mult">%s</td></tr><br/>'

    ##
    # Line-matching routines.
    # Available methods inherited from __init__.py.InternalModule:
    # - getuname(self, uid): returns a username for the given id
    # - gethost(self, ip_addr): reverse lookup on an IP address
    # - get_smm(self, lm): return a systemname, message, and multiplier from
    #        a linemap
    # - mk_size_unit(self, size): make a human-readable size unit from a size
    #         in bytes
    #
    def imap_login(self, linemap):
        return {('imap login'): linemap['mult']}

    def pop_login(self, linemap):
        return {('pop login'): linemap['mult']}

    def inactivity(self, linemap):
        """
        Catches disconnects due to inactivity.

        Log message: imap(<user>): Disconnected for inactivity
        """
        return {('inactivity'): linemap['mult']}

    def internal_err(self, linemap):
        """
        Catches unknown internal errors.

        Log message: imap(<user>): Disconnected: Internal error occurred.
        Refer to server log for more information.
        """
        return {('internal error'): linemap['multiplier']}

    def auth_fail(self, linemap):
        """
        Occurs when disconnected due to an authentification failure.

        Log message: Disconnected (auth failed)
        """
        return {('auth fail'): linemap['multiplier']}

    def logout(self, linemap):
        """
        Disconnect due to normal logout.
        """
        return {('logout'): linemap['multiplier']}

    def no_auth_atmpt(self, linemap):
        """
        Log message: Aborted login (no auth attempts in <num> secs)
        Or: Disconnected (no auth attempts in <num> secs)
        """
        return {('no auth attempt'): linemap['multiplier']}

    def server_disc(self, linemap):
        return {('server disc'): linemap['multiplier']}

    def invalid_imap(self, linemap):
        """
        Catches disconnects due to invalid commands.
        Log message: imap(<user>): Disconnected: Too many invalid IMAP commands
        """
        return {('invalid imap'): linemap['multiplier']}

    def disallow_ptxt(self, linemap):
        """
        Occurs when someone tries something bad during auth.
        Log message: Aborted login (tried to use disallowed plaintext auth)
        """
        return {('disallow ptxt'): linemap['multiplier']}

    def unex_eof(self, linemap):
        """
        TODO
        """
        return {('unex eof'): linemap['multiplier']}

    def imap_close(self, linemap):
        return {('imap close'): linemap['multiplier']}

    def disc_idle(self, linemap):
        return {('disc idle'): linemap['multiplier']}
    
    def fail_append(self, linemap):
        """
        TODO
        """
        return {('fail append'): linemap['multiplier']}

    def direc_error(self, linemap):
        return {('direc error'): linemap['multiplier']}

    ##
    # Returns the final report.
    # TODO. Let's hope that Epylog does its math correctly.
    #
    def finalize(self, resultset):
        report = []

        while True:
            try:
                key, mult = resultset.popitem()
                report.append(self.report_line % (key, mult))
            except KeyError:
                break

        final_report = ''.join(report)
        final_report = self.report_table % final_report
        return final_report

##
# This is useful when testing your module out.
# Invoke without command-line parameters to learn about the proper
# invocation.
#
if __name__ == '__main__':
    from epylog.helpers import ModuleTest
    ModuleTest(dovecot_mod, sys.argv)
