import epylog
import os
import re
import string
import time

def mkmonthmap():
    pad = 2
    months = []
    for i in range(0, 12):
        months.append(time.strftime("%b", (0, i+1, 0, 0,
                                           0, 0, 0, 0, 0)))
    basetime = time.localtime(time.time())
    now_year = basetime[0]
    now_month = basetime[1]
    pad_month = now_month + pad
    monthmap = {}
    for m in range(pad_month - 12, pad_month):
        monthname = months[m % 12]
        year = now_year + (m / 12) 
        monthmap[monthname] = year
    return monthmap

def mkstamp_from_syslog_datestr(datestr, monthmap):
    try:
        (m, d, t) = datestr.split()[:3]
        y = str(monthmap[m])
        datestr = string.join([y, m, d, t], ' ')
        timestamp = time.mktime(time.strptime(datestr, '%Y %b %d %H:%M:%S'))
    except:
        timestamp = -1
    return timestamp


class LogTracker:
    def __init__(self, config, logger):
        self.logger = logger
        logger.put(5, 'Entering LogTracker.__init__')
        self.tmpprefix = config.tmpprefix
        self.entries = []
        self.logs = []
        self.monthmap = mkmonthmap()
        logger.put(5, 'Exiting LogTracker.__init__')

    def getlog(self, entry):
        logger = self.logger
        logger.put(5, 'Entering LogTracker.getlog')
        logger.put(5, 'Checking if we have a log for entry "%s"' % entry)
        if entry in self.entries:
            logger.put(5, 'Yes, returning that log')
            log = self._get_log_by_entry(entry)
        else:
            logger.put(5, 'Logfile for "%s" not yet initialized' % entry)
            log = self._init_log_by_entry(entry)
        logger.put(5, 'Exiting LogTracker.getlog')
        return log

    def get_offset_map(self):
        logger = self.logger
        logger.put(5, 'Entering LogTracker.get_offset_map')
        omap = []
        for log in self.logs:
            entry = log.entry
            inode = log.getinode()
            if log.orange.endix != 0:
                offset = 0
            else:
                offset = log.orange.end_offset
            omap.append([entry, inode, offset])
        logger.put(5, 'omap follows')
        logger.put(5, omap)
        logger.put(5, 'Exiting LogTracker.get_offset_map')
        return omap

    def set_start_offset_by_entry(self, entry, inode, offset):
        logger = self.logger
        logger.put(5, '>LogTracker.set_offset_by_entry')
        logger.put(5, 'entry=%s' % entry)
        logger.put(5, 'inode=%d' % inode)
        logger.put(5, 'offset=%d' % offset)
        if entry in self.entries:
            log = self._get_log_by_entry(entry)
            if log.getinode() != inode:
                logger.put(5, 'Inodes do not match. Assuming logrotation')
                try:
                    log.set_range_param(1, offset, 0)
                except epylog.OutOfRangeError:
                    logger.put(5, 'No rotated file in place. Set offset to 0')
                    log.set_range_param(0, 0, 0)
            else:
                logger.put(5, 'Inodes match, setting offset to "%d"' % offset)
                log.set_range_param(0, offset, 0)
        else:
            msg = 'No such log entry "%s"' % entry
            raise epylog.NoSuchLogError(msg, logger)
        logger.put(5, '<LogTracker.set_offset_by_entry')

    def dump_all_strings(self, fh):
        logger = self.logger
        logger.put(5, '>LogTracker.dump_all_strings')
        len = 0
        for log in self.logs:
            logger.put(5, 'Dumping strings for log entry "%s"' % log.entry)
            len = len + log.dump_strings(fh)
        logger.put(5, 'Total of %d bytes dumped into "%s"' % (len, fh.name))
        logger.put(5, '<LogTracker.dump_all_strings')
        return len

    def get_stamps(self):
        ##
        # Returns a tuple with the earliest and the latest time stamp
        # from all the logs.
        #
        logger = self.logger
        logger.put(5, '>LogTracker.get_stamps')
        start_stamps = []
        end_stamps = []
        for log in self.logs:
            if log.is_range_empty():
                logger.put(5, 'The range for this log is empty')
                continue
            [start_stamp, end_stamp] = log.get_stamps()
            if start_stamp != 0:
                start_stamps.append(start_stamp)
            if end_stamp != 0:
                end_stamps.append(end_stamp)
        if len(start_stamps):
            start_stamps.sort()
            start_stamp = start_stamps.pop(0)
        else:
            start_stamp = 0
        if len(end_stamps):
            end_stamps.sort()
            end_stamp = end_stamps.pop(-1)
        else:
            end_stamp = 0
        logger.put(5, 'start_stamp=%d' % start_stamp)
        logger.put(5, 'end_stamp=%d' % end_stamp)
        return [start_stamp, end_stamp]
        logger.put(5, '<LogTracker.get_stamps')

    def set_range_by_timestamps(self, start_stamp, end_stamp):
        logger = self.logger
        logger.put(5, '>LogTracker.set_offsets_by_timestamp')
        for log in self.logs:
            try:
                log.set_range_by_timestamps(start_stamp, end_stamp)
            except epylog.OutOfRangeError:
                msg = 'Timestamps not found for log entry "%s"' % log.entry
                logger.put(0, msg)
        logger.put(5, '<LogTracker.set_offsets_by_timestamp')
        
    def _init_log_by_entry(self, entry):
        logger = self.logger
        logger.put(5, 'Entering LogTracker._init_log_by_entry')
        logger.puthang(5, 'Initializing log object for entry "%s"' % entry)
        log = Log(entry, self.tmpprefix, self.monthmap, self.logger)
        logger.endhang(5)
        self.entries.append(entry)
        self.logs.append(log)
        logger.put(5, 'Exiting LogTracker._init_log_by_entry')
        return log

    def _get_log_by_entry(self, entry):
        logger = self.logger
        logger.put(5, 'Entering LogTracker._get_log_by_entry')
        for log in self.logs:
            if log.entry == entry:
                logger.put(5, 'Found log object "%s"' % entry)
                logger.put(5, 'Exiting LogTracker._get_log_by_entry')
                return log
        logger.put(5, 'No such log file! Returning None. How did this happen?')
        return None

