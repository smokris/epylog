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
from log import LogFile

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

class Epylog:
    def __init__(self, cfgfile, logger):
        logger.puthang(2, 'Starting the epylog object initialization')
        logger.put(5, 'Sticking logger into the object')
        self.logger = logger
        
        logger.put(3, 'Setting some defaults')
        self.report = None
        self.modules = []
        self.offsets = None

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
            raise ConfigError(('Could not parse the main config file "%s"'
                              % cfgfile), logger)
        logger.put(4, 'cfgdir=%s' % self.cfgdir)
        logger.put(4, 'vardir=%s' % self.vardir)
        logger.endhang(3)
        
        logger.put(3, 'Checking if we can write to vardir')
        if not os.access(self.vardir, os.W_OK):
            raise ConfigError('Write access required for vardir "%s"'
                              % self.vardir, logger)

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
            raise ConfigError('Could not create a temp directory in "%s"'
                              % tmpprefix, logger)
        self.tmpprefix = tmpprefix
        tempfile.tempdir = tmpprefix
        logger.put(3, 'Temporary directory created in "%s"' % tmpprefix)
        logger.put(3, 'Sticking tmpprefix into config to pass to other objs')
        config.tmpprefix = self.tmpprefix

        logger.puthang(3, 'Initializing the Report')
        self.report = Report(config, logger)
        logger.endhang(3)

        modcfgdir = os.path.join(self.cfgdir, 'modules.d')
        logger.put(3, 'Checking if module config dir "%s" exists' % modcfgdir)
        if not os.path.isdir(modcfgdir):
            raise ConfigError('Module configuration directory "%s" not found'
                              % modcfgdir, logger)
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
                module = Module(cfgfile, logger)
                logger.endhang(3)
                if module.enabled:
                    logger.put(3, 'Module "%s" is enabled' % module.name)
                    logger.put(3, 'Checking "%s" for sanity' % module.name)
                    module.sanity_check()
                    logger.put(3, 'Sanity checks passed. Remembering module')
                    self.modules.append(module)
                else:
                    logger.put(3, 'Module "%s" is not enabled, ignoring'
                               % module.name)
            else:
                logger.put(3, '%s is not a regular file, ignoring' % cfgfile)
        logger.put(3, 'Total of %d modules initialized' % len(self.modules))
        logger.put(3, 'Looking at what logfiles to initialize')
        logmap = {}
        for module in self.modules:
            logger.put(3, 'Looking in module "%s"' % module.name)
            logger.put(5, module.lognames)
            for logname in module.lognames:
                logger.put(3, 'Found logfile declaration "%s"' % logname[0])
                if logmap.has_key(logname[0]):
                    logger.put(3, 'Log file "%s" already initialized'
                               % logname[0])
                    logger.put(3, 'Sticking it into the module')
                    module.logs.append(logmap[logname[0]])
                else:
                    logger.put(3, '%s is not yet initialized. Initializing.'
                               % logname[0])
                    try:
                        logger.puthang(3, 'Calling LogFile init routines')
                        logobj = LogFile(logname[0], logger)
                        logger.endhang(3)
                    except AccessError:
                        raise ConfigError(('Log file "%s" does not exist or ' +
                                           'is not accessible for reading')
                                          % logname[0], logger)
                    logger.put(3, 'Opening the logfile "%s"' % logname[0])
                    logobj.initfile()
                    if logname[1] is not None:
                        logger.put(3, 'Initializing the rotated logfile "%s"'
                                   % logname[1])
                        try:
                            rotobj = LogFile(logname[1], logger)
                            logger.put(3, ('Sticking rotated logfile object' +
                                           ' into the log object'))
                            logobj.rotated = rotobj
                        except AccessError:
                            logger.put(3, 'Error opening. Hmm... Oh well.')
                            logger.put(3, 'Ignoring rotated logfile "%s"'
                                       % logname[1])
                    logger.put(3, 'Sticking the log object into the module')
                    module.logs.append(logobj)
                    logger.put(3, 'Copying object into the logs map')
                    logmap[logname[0]] = logobj

        self.logmap = logmap
        if self.report.unparsed:
            logger.put(3, 'Creating a temporary file for filtered strings')
            filt_fh = open(tempfile.mktemp('FILT'), 'w')
            logger.put(3, 'Filtered strings file created in "%s"'
                       % filt_fh.name)
            logger.put(3, 'Sticking filt_fh into the report object')
            self.report.filt_fh = filt_fh
        logger.endhang(2)

    def restore_log_offsets(self):
        logger = self.logger
        logger.put(2, 'Invoking the restore_log_offsets routine')
        logger.put(2, 'Setting up the iterator')
        iter = self.logmap.iteritems()
        earliest_stamp = None
        latest_stamp = None
        while 1:
            try:
                (logname, logobj) = iter.next()
                logger.put(2, 'Processing logname "%s"' % logname)
                self.__restore_log_offset(logobj)
                start_stamp = logobj.get_offset_start_stamp()
                end_stamp = logobj.get_offset_end_stamp()
                if earliest_stamp is None:
                    earliest_stamp = start_stamp
                if latest_stamp is None:
                    latest_stamp = end_stamp
                if start_stamp < earliest_stamp:
                    earliest_stamp = start_stamp
                if end_stamp > latest_stamp:
                    latest_stamp = end_stamp
            except StopIteration:
                logger.put(2, 'Iteration finished')
                break
        self.report.start_stamp = earliest_stamp
        self.report.end_stamp = latest_stamp

    def store_log_offsets(self):
        logger = self.logger
        logger.put(2, 'Invoking the store_log_offsets routine')
        logger.put(2, 'Setting up the iterator')
        iter = self.logmap.iteritems()
        while 1:
            try:
                (logname, logobj) = iter.next()
                logger.put(2, 'Processing logname "%s"' % logname)
                self.__store_log_offset(logobj)
            except StopIteration:
                logger.put(2, 'Iteration finished')
                break
        logger.put(2, 'Calling the pickling routine')
        self.__pickle_offsets()

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
