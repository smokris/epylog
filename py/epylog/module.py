import ConfigParser
import epylog
import os
import mytempfile as tempfile
import string
import re
import time
import threading
import pwd
import socket

from ihooks import BasicModuleLoader
_loader = BasicModuleLoader()

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
            logger.put(5, 'Found extra options')
            for option in config.options('conf'):
                value = config.get('conf', option)
                logger.put(5, '%s=%s' % (option, value))
                self.extraopts[option] = value
            logger.put(5, 'Done with extra options')

        logger.put(5, 'name=%s' % self.name)
        logger.put(5, 'executable=%s' % self.executable)
        logger.put(5, 'enabled=%d' % self.enabled)
        logger.put(5, 'internal=%d' % self.internal)
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

    def is_internal(self):
        if self.internal:
            self.logger.put(5, 'This module is internal')
            return 1
        else:
            self.logger.put(5, 'This module is not internal')
            return 0

    def invoke_module(self, tmpprefix, cfgdir):
        logger = self.logger
        logger.put(5, '>Module.invoke_module')
        tempfile.tempdir = tmpprefix
        logdump = tempfile.mktemp()
        logger.put(5, 'Dumping strings into a tempfile "%s"' % logdump)
        totallen = self._dump_log_strings(logdump)
        if totallen == 0:
            logger.put(2, 'Nothing in the logs for this module. Passing exec')
            return
        if self.is_internal():
            self._invoke_internal_module(tmpprefix, logdump, cfgdir)
        else:
            self._invoke_external_module(tmpprefix, logdump, cfgdir)
        logger.put(5, '<Module.invoke_module')

    def _invoke_internal_module(self, tmpprefix, logdump, cfgdir):
        logger = self.logger
        logger.put(5, '>Module._invoke_internal_module')
        dirname = os.path.dirname(self.executable)
        modname = os.path.basename(self.executable)
        modname = re.sub(re.compile('\.py'), '', modname)
        logger.puthang(5, 'Importing module "%s"' % modname)
        stuff = _loader.find_module_in_dir(modname, dirname)
        if stuff:
            module = _loader.load_module(modname, stuff)
        else:
            msg = 'Could not import module "%s"' % self.name
            raise epylog.ModuleExecError(msg, logger)
        logger.endhang(5)
        try:
            modclass = getattr(module, modname)
            epymod = modclass(self.extraopts, logger)
        except AttributeError:
            msg = 'Could not instantiate class "%s" in module "%s"'
            msg = msg % (modname, self.executable)
            raise epylog.ModuleExecError(msg, logger)
        logger.put(5, 'Opening "%s" for readlining' % logdump)
        dfh = open(logdump)
        semaphore = threading.BoundedSemaphore(value=epymod.athreads)
        logger.put(5, 'Semaphore thread limit set to "%s"' % epymod.athreads)
        thread_limit = epylog.TOTAL_THREAD_LIMIT
        logger.put(5, 'Total thread limit is "%s"' % thread_limit)
        logreport = tempfile.mktemp('.%s.REPORT' % modname)
        logfilter = tempfile.mktemp('.%s.FILTER' % modname)
        logger.put(2, 'logreport=%s' % logreport)
        logger.put(2, 'logfilter=%s' % logfilter)
        ##
        # Get a monthmap out of one of the logs
        #
        monthmap = self.logs[0].monthmap
        threads = []
        line = dfh.readline()
        while line:
            for regex in epymod.regex_map.keys():
                if regex.search(line):
                    logger.put(5, 'Match: %s' % line)
                    while threading.activeCount() - 1 > thread_limit:
                        time.sleep(0.01)
                    handler = epymod.regex_map[regex]
                    t = ThreadedLineHandler(line, handler, semaphore,
                                            monthmap, logger)
                    threads.append(t)
                    logger.put(5, 'Starting handler thread')
                    t.start()
                    ##
                    # Don't try other regexes
                    #
                    break
            line = dfh.readline()
        dfh.close()
        logger.put(5, 'Done processing the lines')
        logger.put(5, 'Waiting for threads to finish and collecting results')
        rs = ResultSet()
        filtfh = open(logfilter, 'w+')
        for t in threads:
            t.join()
            if t.result is not None:
                rs.add(t.result)
                filtfh.write(t.line)
        if filtfh.tell():
            logger.put(5, 'We have filtered strings')
            self.logfilter = logfilter
        filtfh.close()
        logger.put(5, 'Done with all threads')
        if not rs.is_empty():
            logger.put(5, 'Finalizing the processing')
            report = epymod.finalize(rs)
        else:
            logger.put(5, 'No results in the resultset, skipping finalizing')
            report = ''
        if report:
            logger.put(5, 'Report follows:')
            logger.put(5, report)
            repfh = open(logreport, 'w')
            repfh.write(report)
            repfh.close()
            self.logreport = logreport
        else:
            logger.put(5, 'NO report from this module')
        logger.put(5, 'Done with this module, deleting')
        del module
        logger.put(5, '<Module._invoke_internal_module')
    
    def _invoke_external_module(self, tmpprefix, logdump, cfgdir):
        logger = self.logger
        logger.put(5, '>Module._invoke_external_module')
        logger.put(2, 'Setting LOGCAT to "%s"' % logdump)
        os.putenv('LOGCAT', logdump)
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
        logger.put(5, '<Module._invoke_external_module')
        
    def sanity_check(self):
        logger = self.logger
        logger.put(5, '>Module.sanity_check')
        logger.put(2, 'Checking if executable "%s" is sane' % self.executable)
        if not os.access(self.executable, os.F_OK):
            msg = ('Executable "%s" for module "%s" does not exist'
                   % (self.executable, self.name))
            raise epylog.ModuleSanityError(msg, logger)
        if not self.is_internal():
            if not os.access(self.executable, os.X_OK):
                msg = ('Executable "%s" for module "%s" is not set to execute'
                       % (self.executable, self.name))
                raise epylog.ModuleSanityError(msg, logger)
        logger.put(5, '<Module.sanity_check')
        
    def get_html_report(self):
        logger = self.logger
        logger.put(5, '>Module.get_html_report')
        if self.logreport is None:
            logger.put(3, 'No report from this module')
            return None
        logger.put(3, 'Getting the report from "%s"' % self.logreport)
        if not os.access(self.logreport, os.R_OK):
            msg = 'Log report from module "%s" is missing' % self.name
            raise epylog.ModuleSanityError(msg, logger)
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
        logger = self.logger
        logger.put(5, '>Module.get_filtered_strings_fh')
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
           
    def _dump_log_strings(self, filename):
        logger = self.logger
        logger.put(5, '>Module._dump_log_strings')
        logger.put(5, 'filename=%s' % filename)
        logger.put(4, 'Opening the "%s" for writing' % filename)
        fh = open(filename, 'w')
        len = 0
        for log in self.logs:
            len = len + log.dump_strings(fh)
        logger.put(3, 'Total length of the log is "%d"' % len)
        logger.put(5, '<Module._dump_log_strings')
        return len

    def _make_into_html(self, report):
        logger = self.logger
        logger.put(5, '>Module._make_into_html')
        import re
        logger.put(5, 'Regexing entities')
        report = re.sub(re.compile('&'), '&amp;', report)
        report = re.sub(re.compile('<'), '&lt;', report)
        report = re.sub(re.compile('>'), '&gt;', report)
        report = '<pre>\n%s\n</pre>' % report
        logger.put(5, '<Module._make_into_html')
        return report

