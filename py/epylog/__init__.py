import ConfigParser
import exceptions
import os
import shutil
import mytempfile as tempfile
import re
import threading
import pwd
import socket

from report import Report
from module import Module
from log import LogTracker

VERSION = 'Epylog-0.9.0'
CHUNK_SIZE = 8192
GREP_LINES = 10000
QUEUE_LIMIT = 500
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
            if threads < 2:
                logger.put(0, 'Threads set to less than 2, fixing')
                threads = 2
            self.threads = threads
        except:
            self.threads = 50
        logger.put(5, 'threads=%d' % self.threads)
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
        pq = ProcessingQueue(QUEUE_LIMIT, logger)
        logger.put(5, 'Starting the consumer threads')
        threads = []
        for i in range(0, self.threads):
            t = ConsumerThread(pq, logger)
            t.start()
            threads.append(t)
        for entry in logmap.keys():
            logger.puthang(1, 'Processing Log: %s' % entry)
            log = self.logtracker.getlog(entry)
            matched = 0
            while 1:
                logger.put(5, 'Getting next line from "%s"' % entry)
                try:
                    linemap = log.nextline()
                except FormatError: continue
                except OutOfRangeError: break
                logger.put(5, 'We have the following:')
                logger.put(5, 'line=%s' % linemap['line'])
                logger.put(5, 'stamp=%d' % linemap['stamp'])
                logger.put(5, 'system=%s' % linemap['system'])
                logger.put(5, 'message=%s' % linemap['message'])
                logger.put(5, 'multiplier=%d' % linemap['multiplier'])
                for module in logmap[entry]:
                    logger.put(5, 'Matching module "%s"' % module.name)
                    handler = module.message_match(linemap['message'])
                    if handler is not None:
                        matched += 1
                        pq.put_linemap(linemap, handler, module)
                        if not self.multimatch:
                            logger.put(5, 'multimatch is not set')
                            logger.put(5, 'Not matching other modules')
                            break
            logger.put(1, '%d lines matched' % matched)
            logger.endhang(1)
        logger.put(5, 'Notifying the threads that they may die now')
        pq.tell_threads_to_quit(threads)
        logger.put(5, 'Waiting for threads to die')
        for t in threads: t.join()
        logger.put(5, 'Finished all matching, now finalizing')
        for module in modules:
            logger.put(5, 'Finalizing "%s"' % module.name)
            try:
                rs = pq.get_resultset(module)
                module.finalize_processing(rs)
            except KeyError:
                module.no_report()
        logger.endhang(1)
        logger.put(5, '<Epylog._process_internal_modules')

class ProcessingQueue:
    def __init__(self, limit, logger):
        self.logger = logger
        self.mon = threading.RLock()
        self.iw = threading.Condition(self.mon)
        self.ow = threading.Condition(self.mon)
        self.lineq = []
        self.resultsets = {}
        self.limit = limit
        self.working = 1

    def put_linemap(self, linemap, handler, module):
        self.mon.acquire()
        while len(self.lineq) >= self.limit:
            self.logger.put(5, 'Line queue is full, waiting...')
            self.ow.wait()
        self.lineq.append([linemap, handler, module])
        self.iw.notify()
        self.mon.release()

    def get_linemap(self):
        logger = self.logger
        self.mon.acquire()
        while not self.lineq and self.working:
            logger.put(5, 'Line queue is empty, waiting...')
            self.iw.wait()
        if self.working:
            item = self.lineq.pop(0)
            self.ow.notify()
        else: item = None
        self.mon.release()
        return item

    def put_result(self, line, result, module):
        self.mon.acquire()
        if result is not None:
            try: self.resultsets[module].add(result)
            except KeyError:
                self.resultsets[module] = ResultSet()
                self.resultsets[module].add(result)
            module.put_filtered(line)
        self.mon.release()

    def get_resultset(self, module):
        return self.resultsets[module]
    
    def tell_threads_to_quit(self, threads):
        self.mon.acquire()
        self.logger.put(5, 'Waiting till queue is empty')
        while self.lineq:
            self.ow.wait()
        self.logger.put(5, 'Set working to 0')
        self.working = 0
        for t in threads:
            self.iw.notify()
        self.mon.release()


class ConsumerThread(threading.Thread):
    def __init__(self, queue, logger):
        threading.Thread.__init__(self)
        self.logger = logger
        self.queue = queue

    def run(self):
        logger = self.logger
        while self.queue.working:
            logger.put(5, '%s: getting a new linemap' % self.getName())
            item = self.queue.get_linemap()
            if item is not None:
                linemap, handler, module = item
                logger.put(5, '%s: calling the handler' % self.getName())
                result = handler(linemap)
                if result is not None:
                    line = linemap['line']
                    logger.put(5, '%s: returning the result' % self.getName())
                    self.queue.put_result(line, result, module)
                else:
                    logger.put(5, '%s: Result is None.' % self.getName())
            else:
                logger.put(5, '%s: Item is none.' % self.getName())
        logger.put(5, '%s: I am now dying' % self.getName())

class ResultSet:
    def __init__(self):
        self.resultset = {}

    def add(self, resobj):
        result = resobj.result
        multiplier = resobj.multiplier
        try: self.resultset[result] += multiplier
        except KeyError: self.resultset[result] = multiplier

    def get_distinct(self, matchtup, sort=1):
        lim = len(matchtup)
        matches = []
        reskeys = self.resultset.keys()
        if sort: reskeys.sort()
        for key in reskeys:
            if matchtup == key[0:lim]:
                if key[lim] not in matches:
                    matches.append(key[lim])
        return matches

    def get_submap(self, matchtup, sort=1):
        lim = len(matchtup)
        matchmap = {}
        reskeys = self.resultset.keys()
        reskeys.sort()
        for key in reskeys:
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

class InternalModule:
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
        
    def get_smm(self, lm):
        return (lm['system'], lm['message'], lm['multiplier'])

class Logger:
    indent = '  '
    hangmsg = []
    hanging = 0
    
    def __init__(self, loglevel):
        self.loglevel = loglevel

    def is_quiet(self):
        if self.loglevel == 0:
            return 1
        else:
            return 0

    def debuglevel(self):
        return str(self.loglevel)

    def put(self, level, message):
        if (level <= self.loglevel):
            if self.hanging:
                self.hanging = 0
            print '%s%s' % (self.__getindent(), message)

    def puthang(self, level, message):
        if (level <= self.loglevel):
            print '%sInvoking: "%s"...' % (self.__getindent(), message)
            self.hanging = 1
            self.hangmsg.append(message)


    def endhang(self, level, message='done'):
        if (level <= self.loglevel):
            hangmsg = self.hangmsg.pop()
            if self.hanging:
                self.hanging = 0
                print '%s%s...%s' % (self.__getindent(), hangmsg, message)
            else:
                print '%s(Hanging from "%s")....%s' % (self.__getindent(),
                                                       hangmsg, message)

    def __getindent(self):
        indent = self.indent * len(self.hangmsg)
        return indent