class OffsetRange:
    def __init__(self, startix, start_offset, endix, end_offset, logger):
        self.logger = logger
        logger.put(5, '>OffsetRange.__init__')
        self.startix = startix
        self.endix = endix
        self.start_offset = start_offset
        self.end_offset = end_offset
        logger.put(5, 'startix=%d' % self.startix)
        logger.put(5, 'start_offset=%d' % self.start_offset)
        logger.put(5, 'endix=%d' % self.endix)
        logger.put(5, 'end_offset=%d' % self.end_offset)
        logger.put(5, '<OffsetRange.__init__')

    def setstart(self, ix, offset):
        logger = self.logger
        logger.put(5, '>OffsetRange.setstart')
        self.startix = ix
        self.start_offset = offset
        logger.put(5, 'new startix=%d' % self.startix)
        logger.put(5, 'new start_offset=%d' % self.start_offset)
        logger.put(5, '<OffsetRange.setstart')

    def setend(self, ix, offset):
        logger = self.logger
        logger.put(5, '<OffsetRange.setend')
        self.endix = ix
        self.end_offset = offset
        logger.put(5, 'new endix=%d' % self.endix)
        logger.put(5, 'new end_offset=%d' % self.end_offset)
        logger.put(5, '>OffsetRange.setend')

    def start_is_end(self):
        logger = self.logger
        logger.put(5, '>OffsetRange.start_is_end')
        empty = 0
        if self.startix == self.endix:
            if self.start_offset == self.end_offset:
                empty = 1
                logger.put(5, 'This range points to same location')
        logger.put(5, '<OffsetRange.start_is_end')
        return empty

    def is_inside(self, ix, offset):
        logger = self.logger
        logger.put(5, '>OffsetRange.is_inside')
        cond = 1
        if ix < self.startix: cond = 0
        elif ix > self.endix: cond = 0
        elif ix == self.startix and offset < self.start_offset: cond = 0
        elif ix == self.endix and offset > self.end_offset: cond = 0
        if cond:
            logger.put(5, 'ix=%d, offset=%d is inside' % (ix, offset))
        logger.put(5, '<OffsetRange.is_inside')
        return cond

class LinePointer:
    def __init__(self, ix, offset, logger):
        self.logger = logger
        logger.put(5, '>LinePointer.__init__')
        self.ix = ix
        self.offset = offset
        logger.put(5, '<LinePointer.__init__')

    def set(self, ix, offset):
        logger = self.logger
        logger.put(5, '>LinePointer.set')
        self.ix = ix
        self.offset = offset
        logger.put(5, 'ix=%d' % ix)
        logger.put(5, 'offset=%d' % offset)
        logger.put(5, '<LinePointer.set')

