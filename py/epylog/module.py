import ConfigParser
import epylog
import os
import mytempfile as tempfile
import string

class Module:
    """epylog Module class"""
    
    def __init__(self, cfgfile, logtracker, logger):
        self.logger = logger
        logger.put(5, '>Module.__init__')
        self.logreport = None
        self.logfilter = None
        logger.put(2, 'Initializing module for cfgfile %s' % cfgfile)
        config = ConfigParser.ConfigParser()
        logger.put(2, 'Reading in the cfgfile %s' % cfgfile)
        config.read(cfgfile)
        try: self.name = config.get('module', 'desc')
        except: self.name = 'Unnamed Module'
        try: self.enabled = config.getboolean('module', 'enabled')
        except: self.enabled = 0
        if not self.enabled:
            logger.put(2, 'This module is not enabled. Skipping init.')
            return
        try: self.executable = config.get('module', 'exec')
        except:
            raise epylog.ConfigError('Did not find executable name in %s'
                                     % cfgfile, logger)
        try: self.python = config.getboolean('module', 'python')
        except: self.python = 0
        try: self.priority = config.getint('module', 'priority')
        except: self.priority = 10
        
        try: logentries = config.get('logs', 'files')
        except:
            raise epylog.ConfigError(('Cannot find log definitions in ' +
                                      'module config "%s"') % cfgfile)
        try: self.outhtml = config.getboolean('output', 'html')
        except: self.outhtml = 0

        self.extraopts = {}
        if config.has_section('conf'):
            logger.put(5, 'Found extra options')
            for option in config.options('conf'):
                value = config.get('conf', option)
                logger.put(5, '%s=%s' % (option, value))
                self.extraopts[option] = value
            logger.put(5, 'Done with extra options')

        logger.put(5, 'name=%s' % self.name)
        logger.put(5, 'executable=%s' % self.executable)
        logger.put(5, 'enabled=%d' % self.enabled)
        logger.put(5, 'python=%d' % self.python)
        logger.put(5, 'priority=%d' % self.priority)
        logger.put(5, 'logentries=%s' % logentries)
        logger.put(2, 'outhtml=%d' % self.outhtml)
        
        logger.put(3, 'Figuring out the logfiles from the log list')
        entrylist = logentries.split(',')
        self.logs = []
        for entry in entrylist:
            entry = entry.strip()
            logger.put(5, 'entry=%s' % entry)
            logger.put(3, 'Getting a log object from entry "%s"' % entry)
            try:
                log = logtracker.getlog(entry)
            except epylog.AccessError, e:
                ##
                # Do not die, but disable this module and complain loudly
                #
                logger.put(0, 'Could not init logfile for entry "%s"' % entry)
                self.enabled = 0
                logger.put(0, 'Module "%s" disabled' % self.name)
                return
            logger.put(5, 'Appending the log object to self.logs[]')
            self.logs.append(log)
        logger.put(5, '<Module.__init__')

    def is_python(self):
        if self.python:
            self.logger.put(5, 'This module is python')
            return 1
        else:
            self.logger.put(5, 'This module is not python')
            return 0
                
    def invoke_external_module(self, tmpprefix, cfgdir):
        logger = self.logger
        logger.put(5, '>Module.invoke_external_module')
        tempfile.tempdir = tmpprefix
        logcat = tempfile.mktemp()
        totallen = self.__dump_log_strings(logcat)
        if totallen == 0:
            logger.put(2, 'Nothing in the logs for this module. Passing exec')
            return
        logger.put(2, 'Setting LOGCAT to "%s"' % logcat)
        os.putenv('LOGCAT', logcat)

        modtmpprefix = os.path.join(tmpprefix, 'EPYLOG')
        logger.put(2, 'Setting TMPPREFIX env var to "%s"' % modtmpprefix)
        os.putenv('TMPPREFIX', modtmpprefix)
        logger.put(2, 'Setting CONFDIR env var to "%s"' % cfgdir)
        os.putenv('CONFDIR', cfgdir)
        if logger.is_quiet():
            logger.put(2, 'This line will never be seen. :)')
            os.putenv('QUIET', 'YES')
        logger.put(2, 'Setting DEBUG to "%s"' % logger.debuglevel())
        os.putenv('DEBUG', logger.debuglevel())
        descriptor = os.path.basename(self.executable)
        logreport = tempfile.mktemp('.%s.REPORT' % descriptor)
        logfilter = tempfile.mktemp('.%s.FILTER' % descriptor)
        logger.put(2, 'Setting LOGREPORT to "%s"' % logreport)
        logger.put(2, 'Setting LOGFILTER to "%s"' % logfilter)
        os.putenv('LOGREPORT', logreport)
        os.putenv('LOGFILTER', logfilter)
        if len(self.extraopts):
            logger.put(3, 'Setting extra options')
            for extraopt in self.extraopts.keys():
                optname = string.upper(extraopt)
                optval = self.extraopts[extraopt]
                logger.put(2, 'Setting %s to "%s"' % (optname, optval))
                os.putenv(optname, optval)
        logger.put(2, 'Invoking "%s"' % self.executable)
        exitcode = os.system(self.executable)
        logger.put(2, 'External module finished with code "%d"' % exitcode)
        if exitcode and exitcode != 256:
            msg = ('External module "%s" exited abnormally (exit code %d)' %
                   (self.executable, exitcode))
            raise epylog.ModuleExecError(msg, logger)
        logger.put(2, 'Checking if we have the report')
        if os.access(logreport, os.R_OK):
            logger.put(2, 'Report "%s" exists and is readable' % logreport)
            self.logreport = logreport
        logger.put(2, 'Checking if we have the filtered strings')
        if os.access(logfilter, os.R_OK):
            logger.put(2, 'Filtered strings file "%s" exists and is readable'
                       % logfilter)
            self.logfilter = logfilter
        
    def sanity_check(self):
        logger = self.logger
        logger.put(2, 'Checking if executable "%s" is sane' % self.executable)
        if not os.access(self.executable, os.F_OK):
            raise epylog.ModuleSanityError(('Executable "%s" for module "%s" '
                                            + 'does not exist')
                                           % (self.executable, self.name),
                                           logger)
        if self.is_python():
            logger.put(5, 'Module is python, not checking for exec bit')
            return
        if not os.access(self.executable, os.X_OK):
            raise epylog.ModuleSanityError(('Executable "%s" for module "%s" '
                                            + 'is not set to execute')
                                           % (self.executable, self.name),
                                           logger)
        
    def get_html_report(self):
        logger = self.logger
        logger.put(2, 'Invoking the get_html_report routine')
        if self.is_python():
            ##
            # TODO: Code for python modules
            #
            pass
        else:
            if self.logreport is None:
                logger.put(2, 'No report from this module')
                return None
            logger.put(2, 'Getting the report from "%s"' % self.logreport)
            if not os.access(self.logreport, os.R_OK):
                raise epylog.ModuleSanityError(('Log report from module "%s" '
                                               + 'is missing')
                                              % self.name, logger)
            logger.puthang(2, 'Reading the report from file "%s"'
                           % self.logreport)
            fh = open(self.logreport)
            report = fh.read()
            fh.close()
            logger.endhang(2, 'done')
            if len(report):
                if not self.outhtml:
                    logger.put(2, 'Report is not html')
                    report = self.__make_into_html(report)
                return report
            else:
                return None

    def get_filtered_strings_fh(self):
        logger = self.logger
        logger.put(5, '>Module.get_filtered_strings_fh')
        if self.is_python():
            ##
            # TODO: Code for python modules
            #
            pass
        else:
           if self.logfilter is None:
               logger.put(2, 'No filtered strings from this module')
               return None
           logger.put(3, 'Opening filtstrings file "%s"' % self.logfilter)
           if not os.access(self.logfilter, os.R_OK):
               msg = 'Filtered strings file for "%s" is missing' % self.name
               raise epylog.ModuleSanityError(msg, logger)
           fh = open(self.logfilter)
        logger.put(5, '<Module.get_filtered_strings_fh')
        return fh
           
    def __dump_log_strings(self, filename):
        logger = self.logger
        logger.put(5, '>Module.__dump_log_strings()')
        logger.put(5, 'filename=%s' % filename)
        logger.put(4, 'Opening the "%s" for writing' % filename)
        fh = open(filename, 'w')
        len = 0
        for log in self.logs:
            len = len + log.dump_strings(fh)
        logger.put(3, 'Total length of the log is "%d"' % len)
        return len

    def __make_into_html(self, report):
        logger = self.logger
        logger.put(5, '>Module.__make_into_html')
        import re
        logger.put(5, 'Regexing entities')
        report = re.sub(re.compile('&'), '&amp;', report)
        report = re.sub(re.compile('<'), '&lt;', report)
        report = re.sub(re.compile('>'), '&gt;', report)
        report = '<pre>\n%s\n</pre>' % report
        logger.put(5, '<Module.__make_into_html')
        return report
