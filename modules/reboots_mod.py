#!/usr/bin/python -tt

import re
import string

class reboots_mod:
    def __init__(self, logger):
        self.logger = logger
        self.athreads = 50
        self.regex_map = {
            re.compile('kernel: Linux version'): self.linux_reboot
        }
        self.kernel_re = re.compile('Linux\s*version\s*(\S+)')

    def linux_reboot(self, stamp, system, message):
        logger = self.logger
        logger.put(5, '>reboots_mod.linux_reboot')
        mo = self.kernel_re.search(message)
        if mo:
            kernel = mo.group(1)
        else:
            kernel = 'Kernel Unknown'
        logger.put(5, '%s rebooted with version %s' % (system, kernel))
        logger.put(5, '<reboots_mod.linux_reboot')
        return [system, kernel]

    def finalize(self, resultset):
        logger = self.logger
        logger.put(5, '>reboots_mod.finalize')
        if len(resultset):
            report = self.__get_report(resultset)
        else:
            report = ''
        logger.put(5, '<reboots_mod.finalize')
        return report

    def __get_report(self, resultset):
        hosts = {}
        for system, kernel in resultset:
            try:
                hosts[system][kernel] += 1
            except KeyError:
                hosts[system] = {kernel: 1}
        report =  '<table border="0">'
        repline = '<tr><td align="right">%s:</td><td>%s</td></tr>'
        for system in hosts.keys():
            kernels = []
            for kernel in hosts[system].keys():
                kernels.append('%s(%d)' % (kernel, hosts[system][kernel]))
            report += repline % (system, string.join(kernels, ', '))
        report += '</table>'
        return report
