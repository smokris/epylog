import ConfigParser
import exceptions
import os
import pickle
import shutil
import mytempfile as tempfile
import re
import time
import threading

from report import Report
from module import Module
from log import LogTracker

VERSION = 'Epylog-0.9.0'
CHUNK_SIZE = 8192
GREP_LINES = 10000
LOG_SPLIT_RE = re.compile(r'(.{15,15}) (\S+) (.*)$')
SYSLOG_NG_STRIP = re.compile(r'.*[@/]')
MESSAGE_REPEATED_RE = re.compile(r'last message repeated (\S+) times')


class FormatError(exceptions.Exception):
    def __init__(self, message, logger):
        logger.put(2, 'Raising FormatError with message: %s' % message)
        self.args = message

class ConfigError(exceptions.Exception):
    def __init__(self, message, logger):
        logger.put(2, 'Raising ConfigError with message: %s' % message)
        self.args = message

class AccessError(exceptions.Exception):
    def __init__(self, message, logger):
        logger.put(2, 'Raising AccessError with message: %s' % message)
        self.args = message

class OutOfRangeError(exceptions.Exception):
    def __init__(self, message, logger):
        logger.put(2, 'Raising OutOfRangeError with message: %s' % message)
        self.args = message

class ModuleError(exceptions.Exception):
    def __init__(self, message, logger):
        logger.put(2, 'Raising ModuleError with message: %s' % message)
        self.args = message

class SysCallError(exceptions.Exception):
    def __init__(self, message, logger):
        logger.put(2, 'Raising SysCallError with message: %s' % message)
        self.args = message

class NoSuchLogError(exceptions.Exception):
    def __init__(self, message, logger):
        logger.put(2, 'Raising NoSuchLogError with message: %s' % message)
        self.args = message

class GenericError(exceptions.Exception):
    def __init__(self, message, logger):
        logger.put(2, 'Raising GenericError with message: %s' % message)
        self.args = message

