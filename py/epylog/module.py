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
    
    def __init__(self, cfgfile, logtracker, tmpprefix, logger):
        self.logger = logger
        logger.put(5, '>Module.__init__')
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

    def _init_internal_module(self):
        logger = self.logger
        logger.put(5, '>Module._init_internal_module')
        dirname = os.path.dirname(self.executable)
        modname = os.path.basename(self.executable)
        modname = re.sub(re.compile('\.py'), '', modname)
        logger.puthang(5, 'Importing module "%s"' % modname)
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
        logger.endhang(5)
        try:
            modclass = getattr(module, modname)
            self.epymod = modclass(self.extraopts, logger)
        except AttributeError:
            msg = 'Could not instantiate class "%s" in module "%s"'
            msg = msg % (modname, self.executable)
            raise epylog.ModuleError(msg, logger)
        self.threads = []
        logger.put(5, '<Module._init_internal_module')

    def invoke_internal_module(self, line, stamp, sys, msg, mult, semaphore):
        logger = self.logger
        logger.put(5, '>Module.invoke_internal_module')
        match = 0
        for regex in self.epymod.regex_map.keys():
            if regex.search(msg):
                logger.put(5, 'match: %s' % msg)
                handler = self.epymod.regex_map[regex]
                t = ThreadedLineHandler(line, stamp, sys, msg, mult, handler,
                                        semaphore, logger)
                self.threads.append(t)
                logger.put(5, 'Starting handler thread')
                t.start()
                match = 1
                break
        logger.put(5, '<Module.invoke_internal_module')
        return match

    def finalize_processing(self):
        logger = self.logger
        logger.put(5, '>Module.finalize_processing')
        logger.put(5, 'Finalizing for module "%s"' % self.name)
        if len(self.threads):
            rs = ResultSet()
            logger.put(5, 'Opening "%s" for writing' % self.logfilter)
            filtfh = open(self.logfilter, 'w+')
            while 1:
                try: t = self.threads.pop(0)
                except IndexError: break
                t.join()
                try:
                    result = t.result
                    if result is not None:
                        logger.put(5, 'Adding result for line: %s' % t.line)
                        rs.add(t.result)
                        filtfh.write(t.line)
                    del t
                except AttributeError:
                    ##
                    # We should probably warn the end-user?
                    #
                    pass
            if not filtfh.tell():
                logger.put(5, 'No filtered strings')
                self.logfilter = None
            logger.put(5, 'Closing "%s"' % self.logfilter)
            filtfh.close()
            logger.put(5, 'Done with all threads')
            if not rs.is_empty():
                logger.put(5, 'Finalizing the processing')
                report = self.epymod.finalize(rs)
                if report:
                    logger.put(5, 'Report follows:')
                    logger.put(5, report)
                    repfh = open(self.logreport, 'w')
                    repfh.write(report)
                    repfh.close()
            else:
                logger.put(2, 'NO results/report from this module')
                self.logreport = None
        else:
            self.logreport = None
            self.logfilter = None
        logger.put(5, 'Done with this module, deleting')
        del self.epymod
        logger.put(5, '<Module._invoke_internal_module')
    
    def invoke_external_module(self, cfgdir):
        logger = self.logger
        logger.put(5, '>Module._invoke_external_module')
        logger.put(5, 'Dumping strings into "%s"' % self.logdump)
        totallen = self._dump_log_strings(self.logdump)
        if totallen == 0:
            logger.put(2, 'Nothing in the logs for this module. Passing exec')
            return
        logger.put(2, 'Setting LOGCAT to "%s"' % self.logdump)
        os.putenv('LOGCAT', self.logdump)
        modtmpprefix = os.path.join(self.tmpprefix, 'EPYLOG')
        logger.put(2, 'Setting TMPPREFIX env var to "%s"' % modtmpprefix)
        os.putenv('TMPPREFIX', modtmpprefix)
        logger.put(2, 'Setting CONFDIR env var to "%s"' % cfgdir)
        os.putenv('CONFDIR', cfgdir)
        if logger.is_quiet():
            logger.put(2, 'This line will never be seen. :)')
            os.putenv('QUIET', 'YES')
        logger.put(2, 'Setting DEBUG to "%s"' % logger.debuglevel())
        os.putenv('DEBUG', logger.debuglevel())
        logger.put(2, 'Setting LOGREPORT to "%s"' % self.logreport)
        logger.put(2, 'Setting LOGFILTER to "%s"' % self.logfilter)
        os.putenv('LOGREPORT', self.logreport)
        os.putenv('LOGFILTER', self.logfilter)
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
            raise epylog.ModuleError(msg, logger)
        logger.put(2, 'Checking if we have the report')
        if not os.access(self.logreport, os.R_OK):
            logger.put(2, 'Report %s does not exist!' % self.logreport)
            self.logreport = None
        logger.put(2, 'Checking if we have the filtered strings')
        if not os.access(self.logfilter, os.R_OK):
            logger.put(2, 'Filtered file %s does not exist!' % self.logfilter)
            self.logfilter = None
        logger.put(5, '<Module._invoke_external_module')
        
    def sanity_check(self):
        logger = self.logger
        logger.put(5, '>Module.sanity_check')
        logger.put(2, 'Checking if executable "%s" is sane' % self.executable)
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
        logger = self.logger
        logger.put(5, '>Module.get_filtered_strings_fh')
        if self.logfilter is None:
            logger.put(2, 'No filtered strings from this module')
            return None
        logger.put(3, 'Opening filtstrings file "%s"' % self.logfilter)
        if not os.access(self.logfilter, os.R_OK):
            msg = 'Filtered strings file for "%s" is missing' % self.name
            raise epylog.ModuleError(msg, logger)
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
    def __init__(self, line, stamp, sys, msg, mult, handler, sem, logger):
        threading.Thread.__init__(self)
        self.logger = logger
        logger.put(5, '>ThreadedLineHandler.__init__')
        logger.put(5, 'My line is: %s' % line)
        self.line = line
        self.stamp = stamp
        self.system = sys
        self.message = msg
        self.multiplier = mult
        self.handler = handler
        self.semaphore = sem
        logger.put(5, '<ThreadedLineHandler.__init__')

    def run(self):
        self.semaphore.acquire()
        self.result = self.handler(self.stamp, self.system, self.message,
                                   self.multiplier)
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

        self._known_hosts[ip_addr] = name
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
    def __init__(self, result, multiplier):
        self.result = result
        self.multiplier = multiplier

        
