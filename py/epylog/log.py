import epylog
import os
import re
import string
import time

class LogTracker:
    def __init__(self, config, logger):
        self.logger = logger
        logger.put(5, 'Entering LogTracker.__init__')
        self.tmpprefix = config.tmpprefix
        self.entries = []
        self.logs = []
        logger.put(5, 'Exiting LogTracker.__init__')

    def getlog(self, entry):
        logger = self.logger
        logger.put(5, 'Entering LogTracker.getlog')
        logger.put(5, 'Checking if we have a log for entry "%s"' % entry)
        if entry in self.entries:
            logger.put(5, 'Yes, returning that log')
            log = self.__get_log_by_entry(entry)
        else:
            logger.put(5, 'Logfile for "%s" not yet initialized' % entry)
            log = self.__init_log_by_entry(entry)
        logger.put(5, 'Exiting LogTracker.getlog')
        return log

    def get_offset_map(self):
        logger = self.logger
        logger.put(5, 'Entering LogTracker.get_offset_map')
        omap = {}
        for log in self.logs:
            key = log.entry
            inode = log.getinode()
            if log.orange.endix != 0:
                offset = 0
            else:
                offset = log.orange.end_offset
            omap[key] = [inode, offset]
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
            log = self.__get_log_by_entry(entry)
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

    def __init_log_by_entry(self, entry):
        logger = self.logger
        logger.put(5, 'Entering LogTracker.__init_log_by_entry')
        logger.puthang(5, 'Initializing log object for entry "%s"' % entry)
        log = Log(entry, self.tmpprefix, self.logger)
        logger.endhang(5)
        self.entries.append(entry)
        self.logs.append(log)
        logger.put(5, 'Exiting LogTracker.__init_log_by_entry')
        return log

    def __get_log_by_entry(self, entry):
        logger = self.logger
        logger.put(5, 'Entering LogTracker.__get_log_by_entry')
        for log in self.logs:
            if log.entry == entry:
                logger.put(5, 'Found log object "%s"' % entry)
                logger.put(5, 'Exiting LogTracker.__get_log_by_entry')
                return log
        logger.put(5, 'No such log file! Returning None. How did this happen?')
        return None
            

class OffsetRange:
    def __init__(self, startix, start_offset, endix, end_offset, logger):
        self.logger = logger
        logger.put(5, 'Entering OffsetRange.__init__')
        self.startix = startix
        self.endix = endix
        self.start_offset = start_offset
        self.end_offset = end_offset
        logger.put(5, 'startix=%d' % self.startix)
        logger.put(5, 'start_offset=%d' % self.start_offset)
        logger.put(5, 'endix=%d' % self.endix)
        logger.put(5, 'end_offset=%d' % self.end_offset)
        logger.put(5, 'Exiting OffsetRange.__init__')

    def setstart(self, ix, offset):
        logger = self.logger
        logger.put(5, 'Entering OffsetRange.setstart')
        self.startix = ix
        self.start_offset = offset
        logger.put(5, 'new startix=%d' % self.startix)
        logger.put(5, 'new start_offset=%d' % self.start_offset)
        logger.put(5, 'Exiting OffsetRange.setstart')

    def setend(self, ix, offset):
        logger = self.logger
        logger.put(5, 'Entering OffsetRange.setend')
        self.endix = ix
        self.end_offset = offset
        logger.put(5, 'new endix=%d' % self.endix)
        logger.put(5, 'new end_offset=%d' % self.end_offset)
        logger.put(5, 'Exiting OffsetRange.setend')

