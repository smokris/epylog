#!/bin/bash
# weedeater.mod.sh
# -----------------
#
# Weeds out annoying useless entries, taking them from $CONFDIR/weed.list. The
# format of weed.list is very straightforward -- put one regexp match rule 
# per line. Blank lines and lines starting with "#" will be ignored.
#
# If you add your own entries, it is best to add them to 
# $CONFDIR/weed.list.local -- the module will check for the presence of 
# the file and append the rules in it to the overall rules.
#
# If there are some rules in the global weed list that you wish not to have
# removed, just copy these rules verbatim into the $CONFDIR/weed.list.except
# file -- it will be fgrep'd out of the final ruleset.
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
# @author  Konstantin Riabitsev <icon@phy.duke.edu> ($Author$)
# @version $Date$
#

egrep -v "^#" $CONFDIR/weed.list | egrep -v "^$" > $TMPPREFIX.weed.list
##
# Remove unwanted entries from weed.list
#
if [ -r "$CONFDIR/weed.list.except" ]; then
    fgrep -v -f $CONFDIR/weed.list.except $TMPPREFIX.weed.list \
	> $TMPPREFIX.weed.list.tmp
    mv -f $TMPPREFIX.weed.list.tmp $TMPPREFIX.weed.list
fi
##
# Add local rules
#
if [ -r "$CONFDIR/weed.list.local" ]; then
    egrep -v "^#" $CONFDIR/weed.list.local | egrep -v "^$" \
	>> $TMPPREFIX.weed.list
fi
##
# Whee...
#
grep -f $TMPPREFIX.weed.list $LOGCAT > $LOGFILTER
