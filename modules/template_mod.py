#!/usr/bin/python -tt

import re
import epylog

class template_mod(epylog.module.PythonModule):
    ##
    # opts: is a map with extra options set in
    #       [conf] section of the module config.
    # logger: A logging object. API:
    #         logger.put(loglvl, 'Message')
    #         Only critical stuff needs to go onto lvl 0.
    #         Common output goes to lvl 1.
    #         Others are debug levels.
    #
    def __init__(self, opts, logger):
        epylog.module.PythonModule.__init__(self)
        self.logger = logger
        rc = re.compile
        ##
        # The following two variables need to exist and be set!!
        #
        # athreads -- number of active threads. If most of what your
        # module is doing is looking up hostnames, then you can set it to
        # around a 100 (hard-coded limit, see __init__.py).
        # If, OTOH, you are doing a lot of intensive computations, you should
        # set this to a lower number
        #
        self.athreads = 50
        ##
        # This map specifies the regexes and the handlers for them.
        # The format is as follows:
        #self.regex_map = {
        #    rc('STRING TO MATCH'): self.handler_func,
        #    rc('ANOTHER STRING'): self.other_handler_func
        #    }
        #
        self.regex_map = {
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
