"""
Description will eventually go here.
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
import exceptions
import os
import shutil
import mytempfile as tempfile
import re
import threading
import pwd
import socket
import sys

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
        logger.put(5, 'Unparsed strings will go into %s' % self.unparsed)
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
        self.imodules = []
        self.emodules = []
        for module in self.modules:
            logger.put(5, 'module: %s, priority: %d'
                       % (module.name, module.priority))
            if module.is_internal(): self.imodules.append(module)
            else: self.emodules.append(module)
        logger.put(5, '<Epylog.__init__')

    def process_modules(self):
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
        logger = self.logger
        logger.put(5, '>Epylog.publish_report')
        logger.put(2, 'Dumping all log strings into a temp file')
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
        logger = self.logger
        logger.put(2, 'Cleanup routine called')
        logger.put(2, 'Removing the temp dir "%s"' % self.tmpprefix)
        shutil.rmtree(self.tmpprefix)

    def _get_unparsed(self):
        fh = open(self.unparsed, 'r')
        unparsed = fh.read()
        fh.close
        return unparsed

    def _process_internal_modules(self):
        logger = self.logger
        logger.put(5, '>Epylog._process_internal_modules')
        logger.puthang(1, 'Processing internal modules')
        logger.put(4, 'Collecting logfiles used by internal modules')
        upfh = open(self.unparsed, 'w')
        logger.put(5, 'Opened unparsed strings file in "%s"' % self.unparsed)
        logmap = {}
        for module in self.imodules:
            for log in module.logs:
                try: logmap[log.entry].append(module)
                except KeyError: logmap[log.entry] = [module]
        logger.put(5, 'logmap follows')
        logger.put(5, logmap)
        pq = ProcessingQueue(QUEUE_LIMIT, logger)
        logger.put(5, 'Starting the processing threads')
        threads = []
        try:
            for i in range(0, self.threads):
                t = ConsumerThread(pq, logger)
                t.start()
                threads.append(t)
            for entry in logmap.keys():
                log = self.logtracker.getlog(entry)
                matched = 0
                lines = 0
                while 1:
                    logger.put(5, 'Getting next line from "%s"' % entry)
                    try:
                        linemap = log.nextline()
                    except FormatError: continue
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
                        handler = module.message_match(linemap['message'])
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
            logger.put(5, 'Notifying the threads that they may die now')
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
            try: self.resultsets[module].add_result(result)
            except KeyError:
                self.resultsets[module] = Result()
                self.resultsets[module].add_result(result)
            module.put_filtered(line)
        self.mon.release()

    def get_resultset(self, module):
        return self.resultsets[module]
    
    def tell_threads_to_quit(self, threads):
        self.mon.acquire()
        self.logger.put(1, 'Telling all threads to quit')
        self.logger.put(5, 'Waiting till queue is empty')
        while self.lineq: self.ow.wait()
        self.logger.put(5, 'Set working to 0')
        self.working = 0
        for t in threads: self.iw.notify()
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
        logger.put(5, '%s: I am now dying' % self.getName())

class Result(dict):
    def add_result(self, result):
        try:
            restuple, mult = result.popitem()
            if restuple in self: self[restuple] += mult
            else: self[restuple] = mult
        except KeyError: pass

    def get_distinct(self, matchtup, sort=1):
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

    def get_distinct_values(self, matchtup):
        submap = self.get_submap(matchtup)
        if not submap: return []
        values = []
        while 1:
            try: restuple, mult = submap.popitem()
            except KeyError: break
            for i in range(0, len(restuple)):
                entry = restuple[i]
                ##
                # Get the list of values already at that position
                #
                try: vallist = values[i]
                except IndexError:
                    while 1:
                        values.append([])
                        try:
                            vallist = values[i]
                            break
                        except IndexError: pass
                if entry is None: continue
                if entry not in vallist:
                    vallist.append(entry)
                    values[i] = vallist
        return values

    def get_top(self, lim):
        if not lim: return {}
        sortlist = []
        for tuple, mult in self.items():
            sortlist.append((mult, tuple))
        sortlist.sort()
        sortlist = sortlist[-lim:]
        sortlist.reverse()
        return sortlist

    def is_empty(self):
        if self: return 0
        else: return 1

class InternalModule:
    def __init__(self):
        self._known_hosts = {}
        self._known_uids = {}
        self.amp_re = re.compile('&')
        self.lt_re  = re.compile('<')
        self.gt_re  = re.compile('>')

    def htmlsafe(self, unsafe):
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
        try: return self._known_hosts[ip_addr]
        except KeyError: pass

        try: name = socket.gethostbyaddr(ip_addr)[0]
        except socket.error: name = ip_addr

        self._known_hosts[ip_addr] = name
        return name
        
    def get_smm(self, lm):
        return (lm['system'], lm['message'], lm['multiplier'])

    def mk_size_unit(self, size):
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
            print '%s%s' % (self._getindent(), message)

    def puthang(self, level, message):
        if (level <= self.loglevel):
            print '%sInvoking: "%s"...' % (self._getindent(), message)
            self.hanging = 1
            self.hangmsg.append(message)

    def endhang(self, level, message='done'):
        if (level <= self.loglevel):
            hangmsg = self.hangmsg.pop()
            if self.hanging:
                self.hanging = 0
                print '%s%s...%s' % (self._getindent(), hangmsg, message)
            else:
                print '%s(Hanging from "%s")....%s' % (self._getindent(),
                                                       hangmsg, message)

    def progressbar(self, level, title, done, total):
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
        indent = self.indent * len(self.hangmsg)
        return indent
