import epylog
import os
import re
import time

from publishers import *

class Report:
    section = 'report'
    
    def __init__(self, config, logger):
        logger.put(2, 'Starting Report object intialization')
        logger.put(3, 'Storing logger in object')
        self.logger = logger
        
        logger.put(3, 'Setting some defaults')
        self.publishers = []
        self.module_reports = {}
        self.filt_fh = None
        self.start_stamp = None
        self.end_stamp = None
        self.useful = 0
        
        self.tmpprefix = config.tmpprefix
        sec = self.section
        logger.put(2, 'Section name is %s' % sec)
        self.runtime = time.localtime()
        logger.put(2, 'Timestamp is "%s"' % time.strftime('%c', self.runtime))
        try:
            title = config.get(sec, 'title')
        except:
            title = '%HOSTNAME% system events: %LOCALTIME%'
        logger.put(2, 'Title as defined in config is: "%s"' % title)
        
        import socket
        title = re.sub(re.compile('%HOSTNAME%', re.M),
                       socket.gethostname(), title)
        title = re.sub(re.compile('%LOCALTIME%', re.M),
                       time.strftime('%c', self.runtime), title)
        self.title = title
        logger.put(2, 'Title regexed into: "%s"' % self.title)

        try:
            template = config.get(sec, 'template').strip()
        except:
            raise epylog.ConfigError('Report template not specified', logger)
        if not os.access(template, os.R_OK):
            raise epylog.AccessError(('Report template "%s" does not exist or'
                                     + ' is not readable') % template, logger)
        self.template = template
        logger.put(3, 'template=%s' % self.template)
        
        try:
            self.unparsed = config.getboolean(sec, 'include_unparsed')
        except:
            self.unparsed = 1
        logger.put(3, 'unparsed=%d' % self.unparsed)

        logger.put(2, 'Looking at defined publishers')
        try:
            publishers = config.get(sec, 'publishers')
        except:
            raise epylog.ConfigError('No publishers defined in the "%s" section'
                                    % sec, logger)

        logger.put(2, 'Publishers: "%s"' % publishers)
        logger.put(2, 'Initializing publishers')
        for sec in publishers.split(','):
            sec = sec.strip()
            logger.put(2, 'Looking for section definition "%s"' % sec)
            if sec not in config.sections():
                raise epylog.ConfigError('Could not find publisher section "%s"'
                                        % sec, logger)
            logger.put(2, 'Looking for method declaration')
            try:
                method = config.get(sec, 'method')
            except:
                raise epylog.ConfigError('Publishing method not found in "%s"'
                                        % sec, logger)
            logger.put(2, 'Found method "%s"' % method)
            if method == 'file':
                publisher = FilePublisher(sec, config, logger)
            elif method == 'mail':
                publisher = MailPublisher(sec, config, logger)
            else:
                raise epylog.ConfigError('Publishing method "%s" not supported'
                                        % method, logger)
            self.publishers.append(publisher)            
        logger.put(2, 'Finished with Report object initialization')

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
                fgrep_com = ('/bin/fgrep -q -v -f %s %s > %s' %
                             (self.filt_fh.name, rawstr_file, weeded_file))
                logger.put(3, 'Calling fgrep with command "%s"' % fgrep_com)
                exitcode = os.system(fgrep_com)
                ##
                # TODO: Find out wtf is exit code 256!
                #
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