class Log:
    def __init__(self, entry, tmpprefix, monthmap, logger):
        logger.put(5, 'Entering Log.__init__')
        logger.puthang(3, 'Initializing Log object for entry "%s"' % entry)
        self.logger = logger
        self.tmpprefix = tmpprefix
        self.monthmap = monthmap
        self.entry = entry
        filename = self._get_filename()
        logger.puthang(4, 'Initializing the logfile "%s"' % filename)
        logfile = LogFile(filename, tmpprefix, monthmap, logger)
        logger.endhang(4)
        logger.put(3, 'Appending logfile to the loglist')
        self.loglist = [logfile]
        self.orange = OffsetRange(0, 0, 0, logfile.end_offset, logger)
        logger.endhang(3)
        self.lp = None
        logger.put(5, 'Exiting Log.__init__')

    def set_range_param(self, ix, offset, whence=0):
        logger = self.logger
        logger.put(5, 'Entering Log.set_range_param')
        logger.put(5, 'ix=%d' % ix)
        logger.put(5, 'offset=%d' % offset)
        logger.put(5, 'whence=%d' % whence)
        while not self._is_valid_ix(ix):
            try:
                self._init_next_rotfile()
            except epylog.NoSuchLogError:
                msg = 'Invalid index "%d" for log "%s"' % (ix, self.entry)
                raise epylog.OutOfRangeError(msg, logger)
        if whence:
            logger.put(5, 'Setting range END for entry "%s"' % self.entry)
            self.orange.setend(ix, offset)
        else:
            logger.put(5, 'Setting range START for entry "%s"' % self.entry)
            self.orange.setstart(ix, offset)
        logger.put(5, 'Exiting Log.set_range_param')

    def getinode(self):
        logger = self.logger
        logger.put(5, '>Log.getinode')
        logfile = self.loglist[0]
        inode = logfile.getinode()
        logger.put(5, 'inode=%d' % inode)
        logger.put(5, '<Log.getinode')
        return inode

    def nextline(self):
        logger = self.logger
        logger.put(5, '>Log.nextline')
        if self.lp is None:
            ix = self.orange.startix
            offset = self.orange.start_offset
            logger.put(5, 'setting init linepointer with ix=%d, offset=%d' %
                       (ix, offset))
            self.lp = LinePointer(ix, offset, logger)
        ix = self.lp.ix
        offset = self.lp.offset
        offset_orig = offset
        logger.put(5, 'Checking if we are past the orange end')
        if not self.orange.is_inside(ix, offset):
            msg = 'Moved past the end of the range'
            raise epylog.OutOfRangeError(msg, logger)
        ologs = self._get_orange_logs()
        log = ologs[ix]
        line, offset = log.get_line_at_offset(offset)
        try:
            stamp, system, message = self._get_stamp_sys_msg(line)
        except epylog.FormatError, e:
            logger.put(0, 'Invalid syslog format string in %s: %s'
                       (log.filename, line))
            # Pass it on
            raise epylog.FormatError(e, logger)
        mo = epylog.MESSAGE_REPEATED_RE.search(message)
        multiplier = 1
        if mo:
            try:
                message = self._lookup_repeated(system)
                multiplier = int(mo.group(1))
            except epylog.FormatError: pass
        if offset == log.end_offset:
            logger.put(5, 'End of log "%s" reached' % log.filename)
            ix += 1
            offset = 0
        self.lp.set(ix, offset)
        logger.put(5, '<Log.nextline')
        return stamp, system, message, multiplier

    def _lookup_repeated(self, system):
        logger = self.logger
        logger.put(5, '>Log.lookup_repeated')
        host_re = re.compile('.{15,15} .*[@/]*%s' % system)
        ologs = self._get_orange_logs()
        log = ologs[self.lp.ix]
        offset = self.lp.offset
        logger.put(5, 'Looking in "%s" for the previous report from %s' %
                   (log.filename, system))
        offset_orig = offset
        line = None
        while 1:
            try:
                cline, offset = log.find_previous_entry_by_re(offset, host_re)
            except IOError: break
            if epylog.MESSAGE_REPEATED_RE.search(cline):
                try:
                    rep_offset = log.repeated_lines[offset]
                    logger.put(5, 'Found in cached values')
                    line = log.get_line_at_offset(rep_offset)
                    logger.put(5, 'line=%s' % line)
                    log.repeated_lines[offset_orig] = rep_offset
                    break
                except KeyError: pass
            else:
                logger.put(5, 'Found by backstepping')
                line = cline
                logger.put(5, 'line=%s' % line)
                log.repeated_lines[offset_orig] = offset
                break
        if line is None:
            msg = 'Could not find the original message'
            raise epylog.GenericError(msg, logger)
        try:
            stamp, system, message = self._get_stamp_sys_msg(line)
        except epylog.FormatError, e:
            logger.put(0, 'Invalid syslog format string in %s: %s'
                       (log.filename, line))
        logger.put(5, '<Log.lookup_repeated')
        return message
                    
    def dump_strings(self, fh):
        logger = self.logger
        logger.put(5, '>Log.dump_strings')
        logger.put(4, 'Dumping strings for log entry "%s"' % self.entry)
        ologs = self._get_orange_logs()
        if len(ologs) == 1:
            ##
            # All strings in the same file. Easy.
            #
            starto = self.orange.start_offset
            endo = self.orange.end_offset
            log = ologs[0]
            log.set_offset_range(starto, endo)
            buflen = log.dump_strings(fh)
            logger.put(3, '%d bytes dumped from %s into %s' %
                       (buflen, log.filename, fh.name))
        else:
            ##
            # Strings are in different rotfiles. Hard.
            #
            buflen = 0
            flog = ologs.pop(0)
            elog = ologs.pop(-1)
            logger.put(5, 'Processing the earliest logfile')
            starto = self.orange.start_offset
            endo = flog.end_offset
            flog.set_offset_range(starto, endo)
            buflen = buflen + flog.dump_strings(fh)
            if len(ologs):
                logger.put(5, 'There are logfiles between the first and last')
                for mlog in ologs:
                    mlog.set_offset_range(0, mlog.end_offset)
                    buflen = buflen + mlog.dump_strings(fh)
            logger.put(5, 'Processing the latest logfile')
            starto = 0
            endo = self.orange.end_offset
            elog.set_offset_range(starto, endo)
            buflen = buflen + elog.dump_strings(fh)
            logger.put(3, '%d bytes dumped from multiple rotfiles into "%s"'
                       % (buflen, fh.name))
        logger.put(5, '<Log.dump_strings')
        return buflen

    def _get_stamp_sys_msg(self, line):
        logger = self.logger
        logger.put(5, '>Log._get_stamp_sys_msg')
        mo = epylog.LOG_SPLIT_RE.match(line)
        if not mo:
            msg = 'Unknown format of string "%s"' % line
            raise epylog.FormatError(msg, logger)
        time, sys, msg = mo.groups()
        stamp = mkstamp_from_syslog_datestr(time, self.monthmap)
        sys = re.sub(epylog.SYSLOG_NG_STRIP, '', sys)
        logger.put(5, 'stamp=%d' % stamp)
        logger.put(5, 'sys=%s' % sys)
        logger.put(5, 'msg=%s' % msg)
        logger.put(5, '<Log._get_stamp_sys_msg')
        return stamp, sys, msg

    def get_stamps(self):
        ##
        # Returns a list with the earliest and the latest stamp in the
        # current log range.
        #
        logger = self.logger
        logger.put(5, '>Log.get_stamps')
        logs = self._get_orange_logs()
        flog = logs.pop(0)
        [start_stamp, end_stamp] = flog.get_range_stamps()
        if len(logs):
            elog = logs.pop(-1)
            [junk, end_stamp] = elog.get_range_stamps()
        logger.put(5, 'start_stamp=%d' % start_stamp)
        logger.put(5, 'end_stamp=%d' % end_stamp)
        logger.put(5, '<Log.get_stamps')
        return [start_stamp, end_stamp]

    def set_range_by_timestamps(self, start_stamp, end_stamp):
        logger = self.logger
        logger.put(5, '>Log.set_range_by_timestamps')
        if start_stamp > end_stamp:
            msg = 'Start stamp must be before end stamp'
            raise epylog.OutOfRangeError(msg, logger)
        logger.put(5, 'looking for start_stamp=%d' % start_stamp)
        logger.put(5, 'looking for end_stamp=%d' % end_stamp)
        ix = 0
        start_offset = None
        end_offset = None
        while 1:
            logger.put(5, 'ix=%d' % ix)
            try:
                curlog = self.loglist[ix]
            except IndexError:
                logger.put(5, 'This log is not yet initialized')
                try:
                    curlog = self._init_next_rotfile()
                except epylog.NoSuchLogError:
                    logger.put(5, 'No more rotated files present')
                    if end_offset is not None:
                        logger.put(5, 'setting start_offset to 0, last ix')
                        start_offset = 0
                        start_ix = len(self.loglist) - 1
                        break
                    else:
                        msg = 'Range not found when searching for timestamps'
                        raise epylog.OutOfRangeError(msg, logger)
            logger.put(5, 'Analyzing log file "%s"' % curlog.filename)
            try:
                pos_start = curlog.stamp_in_log(start_stamp)
                pos_end = curlog.stamp_in_log(end_stamp)
            except epylog.OutOfRangeError:
                logger.put(5, 'No useful entries in this log, ignoring')
                ix = ix + 1
                continue
            if pos_start == 0:
                ##
                # In this log
                #
                logger.put(5, 'start_stamp is in "%s"' % curlog.filename)
                start_ix = ix
                start_offset = curlog.find_offset_by_timestamp(start_stamp)
            elif pos_start > 0:
                ##
                # Past this log. This means that we have missed the start
                # of this stamp. Set by the end_offset of the current log.
                #
                logger.put(5, 'start_stamp is past "%s"' % curlog.filename)
                logger.put(5, 'setting to end_offset of this log')
                start_ix = ix
                start_offset = curlog.end_offset
            if pos_end == 0:
                ##
                # In this log
                #
                logger.put(5, 'end_stamp is in "%s"' % curlog.filename)
                end_ix = ix
                end_offset = curlog.find_offset_by_timestamp(end_stamp)
            elif pos_end > 0 and end_offset is None:
                ##
                # Means that end of the search is past the end of the last
                # log.
                #
                logger.put(5, 'end_stamp is past the most current entry')
                logger.put(5, 'setting to end_offset of this ix')
                end_ix = ix
                end_offset = curlog.end_offset
            if start_offset is not None and end_offset is not None:
                logger.put(5, 'Found both the start and the end')
                break
            ix = ix + 1
        logger.put(5, 'start_ix=%d' % start_ix)
        logger.put(5, 'start_offset=%d' % start_offset)
        logger.put(5, 'end_ix=%d' % end_ix)
        logger.put(5, 'end_offset=%d' % end_offset)
        self.orange.setstart(start_ix, start_offset)
        self.orange.setend(end_ix, end_offset)
        logger.put(5, '<Log.set_range_by_timestamps')

    def is_range_empty(self):
        logger = self.logger
        logger.put(5, '>Log.is_range_empty')
        empty = 0
        if self.orange.start_is_end():
            empty = 1
            logger.put(5, 'Yes, range is empty')
        else:
            startlog = self.loglist[self.orange.startix]
            endlog = self.loglist[self.orange.endix]
            if (startlog.end_offset == self.orange.end_offset and
                self.orange.endix == self.orange.startix + 1 and
                self.orange.end_offset == 0):
                ##
                # This means that start is at the end of the last rotlog
                # and end is at the start of next rotlog, meaning that the
                # range is really empty.
                empty = 1
        logger.put(5, '<Log.is_range_empty')
        return empty

    def _get_orange_logs(self):
        logger = self.logger
        logger.put(5, '>Log._get_orange_logs')
        ologs = []
        for ix in range(self.orange.startix, self.orange.endix - 1, -1):
            logger.put(5, 'appending "%s"' % self.loglist[ix].filename)
            ologs.append(self.loglist[ix])
        logger.put(5, '<Log._get_orange_logs')
        return ologs

    def _is_valid_ix(self, ix):
        logger = self.logger
        logger.put(5, '>Log._is_valid_ix')
        ixlen = len(self.loglist) - 1
        isvalid = 1
        if ix > ixlen:
            logger.put(5, 'index %d is not valid' % ix)
            isvalid = 0
        logger.put(5, '<Log._is_valid_ix')
        return isvalid

    def _init_next_rotfile(self):
        logger = self.logger
        logger.put(5, '>Log._init_next_rotfile')
        ix = len(self.loglist)
        rotname = self._get_rotname_by_ix(ix)
        try:
            logger.put(5, 'Initializing log for rotated file "%s"' % rotname)
            rotlog = LogFile(rotname, self.tmpprefix, self.monthmap, logger)
        except epylog.AccessError:
            msg = 'No further rotated files for entry "%s"' % self.entry
            raise epylog.NoSuchLogError(msg, logger)
        self.loglist.append(rotlog)
        logger.put(5, '<Log._init_next_rotfile')
        return rotlog

    def _get_rotname_by_ix(self, ix):
        logger = self.logger
        logger.put(5, '>Log._get_rotname_by_ix')
        logger.put(5, 'ix=%d' % ix)
        if re.compile('\[/').search(self.entry):
            ##
            # Full filename specified in the brackets:
            # e.g. /var/log/messages[/var/log/rotated/messages.#.gz]
            #
            rot_m = re.compile('\[(.*?)\]').search(self.entry)
            try:
                rotname = rot_m.group(1)
            except:
                msg = ('Could not figure out the rotated filename in "%s"'
                       % self.entry)
                raise epylog.ConfigError(msg, logger)
        else:
            rotname = re.sub(re.compile('\[|\]'), '', self.entry)
        rotname = re.sub(re.compile('#'), str(ix), rotname)
        logger.put(5, 'rotname=%s' % rotname)
        logger.put(5, '<Log._get_rotname_by_ix')
        return rotname

    def _get_filename(self):
        logger = self.logger
        logger.put(5, '>Log._get_filename')
        logger.put(5, 'entry=%s' % self.entry)
        filename = re.sub(re.compile('\[.*?\]'), '', self.entry)
        logger.put(5, 'filename=%s' % filename)
        logger.put(5, '<Log._get_filename')
        return filename
            
