#!/usr/bin/python -tt

import re
import string
from epylog.module import Result

class reboots_mod:
    def __init__(self, opts, logger):
        self.logger = logger
        self.regex_map = {
            re.compile('kernel: Linux version'): self.linux_reboot
        }
        self.kernel_re = re.compile('Linux\s*version\s*(\S+)')
        try: self.report_wrap = opts['report_wrap']
        except KeyError: self.report_wrap = '<table border="0">%s</table>'
        try: self.report_line = opts['report_line']
        except KeyError: self.report_line = '<tr><td>%s:</td><td>%s</td></tr>'

    def linux_reboot(self, stamp, system, message, multiplier):
        logger = self.logger
        logger.put(5, '>reboots_mod.linux_reboot')
        mo = self.kernel_re.search(message)
        if mo: kernel = mo.group(1)
        else: kernel = 'Kernel Unknown'
        logger.put(5, '<reboots_mod.linux_reboot')
        return Result((system, kernel), multiplier)

    def finalize(self, rs):
        logger = self.logger
        logger.put(5, '>reboots_mod.finalize')
        report = ''
        for system in rs.get_distinct(()):
            mymap = rs.get_submap((system,))
            kernels = []
            for kernel in mymap.keys():
                kernels.append('%s(%d)' % (kernel[0], mymap[kernel]))
            report += self.report_line % (system, string.join(kernels, ', '))
        report = self.report_wrap % report
        return report
