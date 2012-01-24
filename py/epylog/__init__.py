"""
This module contains the main classes and methods for Epylog.
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
# @Author Konstantin Ryabitsev <icon@linux.duke.edu>
# @version $Date$
#

import ConfigParser
import exceptions
import os
import shutil
import tempfile
import re
import threading
import pwd
import socket
import sys

if 'mkdtemp' not in dir(tempfile):
    ##
    # Must be python < 2.3
    #
    del tempfile
    import mytempfile as tempfile

from report import Report
from module import Module
from log import LogTracker

VERSION = 'Epylog-1.0.5'
CHUNK_SIZE = 8192
GREP_LINES = 10000
QUEUE_LIMIT = 500
LOG_SPLIT_RE = re.compile(r'(.{15,15})\s+(\S+)\s+(.*)$')
SYSLOG_NG_STRIP = re.compile(r'.*[@/]')
MESSAGE_REPEATED_RE = re.compile(r'last message repeated (\S+) times')

class FormatError(exceptions.Exception):
    """
    This exception is raised when there are problems with the syslog
    line processed.
    """
    def __init__(self, message, logger):
        exceptions.Exception.__init__(self)
        logger.put(5, '!FormatError: %s' % message)
        self.args = message

class ConfigError(exceptions.Exception):
    """
    This exception is raised when there are misconfiguration problems.
    """
    def __init__(self, message, logger):
        exceptions.Exception.__init__(self)
        logger.put(5, '!ConfigError: %s' % message)
        self.args = message

class AccessError(exceptions.Exception):
    """
    This exception is raised when there are errors accessing certain
    components of Epylog, log files, or temporary writing spaces.
    """
    def __init__(self, message, logger):
        exceptions.Exception.__init__(self)
        logger.put(5, '!AccessError: %s' % message)
        self.args = message

class OutOfRangeError(exceptions.Exception):
    """
    This happens when Epylog tries to access a line in a logfile that is
    outside the specified range.
    """
    def __init__(self, message, logger):
        exceptions.Exception.__init__(self)
        logger.put(5, '!OutOfRangeError: %s' % message)
        self.args = message

class ModuleError(exceptions.Exception):
    """
    This exception is raised when an Epylog module crashes or otherwise
    creates a problem.
    """
    def __init__(self, message, logger):
        exceptions.Exception.__init__(self)
        logger.put(5, '!ModuleError: %s' % message)
        self.args = message

class SysCallError(exceptions.Exception):
    """
    This exception is raised when a call to a system binary is not
    successful. Most notable ones are grep (only used with external modules)
    and lynx/links/w3m.
    """
    def __init__(self, message, logger):
        exceptions.Exception.__init__(self)
        logger.put(5, '!SysCallError: %s' % message)
        self.args = message

class NoSuchLogError(exceptions.Exception):
    """
    This exception is raised when Epylog tries to access or initialize a
    logfile that does not exist.
    """
    def __init__(self, message, logger):
        exceptions.Exception.__init__(self)
        logger.put(5, '!NoSuchLogError: %s' % message)
        self.args = message

class EmptyLogError(exceptions.Exception):
    """
    This exception is raised when Epylog finds an empty logfile.
    """
    def __init__(self, message, logger):
        exceptions.Exception.__init__(self)
        logger.put(5, '!EmptyLogError: %s' % message)
        self.args = message

class GenericError(exceptions.Exception):
    """
    This exception is raised for all other Epylog conditions.
    """
    def __init__(self, message, logger):
        exceptions.Exception.__init__(self)
        logger.put(5, '!GenericError: %s' % message)
        self.args = message

class Epylog:
    """
    This is the core class of Epylog. A UI would usually communicate
    with it an it only.
    """
    def __init__(self, cfgfile, logger):
        """
        UIs may override the included logger, which would be useful for
        things like a possible GTK interface, a web interface, etc.
        """
        self.logger = logger
        logger.put(5, '>Epylog.__init__')

        config = ConfigParser.ConfigParser()
        logger.puthang(3, 'Reading the config file "%s"' % cfgfile)
        try: config.read(cfgfile)
        except:
            msg = 'Could not read/parse config file "%s"' % cfgfile
            raise ConfigError(msg, logger)
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
        logger.put(5, 'cfgdir=%s' % self.cfgdir)
        logger.put(5, 'vardir=%s' % self.vardir)
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
        except: pass
        logger.put(3, 'Creating a safe temporary directory')
        try: tmpprefix = tempfile.mkdtemp('EPYLOG')
        except:
            msg = 'Could not create a safe temp directory in "%s"' % tmpprefix
            raise ConfigError(msg, logger)
        self.tmpprefix = tmpprefix
        tempfile.tempdir = tmpprefix
        logger.put(3, 'Temporary directory created in "%s"' % tmpprefix)
        logger.put(3, 'Sticking tmpprefix into config to pass to other objs')
        config.tmpprefix = self.tmpprefix
        ##
        # Create a file for unparsed strings.
        #
        self.unparsed = tempfile.mktemp('UNPARSED')
        logger.put(3, 'Unparsed strings will go into %s' % self.unparsed)
        ##
        # Get multimatch pref
        #
        try: self.multimatch = config.getboolean('main', 'multimatch')
        except: self.multimatch = 0
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
                if not re.compile('\.conf$').search(cfgfile, 1):
                    logger.put(3, 'Not a module config file, skipping.')
                    continue
                logger.puthang(3, 'Calling the Module init routines')
                try:
                    module = Module(cfgfile, logtracker, tmpprefix, logger)
                except (ConfigError, ModuleError), e:
                    msg = 'Module Error: %s' % e
                    logger.put(0, msg)
                    continue
                logger.endhang(3)
                if module.enabled:
                    logger.put(3, 'Module "%s" is enabled' % module.name)
                    module.sanity_check()
                    self.modules.append(module)
                    priorities.append(module.priority)
                else:
                    logger.put(3, 'Module "%s" is not enabled, ignoring'
                               % module.name)
            else:
                logger.put(3, '%s is not a regular file, ignoring' % cfgfile)
        logger.put(3, 'Total of %d modules initialized' % len(self.modules))
        if len(self.modules) == 0:
            raise ConfigError('No modules are enabled. Exiting.', logger)
        ##
        # Sort modules by priority
        #
        logger.put(3, 'sorting modules by priority')
        priorities.sort()
        for module in self.modules:
            logger.put(3, 'analyzing module: %s' % module.name)
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
        self.imodules = []
        self.emodules = []
        for module in self.modules:
            logger.put(5, 'module: %s, priority: %d'
                       % (module.name, module.priority))
            if module.is_internal(): self.imodules.append(module)
            else: self.emodules.append(module)
        logger.put(5, '<Epylog.__init__')

    def process_modules(self):
        """
        Invoke the modules to process the logfile entries.
        """
        logger = self.logger
        logger.put(5, '>Epylog.process_modules')
        logger.put(3, 'Finding internal modules')
        if len(self.imodules):
            self._process_internal_modules()
        if len(self.emodules):
            logger.puthang(3, 'Processing external modules')
            for module in self.emodules:
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
        """
        Create the report based on the result of the Epylog run.
        """
        logger = self.logger
        logger.put(5, '>Epylog.make_report')
        for module in self.modules:
            logger.put(3, 'Analyzing reports from module "%s"' % module.name)
            logger.put(5, 'logerport=%s' % module.logreport)
            logger.put(5, 'logfilter=%s' % module.logfilter)
            if module.logreport is None and module.logfilter is None:
                logger.put(3, 'No output from module "%s"' % module.name)
                logger.put(3, 'Skipping module "%s"' % module.name)
                continue
            logger.put(3, 'Preparing a report for module "%s"' % module.name)
            module_report = module.get_html_report()
            if module_report is not None:
                self.report.append_module_report(module.name, module_report)
            if self.emodules:
                ##
                # We only need filtered strings if we have external modules
                #
                fsfh = module.get_filtered_strings_fh()
                self.report.append_filtered_strings(module.name, fsfh)
                fsfh.close()
        self.report.set_stamps(self.logtracker.get_stamps())
        logger.put(5, '<Epylog.make_report')
        return self.report.is_report_useful()

    def publish_report(self):
        """
        Publish the report.
        """
        logger = self.logger
        logger.put(5, '>Epylog.publish_report')
        logger.put(3, 'Dumping all log strings into a temp file')
        tempfile.tempdir = self.tmpprefix
        rawfh = open(tempfile.mktemp('RAW'), 'w+')
        logger.put(3, 'RAW strings file created in "%s"' % rawfh.name)
        self.logtracker.dump_all_strings(rawfh)
        if not self.emodules:
            ##
            # All modules were internal, meaning we have all unparsed
            # strings in the self.unparsed file.
            #
            unparsed = self._get_unparsed()
        else: unparsed = None
        self.report.publish(rawfh, unparsed)
        logger.put(5, '<Epylog.publish_report')
        
    def cleanup(self):
        """
        Clean up after ourselves.
        """
        logger = self.logger
        logger.put(3, 'Cleanup routine called')
        logger.put(3, 'Removing the temp dir "%s"' % self.tmpprefix)
        shutil.rmtree(self.tmpprefix)

    def _get_unparsed(self):
        """
        Get all unparsed strings stored in the "unparsed" file.
        """
        fh = open(self.unparsed, 'r')
        unparsed = fh.read()
        fh.close()
        return unparsed

    def _process_internal_modules(self):
        """
        Invoke and process internal (python) modules.
        """
        logger = self.logger
        logger.put(5, '>Epylog._process_internal_modules')
        logger.puthang(1, 'Processing internal modules')
        logger.put(3, 'Collecting logfiles used by internal modules')
        upfh = open(self.unparsed, 'w')
        logger.put(3, 'Opened unparsed strings file in "%s"' % self.unparsed)
        logmap = {}
        for module in self.imodules:
            for log in module.logs:
                try: logmap[log.entry].append(module)
                except KeyError: logmap[log.entry] = [module]
        logger.put(5, 'logmap follows')
        logger.put(5, logmap)
        pq = ProcessingQueue(QUEUE_LIMIT, logger)
        logger.put(3, 'Starting the processing threads')
        threads = []
        try:
            while 1:
                t = ConsumerThread(pq, logger)
                t.start()
                threads.append(t)
                if len(threads) > self.threads: break
            for entry in logmap.keys():
                log = self.logtracker.getlog(entry)
                if log.is_range_empty(): continue
                matched = 0
                lines = 0
                while 1:
                    logger.put(3, 'Getting next line from "%s"' % entry)
                    try:
                        linemap = log.nextline()
                    except FormatError, e:
                        logger.put(5, 'Writing the line to unparsed')
                        upfh.write(str(e))
                        continue
                    except OutOfRangeError: break
                    lines += 1
                    logger.put(5, 'We have the following:')
                    logger.put(5, 'line=%s' % linemap['line'])
                    logger.put(5, 'stamp=%d' % linemap['stamp'])
                    logger.put(5, 'system=%s' % linemap['system'])
                    logger.put(5, 'message=%s' % linemap['message'])
                    logger.put(5, 'multiplier=%d' % linemap['multiplier'])
                    match = 0
                    for module in logmap[entry]:
                        logger.put(5, 'Matching module "%s"' % module.name)
                        message = linemap['message']
                        handler, regex = module.message_match(message)
                        linemap['regex'] = regex
                        if handler is not None:
                            match = 1
                            pq.put_linemap(linemap, handler, module)
                            if not self.multimatch:
                                logger.put(5, 'multimatch is not set')
                                logger.put(5, 'Not matching other modules')
                                break
                    matched += match
                    if not match:
                        logger.put(5, 'Writing the line to unparsed')
                        upfh.write(linemap['line'])
                bartitle = log.entry
                message = '%d of %d lines parsed' % (matched, lines)
                logger.endbar(1, bartitle, message)
        finally:
            logger.put(3, 'Notifying the threads that they may die now')
            pq.tell_threads_to_quit(threads)
            bartitle = 'Waiting for threads to finish'
            bartotal = len(threads)
            bardone = 1
            for t in threads:
                logger.progressbar(1, bartitle, bardone, bartotal)
                t.join()
                bardone += 1
            logger.endbar(1, bartitle, 'all threads done')
        upfh.close()
        logger.puthang(1, 'Finished all matching, now finalizing')
        for module in self.imodules:
            logger.puthang(1, 'Finalizing "%s"' % module.name)
            try:
                rs = pq.get_resultset(module)
                try:
                    module.finalize_processing(rs)
                except Exception, e:
                    msg = ('Module %s crashed in finalize stage: %s' % 
                           (module.name, e))
                    logger.put(0, msg)
                    module.no_report()
            except KeyError:
                module.no_report()
            logger.endhang(1)
        logger.endhang(1)
        logger.endhang(1)
        logger.put(5, '<Epylog._process_internal_modules')

class ProcessingQueue:
    """
    This is a standard cookie-cutter helper class for using threads in a
    Python application.
    """
    def __init__(self, limit, logger):
        self.logger = logger
        logger.put(5, '>ProcessingQueue.__init__')
        logger.put(3, 'Initializing ProcessingQueue')
        self.mon = threading.RLock()
        self.iw = threading.Condition(self.mon)
        self.ow = threading.Condition(self.mon)
        self.lineq = []
        self.resultsets = {}
        self.limit = limit
        self.working = 1
        logger.put(5, '<ProcessingQueue.__init__')

    def put_linemap(self, linemap, handler, module):
        """
        Accepts a linemap and stores it to be picked up by a thread.
        """
        self.mon.acquire()
        logger = self.logger
        logger.put(5, '>ProcessingQueue.put_linemap')
        while len(self.lineq) >= self.limit:
            logger.put(5, 'Line queue is full, waiting...')
            self.ow.wait()
        self.lineq.append([linemap, handler, module])
        logger.put(3, 'Added a new line in lineq')
        logger.put(5, 'items in lineq: %d' % len(self.lineq))
        self.iw.notify()
        logger.put(5, '<ProcessingQueue.put_linemap')
        self.mon.release()

    def get_linemap(self):
        """
        This is used by a running thread, which gets the linemap
        and processes it.
        """
        self.mon.acquire()
        logger = self.logger
        logger.put(5, '>ProcessingQueue.get_linemap')
        while not self.lineq and self.working:
            logger.put(5, 'Line queue is empty, waiting...')
            self.iw.wait()
        if self.working:
            item = self.lineq.pop(0)
            logger.put(3, 'Got new linemap for the thread.')
            logger.put(5, 'items in lineq: %d' % len(self.lineq))
            self.ow.notify()
        else: item = None
        logger.put(5, '<ProcessingQueue.get_linemap')
        self.mon.release()
        return item

    def put_result(self, line, result, module):
        """
        Once the running thread is done with the module, it returns the
        result and places it here.
        """
        self.mon.acquire()
        logger = self.logger
        logger.put(5, '>ProcessingQueue.put_result')
        if result is not None:
            try: self.resultsets[module].add_result(result)
            except KeyError:
                self.resultsets[module] = Result()
                self.resultsets[module].add_result(result)
            module.put_filtered(line)
            logger.put(3, 'Added result from module "%s"' % module.name)
        else:
            logger.put(3, '"%s" returned result None. Skipping.' % module.name)
        logger.put(5, '<ProcessingQueue.put_result')
        self.mon.release()

    def get_resultset(self, module):
        """
        When all threads are done, the resultset is returned to anyone
        interested.
        """
        self.logger.put(5, '>ProcessingQueue.get_resultset')
        rs = self.resultsets[module]
        self.logger.put(5, '<ProcessingQueue.get_resultset')
        return rs
    
    def tell_threads_to_quit(self, threads):
        """
        Tell all threads that they should exit as soon as possible.
        """
        self.mon.acquire()
        logger = self.logger
        logger.put(5, '>ProcessingQueue.tell_threads_to_quit')
        logger.put(1, 'Telling all threads to quit')
        logger.put(5, 'Waiting till queue is empty')
        while self.lineq:
            logger.put(5, 'items in lineq: %d' % len(self.lineq))
            self.ow.wait()
        self.logger.put(5, 'working=0')
        self.working = 0
        logger.put(3, 'Sending %d semaphore notifications' % len(threads))
        for t in threads: self.iw.notify()
        logger.put(5, '<ProcessingQueue.tell_threads_to_quit')
        self.mon.release()

class ConsumerThread(threading.Thread):
    """
    This class extends Thread, and is used to thread up the internal
    module invocation.
    """
    def __init__(self, queue, logger):
        threading.Thread.__init__(self)
        logger.put(5, '>ConsumerThread.__init__')
        self.logger = logger
        self.queue = queue
        logger.put(5, '<ConsumerThread.__init__')

    def run(self):
        logger = self.logger
        logger.put(5, '>ConsumerThread.run')
        while self.queue.working:
            logger.put(3, '%s: getting a new linemap' % self.getName())
            item = self.queue.get_linemap()
            if item is not None:
                linemap, handler, module = item
                logger.put(3, '%s: calling the handler' % self.getName())
                try:
                    result = handler(linemap)
                    if result is not None:
                        line = linemap['line']
                        logger.put(5, '%s: returning result' % self.getName())
                        self.queue.put_result(line, result, module)
                    else:
                        logger.put(5, '%s: Result is None.' % self.getName())
                except Exception, e:
                    erep  = 'Handler crash. Dump follows:\n'
                    erep += '  Thread : %s\n' % self.getName()
                    erep += '  Module : %s\n' % module.executable
                    erep += '  Handler: %s\n' % handler.__name__
                    erep += '  Error  : %s\n' % e
                    erep += '  Line   : %s\n' % linemap['line'].strip()
                    erep += 'End Dump'
                    logger.put(0, erep)
            else:
                logger.put(5, '%s: Item is none.' % self.getName())
        logger.put(3, '%s: I am now dying' % self.getName())
        logger.put(5, '<ConsumerThread.run')

class Result(dict):
    """
    Result is an extension of a standard dictionary.
    """
    def add_result(self, result):
        """
        Adds another result to the resultset.
        """
        try:
            restuple, mult = result.popitem()
            if restuple in self: self[restuple] += mult
            else: self[restuple] = mult
        except KeyError: pass

    def get_distinct(self, matchtup, sort=1):
        """
        This is a helper method that allows one to do the following:
        say you have this resultset:
          {
            (foo, bar, baz): 1,
            (foo, bar, quux): 3,
            (foo, zed, baz): 1,
            (foo, zed, quux): 1
          }
        if you do .get_distinct((foo,)), you will get a list of all distinct
        tuple members directly following (foo,), which would be
        [bar, zed]. If you do .get_distinct((foo, bar)), you will get
        [baz, quux].

        Note, that this is slow and inefficient on large resultsets.
        """
        lim = len(matchtup)
        matches = []
        reskeys = self.keys()
        if sort: reskeys.sort()
        for key in reskeys:
            if matchtup == key[0:lim]:
                if key[lim] not in matches:
                    matches.append(key[lim])
        return matches

    def get_submap(self, matchtup, sort=1, remove=0):
        """
        Similarly to get_distinct, this is a helper method.
        say you have this resultset:
          {
            (foo, bar, baz): 1,
            (foo, bar, quux): 3,
            (foo, zed, baz): 1,
            (foo, zed, quux): 1
          }
        If you do .get_submap((foo,)), it will return the following list:
        [(bar, baz), (bar, quux), (zed, baz), (zed, quux)], and if you do
        .get_submap((foo, bar)), you will get:
        [(baz,), (quux,)]

        Note, that this is slow and inefficient on large resultsets.

        """
        lim = len(matchtup)
        matchmap = {}
        reskeys = self.keys()
        if sort: reskeys.sort()
        for key in reskeys:
            if matchtup == key[0:lim]:
                subtup = key[lim:]
                try: matchmap[subtup] += self[key]
                except KeyError: matchmap[subtup] = self[key]
                if remove: del self[key]
        return matchmap

    def get_top(self, lim):
        """
        This method returns the top most common entries (the ones that have
        the highest mult. The limit is passed as argument.
        """
        if not lim: return {}
        sortlist = []
        for tuple, mult in self.items():
            sortlist.append((mult, tuple))
        sortlist.sort()
        sortlist = sortlist[-lim:]
        sortlist.reverse()
        return sortlist

    def is_empty(self):
        """
        Returns a 0 if this dict is empty.
        """
        if self: return 0
        else: return 1

class InternalModule:
    """
    This is a helper class to be extended by internal modules.
    """
    def __init__(self):
        self._known_hosts = {}
        self._known_uids = {}
        self.amp_re = re.compile('&')
        self.lt_re  = re.compile('<')
        self.gt_re  = re.compile('>')

    def htmlsafe(self, unsafe):
        """
        Escapes all x(ht)ml control characters.
        """
        unsafe = re.sub(self.amp_re, '&amp;', unsafe)
        unsafe = re.sub(self.lt_re, '&lt;', unsafe)
        unsafe = re.sub(self.gt_re, '&gt;', unsafe)
        return unsafe
        
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
        ##
        # Handle silly fake ipv6 addresses
        #
        try:
            if ip_addr[:7] == '::ffff:': ip_addr = ip_addr[7:]
        except: pass
        try: return self._known_hosts[ip_addr]
        except KeyError: pass
        try: name = socket.gethostbyaddr(ip_addr)[0]
        except socket.error: name = ip_addr
        self._known_hosts[ip_addr] = name
        return name
        
    def get_smm(self, lm):
        """
        Return a systemname, message, and multiplier from a linemap, since
        these are most commonly needed in a module.
        """
        return (lm['system'], lm['message'], lm['multiplier'])

    def mk_size_unit(self, size):
        """
        Make a human-readable size unit from a size in bytes.
        """
        ksize = int(size/1024)
        if ksize:
            msize = int(ksize/1024)
            if msize:
                gsize = int(msize/1024)
                if gsize: return (gsize, 'GB')
                return (msize, 'MB')
            return (ksize, 'KB')
        return (size, 'Bytes')

class Logger:
    """
    A default command-line logger class. Other GUIs should use their own,
    but fully implement the API.
    """
    indent = '  '
    hangmsg = []
    hanging = 0

    def __init__(self, loglevel):
        self.loglevel = loglevel

    def is_quiet(self):
        """Check if we should be quiet"""
        if self.loglevel == 0:
            return 1
        else:
            return 0

    def debuglevel(self):
        """Return the current debug level"""
        return str(self.loglevel)

    def put(self, level, message):
        """Log a message, but only if debug levels are lesser or match"""
        if (level <= self.loglevel):
            if self.hanging:
                self.hanging = 0
            print '%s%s' % (self._getindent(), message)

    def puthang(self, level, message):
        """
        This indents the output, create an easier-to-read debug data.
        """
        if (level <= self.loglevel):
            print '%sInvoking: "%s"...' % (self._getindent(), message)
            self.hanging = 1
            self.hangmsg.append(message)

    def endhang(self, level, message='done'):
        """Must be called after puthang has been put in effect"""
        if (level <= self.loglevel):
            hangmsg = self.hangmsg.pop()
            if self.hanging:
                self.hanging = 0
                print '%s%s...%s' % (self._getindent(), hangmsg, message)
            else:
                print '%s(Hanging from "%s")....%s' % (self._getindent(),
                                                       hangmsg, message)

    def progressbar(self, level, title, done, total):
        """
        A simple command-line progress bar.
        """
        if level != self.loglevel: return
        ##
        # Do some nifty calculations to present the bar
        #
        if len(title) > 40: title = title[:40]
        barwidth = 60 - len(title) - 2 - len(self._getindent())
        barmask = "[%-" + str(barwidth) + "s]"
        if total != 0: bardown = int(barwidth*(float(done)/float(total)))
        else: bardown = 0
        bar = barmask % ("=" * bardown)
        sys.stdout.write("\r%s%s: %s\r" % (self._getindent(), title, bar))

    def endbar(self, level, title, message):
        """
        After the progress bar is no longer useful, let's replace it with
        something useful.
        """
        if level != self.loglevel: return
        if not message:
            print
            return
        ##
        # Do some nifty calculations to present the bar
        #
        if len(title) > 40: title = title[:40]
        barwidth = 60 - len(title) - len(self._getindent()) - 2
        message = '[%s]' % message.center(barwidth)
        sys.stdout.write("\r%s%s: %s\n" % (self._getindent(), title, message))

    def _getindent(self):
        """
        Get the indent spaces.
        """
        indent = self.indent * len(self.hangmsg)
        return indent
