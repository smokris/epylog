#!/usr/bin/perl -w
# epylog.pm
# ----------------
#
# Copyright (C) 2002 by Duke University
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
#          Michael Stenner <mstenner@phy.duke.edu>
# @version $Date$
#
package epylog;

##
# Strict enforces good coding practices by making you observe the
# variable scope.
#
use strict;
use Socket;

##
# Create the object and bless it.
#
# @return    the reference to the epylog object.
#
sub new {
    my $this = {};
    $this->{known_uids}  = undef;
    $this->{known_hosts} = undef;
    $this->{logfilter}   = undef;
    $this->{filtsize}    = undef;
    $this->{report}      = undef;
    $this->{logcat}      = undef;
    $this->{modname}     = undef;
    $this->{headerline}  = undef;
    $this->{loglevel}    = undef;
    $this->{logeof}      = undef;

    bless $this;
    return $this;
}

##
# Initialize our brand-new epylog object.
#
# @param  $1  The name of the module using this object. Used to generate
#              log entries.
# @return     void
#
sub init {
    my $this             = shift;
    my $modname          = shift;
    my $headerline       = "#\n# %s\n#";
    $this->{known_uids}  = {};
    $this->{known_hosts} = {};
    $this->{report}      = [];
    $this->{filtsize}    = 0;

    ##
    # Open the logfile, or STDIN if LOGCAT is undefined.
    #
    my $logcat = $this->option('LOGCAT', undef);
    if (defined($logcat)) {
        open(LOGCAT, $logcat) or die "cannot open input file $logcat";
    } else {
        *LOGCAT = *STDIN;
    }
    $this->{logcat}      = *LOGCAT;
    if (!eof(LOGCAT)){
        $this->{logeof} = 0;
    } else {
        $this->{logeof} = 1;
    }

    ##
    # Open the file for processed strings, or write to STDERR if
    # LOGFILTER is not defined.
    #
    my $logfilter = $this->option('LOGFILTER', undef);
    if (defined($logfilter)){
        open(LOGFILTER, ">$logfilter") or
            $this->mlog(0, "cannot open filtered strings file $logfilter");
    } else {
        *LOGFILTER = *STDERR;
    }
    $this->{logfilter}   = *LOGFILTER;
    
    $this->{modname}     = $modname;
    $this->{headerline}  = $headerline;
    $this->{loglevel}    = 0;
    
    ##
    # By default, the loglevel is set to 1.  QUIET sets it to 0.
    # DEBUG overrides QUIET and sets it to the value of DEBUG.
    # module_DEBUG (where module is replaced by the upper-case module
    # name) overrides DEBUG and sets loglevel to the value of
    # module_DEBUG.

    my $debug = $this->option('DEBUG', undef);
    my $md = uc($this->{modname}) . '_DEBUG';
    my $module_debug = $this->option($md, undef);
    if (defined($debug) or defined($module_debug)) {
        if (defined($debug)) {
            $this->{loglevel} = $debug;
        }
        if (defined($module_debug)) {
            $this->{loglevel} = $module_debug;
        }
    } else {	
        my $quiet = $this->option('QUIET', undef);
        if (!defined($quiet)){
            $this->{loglevel} = 1;
        }
    }
}

##
# This sub takes a uid and looks up the user name.
#
# @param  $1 the uid to look up.
# @return    the username.
#
sub getuname {
    my $this = shift;
    my $uid = shift;
    if (!defined($uid)){
        return(undef);
    }
    
    if (exists($this->{known_uids}{$uid})){
        return($this->{known_uids}{$uid});
    } else {
        (my $uname) = getpwuid($uid);
        if (!defined($uname)){
            $uname = "uid=$uid";
        }
        $this->{known_uids}{$uid} = $uname;
        return $uname;
    }
}

##
# This sub tries to resolve hostnames if possible. If not, it returns
# the ip address back. The %known_hosts hash is used to cache the values
# for optimization.
#
# @param  $1 The IP of a host to lookup.
# @return    The FQDN, or the IP address if lookup failed.
#
sub gethost {
    my $this = shift;
    my $host = shift;
    if (exists($this->{known_hosts}{$host})) {
        return($this->{known_hosts}{$host});
    } else {
        ##
        # hash resolved names.  This speeds things up because we often get
        # many hits from the same host.
        #
        my @host_a = gethostbyaddr(pack('CCCC', split(/\./, $host)), AF_INET);
        my $hostname = defined($host_a[0]) ? $host_a[0] : $host;
        $this->{known_hosts}{$host} = $hostname;
        return $hostname;
    }
}

##
# Since all syslog lines start uniformly, use this sub to
# grab the name of the system from the log line.
#
# @param  $1 The log line.
# @return    The name of the system this log line refers to.
#
sub getsystem {
    my $this = shift;
    my $line = shift;
    (my $system) = $line =~ m/.{15}\s(\S*)\s.*/;
    ##
    # syslog-ng can report hosts in a more complicated way :)
    #
    if ($system =~ m{[@/](\S+)}) { $system = $1; }
    return($system);
}

