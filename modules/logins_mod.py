#!/usr/bin/python -tt

import re
import epylog

class logins_mod(epylog.module.PythonModule):
    def __init__(self, logger):
        epylog.module.PythonModule.__init__(self)
        self.logger = logger
        rc = re.compile
        self.athreads = 50
        self.regex_map = {
            rc('\(pam_unix\)'): self.newpam
        }

    def handler_func(self, stamp, system, message):
        ##
        # stamp: unix timestamp of the event
        # system: the reporting hostname
        # message: The actual message
        #
        # Return some sort of a resultset that can be appended to the list
        # and later comprehended by finalize.
        return 'some result'

    def finalize(self, resultset):
        ##
        # This is where you get the list of results returned by
        # your handler functions and make sense out of them
        #
        # Return a html report.
        return '<b>REPORT</b>'
