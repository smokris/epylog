import epylog
import re
import os

def make_html_page(template, starttime, endtime, title, module_reports,
                   unparsed_strings, logger):
    logger.put(4, 'Making a standard report page')
    logger.put(4, 'Regexing @@STARTTIME@@ into "%s"' % starttime)
    endpage = re.sub(re.compile('@@STARTTIME@@', re.M), starttime, template)
    logger.put(4, 'Regexing @@ENDTIME@@ into "%s"' % endtime)
    endpage = re.sub(re.compile('@@ENDTIME@@', re.M), endtime, endpage)
    logger.put(4, 'Regexing @@TITLE@@ into "%s"' % title)
    endpage = re.sub(re.compile('@@TITLE@@', re.M), title, endpage)
    import socket
    hostname = socket.gethostname()
    logger.put(4, 'Regexing @@HOSTNAME@@ into "%s"' % hostname)
    endpage = re.sub(re.compile('@@HOSTNAME@@', re.M), hostname, endpage)

    logger.put(4, 'Concatenating the module reports together')
    iter = module_reports.iteritems()
    allrep = ''
    while 1:
        try:
            (module_name, report) = iter.next()
            logger.puthang(4, 'Processing report for "%s"' % module_name)
            allrep = '%s\n<h2>%s</h2>\n%s' % (allrep, module_name, report)
            logger.endhang(4)
        except StopIteration:
            logger.put(4, 'Iteration finished')
            break
    if allrep == '':
        allrep = 'No module reports'
    logger.put(5, allrep)
    logger.put(4, 'Regexing @@MODULE_REPORTS@@ into the report itself')
    endpage = re.sub(re.compile('@@MODULE_REPORTS@@', re.M), allrep, endpage)
    if unparsed_strings is not None:
        logger.put(4, 'Wrapping unparsed strings into <pre>')
        unparsed_strings = '<pre>\n%s</pre>' % unparsed_strings
    else:
        unparsed_strings = 'No unparsed strings'
    logger.put(4, 'Regexing @@UNPARSED_STRINGS into the strings themselves')
    endpage = re.sub(re.compile('@@UNPARSED_STRINGS@@', re.M),
                     unparsed_strings, endpage)
    logger.put(4, 'Regexing @@VERSION@@ into version')
    endpage = re.sub(re.compile('@@VERSION@@', re.M), epylog.VERSION, endpage)
    logger.put(5, endpage)
    return endpage
    
