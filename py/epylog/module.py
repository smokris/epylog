import ConfigParser
import epylog
import os
import mytempfile as tempfile

class Module:
    """epylog Module class"""
    
    def __init__(self, cfgfile, logtracker, logger):
        self.logger = logger
        logger.put(5, 'Entering Module.__init__')
        self.logreport = None
        self.logfilter = None
        logger.put(2, 'Initializing module for cfgfile %s' % cfgfile)
        config = ConfigParser.ConfigParser()
        logger.put(2, 'Reading in the cfgfile %s' % cfgfile)
        config.read(cfgfile)
        try:
            self.name = config.get('module', 'desc')
        except:
            self.name = 'Unnamed Module'
        try:
            self.enabled = config.getboolean('module', 'enabled')
        except:
            self.enabled = 0
        if not self.enabled:
            logger.put(2, 'This module is not enabled. Skipping init.')
            return
        try:
            self.executable = config.get('module', 'exec')
        except:
            raise epylog.ConfigError('Did not find executable name in %s'
                                     % cfgfile, logger)
        try:
            self.python = config.getboolean('module', 'python')
        except:
            self.python = 0
        try:
            logentries = config.get('logs', 'files')
        except:
            raise epylog.ConfigError(('Cannot find log definitions in ' +
                                      'module config "%s"') % cfgfile)
        try:
            rotdir = config.get('logs', 'rotdir')
        except:
            rotdir = None
        try:
            self.outhtml = config.getboolean('output', 'html')
        except:
            self.outhtml = 0

        logger.put(5, 'name=%s' % self.name)
        logger.put(5, 'executable=%s' % self.executable)
        logger.put(5, 'enabled=%d' % self.enabled)
        logger.put(5, 'python=%d' % self.python)
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
        logger.put(5, 'Exiting Module.__init__')

    def is_python(self):
        if self.python:
            self.logger.put(5, 'This module is python')
            return 1
        else:
            self.logger.put(5, 'This module is not python')
            return 0
                
    def invoke_external_module(self, tmpprefix, cfgdir):
        logger = self.logger
        logger.put(2, 'Setting env vars and dumping the log strings')
        logcat = tempfile.mktemp()
        logger.put(2, 'Dumping log strings into "%s"' % logcat)
        totallen = self.__dump_log_strings(logcat)
        if totallen == 0:
            logger.put(2, 'Nothing in the logs for this module. Passing exec')
            return
        logger.put(2, 'Setting LOGCAT to "%s"' % logcat)
        os.putenv('LOGCAT', logcat)

        logger.put(2, 'Setting tempdir to "%s"' % tmpprefix)
        tempfile.tempdir = tmpprefix
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
        logreport = tempfile.mktemp()
        logfilter = tempfile.mktemp()
        logger.put(2, 'Setting LOGREPORT to "%s"' % logreport)
        logger.put(2, 'Setting LOGFILTER to "%s"' % logfilter)
        os.putenv('LOGREPORT', logreport)
        os.putenv('LOGFILTER', logfilter)
        logger.put(2, 'Invoking "%s"' % self.executable)
        exitcode = os.system(self.executable)
        logger.put(2, 'External module finished with code "%d"' % exitcode)
        if exitcode and exitcode != 256:
            raise epylog.ModuleExecError(('External module "%s" exited '
                                        + 'abnormally (exit code "%d")')
                                        % (self.executable, exitcode), logger)
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
                    logger.put(2, 'Report is not html, wrapping in <pre>')
                    report = '<pre>%s</pre>' % report
                return report
            else:
                return None

    def get_filtered_strings(self):
        logger = self.logger
        logger.put(2, 'Fetching the filtered strings')
        if self.is_python():
            ##
            # TODO: Code for python modules
            #
            pass
        else:
           if self.logfilter is None:
               logger.put(2, 'No filtered strings from this module')
               return None
           logger.put(2, 'Getting the strings from "%s"' % self.logfilter)
           if not os.access(self.logfilter, os.R_OK):
               raise epylog.ModuleSanityError(('Filtered strings file for'
                                              + ' module "%s" is missing')
                                             % self.name, logger)
           logger.puthang(3, 'Reading the strings from file "%s"'
                          % self.logfilter)
           fh = open(self.logfilter)
           filter = fh.read()
           fh.close()
           logger.endhang(3)
           if len(filter):
               return filter
           else:
               return None
           
    def __dump_log_strings(self, filename):
        logger = self.logger
        logger.put(2, 'Invoking module.dump_log_strings()')
        logger.put(3, 'filename=%s' % filename)
        logger.put(2, 'Opening the "%s" for writing' % filename)
        fh = open(filename, 'w')
        logger.put(3, self.logs)
        totallen = 0
        for logobj in self.logs:
            logger.put(2, 'Processing log object "%s"' % logobj.filename)
            length = logobj.dump_strings(fh)
            totallen = totallen + length
        logger.put(3, 'Total length of the log is "%d"' % totallen)
        return totallen
