#!/usr/bin/perl -w
# annoy.mod.pl
# -------------
#
# Copyright (C) 2001-2002 by Duke University
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
#
# To view the help for this module, run "perldoc template.mod.pl"
# To create the text version, run
#      "perldoc -t template.mod.pl > template.mod.txt"
# for help with POD (plain old documentation) see the "perlpod"
# man page.  POD is really easy, so check it out!
#
# $Id$
#
# @Author  Konstantin Riabitsev <icon@phy.duke.edu>
# @version $Date$
#
=pod

=head1 NAME

annoy.mod.pl - a epylog module.

=head1 DESCRIPTION

This module processes various annoying logfile entries and displays
them in a non-intrusive, sane manner.

=cut

##
# Strict enforces good coding practices by making you observe the
# variable scope.
# Add other packages, too.
#
use strict;
use epylog;

=pod

=head1 OUTPUT FORMAT OPTIONS

There are three formatting rules that affect the final report.

=over 5

=item $system_pattern = '%-10s -> ';

How should a system name be presented in the report.

=item $notice_pattern = '%s (%d)';

How to represent the notice itself.

=item $indent_pattern = '%14s';

Sometimes there is more than one annoyance report per system. Any
further reports for the system will be output on the next line, but we
need to make sure that it indents properly and aligns with the
$system_pattern.

=back

=cut

##
# Sprintf rules.
#
my $system_pattern = '%-10s -> ';
my $notice_pattern = '%s (%d)';
my $indent_pattern = '%14s';

##
# A couple of globals.
#
my $struct;
my $flops;

##
# Main module code.
#
my $du = new epylog();
$du->init('annoy');
$du->mlog(1, "beginning to read input");

##
# Iterate through all lines in the logs and analyze the ones that
# match. Analyzed and processed lines get pushed into LOGFILTER
# so they can be later weeded by epylog.
#
while ($du->islogeof() == 0) {
    my $line = $du->nextline();
    my $system = $du->getsystem($line);
    ##
    # Try to find dirty floppy mounts. They usually come separated
    # in three lines. This tries to catch this garbage and organize
    # it nicely using the $flops "struct" to hold the values.
    #
    if ($line =~ /kernel: attempt to access beyond end of device/){
	push(@{$flops->{$system}}, $line);
    }
    elsif ($line =~ /kernel: .*rw=.*want=.*limit=/){
	push(@{$flops->{$system}}, $line);
    }
    elsif ($line =~ /kernel: Directory sread .* failed/){
	push(@{$flops->{$system}}, $line);
	if (defined($flops->{$system}) && $#{$flops->{$system}} == 2){
	    ##
	    # Yes, looks like a dirty floppy mount.
	    #
	    my $msg = 'dirty floppy mount';
	    addtostruct($system, $msg);
	    ##
	    # Push the lines we caught into the filtered array.
	    #
	    $du->pushfilt(@{$flops->{$system}});
	}
	undef $flops->{$system};
    }
    ##
    # Look for depmod messages.
    #
    elsif ($line =~ /modules.conf is more recent/){
	my $msg = 'modules.conf mismatch';
	addtostruct($system, $msg);
	$du->pushfilt($line);
    }
    ##
    # Look for Gconfd locking issues. This usually occurs when
    # some user tries to log into several machines running Gnome-1.4
    # at the same time. Leaves a lot of NASTY strings in the logs.
    #
    elsif ($line =~ /gconfd.*: Failed to get lock.*Failed to create or open/
	   || $line =~ /gconfd.*: Error releasing lockfile/
	   || $line =~ /gconfd.*: .* Could not lock temporary file/
	   || $line =~ /gconfd.*: .* another process has the lock/){
	my $msg = 'gconfd locking errors';
	addtostruct($system, $msg);
	$du->pushfilt($line);
    }
    ##
    # Look for fatal X errors. These usually occur when someone logs out,
    # but if they repeat a lot, then it's something that should be looked
    # at.
    #
    elsif ($line =~ /Fatal X error/){
	my $msg = 'fatal X errors';
	addtostruct($system, $msg);
	$du->pushfilt($line);
    }
    ##
    # Look for sftp activity.
    #
    elsif ($line =~ /sftp-server.*:/
	   || $line =~ /subsystem request for sftp/){
	my $msg = 'sftp activity';
	addtostruct($system, $msg);
	$du->pushfilt($line);
    }
    ##
    # Look for sshd misc things.
    #
    elsif ($line =~ /sshd.*: .*terminating/){
	my $msg = 'sshd terminated';
	addtostruct($system, $msg);
	$du->pushfilt($line);
    }
    elsif ($line =~ /sshd.*: Server listening on/){
	my $msg = 'sshd started';
	addtostruct($system, $msg);
	$du->pushfilt($line);
    }
    ##
    # Look for misc floppy errors (vmware likes to leave those).
    #
    elsif ($line =~ /floppy0:/ || $line =~ /\(floppy\)/){
	my $msg = 'misc floppy errors';
	addtostruct($system, $msg);
	$du->pushfilt($line);
    }
}

##
# Process the results, if any.
#
if ($du->filtsize() > 0){
    $du->mlog(1, 'Generating a report');
    $du->pushrep($du->mkrephdr('NOTICES'));
    foreach my $system_key (sort(keys(%{$struct}))){
	my $counter = 0;
	foreach my $notice_key(keys(%{$struct->{$system_key}})){
	    $counter++;
	    my $outline;
	    if ($counter == 1){
		$outline = sprintf($system_pattern, $system_key);
	    } else {
		$outline = sprintf($indent_pattern, " ");
	    }
	    $outline .= sprintf($notice_pattern, $notice_key,
				$struct->{$system_key}{$notice_key});
	    $du->pushrep($outline);
	}
    }
}
$du->mlog(1, "Finalizing");
$du->finalize();

###################################################################
# subroutines

##
# A convenience wrapper sub which adds a hash value to the "struct"
# if it doesn't exist, or increments it by one if it does.
#
# @param  $1 The "message" used as a hash key.
# @return    void.
#
sub addtostruct {
    (my $system, my $msg) = @_;
    if (defined($struct->{$system}{$msg})){
	$struct->{$system}{$msg}++;
    } else {
	$struct->{$system}{$msg}++;
    }
}

__END__

=pod

=head1 AUTHOR

Konstantin Riabitsev, <icon@phy.duke.edu>

=head1 REVISION

$Revision$

=head1 SEE ALSO

epylog(8), epylog-modules(5), epylog(3)

=cut