class MailPublisher:
    name = 'Mail Publisher'
    
    def __init__(self, sec, config, logger):
        logger.put(2, 'Initializing the MailPublisher object')
        logger.put(3, 'Sticking logger into the object')
        self.logger = logger
        self.tmpprefix = config.tmpprefix
        self.section = sec
        logger.put(2, 'Looking for required elements in mail method config')
        try:
            self.mailto = config.get(self.section, 'mailto')
        except:
            self.mailto = 'root'
        logger.put(3, 'mailto=%s' % self.mailto)
        try:
            format = config.get(self.section, 'format')
        except:
            format = 'both'

        if (format != 'plain') and (format != 'html') and (format != 'both'):
            raise epylog.ConfigError(('Format for Mail Publisher must be either'
                                    + ' html, plain, or both. Format "%s" is'
                                    + ' unknown') % format, logger)
        self.format = format
        logger.put(3, 'format=%s' % self.format)

        if format != 'html':
            logger.put(2, 'Plaintext version requested. Checking for lynx')
            try:
                lynx = config.get(self.section, 'lynx')
            except:
                lynx = '/usr/bin/lynx'
            if not os.access(lynx, os.X_OK):
                raise epylog.ConfigError('Could not find "%s"' % lynx, logger)
            self.lynx = lynx
            logger.put(2, 'Lynx found in "%s" and is executable' % self.lynx)

        try:
            include_rawlogs = config.getboolean(self.section,
                                                'include_rawlogs')
        except:
            include_rawlogs = 1

        if include_rawlogs:
            try:
                rawlogs = int(config.get(self.section, 'rawlogs_limit'))
            except:
                rawlogs = 200
            self.rawlogs = rawlogs * 1024
        else:
            self.rawlogs = 0
        logger.put(3, 'rawlogs=%d' % self.rawlogs)
        
        try:
            self.smtpserv = config.get(self.section, 'smtpserv')
        except:
            self.smtpserv = 'localhost'
        logger.put(3, 'smtpserv=%s' % self.smtpserv)
        
        logger.put(2, 'Done with MailPublisher object initialization')
        
    def publish(self, template, starttime, endtime, title, module_reports,
                unparsed_strings, raw_strings):
        logger = self.logger
        logger.puthang(3, 'Creating a standard html page report')
        html_report = make_html_page(template, starttime, endtime, title,
                                     module_reports, unparsed_strings, logger)
        self.htmlrep = html_report
        logger.endhang(3)

        self.plainrep = None
        if self.format != 'html':
            import mytempfile as tempfile
            tempfile.tempdir = self.tmpprefix
            logger.puthang(3, 'Creating a plaintext format of the report')
            htmlfile = tempfile.mktemp('HTML')
            tfh = open(htmlfile, 'w')
            tfh.write(html_report)
            tfh.close()
            logger.put(4, 'HTML report is in "%s"' % htmlfile)
            plainfile = tempfile.mktemp('PLAIN')
            logger.put(4, 'PLAIN report will go into "%s"' % plainfile)
            logger.put(4, 'Making a syscall to "%s"' % self.lynx)
            exitcode = os.system('%s -dump %s > %s 2>/dev/null'
                                 % (self.lynx, htmlfile, plainfile))
            if exitcode or not os.access(plainfile, os.R_OK):
                raise epylog.SysCallError('Error making a call to "%s"'
                                         % self.lynx, logger)
            logger.puthang(4, 'Reading in the plain version')
            tfh = open(plainfile)
            self.plainrep = tfh.read()
            tfh.close()
            logger.put(5, self.plainrep)
            logger.endhang(4)
            logger.endhang(3)

        self.gzlogs = None
        if self.rawlogs and raw_strings is not None:
            logger.puthang(3, 'Gzipping the strings')
            ##
            # GzipFile doesn't work with StringIO. :/ Bleh.
            #
            import mytempfile as tempfile, gzip
            tempfile.tempdir = self.tmpprefix
            fh = open(tempfile.mktemp('GZIP'), 'w+')
            gzfh = gzip.GzipFile('rawlogs', fileobj=fh)
            gzfh.write(raw_strings)
            gzfh.close()
            fh.seek(0)
            gz_logs = fh.read()
            fh.close()
            size = len(gz_logs)
            logger.endhang(3, 'Strings gzipped down to %d bytes' % size)
            self.gzlogs = gz_logs

        if self.gzlogs is None:
            self.rawlogs = 0
        if self.rawlogs and size > self.rawlogs:
            logger.put(2, 'Gzipped Raw Logs over the defined max of "%d"'
                       % self.rawlogs)
            self.rawlogs = 0
        ##
        # Using MimeWriter, since package 'email' doesn't come with rhl-7.3
        # Suck-o.
        #
        logger.puthang(3, 'Creating an email message')
        import StringIO, MimeWriter
        fh = StringIO.StringIO()
        logger.put(4, 'Creating a main header')
        mw = MimeWriter.MimeWriter(fh)
        mw.addheader('Subject', title)
        mw.addheader('To', self.mailto)
        mw.addheader('X-Mailer', epylog.VERSION)
        self.mw = mw
        
        if self.rawlogs > 0 and self.format == 'both':
            logger.put(4, 'Making a html + plain + gzip message')
            self.__mk_both_rawlogs()
        elif self.rawlogs > 0 and self.format == 'html':
            logger.put(4, 'Making a html + gzip message')
            self.__mk_html_rawlogs()
        elif self.rawlogs > 0 and self.format == 'plain':
            logger.put(4, 'Making a plain + gzip message')
            self.__mk_plain_rawlogs()
        elif self.rawlogs == 0 and self.format == 'both':
            logger.put(4, 'Making a html + plain message')
            self.__mk_both_nologs()
        elif self.rawlogs == 0 and self.format == 'html':
            logger.put(4, 'Making a html message')
            self.__mk_html_nologs()
        elif self.rawlogs == 0 and self.format == 'plain':
            logger.put(4, 'Making a plain message')
            self.__mk_plain_nologs()
        logger.endhang(3)

        fh.seek(0)
        msg = fh.read()
        fh.close()

        logger.puthang(3, 'Mailing it via the SMTP server %s' % self.smtpserv)
        import smtplib, socket
        fromaddr = 'root@%s' % socket.gethostname() 
        server = smtplib.SMTP(self.smtpserv)
        server.sendmail(fromaddr, self.mailto, msg)
        server.quit()
        logger.endhang(3)

    def __mk_both_rawlogs(self):
        import quopri, base64
        logger = self.logger
        mixed_mw = self.mw
        mixed_mw.addheader('Mime-Version', '1.0')
        logger.put(4, 'Creating a multipart/mixed part')
        mixed_mw.startmultipartbody('mixed')

        logger.put(4, 'Creating a multipart/alternative part')
        alt_mw = mixed_mw.nextpart()
        alt_mw.startmultipartbody('alternative')

        logger.put(4, 'Creating a text/plain part')
        plain_mw = alt_mw.nextpart()
        plain_mw.addheader('Content-Transfer-Encoding', 'quoted-printable')
        plain_fh = plain_mw.startbody('text/plain; charset=iso-8859-1')
        plain_fh.write(quopri.a2b_qp(self.plainrep))

        logger.put(4, 'Creating a text/html part')
        html_mw = alt_mw.nextpart()
        html_mw.addheader('Content-Transfer-Encoding', 'quoted-printable')
        html_fh = html_mw.startbody('text/html; charset=iso-8859-1')
        html_fh.write(quopri.a2b_qp(self.htmlrep))

        alt_mw.lastpart()
        logger.put(4, 'Creating an application/gzip part')
        gzip_mw = mixed_mw.nextpart()
        gzip_mw.addheader('Content-Transfer-Encoding', 'base64')
        gzip_mw.addheader('Content-Disposition',
                          'attachment; filename=rawlogs.gz')
        gzip_fh = gzip_mw.startbody('application/gzip; NAME=rawlogs.gz')
        gzip_fh.write(base64.encodestring(self.gzlogs))
        mixed_mw.lastpart()

    def __mk_html_rawlogs(self):
        import quopri, base64
        logger = self.logger
        mixed_mw = self.mw
        mixed_mw.addheader('Mime-Version', '1.0')
        logger.put(4, 'Creating a multipart/mixed part')
        mixed_mw.startmultipartbody('mixed')

        logger.put(4, 'Creating a text/html part')
        html_mw = mixed_mw.nextpart()
        html_mw.addheader('Content-Transfer-Encoding', 'quoted-printable')
        html_fh = html_mw.startbody('text/html; charset=iso-8859-1')
        html_fh.write(quopri.a2b_qp(self.htmlrep))

        logger.put(4, 'Creating an application/gzip part')
        gzip_mw = mixed_mw.nextpart()
        gzip_mw.addheader('Content-Transfer-Encoding', 'base64')
        gzip_mw.addheader('Content-Disposition',
                          'attachment; filename=rawlogs.gz')
        gzip_fh = gzip_mw.startbody('application/gzip; NAME=rawlogs.gz')
        gzip_fh.write(base64.encodestring(self.gzlogs))
        mixed_mw.lastpart()

    def __mk_plain_rawlogs(self):
        import quopri, base64
        logger = self.logger
        mixed_mw = self.mw
        mixed_mw.addheader('Mime-Version', '1.0')
        logger.put(4, 'Creating a multipart/mixed part')
        mixed_mw.startmultipartbody('mixed')

        logger.put(4, 'Creating a text/plain part')
        plain_mw = mixed_mw.nextpart()
        plain_mw.addheader('Content-Transfer-Encoding', 'quoted-printable')
        plain_fh = plain_mw.startbody('text/plain; charset=iso-8859-1')
        plain_fh.write(quopri.a2b_qp(self.plainrep))

        logger.put(4, 'Creating an application/gzip part')
        gzip_mw = mixed_mw.nextpart()
        gzip_mw.addheader('Content-Transfer-Encoding', 'base64')
        gzip_mw.addheader('Content-Disposition',
                          'attachment; filename=rawlogs.gz')
        gzip_fh = gzip_mw.startbody('application/gzip; NAME=rawlogs.gz')
        gzip_fh.write(base64.encodestring(self.gzlogs))
        mixed_mw.lastpart()

    def __mk_both_nologs(self):
        import quopri
        logger = self.logger
        alt_mw = self.mw
        alt_mw.addheader('Mime-Version', '1.0')
        logger.put(4, 'Creating a multipart/alternative part')
        alt_mw.startmultipartbody('alternative')

        logger.put(4, 'Creating a text/plain part')
        plain_mw = alt_mw.nextpart()
        plain_mw.addheader('Content-Transfer-Encoding', 'quoted-printable')
        plain_fh = plain_mw.startbody('text/plain; charset=iso-8859-1')
        plain_fh.write(quopri.a2b_qp(self.plainrep))

        logger.put(4, 'Creating a text/html part')
        html_mw = alt_mw.nextpart()
        html_mw.addheader('Content-Transfer-Encoding', 'quoted-printable')
        html_fh = html_mw.startbody('text/html; charset=iso-8859-1')
        html_fh.write(quopri.a2b_qp(self.htmlrep))

        alt_mw.lastpart()

    def __mk_html_nologs(self):
        import quopri
        logger = self.logger
        html_mw = self.mw
        logger.put(4, 'Creating a text/html part')
        html_mw.addheader('Content-Transfer-Encoding', 'quoted-printable')
        html_fh = html_mw.startbody('text/html; charset=iso-8859-1')
        html_fh.write(quopri.a2b_qp(self.htmlrep))

    def __mk_plain_nologs(self):
        import quopri
        logger = self.logger
        plain_mw = self.mw
        logger.put(4, 'Creating a text/plain part')
        plain_mw.addheader('Content-Transfer-Encoding', 'quoted-printable')
        plain_fh = plain_mw.startbody('text/plain; charset=iso-8859-1')
        plain_fh.write(quopri.a2b_qp(self.plainrep))


class FilePublisher:
    name = 'File Publisher'
    def __init__(self, sec, config, logger):
        logger.put(2, 'Initializing the FilePublisher object')
        logger.put(3, 'Sticking logger into the object')
        self.logger = logger
        self.tmpprefix = config.tmpprefix
        self.section = sec
        logger.put(2, 'Looking for required elements in file method config')
        try:
            self.pathmask = config.get(self.section, 'pathmask')
            self.expirytime = int(config.get(self.section, 'expirytime'))
        except:
            raise epylog.ConfigError(('Required attributes "pathmask" and/or ' +
                                     '"expirytime" not found'), logger)
        logger.put(2, 'pathmask=%s' % self.pathmask)
        logger.put(2, 'expirytime=%d' % self.expirytime)
        logger.put(2, 'Done with FilePublisher object intialization')

    def publish(self, *args):
        pass