class Log:
    def __init__(self, entry, tmpprefix, logger):
        logger.put(5, 'Entering Log.__init__')
        logger.puthang(3, 'Initializing Log object for entry "%s"' % entry)
        self.logger = logger
        self.tmpprefix = tmpprefix
        self.entry = entry
        filename = self.__get_filename()
        logger.puthang(4, 'Initializing the logfile "%s"' % filename)
        logfile = LogFile(filename, tmpprefix, logger)
        logger.endhang(4)
        logger.put(3, 'Appending logfile to the loglist')
        self.loglist = [logfile]
        self.orange = OffsetRange(0, 0, 0, logfile.end_offset, logger)
        logger.endhang(3)
        logger.put(5, 'Exiting Log.__init__')

    def set_range_param(self, ix, offset, whence=0):
        logger = self.logger
        logger.put(5, 'Entering Log.set_range_param')
        logger.put(5, 'ix=%d' % ix)
        logger.put(5, 'offset=%d' % offset)
        logger.put(5, 'whence=%d' % whence)
        try:
            while not self.__is_valid_ix(ix):
                self.__init_next_logfile()
        except epylog.NoSuchLogError:
            msg = 'Invalid index "%d" for log entry "%s"' % (ix, self.entry)
            raise epylog.OutOfRangeError(msg, logger)
        if whence:
            logger.put(5, 'Setting range END for entry "%s"' % self.entry)
            self.orange.setend(ix, offset)
        else:
            logger.put(5, 'Setting range START for entry "%s"' % self.entry)
            self.orange.setstart(ix, offset)
        logger.put(5, 'Exiting Log.set_range_param')

    def __is_valid_ix(self, ix):
        logger = self.logger
        logger.put(5, 'Entering Log.__is_valid_ix')
        ixlen = len(self.loglist) - 1
        isvalid = 1
        if ix > ixlen:
            logger.put(5, 'index %d is not valid' % ix)
            isvalid = 0
        logger.put(5, 'Exiting Log.__is_valid_ix')
        return isvalid

    def __init_next_rotfile(self):
        logger = self.logger
        logger.put(5, '>Log.__init_next_rotfile')
        ix = len(self.loglist)
        rotname = self.__get_rotname_by_ix(ix)
        try:
            logger.put(5, 'Initializing log for rotated file "%s"' % rotname)
            rotlog = LogFile(rotname, self.tmpprefix, logger)
        except epylog.AccessError:
            msg = 'No further rotated files for entry "%s"' % self.entry
            raise epylog.NoSuchLogError(msg, logger)
        self.loglist.append(rotlog)
        logger.put(5, '<Log.__init_next_rotfile')

    def __get_rotname_by_ix(self, ix):
        logger = self.logger
        logger.put(5, '>Log.__get_rotname_by_ix')
        logger.put(5, 'ix=%d' % ix)
        rotname = re.sub(re.compile('\[|\]'), '', self.entry)
        rotname = re.sub(re.compile('#'), str(ix), rotname)
        logger.put(5, 'rotname=%s' % rotname)
        logger.put(5, '<Log.__get_rotname_by_ix')
        return rotname

    def __get_filename(self):
        logger = self.logger
        logger.put(5, '>Log.__get_filename')
        logger.put(5, 'entry=%s' % self.entry)
        filename = re.sub(re.compile('\[.*?\]'), '', self.entry)
        logger.put(5, 'filename=%s' % filename)
        logger.put(5, '<Log.__get_filename')
        return filename
    
    def getinode(self):
        logger = self.logger
        logger.put(5, 'Entering Log.getinode')
        logfile = self.loglist[0]
        inode = logfile.getinode()
        logger.put(5, 'inode=%d' % inode)
        logger.put(5, 'Exiting Log.getinode')
        return inode
        
