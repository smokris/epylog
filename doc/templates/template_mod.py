#!/usr/bin/python -tt
import sys
import re

##
# This is for testing purposes, so you can invoke this from the
# modules directory. See also the testing notes at the end of the
# file.
#
sys.path.insert(0, '../py/')
from epylog import InternalModule

class template_mod(InternalModule):
    ##
    # opts: is a map with extra options set in
    #       [conf] section of the module config, or on the
    #       command line using -o flag to the module.
    # logger: A logging object. API:
    #         logger.put(loglvl, 'Message')
    #         Only critical stuff needs to go onto lvl 0.
    #         Common output goes to lvl 1.
    #         Others are debug levels.
    #
    def __init__(self, opts, logger):
        ##
        # Do a "super-init" so the class we are subclassing gets
        # instantiated.
        #
        InternalModule.__init__(self)
        self.logger = logger
        ##
        # Convenience
        #
        rc = re.compile
        ##
        # This map specifies the regexes and the handlers for them.
        # ===> THIS MAP MUST EXIST AND BE NAMED "regex_map" <==
        # The format is as follows:
        #self.regex_map = {
        #    rc('STRING TO MATCH'): self.handler_func,
        #    rc('ANOTHER STRING'): self.other_handler_func
        #    }
        #
        self.regex_map = {
        }

    ##
    # Line-matching routines
    #
    def handler_func(self, linemap):
        ##
        # linemap is a dictionary with the following members:
        # line: the original, unadulterated line.
        # stamp: unix timestamp of the event
        # system: the reporting hostname
        # message: The actual message
        # multiplier: This is how many times this event occurs.
        #             Most often this will be set to 1, but it
        #             can have other values as a result of unwrapping
        #             the "last message repeated" lines by epylog.
        #

        ##
        # See the methods in epylog.InternalModule for insight on
        # which convenience methods are available to you.
        #

        ##
        # DO SOME STUFF HERE
        #

        ##
        # The result of your computation must be a dictionary with the
        # following fields:
        # * A tuple of values used as key
        # * An integer indicating how many times this occurs.
        #   Usually this will be the "multiplier" carried over, but
        #   somethimes that value will be incremented depending on the
        #   result of your processing.
        # E.g.: return {('linux0', '2.4.20-9', 'Linux'): 1}
        # Multiple fields are permitted.
        #
        # Returning None will indicate that the line has not been processed
        # successfully.
        #
        return {}

    def finalize(self, resultset):
        ##
        # A resultset is a dictionary of all values returned by your
        # handler functions -- except they are unique and show how many
        # times each tuple occurs.
        # See epylog.Result for some convenience methods to use when
        # processing and analyzing the results.
        #
        return '<b>REPORT</b>'

##
# This is useful when testing your module out.
# Invoke without command-line parameters to learn about the proper
# invocation.
#
if __name__ == '__main__':
    from epylog.helpers import ModuleTest
    ModuleTest(template_mod, sys.argv)
