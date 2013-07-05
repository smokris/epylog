#!/usr/bin/python -tt
"""
This module watches Dovecot 2, recording information about logins, disconnects,
This module watches Dovecot, recording information about logins, disconnects,
and the like. Output gives a high-level view of all the disconnects and login
failures.
"""

import sys
import re
from itertools import izip

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

        # Save this for use later. (Captures usernames for login failures)
        self.re_mix = re.compile(r'auth: error: userdb\((?P<user>\w*),(?P<ip>\d*\.\d*\.\d*\.\d*),(?:.*)\)', re.I)

        self.regex_map = {
            # Logins
            re.compile(r'imap-login:\slogin:', re.I)                    : self.login_imap,
            re.compile(r'pop3-login:\slogin:', re.I)                    : self.login_pop,

            # Logouts
            re.compile(r'imap\(\w*\): disconnected: logged out', re.I)  : self.logout_imap,
            re.compile(r'pop3\(\w*\): disconnected: logged out', re.I)  : self.logout_pop,

            # Disconnects and closed connections
            re.compile(r'disconnected:?\s(?:for)?\sinactivity', re.I)   : self.disc_inactivity,
            re.compile(r'disconnected:\sinternal\serror', re.I)         : self.disc_interr,
            re.compile(r'disconnected\sby\sserver', re.I)               : self.disc_server,
            re.compile(r'disconnected\sby\sclient', re.I)               : self.disc_client,
            re.compile(r'disconnected\sin\sidle', re.I)                 : self.disc_idle,
            re.compile(r'disconnected\sin\sappend', re.I)               : self.disc_append,
            re.compile(r'imap\(\w*\):\sconnection\sclosed', re.I)       : self.close_imap,
            re.compile(r'pop3\(\w*\):\sconnection\sclosed', re.I)       : self.close_pop,

            # Other things: failures, etc.
            re.compile(r'authenticated user not found', re.I)           : self.user_notfound,
            self.re_mix                                                 : self.user_mixedcase,
            re.compile(r'auth\sfail(?:ed)?', re.I)                      : self.auth_fail,
            re.compile(r'no\sauth\sattempt', re.I)                      : self.no_auth_atmpt,
            re.compile(r'(?:too\smany)?\s?invalid\simap', re.I)         : self.invalid_imap,
            re.compile(r'(?:disallowed)?\s?plaintext\sauth', re.I)      : self.disallow_ptxt,
            re.compile(r'\seof\s', re.I)                                : self.unex_eof,

            # Lines we choose to forcefully ignore
            re.compile(r'director:\serror', re.I)                       : self.ignore
        }

    longnames = {
        'login_imap': 'Total IMAP logins',
        'login_pop': 'Total POP3 logins',
        'disc_inactivity': 'Inactivity',
        'disc_interr': 'Internal error occurred. Refer to server log for more information.',
        'auth_fail': 'auth failed',
        'disc_append': 'failed append',
        'logout_imap': 'logged out: IMAP',
        'logout_pop': 'logged out: POP3',
        'no_auth_atmpt': 'no auth attempt',
        'invalid_imap': 'too many invalid IMAP commands',
        'disallow_ptxt': 'tried to use disallowed plaintext auth',
        'unex_eof': 'unexpected eof'
    }

    ##
    # Login routines
    #
    def login_imap(self, linemap):
        """
        Records successful IMAP logins.
        Log message: imap-login: Login: ...
        """
        return {('connect', 'login_imap'): linemap['multiplier']}

    def login_pop(self, linemap):
        """
        Records successful POP logins.
        Log message: pop3-login: Login: ...
        """
        return {('connect', 'login_pop'): linemap['multiplier']}

    ##
    # Logout routines
    #
    def logout_imap(self, linemap): 
        """
        Records success (i.e. no indication of failure) on IMAP logout.
        Log message: imap(<user>): Disconnected: Logged out
        """
        return {('disconnect', 'logout_imap'): linemap['multiplier']}

    def logout_pop(self, linemap):
        """
        Records success (i.e. no indication of failure) on POP3 logout.
        Log message: pop3(<user>): Disconnected: Logged out
        """
        return {('disconnect', 'logout_pop'): linemap['multiplier']}

    ##
    # Disconnects and connection closures
    #
    def disc_inactivity(self, linemap):
        """
        Catches disconnects due to inactivity.
        Log message: (<user>): Disconnected for inactivity
        """
        return {('disconnect', 'disc_inactivity'): linemap['multiplier']}

    def disc_interr(self, linemap):
        """
        Catches unknown internal errors.
        Log message:    imap(<user>): Disconnected: Internal error occurred.
                        Refer to server log for more information.
        """
        return {('disconnect', 'disc_interr'): linemap['multiplier']}

    def disc_server(self, linemap):
        """
        Catches disconnects by the server.
        Log message: Disconnected by server
        """
        return {('disconnect', 'disc_server'): linemap['multiplier']}

    def disc_client(self, linemap):
        """
        Catches disconnects from the client side.
        Log message: Disconnected by client
        """
        return {('disconnect', 'disc_client'): linemap['multiplier']};

    def disc_idle(self, linemap):
        """
        Catches disconnects due to idleness.
        Log message: Disconnected: disconnected in IDLE
        """
        return {('disconnect', 'disc_idle'): linemap['multiplier']}

    def disc_append(self, linemap):
        """
        Catches failed append errors.
        Log message: Disconnected in APPEND
        """
        return {('disconnect', 'disc_append'): linemap['multiplier']}

    def close_imap(self, linemap):
        """
        Catches closed IMAP connections.
        Log message: imap(<user>): Connection closed
        """
        return {('disconnect', 'close_imap'): linemap['multiplier']}

    def close_pop(self, linemap):
        """
        Catches closed POP3 connections.
        Log message: pop3(<user>): Connection closed
        """
        return {('disconnect', 'close_pop'): linemap['multiplier']}

    ##
    # Other failures
    #
    def user_notfound(self, linemap):
        """
        Occurs when a user attempts to log in, but isn't in the user database.
        Log message: Authenticated uer not found from userdb
        """
        return {('disconnect', 'user_notfound'): linemap['multiplier']}

    def user_mixedcase(self, linemap):
        """
        Strange errors happen when users with mixed case attempt to log in.
        Log message: auth: Error: userdb(<user>, <ip>, ...)
        """
        # Run it through the regex again to get the capturing groups.
        # (TODO: there has to be a better way to do this)
        matchobj = self.re_mix.search(linemap['line'])

        # This should never happen. But better safe than sorry, right?
        if not matchobj:
            self.logger.put(5, 'ERROR: No regex match')
            self.logger.put(5, 'Offending line: ' + linemap['line'])
            return {('mixedcase', '[Unknown]', '[Unknown]') : linemap['multiplier']}

        user, ip = matchobj.group('user'), matchobj.group('ip')

        # Some sanity checks. Hopefully this never happens
        if not user:
            self.logger.put(5, 'WARNING: Mixed-case login failure detected, \
                    but no username could be found in the regex.')
            self.logger.put(5, 'Line: ' + linemap['line'])
            user = '[Unknown]'
        if not ip:
            self.logger.put(5, 'WARNING: Mixed-case login failure detected, \
                    but no IP address could be found in the regex.')
            self.logger.put(5, 'Line: ' + linemap['line'])
            ip = '[Unknown]'

        return {('mixedcase', user, ip): linemap['multiplier']}

    def auth_fail(self, linemap):
        """
        Occurs when disconnected due to an authentification failure.
        Log message: Disconnected (auth failed)
        """
        return {('disconnect', 'auth_fail'): linemap['multiplier']}

    def no_auth_atmpt(self, linemap):
        """
        Log message: Aborted login (no auth attempts in <num> secs)
        Or: Disconnected (no auth attempts in <num> secs)
        """
        return {('disconnect', 'no_auth_atmpt'): linemap['multiplier']}

    def invalid_imap(self, linemap):
        """
        Catches disconnects due to invalid commands.
        Log message: imap(<user>): Disconnected: Too many invalid IMAP commands
        """
        return {('disconnect', 'invalid_imap'): linemap['multiplier']}

    def disallow_ptxt(self, linemap):
        """
        Occurs when someone tries something bad during auth.
        Log message: Aborted login (tried to use disallowed plaintext auth)
        """
        return {('disconnect', 'disallow_ptxt'): linemap['multiplier']}

    def unex_eof(self, linemap):
        """
        Catches eof errors.
        Log message: Unexpected eof
        """
        # TODO what the hell is the real unexpected eof message
        return {('disconnect', 'unex_eof'): linemap['multiplier']}

    ##
    # We just want to ignore these.
    #
    def ignore(self, linemap):
        """
        We purposely want to ignore these messages.
        Currently ignored log messages: Director errors
        """
        return {}

    ##
    # Returns the final report.
    # TODO. Let's hope that Epylog does its math correctly.
    #
    def finalize(self, resultset):
        report = []
        titles = ['Dovecot IMAP and POP3 Connection Totals', 'Dovecot Disconnects']
        categories = ['connect', 'disconnect']
        for title, category in izip(titles, categories):
            block = [title]
            for key in resultset.keys():
                if key[0] == category:
                    block.append([self.longnames[key[1]], resultset[key]])
            report.extend(dovecot_mod.blockformat(block))
        block = ['Login failures with mixed case']
        for ket in resultset.keys():
            if key[0] == 'mixedcase':
                block.append([key[1], key[2], resultset[key]])
        report.extend(dovecot_mod.blockformat(block))

        final_report = '\n'.join(report)
        return final_report

    @staticmethod
    def blockformat(block):
        ret = []
        ret.append(block[0] + ':')
        ret.append('='*len(block[0]))
        for arg in block[1:]:
            if len(arg) == 2:
                ret.append('\t{0}: {1} time(s)'.format(arg[0], arg[1]))
            else:
                ret.append('\t{0} ({1}): {2} time(s)'.format(arg[0], arg[1], arg[2]))
        return ret

##
# This is useful when testing your module out.
# Invoke without command-line parameters to learn about the proper
# invocation.
#
if __name__ == '__main__':
    from epylog.helpers import ModuleTest
    ModuleTest(dovecot_mod, sys.argv)