class LogFile:
    def __init__(self, filename, tmpprefix, monthmap, logger):
        self.logger = logger
        logger.put(5, 'Entering LogFile.__init__')
        self.tmpprefix = tmpprefix
        self.filename = filename
        self.monthmap = monthmap
        ##
        # start_stamp:  the timestamp at the start of the log
        # end_stamp:    the timestamp at the end of the log
        # end_offset:   this is where the end of the log is
        #
        self.start_stamp = None
        self.end_stamp = None
        self.end_offset = None
        ##
        # range_start: the start offset of the range
        # range_end:   the end offset of the range
        #
        self.range_start = 0
        self.range_end = None
        ##
        # repeated_lines: map of offsets to repeated lines for
        #                 unwrapping those pesky "last message repeated"
        #                 entries
        self.repeated_lines = {}
        
        logger.put(3, 'Running sanity checks on the logfile')
        self._accesscheck()
        logger.put(3, 'All checks passed')
        logger.put(5, 'Initializing the file')
        self._initfile()
        logger.put(5, 'Exiting LogFile.__init__')

    def _initfile(self):
        logger = self.logger
        logger.put(5, 'Entering LogFile._initfile')
        logger.put(5, 'Checking if we are gzipped (ends in .gz)')
        if re.compile('\.gz$').search(self.filename, 1):
            logger.put(5, 'Ends in .gz. Using GzipFile to open')
            import gzip
            import epylog.mytempfile as tempfile
            tempfile.tmpdir = self.tmpprefix
            ungzfile = tempfile.mktemp('UNGZ')
            logger.put(5, 'Creating a tempfile in "%s"' % ungzfile)
            ungzfh = open(tempfile.mktemp('UNGZ'), 'w+')
            try:
                gzfh = gzip.open(self.filename)
            except:
                raise epylog.ConfigError(('Could not open file "%s" with'
                                          + ' gzip handler. Not gzipped?')
                                         % self.filename, logger)
            logger.put(5, 'Putting the contents of the gzlog into ungzlog')
            while 1:
                chunk = gzfh.read(epylog.CHUNK_SIZE)
                if chunk:
                    ungzfh.write(chunk)
                    logger.put(5, 'Read "%s" bytes from gzfh' % len(chunk))
                else:
                    logger.put(5, 'Reached EOF')
                    break
            gzfh.close()
            self.fh = ungzfh
        else:
            logger.put(5, 'Does not end in .gz, assuming plain text')
            logger.put(5, 'Opening logfile "%s"' % self.filename)
            self.fh = open(self.filename)
        logger.put(5, 'Finding the start_stamp')
        self.fh.seek(0)
        self.start_stamp = self._get_stamp()
        logger.put(5, 'start_stamp=%d' % self.start_stamp)
        logger.put(5, 'Finding the end offset')
        self.fh.seek(0, 2)
        self._set_at_line_start()
        self.end_offset = self.fh.tell()
        self.range_end = self.fh.tell()
        logger.put(5, 'Finding the end_stamp')
        self.end_stamp = self._get_stamp()
        logger.put(5, 'end_stamp=%d' % self.end_stamp)
        logger.put(5, 'Exiting LogFile._initfile')

    def set_offset_range(self, start, end):
        logger = self.logger
        logger.put(5, '>LogFile.set_offset_range')
        logger.put(5, 'start=%d' % start)
        logger.put(5, 'end=%d' % end)
        if start < 0:
            msg = 'Start of range cannot be less than zero'
            raise epylog.OutOfRangeError(msg, logger)
        if end > self.end_offset:
            msg = 'End of range "%d" is past the end of log' % end
            raise epylog.OutOfRangeError(msg, logger)
        if start > end:
            msg = 'Start of range cannot be greater than end'
            raise epylog.OutOfRangeError(msg, logger)
        self.fh.seek(start)
        self._set_at_line_start()
        self.range_start = self.fh.tell()
        self.fh.seek(end)
        self._set_at_line_start()
        self.range_end = self.fh.tell()
        logger.put(5, '<LogFile.set_offset_range')

    def getinode(self):
        self.logger.put(5, 'Entering LogFile.getinode')
        inode = os.stat(self.filename).st_ino
        self.logger.put(5, 'inode=%d' % inode)
        self.logger.put(5, 'Exiting LogFile.getinode')
        return inode

    def stamp_in_log(self, searchstamp):
        logger = self.logger
        logger.put(5, '>LogFile.stamp_in_log')
        logger.put(5, 'searchstamp=%d' % searchstamp)
        logger.put(5, 'start_stamp=%d' % self.start_stamp)
        logger.put(5, 'end_stamp=%d' % self.end_stamp)
        if self.start_stamp == 0 or self.end_stamp == 0:
            msg = 'No stampable entries in this log'
            raise epylog.OutOfRangeError(msg, logger)
        if searchstamp > self.end_stamp:
            logger.put(5, 'past the end of this log')
            ret = 1
        elif searchstamp < self.start_stamp:
            logger.put(5, 'before the start of this log')
            ret = -1
        elif searchstamp >= self.start_stamp and searchstamp <= self.end_stamp:
            logger.put(5, 'IN this log')
            ret = 0
        logger.put(5, '<LogFile.stamp_in_log')
        return ret
        
    def find_offset_by_timestamp(self, searchstamp):
        logger = self.logger
        logger.put(5, '>LogFile.find_offset_by_timestamp')
        if self.start_stamp == 0 or self.end_stamp == 0:
            logger.put(2, 'Does not seem like anything useful is in this file')
            raise epylog.OutOfRangeError('Nothing useful in this log', logger)
        if self.stamp_in_log(searchstamp) != 0:
            msg = 'This stamp does not appear to be in this log'
            raise epylog.OutOfRangeError(msg, logger)
        self._crude_locate(searchstamp)
        self._fine_locate(searchstamp)
        offset = self.fh.tell()
        logger.put(2, 'Offset found at %d' % offset)
        logger.put(5, '<LogFile.find_offset_by_timestamp')
        return offset

    def dump_strings(self, fh):
        logger = self.logger
        logger.put(5, '>LogFile.dump_strings')
        if self.range_end is None:
            msg = 'No range defined for logfile "%s"' % self.filename
            raise epylog.OutOfRangeError(msg, logger)
        chunklen = self.range_end - self.range_start
        logger.put(5, 'range_start=%d' % self.range_start)
        logger.put(5, 'range_end=%d' % self.range_end)
        logger.put(5, 'chunklen=%d' % chunklen)
        self.fh.seek(self.range_start)
        if chunklen > 0:
            iternum = int(chunklen/epylog.CHUNK_SIZE)
            lastchunk = chunklen%epylog.CHUNK_SIZE
            logger.put(5, 'iternum=%d' % iternum)
            logger.put(5, 'lastchunk=%d' % lastchunk)
            if iternum > 0:
                for i in range(iternum):
                    chunk = self.fh.read(epylog.CHUNK_SIZE)
                    fh.write(chunk)
                    logger.put(5, 'wrote %d bytes from %s to %s' %
                               (len(chunk), self.filename, fh.name))
            if lastchunk > 0:
                chunk = self.fh.read(lastchunk)
                fh.write(chunk)
                logger.put(5, 'wrote %d bytes from %s to %s' %
                           (len(chunk), self.filename, fh.name))
        return chunklen

    def get_range_stamps(self):
        logger = self.logger
        logger.put(5, '>LogFile.get_range_stamps')
        self.fh.seek(self.range_start)
        start_stamp = self._get_stamp()
        self.fh.seek(self.range_end)
        end_stamp = self._get_stamp()
        logger.put(5, 'start_stamp=%d' % start_stamp)
        logger.put(5, 'end_stamp=%d' % end_stamp)
        logger.put(5, '<LogFile.get_range_stamps')
        return [start_stamp, end_stamp]

    def get_line_at_offset(self, offset):
        logger = self.logger
        logger.put(5, '>LogFile.get_line_at_offset')
        self.fh.seek(offset)
        line = self.fh.readline()
        offset = self.fh.tell()
        return [line, offset]
        logger.put(5, '<LogFile.get_line_at_offset')

    def find_previous_entry_by_re(self, offset, re):
        logger = self.logger
        logger.put(5, '>LogFile.find_previous_entry_by_re')
        self.fh.seek(offset)
        while 1:
            self._lineback()
            line = self.fh.readline()
            if re.search(line): break
            self._lineback()
        logger.put(5, '<LogFile.find_previous_entry_by_re')
        return line, self.fh.tell()

    def _crude_locate(self, stamp):
        logger = self.logger
        logger.put(5, '>LogFile._crude_locate')
        logger.put(5, 'Looking for "%d" in file %s' % (stamp, self.filename))
        increment = int(self.end_offset/2)
        relative = increment
        logger.put(5, 'rewinding the logfile')
        self.fh.seek(0)
        logger.put(5, 'initial increment=%d' % increment)
        logger.put(5, 'initial relative=%d' % relative)
        ostamp = None
        while 1:
            old_ostamp = ostamp
            self._rel_position(relative)
            ostamp = self._get_stamp()
            if ostamp == 0:
                logger.put(5, 'Bogus timestamp! Breaking.')
                break
            logger.put(5, 'ostamp=%d' % ostamp)
            if old_ostamp == ostamp:
                logger.put(5, 'ostamp and old_ostamp the same. Breaking')
                break
            increment = increment/2
            logger.put(5, 'increment=%d' % increment)
            if ostamp < stamp:
                logger.put(5, '<<<<<<<')
                relative = increment
                logger.put(5, 'Jumping forward by %d' % relative)
            elif ostamp > stamp:
                logger.put(5, '>>>>>>>')
                relative = -increment
                logger.put(5, 'Jumping backward by %d' % relative)
            elif ostamp == stamp:
                logger.put(5, '=======')
                break
        logger.put(5, 'Crude search finished at offset %d' % self.fh.tell())
        logger.put(5, '<LogFile._crude_locate')

    def _fine_locate(self, stamp):
        logger = self.logger
        logger.put(5, '>LogFile._fine_locate')
        lineloc = 0
        oldlineloc = 0
        before_stamp = None
        after_stamp = None
        current_stamp = None
        while 1:
            try:
                if lineloc > 0:
                    logger.put(5, 'Going forward one line')
                    before_stamp = current_stamp
                    current_stamp = after_stamp
                    after_stamp = None
                    self._lineover()
                elif lineloc < 0:
                    logger.put(5, 'Going back one line')
                    before_stamp = None
                    current_stamp = before_stamp
                    after_stamp = current_stamp
                    self._lineback()
                offset = self.fh.tell()
                if offset >= self.end_offset:
                    ##
                    # We have reached the end of the initialized log.
                    # There are possibly entries past this point, but
                    # we can't trust them, as they are appended after the
                    # init and can screw us up.
                    #
                    logger.put(5, 'End of initialized log reached, breaking')
                    self.fh.seek(self.end_offset)
                    break
                if current_stamp is None:
                    current_stamp = self._get_stamp()
                    self.fh.seek(offset)
                if before_stamp is None:
                    self._lineback()
                    before_stamp = self._get_stamp()
                    self.fh.seek(offset)
                if after_stamp is None:
                    self._lineover()
                    after_stamp = self._get_stamp()
                    self.fh.seek(offset)
            except IOError:
                logger.put(5, 'Either end or start of file reached, breaking')
                break
            logger.put(5, 'before_stamp=%d' % before_stamp)
            logger.put(5, 'current_stamp=%d' % current_stamp)
            logger.put(5, 'after_stamp=%d' % after_stamp)
            logger.put(5, 'searching for %d' % stamp)
            if before_stamp == 0 or current_stamp == 0 or after_stamp == 0:
                logger.put(5, 'Bogus stamps found. Breaking.')
                break
            oldlineloc = lineloc
            if before_stamp >= stamp:
                logger.put(5, '>>>>>')
                lineloc = -1
            elif before_stamp < stamp and after_stamp <= stamp:
                logger.put(5, '<<<<<')
                lineloc = 1
            elif current_stamp < stamp and after_stamp >= stamp:
                logger.put(5, '<<<<<')
                lineloc = 1
            elif before_stamp < stamp and current_stamp >= stamp:
                logger.put(5, '=====')
                break
            if oldlineloc == -lineloc:
                ##
                # fine_locate cannot reverse direction.
                # If it does, that means that entries are not in order,
                # which may happen quite frequently on poorly ntpd'd
                # machines. Get out and hope this is good enough.
                #
                logger.put(5, 'Reversed direction. Breaking.')
                break
        logger.put(5, 'fine locate finished at offset %d' % self.fh.tell())
        logger.put(5, '<LogFile._fine_locate')

    def _lineover(self):
        logger = self.logger
        logger.put(5, '>LogFile._lineover')
        offset = self.fh.tell()
        self.fh.readline()
        if self.fh.tell() == offset:
            logger.put(5, 'End of file reached!')
            raise IOError
        logger.put(5, 'New offset at %d' % self.fh.tell())
        logger.put(5, '<LogFile._lineover')

    def _lineback(self):
        logger = self.logger
        logger.put(5, '>LogFile._lineback')
        #self._set_at_line_start()
        if self.fh.tell() <= 1:
            logger.put(5, 'Start of file reached')
            raise IOError
        self._rel_position(-2)
        logger.put(5, 'New offset at %d' % self.fh.tell())
        logger.put(5, '<LogFile._lineback')

    def _get_stamp(self):
        logger = self.logger
        logger.put(5, '>LogFile._get_stamp')
        self._set_at_line_start()
        offset = self.fh.tell()
        curline = self.fh.readline()
        self.fh.seek(offset)
        if len(curline):
            try:
                stamp = self._mkstamp_from_syslog_datestr(curline)
            except epylog.FormatError:
                logger.put(5, 'Could not figure out the format of this string')
                logger.put(5, 'Making it 0')
                stamp = 0
        else:
            logger.put(5, 'Nothing in the range')
            stamp = 0
        logger.put(5, '<LogFile._get_stamp')
        return stamp

    def _rel_position(self, relative):
        logger = self.logger
        logger.put(5, 'Enter LogFile._rel_position')
        offset = self.fh.tell()
        new_offset = offset + relative
        logger.put(5, 'offset=%d' % offset)
        logger.put(5, 'relative=%d' % relative)
        logger.put(5, 'new_offset=%d' % new_offset)
        if new_offset < 0:
            logger.put(5, 'new_offset less than 0. Setting to 0')
            new_offset = 0
        self.fh.seek(new_offset)
        self._set_at_line_start()
        logger.put(5, 'offset after _set_at_line_start: %d' % self.fh.tell())
        logger.put(5, 'Exiting LogFile._rel_position')
    
    def _mkstamp_from_syslog_datestr(self, datestr):
        logger = self.logger
        logger.put(5, '>LogFile._mk_stamp_from_syslog_datestr')
        logger.put(5, 'datestr=%s' % datestr)
        logger.put(2, 'Trying to figure out the date from the string passed')
        timestamp = mkstamp_from_syslog_datestr(datestr, self.monthmap)
        if timestamp == -1:
            raise epylog.FormatError('Cannot grok the date format in "%s"'
                                     % datestr, logger)
        logger.put(2, 'Timestamp is "%d"' % timestamp)
        logger.put(5, '<LogFile._mkstamp_from_syslog_datestr')
        return timestamp
        
    def _accesscheck(self):
        logger = self.logger
        logger.put(5, 'Entering LogFile._accesscheck')
        logfile = self.filename
        logger.put(2, 'Running sanity checks on file "%s"' % logfile)
        if os.access(logfile, os.F_OK):
            logger.put(2, 'Path "%s" exists' % logfile)
        else:
            logger.put(2, 'Path "%s" does not exist' % logfile)
            raise epylog.AccessError('Log file "%s" does not exist'
                                     % logfile, logger)
        if os.access(logfile, os.R_OK):
            logger.put(2, 'File "%s" is readable' % logfile)
        else:
            logger.put(2, 'Logfile "%s" is not readable' % logfile)
            raise epylog.AccessError('Logfile "%s" is not readable'
                                     % logfile, logger)
        logger.put(5, 'Exiting LogFile._accesscheck')

    def _set_at_line_start(self):
        logger = self.logger
        logger.put(5, '>LogFile._set_at_line_start')
        orig_offset = self.fh.tell()
        if orig_offset == 0:
            logger.put(5, 'Already at file start')
            return
        logger.put(5, 'starting the backstepping loop')
        while 1:
            curchar = self.fh.read(1)
            if curchar == '\n':
                logger.put(5, 'Found newline at offset %d' % self.fh.tell())
                break
            logger.put(5, 'curchar=%s' % curchar)
            offset = self.fh.tell() - 1
            self.fh.seek(offset)
            if offset == 0:
                logger.put(5, 'Beginning of file reached!')
                break
            offset = offset - 1
            self.fh.seek(offset)
        logger.put(5, 'Exited the backstepping loop')
        now_offset = self.fh.tell()
        rewound = orig_offset - now_offset
        logger.put(5, 'Line start found at offset "%d"' % now_offset)
        logger.put(5, 'rewound by %d characters' % rewound)
        logger.put(5, '<LogFile._set_at_line_start')
        return rewound
        