class ThreadedLineHandler(threading.Thread):
    def __init__(self, line, handler, semaphore, monthmap, logger):
        threading.Thread.__init__(self)
        self.logger = logger
        logger.put(5, '>ThreadedLineHandler.__init__')
        logger.put(5, 'My line is: %s' % line)
        self.monthmap = monthmap
        self.semaphore = semaphore
        self.handler = handler
        self.line = line
        logger.put(5, '<ThreadedLineHandler.__init__')

    def run(self):
        self.semaphore.acquire()
        mo = epylog.LOG_SPLIT_RE.match(self.line)
        time, sys, msg = mo.groups()
        stamp = epylog.log.mkstamp_from_syslog_datestr(time, self.monthmap)
        sys = re.sub(epylog.SYSLOG_NG_STRIP, '', sys)
        self.result = self.handler(stamp, sys, msg)
        self.semaphore.release()

class PythonModule:
    def __init__(self):
        self._known_hosts = {}
        self._known_uids = {}
        
    def getuname(self, uid):
        """get username for a given uid"""
        uid = int(uid)
        try: return self._known_uids[uid]
        except KeyError: pass

        try: name = pwd.getpwuid(uid)[0]
        except KeyError: name = "uid=%d" % uid

        self._known_uids[uid] = name
        return name

    def gethost(self, ip_addr):
        """do reverse lookup on an ip address"""
        try: return self._known_hosts[ip_addr]
        except KeyError: pass

        try: name = socket.gethostbyaddr(ip_addr)[0]
        except socket.error: name = ip_addr

        self._known_hosts = name
        return name


class ResultSet:
    def __init__(self):
        self.resultset = {}

    def add(self, resobj):
        result = resobj.result
        multiplier = resobj.multiplier
        try: self.resultset[result] += multiplier
        except KeyError: self.resultset[result] = multiplier

    def get_distinct(self, matchtup):
        lim = len(matchtup)
        matches = []
        for key in self.resultset.keys():
            if matchtup == key[0:lim]:
                if key[lim] not in matches:
                    matches.append(key[lim])
        return matches

    def get_submap(self, matchtup):
        lim = len(matchtup)
        matchmap = {}
        for key in self.resultset.keys():
            if matchtup == key[0:lim]:
                subtup = key[lim:]
                try: matchmap[subtup] += self.resultset[key]
                except KeyError: matchmap[subtup] = self.resultset[key]
        return matchmap

    def is_empty(self):
        if self.resultset == {}: return 1
        else: return 0
        
class Result:
    def __init__(self, result, multiplier=1):
        self.result = result
        self.multiplier = multiplier

        
