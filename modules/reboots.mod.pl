#!/usr/bin/perl -w
# reboots.mod.pl
# ----------------
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
# $Id$
#
# @Author  Michael D. Stenner <mstenner@phy.duke.edu>
#          Konstantin Riabitsev <icon@phy.duke.edu>
# @version $Date$
#
=pod

=head1 NAME

reboots.mod.pl - a epylog module.

=head1 DESCRIPTION

This module monitors the logs and reports any system reboots it notices.

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

How the system name should be formatted and padded.

=item $os_pattern = '%s %s (%d)';

How the os name should be represented, and how many times the system
rebooted, e.g. "linux 2.4.18-4 (2)".

=item $indent_pattern = '%14s';

For the rare occasion when a system reboots more than once, but with a
different kernel version, this tells how many spaces to indent such
report.

=back

=cut

##
# Define the output formats.
#
my $system_pattern = '%-10s -> ';
my $os_pattern     = '%s %s (%d)';
my $indent_pattern = '%14s';

##
# Define any global variables here.
# $struct   is a nested array used to hold the data.
my $struct;

##
# Main module code.
#
my $du = new epylog();
$du->init('reboots');
$du->mlog(1, "beginning to read input");

##
# Iterate through all lines in the logs and analyze the ones that
# match.
#
my $gotcha = 0;
while ($du->islogeof() == 0) {
    my $line = $du->nextline();
    if ($line =~ /kernel: Linux version/){
	my $system = $du->getsystem($line);
	my $os = "Unknown";
	my $version = "Unknown";
	##
	# Linux only, really.
	#
	($os) = $line =~ m/.* kernel: (\S*) version.*/;
	##
	# kernel version
	#
	($version) = $line =~ m/.* version (\S*) \(.*/;
	if (defined($struct->{$system}{$os}{$version})){
	    $struct->{$system}{$os}{$version}++;
	} else {
	    $struct->{$system}{$os}{$version}=1;
	}
	$gotcha = 1;
    }
}
$du->mlog(1, "finished reading input");

if ($gotcha == 1){
    ##
    # Prepare the report
    #
    $du->mlog(1, "Writing noticed reboots");
    $du->pushrep($du->mkrephdr('Noticed system REBOOTS'));
    foreach my $system_key (sort(keys(%{$struct}))){
	my $counter = 0;
	foreach my $os_key (sort(keys(%{$struct->{$system_key}}))){
	    foreach my $version_key (sort(keys(%{$struct->{$system_key}->
						     {$os_key}}))){
		$counter++;
		my $outline;
		if ($counter == 1){
		    $outline = sprintf($system_pattern, $system_key);
		} else {
		    $outline = sprintf($indent_pattern, " ");
		}
		$outline .= sprintf($os_pattern, $os_key, $version_key,
				   $struct->{$system_key}{$os_key}->
				   {$version_key});
		$du->pushrep($outline);
	    }
	}
    }
} else {
    $du->mlog(1, "No reboots noticed");
}
$du->mlog(1, "Finalizing");
$du->finalize();

__END__

=pod

=head1 AUTHOR

Konstantin Riabitsev, <icon@phy.duke.edu>

=head1 REVISION

$Revision$

=head1 SEE ALSO

epylog(8), epylog-modules(5), epylog(3)

=cut
