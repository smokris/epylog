"""
This module handles the... er... modules for epylog, both internal and
external.
"""
##
# Copyright (C) 2003 by Duke University
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.
#
# $Id$
#
# @Author Konstantin Riabitsev <icon@phy.duke.edu>
# @version $Date$
#

import ConfigParser
import epylog
import os
import tempfile
import string
import re

if 'mkdtemp' not in dir(tempfile):
    ##
    # Must be python < 2.3
    #
    del tempfile
    import mytempfile as tempfile

from ihooks import BasicModuleLoader
_loader = BasicModuleLoader()

class Module:
    """epylog Module class"""
    
    def __init__(self, cfgfile, logtracker, tmpprefix, logger):
        self.logger = logger
        logger.put(5, '>Module.__init__')
        logger.put(3, 'Initializing module for cfgfile %s' % cfgfile)
        config = ConfigParser.ConfigParser()
        logger.put(3, 'Reading in the cfgfile %s' % cfgfile)
        config.read(cfgfile)
        try: self.name = config.get('module', 'desc')
        except: self.name = 'Unnamed Module'
        try: self.enabled = config.getboolean('module', 'enabled')
        except: self.enabled = 0
        if not self.enabled:
            logger.put(3, 'This module is not enabled. Skipping init.')
            return
        try: self.executable = config.get('module', 'exec')
        except:
            msg = 'Did not find executable name in "%s"' % cfgfile
            raise epylog.ConfigError(msg, logger)
        try: self.internal = config.getboolean('module', 'internal')
        except: self.internal = 0
        try: self.priority = config.getint('module', 'priority')
        except: self.priority = 10
        
        try: logentries = config.get('module', 'files')
        except:
            msg = 'Cannot find log definitions in module config "%s"' % cfgfile
            raise epylog.ConfigError(msg, logger)
        try: self.outhtml = config.getboolean('module', 'outhtml')
        except: self.outhtml = 0

        self.extraopts = {}
        if config.has_section('conf'):
            logger.put(3, 'Found extra options')
            for option in config.options('conf'):
                value = config.get('conf', option)
                logger.put(5, '%s=%s' % (option, value))
                self.extraopts[option] = value
            logger.put(5, 'Done with extra options')

        modname = os.path.basename(self.executable)
        tempfile.tempdir = tmpprefix
        self.tmpprefix = tmpprefix
        self.logdump = tempfile.mktemp('%s.DUMP' % modname)
        self.logreport = tempfile.mktemp('%s.REPORT' % modname)
        self.logfilter = tempfile.mktemp('%s.FILTER' % modname)

        logger.put(5, 'name=%s' % self.name)
        logger.put(5, 'executable=%s' % self.executable)
        logger.put(5, 'enabled=%d' % self.enabled)
        logger.put(5, 'internal=%d' % self.internal)
        logger.put(5, 'priority=%d' % self.priority)
        logger.put(5, 'logentries=%s' % logentries)
        logger.put(5, 'outhtml=%d' % self.outhtml)
        logger.put(5, 'logdump=%s' % self.logdump)
        logger.put(5, 'logreport=%s' % self.logreport)
        logger.put(5, 'logfilter=%s' % self.logfilter)

        ##
        # Init internal modules
        #
        if self.internal: self._init_internal_module()
        
        logger.put(3, 'Figuring out the logfiles from the log list')
        entrylist = logentries.split(',')
        self.logs = []
        for entry in entrylist:
            entry = entry.strip()
            logger.put(5, 'entry=%s' % entry)
            logger.put(3, 'Getting a log object from entry "%s"' % entry)
            try:
                log = logtracker.getlog(entry)
            except epylog.AccessError:
                ##
                # Do not die, but disable this module and complain loudly
                #
                logger.put(0, 'Could not init logfile for entry "%s"' % entry)
                continue
            logger.put(5, 'Appending the log object to self.logs[]')
            self.logs.append(log)
        if len(self.logs) == 0:
            self.enabled = 0
            logger.put(0, 'Module "%s" disabled' % self.name)
            return
        logger.put(5, '<Module.__init__')

    def is_internal(self):
        """
        Returns true if the module at hand is internal.
        """
        if self.internal:
            self.logger.put(5, 'This module is internal')
            return 1
        else:
            self.logger.put(5, 'This module is not internal')
            return 0

    def _init_internal_module(self):
        """
        Initializes an internal module by importing it and running
        the __init__.
        """
        logger = self.logger
        logger.put(5, '>Module._init_internal_module')
        dirname = os.path.dirname(self.executable)
        modname = os.path.basename(self.executable)
        modname = re.sub(re.compile('\.py'), '', modname)
        logger.puthang(3, 'Importing module "%s"' % modname)
        stuff = _loader.find_module_in_dir(modname, dirname)
        if stuff:
            try: module = _loader.load_module(modname, stuff)
            except Exception, e:
                msg = ('Failure trying to import module "%s" (%s): %s' %
                       (self.name, self.executable, e))
                raise epylog.ModuleError(msg, logger)
        else:
            msg = ('Could not find module "%s" in dir "%s"' %
                   (modname, dirname))
            raise epylog.ModuleError(msg, logger)
        logger.endhang(3)
        try:
            modclass = getattr(module, modname)
            self.epymod = modclass(self.extraopts, logger)
        except AttributeError:
            msg = 'Could not instantiate class "%s" in module "%s"'
            msg = msg % (modname, self.executable)
            raise epylog.ModuleError(msg, logger)
        logger.put(3, 'Opening "%s" for writing' % self.logfilter)
        self.filtfh = open(self.logfilter, 'w+')
        logger.put(5, '<Module._init_internal_module')

    def message_match(self, message):
        """
        Used by internal modules to match the message of a syslog entry
        against the list of regexes in the .regex_map.
        """
        logger = self.logger
        logger.put(5, '>Module.message_match')
        handler = None
        match_regex = None
        for regex in self.epymod.regex_map.keys():
            if regex.search(message):
                logger.put(5, 'match: %s' % message)
                logger.put(5, 'matching module: %s' % self.name)
                match_regex = regex
                handler = self.epymod.regex_map[regex]
                break
        logger.put(5, '<Module.message_match')
        return (handler, match_regex)

    def put_filtered(self, line):
        """
        Puts a filtered line into the file with all filtered lines.
        """
        logger = self.logger
        logger.put(5, '>Module.put_filtered')
        self.filtfh.write(line)
        logger.put(3, 'Wrote "%s" into filtfh' % line)
        logger.put(5, '<Module.put_filtered')

    def no_report(self):
        """
        Cleanup routine in case there is no report for this module.
        """
        self.logger.put(5, '>Module.no_report')
        self.logreport = None
        self.logfilter = None
        self.close_filtered()
        self.logger.put(5, '<Module.no_report')
        
    def close_filtered(self):
        """
        Closes the file with filtered messages.
        """
        logger = self.logger
        logger.put(5, '>Module.close_filtered')
        self.filtfh.close()
        logger.put(5, '<Module.close_filtered')

    def finalize_processing(self, rs):
        """
        Called at the end of all processing to generate the report,
        return it, and delete the imported internal module.
        """
        logger = self.logger
        logger.put(5, '>Module.finalize_processing')
        logger.put(3, 'Finalizing for module "%s"' % self.name)
        if self.filtfh.tell():
            if not rs.is_empty():
                logger.put(3, 'Finalizing the processing')
                report = self.epymod.finalize(rs)
                if report:
                    logger.put(5, 'Report follows:')
                    logger.put(5, report)
                    repfh = open(self.logreport, 'w')
                    repfh.write(report)
                    repfh.close()
            else:
                self.logreport = None
                self.logfilter = None
        else:
            logger.put(3, 'No filtered strings for this module')
            self.logreport = None
            self.logfilter = None
        self.close_filtered()
        logger.put(3, 'Done with this module, deleting')
        del self.epymod
        logger.put(5, '<Module.finalize_processing')
    
    def invoke_external_module(self, cfgdir):
        """
        Invokes an external module by passing some config parameters
        as ENV variables and then executing the module itself.
        """
        logger = self.logger
        logger.put(5, '>Module._invoke_external_module')
        logger.put(3, 'Dumping strings into "%s"' % self.logdump)
        totallen = self._dump_log_strings(self.logdump)
        if totallen == 0:
            logger.put(3, 'Nothing in the logs for this module. Passing exec')
            return
        logger.put(5, 'Setting LOGCAT to "%s"' % self.logdump)
        os.putenv('LOGCAT', self.logdump)
        modtmpprefix = os.path.join(self.tmpprefix, 'EPYLOG')
        logger.put(5, 'Setting TMPPREFIX env var to "%s"' % modtmpprefix)
        os.putenv('TMPPREFIX', modtmpprefix)
        logger.put(5, 'Setting CONFDIR env var to "%s"' % cfgdir)
        os.putenv('CONFDIR', cfgdir)
        if logger.is_quiet():
            logger.put(2, 'This line will never be seen. :)')
            os.putenv('QUIET', 'YES')
        logger.put(5, 'Setting DEBUG to "%s"' % logger.debuglevel())
        os.putenv('DEBUG', logger.debuglevel())
        logger.put(5, 'Setting LOGREPORT to "%s"' % self.logreport)
        logger.put(5, 'Setting LOGFILTER to "%s"' % self.logfilter)
        os.putenv('LOGREPORT', self.logreport)
        os.putenv('LOGFILTER', self.logfilter)
        if len(self.extraopts):
            logger.put(5, 'Setting extra options')
            for extraopt in self.extraopts.keys():
                optname = string.upper(extraopt)
                optval = self.extraopts[extraopt]
                logger.put(5, 'Setting %s to "%s"' % (optname, optval))
                os.putenv(optname, optval)
        logger.put(3, 'Invoking "%s"' % self.executable)
        exitcode = os.system(self.executable)
        logger.put(3, 'External module finished with code "%d"' % exitcode)
        if exitcode and exitcode != 256:
            msg = ('External module "%s" exited abnormally (exit code %d)' %
                   (self.executable, exitcode))
            raise epylog.ModuleError(msg, logger)
        logger.put(3, 'Checking if we have the report')
        if not os.access(self.logreport, os.R_OK):
            logger.put(3, 'Report %s does not exist!' % self.logreport)
            self.logreport = None
        logger.put(3, 'Checking if we have the filtered strings')
        if not os.access(self.logfilter, os.R_OK):
            logger.put(3, 'Filtered file %s does not exist!' % self.logfilter)
            self.logfilter = None
        logger.put(5, '<Module._invoke_external_module')
        
    def sanity_check(self):
        """
        Some sanity checks performed on a module before accepting it as
        a valid one.
        """
        logger = self.logger
        logger.put(5, '>Module.sanity_check')
        logger.put(3, 'Checking if executable "%s" is sane' % self.executable)
        if not os.access(self.executable, os.F_OK):
            msg = ('Executable "%s" for module "%s" does not exist'
                   % (self.executable, self.name))
            raise epylog.ModuleError(msg, logger)
        if not self.is_internal():
            if not os.access(self.executable, os.X_OK):
                msg = ('Executable "%s" for module "%s" is not set to execute'
                       % (self.executable, self.name))
                raise epylog.ModuleError(msg, logger)
        logger.put(5, '<Module.sanity_check')
        
    def get_html_report(self):
        """
        Get the report from a module, and if it's not HTML, making it HTML
        first.
        """
        logger = self.logger
        logger.put(5, '>Module.get_html_report')
        if self.logreport is None:
            logger.put(3, 'No report from this module')
            return None
        logger.put(3, 'Getting the report from "%s"' % self.logreport)
        if not os.access(self.logreport, os.R_OK):
            msg = 'Log report from module "%s" is missing' % self.name
            raise epylog.ModuleError(msg, logger)
        logger.puthang(3, 'Reading the report from file "%s"' % self.logreport)
        fh = open(self.logreport)
        report = fh.read()
        fh.close()
        logger.endhang(3, 'done')
        if len(report):
            if not self.outhtml:
                logger.put(3, 'Report is not html')
                report = self._make_into_html(report)
        else:
            report = None
        logger.put(5, '<Module.get_html_report')
        return report

    def get_filtered_strings_fh(self):
        """
        Get the file handle of the file with filtered strings.
        """
        logger = self.logger
        logger.put(5, '>Module.get_filtered_strings_fh')
        if self.logfilter is None:
            logger.put(3, 'No filtered strings from this module')
            return None
        logger.put(3, 'Opening filtstrings file "%s"' % self.logfilter)
        if not os.access(self.logfilter, os.R_OK):
            msg = 'Filtered strings file for "%s" is missing' % self.name
            raise epylog.ModuleError(msg, logger)
        fh = open(self.logfilter)
        logger.put(5, '<Module.get_filtered_strings_fh')
        return fh
           
    def _dump_log_strings(self, filename):
        """
        Dumps all log strings from the collection of logs it keeps internally
        into a provided filename.
        """
        logger = self.logger
        logger.put(5, '>Module._dump_log_strings')
        logger.put(5, 'filename=%s' % filename)
        logger.put(3, 'Opening the "%s" for writing' % filename)
        fh = open(filename, 'w')
        len = 0
        for log in self.logs:
            len = len + log.dump_strings(fh)
        logger.put(3, 'Total length of the log is "%d"' % len)
        logger.put(5, '<Module._dump_log_strings')
        return len

    def _make_into_html(self, report):
        """
        Utility function that turns plaintext into HTML by essentially
        wrapping it into "<pre></pre>" and escaping the control chars.
        """
        logger = self.logger
        logger.put(5, '>Module._make_into_html')
        logger.put(3, 'Regexing entities')
        report = re.sub(re.compile('&'), '&amp;', report)
        report = re.sub(re.compile('<'), '&lt;', report)
        report = re.sub(re.compile('>'), '&gt;', report)
        report = '<pre>\n%s\n</pre>' % report
        logger.put(5, '<Module._make_into_html')
        return report