class Epylog:
    def __init__(self, cfgfile, logger):
        self.logger = logger
        logger.put(5, '>Epylog.__init__')

        config = ConfigParser.ConfigParser()
        logger.puthang(3, 'Reading the config file "%s"' % cfgfile)
        config.read(cfgfile)
        logger.endhang(3)
        ##
        # Read in the main configuration
        #
        logger.puthang(3, "Reading in main entries")
        try:
            self.cfgdir = config.get('main', 'cfgdir')
            self.vardir = config.get('main', 'vardir')
        except:
            msg = 'Could not parse the main config file "%s"' % cfgfile
            raise ConfigError(msg, logger)
        logger.put(4, 'cfgdir=%s' % self.cfgdir)
        logger.put(4, 'vardir=%s' % self.vardir)
        logger.endhang(3)
        
        logger.put(3, 'Checking if we can write to vardir')
        if not os.access(self.vardir, os.W_OK):
            msg = 'Write access required for vardir "%s"' % self.vardir
            raise ConfigError(msg, logger)

        ##
        # Set up a safe temp dir
        #
        logger.put(3, 'Setting up a temporary directory')
        try:
            tmpdir = config.get('main', 'tmpdir')
            tempfile.tempdir = tmpdir
        except:
            pass
        logger.put(3, 'Creating a safe temporary directory')
        try:
            tmpprefix = tempfile.mkdtemp('EPYLOG')
        except:
            msg = 'Could not create a safe temp directory in "%s"' % tmpprefix
            raise ConfigError(msg, logger)
        self.tmpprefix = tmpprefix
        tempfile.tempdir = tmpprefix
        logger.put(3, 'Temporary directory created in "%s"' % tmpprefix)
        logger.put(3, 'Sticking tmpprefix into config to pass to other objs')
        config.tmpprefix = self.tmpprefix
        ##
        # Get multimatch pref
        #
        try:
            self.multimatch = config.getboolean('main', 'multimatch')
        except:
            self.multimatch = 0
        logger.put(5, 'multimatch=%d' % self.multimatch)
        ##
        # Get threading pref
        #
        try:
            threads = config.getint('main', 'threads')
            athreads = config.getint('main', 'active_threads')
            if threads < 2:
                logger.put(0, 'Threads set to less than 2, fixing')
                threads = 2
            if athreads < 1:
                logger.put(0, 'Active threads set to less than 1, fixing')
                athreads = 1
            if athreads > threads:
                logger.put(0, 'Config sets more active threads than total')
                logger.put(0, 'Setting active threads equaling total threads')
                athreads = threads
            self.threads = threads
            self.athreads = athreads
        except:
            self.threads = 100
            self.athreads = 50
        logger.put(5, 'threads=%d' % self.threads)
        logger.put(5, 'athreads=%d' % self.athreads)
        ##
        # Initialize the Report object
        #
        logger.puthang(3, 'Initializing the Report')
        self.report = Report(config, logger)
        logger.endhang(3)
        ##
        # Initialize the LogTracker object
        #
        logger.puthang(3, 'Initializing the log tracker object')
        logtracker = LogTracker(config, logger)
        self.logtracker = logtracker
        logger.endhang(3)
        ##
        # Process module configurations
        #
        self.modules = []
        priorities = []
        modcfgdir = os.path.join(self.cfgdir, 'modules.d')
        logger.put(3, 'Checking if module config dir "%s" exists' % modcfgdir)
        if not os.path.isdir(modcfgdir):
            msg = 'Module configuration directory "%s" not found' % modcfgdir
            raise ConfigError(msg, logger)
        logger.put(3, 'Looking for module configs in %s' % modcfgdir)
        for file in os.listdir(modcfgdir):
            cfgfile = os.path.join(modcfgdir, file)
            if os.path.isfile(cfgfile):
                logger.put(3, 'Found file: %s' % cfgfile)
                logger.put(3, 'Checking if it ends in ".conf"')
                if not re.compile('\.conf$').search(cfgfile, 1):
                    logger.put(3, 'No match. Skipping this file')
                    continue
                logger.put(3, 'Ends in .conf all right.')
                logger.puthang(3, 'Calling the Module init routines')
                try:
                    module = Module(cfgfile, logtracker, tmpprefix, logger)
                except (ConfigError, ModuleError), e:
                    msg = 'Module Error: %s' % e
                    logger.put(0, msg)
                    continue
                logger.endhang(3)
                if module.enabled:
                    logger.put(2, 'Module "%s" is enabled' % module.name)
                    logger.put(3, 'Checking "%s" for sanity' % module.name)
                    module.sanity_check()
                    logger.put(3, 'Sanity checks passed. Remembering module')
                    self.modules.append(module)
                    priorities.append(module.priority)
                else:
                    logger.put(2, 'Module "%s" is not enabled, ignoring'
                               % module.name)
            else:
                logger.put(3, '%s is not a regular file, ignoring' % cfgfile)
        logger.put(3, 'Total of %d modules initialized' % len(self.modules))
        if len(self.modules) == 0:
            raise ConfigError('No modules are enabled. Exiting.', logger)
        ##
        # Sort modules by priority
        #
        logger.put(5, 'sorting modules by priority')
        priorities.sort()
        for module in self.modules:
            logger.put(5, 'analyzing module: %s' % module.name)
            for i in range(0, len(priorities)):
                try:
                    logger.put(5, 'module.priority=%d, priorities[i]=%d'
                               % (module.priority, priorities[i]))
                except:
                    logger.put(5, 'priorities[i] is module: %s'
                               % priorities[i].name)
                if module.priority == priorities[i]:
                    priorities[i] = module
                    logger.put(5, 'priorities[i] is now: %s' % module.name)
                    break
        self.modules = priorities
        for module in self.modules:
            logger.put(5, 'module: %s, priority: %d'
                       % (module.name, module.priority))
        logger.put(5, '<Epylog.__init__')

    def process_modules(self):
        logger = self.logger
        logger.put(5, '>Epylog.process_modules')
        logger.put(3, 'Finding internal modules')
        imodules = []
        emodules = []
        for module in self.modules:
            if module.is_internal(): imodules.append(module)
            else: emodules.append(module)
        if len(imodules):
            self._process_internal_modules(imodules)
        if len(emodules):
            logger.puthang(3, 'Processing external modules')
            for module in emodules:
                logger.puthang(1, 'Processing module "%s"' % module.name)
                try:
                    module.invoke_external_module(self.cfgdir)
                except ModuleError, e:
                    ##
                    # Module execution error!
                    # Do not die, but provide a visible warning.
                    #
                    logger.put(0, str(e))
                logger.endhang(1, 'done')
            logger.endhang(3)
        logger.put(5, '<Epylog.process_modules')

    def make_report(self):
        logger = self.logger
        logger.put(5, '>Epylog.make_report')
        for module in self.modules:
            logger.put(5, 'Analyzing reports from module "%s"' % module.name)
            logger.put(5, 'logerport=%s' % module.logreport)
            logger.put(5, 'logfilter=%s' % module.logfilter)
            if module.logreport is None and module.logfilter is None:
                logger.put(2, 'No output from module "%s"' % module.name)
                logger.put(2, 'Skipping module "%s"' % module.name)
                continue
            logger.put(2, 'Preparing a report for module "%s"' % module.name)
            module_report = module.get_html_report()
            if module_report is not None:
                self.report.append_module_report(module.name, module_report)
            fsfh = module.get_filtered_strings_fh()
            self.report.append_filtered_strings(module.name, fsfh)
            fsfh.close()
        self.report.set_stamps(self.logtracker.get_stamps())
        logger.put(5, '<Epylog.make_report')
        return self.report.is_report_useful()

    def publish_report(self):
        logger = self.logger
        logger.put(5, '>Epylog.publish_report')
        if self.report.unparsed:
            logger.put(2, 'Dumping all log strings into a temp file')
            tempfile.tempdir = self.tmpprefix
            rsfh = open(tempfile.mktemp('RAW'), 'w+')
            wfh = open(tempfile.mktemp('WEED'), 'w+')
            logger.put(3, 'RAW strings file created in "%s"' % rsfh.name)
            self.logtracker.dump_all_strings(rsfh)
        self.report.publish(rsfh, wfh)
        logger.put(5, '<Epylog.publish_report')
        
    def cleanup(self):
        logger = self.logger
        logger.put(2, 'Cleanup routine called')
        logger.put(2, 'Removing the temp dir "%s"' % self.tmpprefix)
        shutil.rmtree(self.tmpprefix)

    def _process_internal_modules(self, modules):
        logger = self.logger
        logger.put(5, '>Epylog._process_internal_modules')
        logger.puthang(1, 'Processing internal modules')
        logger.put(4, 'Collecting logfiles used by internal modules')
        logmap = {}
        for module in modules:
            for log in module.logs:
                try: logmap[log.entry].append(module)
                except KeyError: logmap[log.entry] = [module]
        logger.put(5, 'logmap follows')
        logger.put(5, logmap)
        semaphore = threading.BoundedSemaphore(value=self.athreads)
        for entry in logmap.keys():
            logger.puthang(1, 'Processing Log: %s' % entry)
            log = self.logtracker.getlog(entry)
            matched = 0
            while 1:
                logger.put(5, 'Getting next line from "%s"' % entry)
                while threading.activeCount() - 1 > self.threads:
                    time.sleep(0.01)
                try:
                    line, stamp, sys, msg, mult = log.nextline()
                except FormatError: continue
                except OutOfRangeError: break
                logger.put(5, 'We have the following:')
                logger.put(5, 'stamp=%d' % stamp)
                logger.put(5, 'sys=%s' % sys)
                logger.put(5, 'msg=%s' % msg)
                logger.put(5, 'mult=%d' % mult)
                for module in logmap[entry]:
                    logger.put(5, 'Matching module "%s"' % module.name)
                    match = module.invoke_internal_module(line, stamp, sys,
                                                          msg, mult, semaphore)
                    matched += match
                    if match and not self.multimatch:
                        logger.put(5, 'Match. Not matching other modules')
                        break
            logger.put(1, '%d lines matched' % matched)
            logger.endhang(1)
        logger.put(5, 'Finished all matching, now finalizing')
        for module in modules:
            logger.put(5, 'Finalizing "%s"' % module.name)
            module.finalize_processing()
        logger.endhang(1)
        logger.put(5, '<Epylog._process_internal_modules')
