import epylog
import os
import re
import time

from publishers import *

class Report:
    def __init__(self, config, logger):
        logger.put(5, 'Entering Report.__init__')
        logger.put(2, 'Starting Report object intialization')
        self.logger = logger
        ##
        # publishers:     a tuple of publisher objects
        # filt_fh:        where the filtered strings from modules will go
        # useful:         tells epylog if the report is of any use or not.
        # module_reports: module reports will be put here eventually
        #
        self.publishers = []
        self.filt_fh = None
        self.useful = 0
        self.module_reports = {}
        
        self.tmpprefix = config.tmpprefix
        self.runtime = time.localtime()
        sec = 'report'
        try:
            title = config.get(sec, 'title')
        except:
            title = '%HOSTNAME% system events: %LOCALTIME%'
        try:
            self.template = config.get(sec, 'template').strip()
        except:
            raise epylog.ConfigError('Report template not specified', logger)
        if not os.access(self.template, os.R_OK):
            msg = 'Report template "%s" is not readable' % self.template
            raise epylog.AccessError(msg, logger)
        try:
            self.unparsed = config.getboolean(sec, 'include_unparsed')
        except:
            self.unparsed = 1
        try:
            publishers = config.get(sec, 'publishers')
        except:
            msg = 'No publishers defined in "%s"' % sec
            raise epylog.ConfigError(msg, logger)

        logger.put(3, 'Title as defined in config is: "%s"' % title)
        hregex = re.compile('@@HOSTNAME@@')
        tregex = re.compile('@@LOCALTIME@@')
        if hregex.search(title):
            import socket
            hostname = socket.gethostname()
            logger.put(3, 'Regexing @@HOSTNAME@@ into "%s"' % hostname)
            title = re.sub(hregex, hostname, title)
        if tregex.search(title):
            timestr = time.strftime('%c', self.runtime)
            logger.put(3, 'Regexing @@LOCALTIME@@ into "%s"' % timestr)
            title = re.sub(tregex, timestr, title)
        self.title = title
        logger.put(3, 'Final title is: "%s"' % self.title)
        
        logger.put(3, 'template=%s' % self.template)
        logger.put(3, 'unparsed=%d' % self.unparsed)
        if self.unparsed:
            logger.put(3, 'Creating a temporary file for filtered strings')
            import epylog.mytempfile as tempfile
            tempfile.tmpdir = self.tmpprefix
            filen = tempfile.mktemp('FILT')
            self.filt_fh = open(filen, 'w+')
            logger.put(3, 'Filtered strings file created in "%s"' % filen)

        logger.put(3, 'Publishers: "%s"' % publishers)
        logger.put(3, 'Initializing publishers')
        for sec in publishers.split(','):
            sec = sec.strip()
            logger.put(3, 'Looking for section definition "%s"' % sec)
            if sec not in config.sections():
                message = 'Required publisher section "%s" not found' % sec
                raise epylog.ConfigError(message, logger)
            logger.put(3, 'Looking for method declaration')
            try:
                method = config.get(sec, 'method')
            except:
                msg = 'Publishing method not found in "%s"' % sec
                raise epylog.ConfigError(msg, logger)
            logger.put(3, 'Found method "%s"' % method)
            if method == 'file':
                publisher = FilePublisher(sec, config, logger)
            elif method == 'mail':
                publisher = MailPublisher(sec, config, logger)
            else:
                msg = 'Publishing method "%s" not supported' % method
                raise epylog.ConfigError(msg, logger)
            self.publishers.append(publisher)            
        logger.put(3, 'Finished with Report object initialization')
        logger.put(5, 'Exiting Report.__init__')

    def append_module_report(self, module_name, module_report):
        if len(module_report) > 0:
            self.logger.put(2, 'Appending report for "%s" to the dict'
                            % module_name)
            self.logger.put(5, module_report)
            self.module_reports[module_name] = module_report
            self.useful = 1
        else:
            logger.put(2, 'Module report is empty, ignoring')

    def append_filtered_strings(self, module_name, filtered_strings):
        logger = self.logger
        if self.filt_fh is None:
            logger.put(2, 'No open filt_fh, ignoring')
            return
        if len(filtered_strings) > 0:
            logger.put(2, 'Appending filtered strings from module "%s"'
                       % module_name)
            logger.put(5, filtered_strings)
            logger.put(2, 'Writing to file "%s"' % self.filt_fh.name)
            self.filt_fh.write(filtered_strings)
            self.useful = 1
        else:
            logger.put(2, 'Filtered Strings are empty, ignoring')

    def set_stamps(self, stamps):
        logger = self.logger
        logger.put(5, '>Publisher.set_stamps')
        [self.start_stamp, self.end_stamp] = stamps
        logger.put(5, 'start_stamp=%d' % self.start_stamp)
        logger.put(5, 'end_stamp=%d' % self.end_stamp)
        logger.put(5, '<Publisher.set_stamps')
        
    def publish(self, rawstr_file, weeded_file):
        logger = self.logger
        logger.put(2, 'Invoking the publish() method of the report obj')
        raw_strings = None
        unparsed_strings = None
        if self.unparsed:
            logger.put(2, 'Checking the size of filt_fh')
            self.filt_fh.seek(0, 2)
            filt_size = self.filt_fh.tell()
            logger.put(2, 'The size of filt file is "%d"' % filt_size)
            logger.put(2, 'Closing the filt_fh handle')
            self.filt_fh.close()
            if filt_size:
                logger.puthang(3, 'Reading in the raw strings')
                fh = open(rawstr_file)
                raw_strings = fh.read()
                fh.close()
                logger.endhang(3)
                logger.put(2, 'Weeding the logs')
                logger.put(5, 'raw strings file: %s' % rawstr_file)
                logger.put(5, 'filtered strings file: %s' % self.filt_fh.name)
                logger.put(5, 'weeded results in: %s' % weeded_file)
                ##
                # Currently this uses fgrep since it's the fastest way.
                # Doing this natively in python consumes loads of memory
                # and takes forever. Suggestions are welcome.
                #
                logger.puthang(2, 'Making a system call to fgrep')
                fgrep_com = ('/bin/fgrep -v -f %s %s > %s' %
                             (self.filt_fh.name, rawstr_file, weeded_file))
                logger.put(3, 'Calling fgrep with command "%s"' % fgrep_com)
                exitcode = os.system(fgrep_com)
                ##
                # TODO: Find out wtf is exit code 256!
                #
                logger.put(5, 'exitcode=%d' % exitcode)
                if exitcode and exitcode != 256:
                    raise epylog.SysCallError(('Call to fgrep for weed failed'
                                              + ' with exit code %d')
                                             % exitcode, logger)
                logger.endhang(2)
                logger.puthang(2, 'Reading the weeded strings from "%s"'
                               % weeded_file)
                try:
                    fh = open(weeded_file)
                    strings = fh.read()
                    fh.close()
                except:
                    ##
                    # The file should exist even if there are no strings
                    # in it, simply due to the nature of > redirect.
                    #
                    raise AccessError('Could not open weeded strings file "%s"'
                                      % weeded_file, logger)
                logger.endhang(2)
                logger.put(5, 'strings=%s' % strings)
                if len(strings.strip()):
                    unparsed_strings = strings
                    logger.put(5, unparsed_strings)
                else:
                    logger.put(3, 'No unparsed strings in the weeded file')

        logger.puthang(3, 'Reading in the template file "%s"' % self.template)
        fh = open(self.template)
        template = fh.read()
        fh.close()
        logger.endhang(3)
        starttime = time.strftime('%c', time.localtime(self.start_stamp))
        endtime = time.strftime('%c', time.localtime(self.end_stamp))
        for publisher in self.publishers:
            logger.puthang(2, 'Invoking publisher "%s"' % publisher.name)
            publisher.publish(template,
                              starttime,
                              endtime,
                              self.title,
                              self.module_reports,
                              unparsed_strings,
                              raw_strings)
            logger.endhang(2)

    def is_report_useful(self):
        return self.useful