class LogFile:
    def __init__(self, filename, tmpprefix, logger):
        self.logger = logger
        logger.put(5, 'Entering LogFile.__init__')
        self.tmpprefix = tmpprefix
        self.filename = filename
        ##
        # start_stamp: the timestamp at the start of the log
        # end_stamp:   the timestamp at the end of the log
        # end_offset:  this is where the end of the log is
        #
        self.start_stamp = None
        self.end_stamp = None
        self.end_offset = None

        logger.put(3, 'Running sanity checks on the logfile')
        self.__accesscheck()
        logger.put(3, 'All checks passed')
        logger.put(5, 'Initializing the file')
        self.__initfile()
        logger.put(5, 'Exiting LogFile.__init__')

    def __initfile(self):
        logger = self.logger
        logger.put(5, 'Entering LogFile.__initfile')
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
                chunk = gzfh.read(1024)
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
        logger.put(5, 'Finding the end offset')
        self.fh.seek(0, 2)
        self.__set_at_line_start()
        self.end_offset = self.fh.tell()
        logger.put(5, 'Exiting LogFile.__initfile')

    def set_init_offset(self):
        logger = self.logger
        logger.put(5, 'Entering LogFile.set_init_offset')
        logger.put(2, 'Setting to last 12 hours since last entry')
        endstamp = self.get_log_end_stamp()
        if endstamp is None:
            logger.put(3, 'Could not find endstamp in the logfile.')
            logger.put(3, 'Is it in the rotated file?')
            if self.rotated is not None:
                logger.put(3, 'Looking into the rotated file')
                self.rotated.initfile()
                endstamp = self.rotated.get_log_end_stamp()
        if endstamp is None:
            logger.put(2, 'No useful entries for this log.')
            self.start_offset = 0
            self.end_offset = 0
        else:
            logger.put(5, 'Calculating the stamp of 12 hours ago')
            dayago = int('%d' % endstamp) - 43200
            logger.put(3, 'dayago=%d' % dayago)
            try:
                offset = self.find_offset_by_timestamp(dayago)
                logger.put(2, 'Offset found and set to pos "%d"' % offset)
            except epylog.OutOfRangeError:
                offset = 0
                logger.put(2, 'Offset NOT found, setting to the start of file')
                self.start_offset = offset
                self.end_offset = self.log_end_offset
        logger.put(3, 'start_offset=%d' % self.start_offset)
        logger.put(3, 'end_offset=%d' % self.end_offset)
        logger.put(5, 'Exiting LogFile.set_init_offset')

    def get_start_offset(self):
        self.logger.put(5, 'Enter/Exit LogFile.get_start_offset')
        self.initfile()
        return self.start_offset

    def get_end_offset(self):
        self.logger.put(5, 'Enter/Exit LogFile.get_end_offset')
        self.initfile()
        return self.end_offset

    def get_offset_start_stamp(self):
        self.logger.put(5, 'Enter/Exit LogFile.get_offset_start_stamp')
        self.initfile()
        if self.start_offset is None:
            return self.get_log_start_stamp()
        else:
            return self.get_stamp_at_offset(self.start_offset)
        
    def get_offset_end_stamp(self):
        self.logger.put(5, 'Enter/Exit LogFile.get_offset_end_stamp')
        self.initfile()
        if self.end_offset is None:
            return self.get_log_end_stamp()
        else:
            return self.get_stamp_at_offset(self.end_offset)

    def getinode(self):
        self.logger.put(5, 'Entering LogFile.getinode')
        inode = os.stat(self.filename).st_ino
        self.logger.put(5, 'inode=%d' % inode)
        self.logger.put(5, 'Exiting LogFile.getinode')
        return inode
        
    def find_offset_by_timestamp(self, searchstamp):
        logger = self.logger
        logger.put(5, 'Entering LogFile.find_offset_by_timestamp')
        self.initfile()
        if (self.get_log_start_stamp() is None
            or self.get_log_end_stamp() is None):
            logger.put(2, 'Does not seem like anything useful is in this file')
            raise epylog.OutOfRangeError('Nothing useful in this log', logger)
        logger.put(2, 'Checking if searchstamp is before the start of log')
        startstamp = self.get_log_start_stamp()
        logger.put(5, 'startstamp=%d' % startstamp)
        logger.put(5, 'searchstamp=%d' % searchstamp)
        if searchstamp < startstamp:
            logger.put(2, 'Yes, looking into the rotated log')
            if self.rotated is None:
                logger.put(2, 'No rotated log for "%s"' % self.filename)
                raise epylog.OutOfRangeError(('Requested timestamp is before '
                                              + 'the start of the log "%s"')
                                             % self.filename, logger)
            try:
                self.rotated.initfile()
                offset = self.rotated.find_offset_by_timestamp(searchstamp)
                logger.put(2, 'Found timestamp in the rotated log at pos "%d"'
                           % offset)
                logger.put(2, 'Flipping it about so we know it is rotated')
                offset = -offset
                return offset
            except epylog.OutOfRangeError:
                logger.put(2, 'Not found in the rotated log either')
                raise epylog.OutOfRangeError(('Requested timestamp is before '
                                              + 'the start of the log "%s"')
                                             % self.filename, logger)
        logger.put(2, 'Searchstamp is not before the start of log')
        logger.put(2, 'Checking if searchstamp is after the end of log')
        endstamp = self.get_log_end_stamp()
        logger.put(5, 'endstamp=%d' % endstamp)
        logger.put(5, 'searchstamp=%d' % searchstamp)
        if searchstamp > endstamp:
            logger.put(2, 'Searchstamp is PAST the end of log stamp')
            raise epylog.OutOfRangeError(('Requested timestamp is past the ' +
                                          'end of the log "%s"')
                                         % self.filename, logger)
        logger.put(2, 'Searchstamp is not past the end of log')
        logger.put(2, 'Starting the binary location routines')
        increment = int(self.log_end_offset/2)
        relative = increment
        logger.put(5, 'rewinding the logfile')
        self.fh.seek(0)
        logger.put(5, 'initial increment=%d' % increment)
        logger.put(5, 'initial relative=%d' % relative)
        line = None
        while 1:
            self.__rel_position(relative)
            increment = increment/2
            logger.put(5, 'increment=%d' % increment)
            oldline = line
            logger.put(5, 'oldline=%s' % oldline)
            offset = self.fh.tell()
            line = self.fh.readline()
            self.fh.seek(offset)
            logger.put(5, 'line=%s' % line)
            if line == oldline:
                logger.put(5, 'line and oldline equal, exiting loop')
                break
            timestamp = self.__mkstamp_from_syslog_datestr(line)
            logger.put(5, 'timestamp=%d' % timestamp)
            logger.put(5, 'searchstamp=%d' % searchstamp)
            if timestamp < searchstamp:
                logger.put(5, 'timestamp match results: Not yet')
                relative = increment
                logger.put(5, 'Jumping forward by %d' % relative)
            elif timestamp > searchstamp:
                logger.put(5, 'timestamp match results: Too far')
                relative = -increment
                logger.put(5, 'Jumping backward by %d' % relative)
            elif timestamp == searchstamp:
                logger.put(5, 'Match! Looking for precise matches')
                self.fh.seek(offset)
                myline = line
                myoffset = offset
                while timestamp == searchstamp:
                    line = myline
                    offset = myoffset
                    self.__rel_position(-2)
                    myoffset = self.fh.tell()
                    myline = self.fh.readline()
                    self.fh.seek(myoffset)
                    timestamp = self.__mkstamp_from_syslog_datestr(myline)
                break
        logger.put(5, 'Line matching searchstamp is: %s' % line)
        logger.put(2, 'Offset found at %d' % offset)
        logger.put(2, 'Done with the binary location routines')
        logger.put(5, 'Exiting LogFile.find_offset_by_timestamp')
        return offset

    def dump_strings(self, fh):
        logger = self.logger
        logger.put(5, 'Entering LogFile.dump_strings')
        logger.put(2, 'Invoking the dump_strings routine of logobj "%s"'
                   % self.filename)
        logger.put(5, 'start_offset=%d' % self.start_offset)
        logger.put(5, 'end_offset=%d' % self.end_offset)
        logger.put(3, 'Doing the rotated logfile workarounds')
        if self.start_offset < 0 and self.end_offset <= 0:
            logger.put(2, 'Both offsets are negative')
            logger.put(2, 'Getting the strings from the rotated file')
            starto = -self.start_offset
            if self.end_offset == 0:
                logger.put(3, 'What a dumb situation, end_offset=0!')
                endo = self.rotated.log_end_offset
            else:
                endo = -self.end_offset
            chunk = self.rotated.get_strings_by_offsets(starto, endo)
            fh.write(chunk)
        elif self.start_offset < 0 and self.end_offset > 0:
            logger.put(2, 'start_offset is negative, end_offset is positive')
            logger.put(2, 'Getting strings from both rotated and common files')
            starto = -self.start_offset
            endo = self.rotated.log_end_offset
            chunk = self.rotated.get_strings_by_offsets(starto, endo)
            fh.write(chunk)
            starto = 0
            endo = self.end_offset
            chunk = self.get_strings_by_offsets(starto, endo)
            fh.write(chunk)
        else:
            logger.put(2, 'Offsets are in this file. Getting strings')
            starto = self.start_offset
            endo = self.end_offset
            chunk = self.get_strings_by_offsets(starto, endo)
            fh.write(chunk)
        logsize = fh.tell()
        logger.put(5, 'logsize=%d' % logsize)
        logger.put(5, 'Exiting LogFile.dump_strings')
        return logsize

    def get_stamp_at_offset(self, offset):
        self.logger.put(5, 'Entering LogFile.get_stamp_at_offset')
        self.logger.put(5, 'offset=%d' % offset)
        stamp = None
        if offset >= 0:
            self.initfile()
            self.fh.seek(offset)
            self.__set_at_line_start()
            curline = self.fh.readline()
            try:
                stamp = self.__mkstamp_from_syslog_datestr(curline)
            except epylog.FormatError, e:
                self.logger.put(5, 'Could not figure out the date format')
        else:
            offset = -offset
            stamp = self.rotated.get_stamp_at_offset(offset)
        self.logger.put(5, 'Exiting LogFile.get_stamp_at_offset')
        return stamp

    def get_strings_by_offsets(self, start_offset, end_offset):
        logger = self.logger
        logger.put(5, 'Entering LogFile.get_strings_by_offsets')
        logger.put(4, 'Getting strings from log file "%s"' % self.filename)
        logger.put(5, 'start_offset=%d' % start_offset)
        logger.put(5, 'end_offset=%d' % end_offset)
        self.fh.seek(start_offset)
        readlen = end_offset - start_offset
        if readlen < 0:
            raise epylog.OutOfRangeError('End_offset greater than start_offset!'
                                        ,logger)
        logger.put(2, 'Reading %d bytes from "%s" starting at offset %d'
                   % (readlen, self.filename, start_offset))
        chunk = self.fh.read(readlen)
        logger.put(5, 'Exiting LogFile.get_strings_by_offsets')
        return chunk
    
    def get_log_start_stamp(self):
        self.logger.put(5, 'Entering LogFile.get_log_start_stamp')
        self.initfile()
        if self.log_start_stamp is None:
            self.fh.seek(0)
            try:
                startline = self.fh.readline()
                startstamp = self.__mkstamp_from_syslog_datestr(startline)
                self.log_start_stamp = startstamp
                self.logger.put(5, 'log_start_stamp=%d' % startstamp)
            except epylog.FormatError, e:
                self.logger.put(5, 'Could not figure out the date format')
                self.logger.put(5, 'Setting log_start_stamp to None')
                self.log_start_stamp = None
        return self.log_start_stamp

    def get_log_end_stamp(self):
        logger = self.logger
        logger.put(5, 'Entering LogFile.get_log_end_stamp')
        self.initfile()
        if self.log_end_stamp is None:
            self.fh.seek(self.log_end_offset)
            self.__rel_position(-2)
            try:
                endline = self.fh.readline()
                endstamp = self.__mkstamp_from_syslog_datestr(endline)
                self.log_end_stamp = endstamp
                logger.put(5, 'log_end_stamp=%d' % self.log_end_stamp)
            except epylog.FormatError, e:
                logger.put(3, 'Hmm... Could not figure out the stamp.')
                logger.put(3, 'Setting to None')
                self.log_end_stamp = None
        logger.put(5, 'Exiting LogFile.get_log_end_stamp')
        return self.log_end_stamp

    def __rel_position(self, relative):
        logger = self.logger
        logger.put(5, 'Enter LogFile.__rel_position')
        offset = self.fh.tell()
        new_offset = offset + relative
        logger.put(5, 'offset=%d' % offset)
        logger.put(5, 'relative=%d' % relative)
        logger.put(5, 'new_offset=%d' % new_offset)
        if new_offset < 0:
            logger.put(5, 'new_offset less than 0. Setting to 0')
            new_offset = 0
        self.fh.seek(new_offset)
        self.__set_at_line_start()
        logger.put(5, 'offset after __set_at_line_start: %d' % self.fh.tell())
        logger.put(5, 'Exiting LogFile.__rel_position')
    
    def __mkmonthmap(self):
        logger = self.logger
        logger.put(5, 'Entering LogFile.__mkmonthmap')
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
        logger.put(2, 'Sticking monthmap into the object')
        self.monthmap = monthmap
        logger.put(5, 'Exiting LogFile.__mkmonthmap')

    def __mkstamp_from_syslog_datestr(self, datestr):
        logger = self.logger
        logger.put(5, 'Entering LogFile.__mk_stamp_from_syslog_datestr')
        logger.put(5, 'datestr=%s' % datestr)
        if self.monthmap is None:
            logger.put(2, 'Making the month map')
            self.__mkmonthmap()
        logger.put(2, 'Trying to figure out the date from the string passed')
        try:
            (m, d, t) = datestr.split()[:3]
            y = str(self.monthmap[m])
            logger.put(5, 'y=%s' % y)
            datestr = string.join([y, m, d, t], ' ')
            logger.put(5, 'datestr=%s' % datestr)
            timestamp = time.mktime(time.strptime(datestr,
                                                  '%Y %b %d %H:%M:%S'))
        except:
            raise epylog.FormatError('Cannot grok the date format in "%s"'
                                    % datestr, logger)
        logger.put(2, 'Timestamp is "%d"' % timestamp)
        logger.put(5, 'Exiting LogFile.__mkstamp_from_syslog_datestr')
        return timestamp
        
    def __accesscheck(self):
        logger = self.logger
        logger.put(5, 'Entering LogFile.__accesscheck')
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
        logger.put(5, 'Exiting LogFile.__accesscheck')

    def __set_at_line_start(self):
        logger = self.logger
        logger.put(5, 'Entering LogFile.__set_at_line_start')
        if self.fh.tell() == 0:
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
        logger.put(5, 'Line start found at offset "%d"' % self.fh.tell())
        logger.put(5, 'Exiting LogFile.__set_at_line_start')
        
