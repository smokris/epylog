import ConfigParser
import exceptions
import os
import pickle
import shutil
import mytempfile as tempfile
import re
import time

from report import Report
from module import Module
from log import LogTracker

VERSION = 'Epylog-0.8'

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

class ModuleSanityError(exceptions.Exception):
    def __init__(self, message, logger):
        logger.put(2, 'Raising ModuleSanityError with message: %s' % message)
        self.args = message

class ModuleExecError(exceptions.Exception):
    def __init__(self, message, logger):
        logger.put(2, 'Raising ModuleExecError with message: %s' % message)
        self.args = message

class SysCallError(exceptions.Exception):
    def __init__(self, message, logger):
        logger.put(2, 'Raising SysCallError with message: %s' % message)
        self.args = message

class NoSuchLogError(exceptions.Exception):
    def __init__(self, message, logger):
        logger.put(2, 'Raising NoSuchLogError with message: %s' % message)
        self.args = message

class Epylog:
    def __init__(self, cfgfile, logger):
        self.logger = logger
        logger.put(5, 'Entering Epylog.__init__')

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
                module = Module(cfgfile, logtracker, logger)
                logger.endhang(3)
                if module.enabled:
                    logger.put(2, 'Module "%s" is enabled' % module.name)
                    logger.put(3, 'Checking "%s" for sanity' % module.name)
                    module.sanity_check()
                    logger.put(3, 'Sanity checks passed. Remembering module')
                    self.modules.append(module)
                else:
                    logger.put(2, 'Module "%s" is not enabled, ignoring'
                               % module.name)
            else:
                logger.put(3, '%s is not a regular file, ignoring' % cfgfile)
        logger.put(3, 'Total of %d modules initialized' % len(self.modules))
        if len(self.modules) == 0:
            raise ConfigError('No modules are enabled. Exiting.', logger)
        logger.put(5, 'Exiting Epylog.__init__')

    def process_modules(self):
        logger = self.logger
        logger.put(2, 'Invoking the process_modules routine')
        logger.put(2, 'Iterating through the modules')
        for module in self.modules:
            logger.puthang(1, 'Processing module "%s"' % module.name)
            if module.is_python():
                ##
                # TODO: Code for python modules
                #
                pass
            else:
                try:
                    module.invoke_external_module(self.tmpprefix, self.cfgdir)
                except ModuleExecError, e:
                    ##
                    # Module execution error!
                    # Do not die, but provide a visible warning.
                    #
                    logger.put(0, str(e))
            logger.endhang(1, 'done')
        logger.put(2, 'Done with the process_modules routine')

    def make_report(self):
        logger = self.logger
        logger.put(2, 'Invoking the make_report routine')
        for module in self.modules:
            if module.logreport is None and module.logfilter is None:
                logger.put(2, 'No output from module "%s"' % module.name)
                logger.put(2, 'Skipping module "%s"' % module.name)
                continue
            logger.put(2, 'Preparing a report for module "%s"' % module.name)
            module_report = module.get_html_report()
            if module_report is not None:
                self.report.append_module_report(module.name, module_report)
            module_strings = module.get_filtered_strings()
            if module_strings is not None:
                self.report.append_filtered_strings(module.name,
                                                    module_strings)

    def something_to_report(self):
        return self.report.is_report_useful()
    
    def publish_report(self):
        logger = self.logger
        if not self.something_to_report():
            logger.put(1, 'All reports are empty. Nothing to do.')
            return
        
        if self.report.unparsed:
            logger.put(2, 'Dumping all log strings into a temp file')
            tempfile.tempdir = self.tmpprefix
            rawstr_file = tempfile.mktemp('RAW')
            weeded_file = tempfile.mktemp('WEED')
            fh = open(rawstr_file, 'w')
            logger.put(2, 'RAW strings file created in "%s"' % rawstr_file)
            iter = self.logmap.iteritems()
            while 1:
                try:
                    (logname, logobj) = iter.next()
                    logger.put(3, 'Dumping strings for log "%s"' % logname)
                    logobj.dump_strings(fh)
                except StopIteration:
                    logger.put(2, 'Iteration finished')
                    break
            fh.close()
        self.report.publish(rawstr_file, weeded_file)
            
    def __unpickle_offsets(self):
        logger = self.logger
        logger.put(2, 'Invoking the __unpickle_offsets routine')
        ofile = os.path.join(self.vardir, 'offsets.p')
        logger.put(2, 'Checking if we have "%s" in the first place'
                   % ofile)
        if os.path.exists(ofile):
            logger.put(2, 'Opening "%s" with unpickler' % ofile)
            try:
                offsets = pickle.load(open(ofile))
                logger.put(5, 'offset data:')
                logger.put(5, offsets)
            except UnpicklingError:
                ##
                # Question: Should I throw an exception here instead?
                #
                logger.put(1, 'Error restoring offsets from "%s"' % ofile)
                logger.put(1, 'Using default values instead')
                offsets = {}
        else:
            logger.put(2, 'No offsets file in place. Using default values')
            offsets = {}
        self.offsets = offsets

    def __pickle_offsets(self):
        logger = self.logger
        logger.put(2, 'Checking if we have the offsets in the first place')
        if self.offsets is None:
            logger.put(1, 'No offsets found when attempting to pickle!')
            return
        logger.puthang(2, 'Pickling the offsets')
        ofile = os.path.join(self.vardir, 'offsets.p')
        logger.put(3, 'Storing pickles in file "%s"' % ofile)
        import fcntl
        fh = open(ofile, 'w')
        logger.put(3, 'Locking the offsets file')
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            pickle.dump(self.offsets, fh)
            logger.put(3, 'Pickles dumped. Mmmm... Pickle juice...')

        except:
            logger.put(0, 'Error trying to save offsets! Offsets not saved!')
        logger.put(3, 'Unlocking the offsets file')
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        fh.close()
        logger.endhang(2)
        
    def __restore_log_offset(self, logobj):
        logger = self.logger
        logger.put(2, 'Invoking the __restore_log_offset routine for "%s"'
                   % logobj.filename)
        if self.offsets is None:
            self.__unpickle_offsets()
        offsets = self.offsets
        logger.put(2, 'Checking if this logfile has defined offset info')
        if offsets.has_key(logobj.filename):
            logger.put(2, 'Comparing the inode information')
            st_inode = offsets[logobj.filename]['inode']
            if logobj.inode != st_inode:
                logger.put(2, 'The logfile seems to have been rotated')
                logger.put(3, 'Flipping the offset so we know')
                offset = -offsets[logobj.filename]['offset']
            else:
                logger.put(3, 'Inodes match. Same file, we presume')
                offset = offsets[logobj.filename]['offset']
            logobj.start_offset = offset
        else:
            logobj.set_init_offset()

    def __store_log_offset(self, logobj):
        logger = self.logger
        logger.put(3, 'Invoking the __store_log_offset routine for "%s"'
                   % logobj.filename)
        if self.offsets is None:
            ##
            # Hey, this can happen!
            #
            self.__unpickle_offsets()
        offsets = self.offsets
        logger.put(3, 'Storing the offset in the offsets map')
        logger.put(3, 'offset for log "%s" is "%d"'
                   % (logobj.filename, logobj.end_offset))
        offsets[logobj.filename] = {
            'offset': logobj.end_offset,
            'inode' : logobj.inode
            }
    
    def cleanup(self):
        logger = self.logger
        logger.put(2, 'Cleanup routine called')
        logger.put(2, 'Removing the temp dir "%s"' % self.tmpprefix)
        shutil.rmtree(self.tmpprefix)