##
# A wrapper to process the options passed in by environment variables.
# If the referred ENV variable is unset, then return the default value.
# This behavior is useful for debugging the module.
#
# @param  $1 The name of the ENV variable to grab.
# @param  $2 The default value to return if the ENV variable is unset.
# @return    The value of the environment variable, or the default value
#            if the variable is unset.
#
sub option {
    my $this    = shift;
    my $op      = shift;
    my $default = shift;
    return(exists($ENV{$op}) ? $ENV{$op} : $default);
}

##
# Fetch the next available line from the logfile (LOGCAT). If the end of
# file is reached, it will set $this->{logeof} to 1.
#
# @return   the next line available.
#
sub nextline {
    my $this   = shift;
    my $logcat = $this->{logcat};
    my $nextline = <$logcat>;
    chomp($nextline);
    if (eof($logcat)){
        $this->{logeof} = 1;
        close($logcat);
    }
    return $nextline;
}

##
# This is used to test if we are at the end of the logfile.
#
# @return   1 if the end of file has been reached.
#
sub islogeof {
    my $this = shift;
    return $this->{logeof};
}

##
# Add a string or an array of strings to the final module report.
#
# @param  $1  an string or array of strings.
#
sub pushrep {
    my $this    = shift;
    push(@{$this->{report}}, @_);
}

##
# Adds a syslog line or an array of syslog lines to the filtered strings
# file.
#
# @param $1  a syslog line or an array of syslog lines.
#
sub pushfilt {
    my $this    = shift;
    my $logfilter = $this->{logfilter};
    my $filtline  = join("\n", @_);
    print $logfilter "$filtline\n";
    $this->{filtsize}++;
}

##
# Produce a debugging output.
#
# @param $1  the level
# @param $2  a string or array of strings to output.
#
sub mlog {
    my $this    = shift;
    my $level   = shift;
    my $modname = $this->{modname};
    if ($this->{loglevel} >= $level){
        print STDOUT "$modname: ", @_, "\n";
    }
}

##
# How many lines are currently in the filtered strings file?
#
# @return   the number of syslog lines in LOGFILTER.
#
sub filtsize {
    my $this = shift;
    return $this->{filtsize};
}

##
# How many lines are currently in the report?
#
# @return  the number of lines in LOGREPORT.
#
sub repsize {
    my $this = shift;
    return $#{$this->{report}};
}

##
# Make a pretty-looking and uniform report header.
#
# @param  $1  a string with some descriptive title
# @return     a string with a formatted report title
#
sub mkrephdr {
    my $this = shift;
    my $msg  = shift;
    my $hdr  = sprintf($this->{headerline}, $msg);
    return $hdr;
}

##
# Closes any open filehandles and writes the report into LOGREPORT.
# This must be called at the end of your module.
#
sub finalize {
    my $this = shift;
    my $title = shift;
    ##
    # Open output file, $LOGREPORT or write to STDOUT if LOGREPORT
    # isn't defined.
    #
    my $logreport = $this->option('LOGREPORT', undef);
    if (defined($logreport)) {
        open(LOGREPORT, ">$logreport") or
            $this->mlog(0, "cannot open output file $logreport");
    } else {
        *LOGREPORT = *STDOUT;
    }
    
    if ($#{$this->{report}} >= 0){
        print LOGREPORT join("\n", @{$this->{report}}) . "\n";
    }
    if ($this->{logfilter} ne *STDERR){
        close($this->{logfilter});
    }
    if (*LOGREPORT ne *STDOUT){
        close(LOGREPORT);
    }
}

1;

__END__

=head1 NAME

epylog - Perl5 module for writing perl modules for epylog.

=head1 SYNOPSIS

 use epylog;

 # create a new epylog object
 my $du = new epylog;

 # initialize the object
 $du->init('modulename');

 # get a username from a userid
 $du->getuname(500);

 # get a hostname from an IP address
 $du->gethost('127.0.0.1');

 # find the system name in a standard syslog line
 $du->getsystem($syslogline);

 # get the value of an environment variable
 # first parameter is the name of the variable, second one is
 # the default value to return if the variable is undefined.
 $du->option('TMPDIR', '/tmp');

 # return the next available syslog line from the logs (LOGCAT)
 $du->nextline();

 # check if the logfile is EOF'd. Returns 0 if not yet.
 $du->islogeof();

 # add a string or an array of strings to the report (LOGREPORT)
 $du->pushrep('Report line');

 # add a syslog line entry to the list of analyzed and filtered 
 # lines (LOGFILTER)
 $du->pushfilt($syslog_line);

 # intelligently output some debug information.
 # first parameter is level, second parameter is the string to output.
 # level 0  -- critical errors, always output
 # level 1  -- standard epylog execution, without "--quiet"
 # level 2> -- additional levels of verbosity.
 $du->mlog(1, 'Processing data');

 # return how many lines were added to the filter file (LOGFILTER)
 $du->filtsize();

 # return how many lines were added to the report file (LOGREPORT)
 $du->repsize();

 # make a pretty report header.
 $du->mkrephdr('NOTICED REBOOTS');

 # call this at the end of your module! It closes the filehandles and
 # writes out the report.
 $du->finalize();

=head1 AUTHORS

 Konstantin Ryabitsev <icon@linux.duke.edu>
 Michael Stenner <mstenner@phy.duke.edu>

 Duke University Physics

=head1 REVISION

$Revision$

=head1 SEE ALSO

epylog(8), epylog_modules(5)

=cut
