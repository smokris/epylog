# $Id$

%define _vardir   %{_localstatedir}/lib
%define _perldir  %{_libdir}/perl5/site_perl
%define __perldoc %{_bindir}/perldoc
%define __pydoc   %{_bindir}/pydoc
%define _pydir    %{_libdir}/python2.2/site-packages

Summary: New logs analyzer and parser.
Name: epylog
Version: 0.9.2
Release: 1
License: GPL
Group: Applications/System
Source: http://linux.duke.edu/projects/epylog/download/%{name}-%{version}.tar.gz
Packager: Konstantin Riabitsev <icon@phy.duke.edu>
Vendor: Duke University
BuildRoot: %{_tmppath}/%{name}-%{version}-root
BuildArch: noarch
BuildPrereq: %{__pydoc}, perl, python, file, gzip, sed
Requires: /usr/bin/python2, perl >= 5.6, elinks, grep
#Obsoletes: dulog
Provides: perl(epylog)

%description
Epylog is a new log notifier and parser which runs periodically out of
cron, looks at your logs, processes the entries in order to present
them in a more comprehensive format, and then provides you with the
output. It is written specifically with large network clusters in mind
where a lot of machines (around 50 and upwards) log to the same
loghost using syslog or syslog-ng.

%prep
%setup -q
##
# Fix version.
#
%{__perl} -pi -e \
    "s/^VERSION\s*=\s*.*/VERSION = '%{name}-%{version}-%{release}'/g" \
    py/epylog/__init__.py

%build
cat <<EOF | %{__python}2
from compileall import compile_dir
compile_dir('py')
compile_dir('modules')
EOF
cat <<EOF | %{__python}2 -OO
from compileall import compile_dir
compile_dir('py')
compile_dir('modules')
EOF
##
# Build module documentation.
#
MDOCDIR="doc/modules"
%{__mkdir_p} -m 755 $MDOCDIR
for FILE in `ls modules/*.pl`; do
    %{__perldoc} -t $FILE > $MDOCDIR/`basename $FILE .pl`.txt
done
pushd modules
for FILE in `ls *.py`; do
    %{__pydoc} ./$FILE > ../$MDOCDIR/`basename $FILE .py`.txt
done
popd
# build the perl module manpage
%{__perldoc} perl/epylog.pm > man/epylog.3

%install
%{__rm} -rf %{buildroot}
%{__mkdir_p} -m 700 %{buildroot}%{_vardir}/%{name}
##
# Install the python libraries
#
%{__mkdir_p} -m 755 %{buildroot}%{_pydir}/%{name}
%{__install} -m 644 py/epylog/*.py* %{buildroot}%{_pydir}/%{name}/
##
# Install the configs
#
%{__mkdir_p} -m 755 %{buildroot}%{_sysconfdir}/%{name}/modules.d
%{__install} -m 644 etc/modules.d/*.conf \
    %{buildroot}%{_sysconfdir}/%{name}/modules.d/
FILES="epylog.conf report_template.html trojans.list"
FILES="$FILES weed_dist.cf weed_local.cf notice_dist.xml notice_local.xml"
for FILE in $FILES; do
  %{__install} -m 644 etc/$FILE %{buildroot}%{_sysconfdir}/%{name}/$FILE
done
##
# Install the modules
#
%{__mkdir_p} -m 755 %{buildroot}%{_datadir}/%{name}/modules
%{__install} -m 755 modules/* %{buildroot}%{_datadir}/%{name}/modules/
##
# Install the executable
#
%{__mkdir_p} -m 755 %{buildroot}%{_sbindir}
%{__install} -m 755 epylog %{buildroot}%{_sbindir}/%{name}
##
# Install the cron script
#
%{__mkdir_p} -m 755 %{buildroot}%{_sysconfdir}/cron.daily
%{__install} -m 755 cron/epylog-cron.daily \
    %{buildroot}%{_sysconfdir}/cron.daily/%{name}.cron
##
# Install manpages
#
pushd man
for MAN in *.*; do 
	SEC=`echo $MAN | sed "s/.*\.//g"`
	gzip $MAN
    LOC="%{buildroot}%{_mandir}/man$SEC"
    %{__mkdir_p} -m 755 $LOC
    %{__install} -m 644 $MAN.gz $LOC
done
popd
##
# Install the perl module
#
%{__mkdir_p} -m 755 %{buildroot}%{_perldir}
%{__install} -m 644 perl/epylog.pm %{buildroot}%{_perldir}/%{name}.pm

%clean
%{__rm} -rf %{buildroot}

%files
%defattr(-,root,root)
%dir %{_vardir}/%{name}
%dir %{_datadir}/%{name}
%{_datadir}/%{name}/modules/*
%{_pydir}/%{name}
%{_sbindir}/%{name}
%{_sysconfdir}/cron.daily/%{name}.cron
%{_perldir}/%{name}.pm
%{_mandir}/man*/*
%config(noreplace) %{_sysconfdir}/%{name}
%doc doc/*

%changelog
* Tue Apr 29 2003 Konstantin Riabitsev <icon@phy.duke.edu> 0.9.2-1
- Notices module reworked to support custom notifications.
- Weeder module now supports 'ALL' for enable
- Some changes to epylog core to return matched regex as part of linemap.

* Fri Apr 25 2003 Konstantin Riabitsev <icon@phy.duke.edu> 0.9.1-1
- Some bugfixes after running pychecker
- Added doc/INSTALL for people not running RPM.

* Thu Apr 18 2003 Konstantin Riabitsev <icon@phy.duke.edu> 0.9.0-1
- A significant rewrite of module handlers.

* Wed Mar 13 2003 Konstantin Riabitsev <icon@phy.duke.edu> 0.8.14-1
- Fixes for html email sending
- Option to send via sendmail vs. smtplib
- Multiple mailto addresses now handled correctly
- Small bugfixes.

* Mon Mar 03 2003 Konstantin Riabitsev <icon@phy.duke.edu> 0.8.13-1
- Two new features for module configs: you can now specify the priority
  and extra options for modules.

* Fri Feb 28 2003 Konstantin Riabitsev <icon@phy.duke.edu> 0.8.12-1
- Two small bugfixes which prevented some modules from ever being 
  executed when the last log was 0 length.

* Thu Feb 27 2003 Konstantin Riabitsev <icon@phy.duke.edu> 0.8.11-1
- Small changes to logrotation modules, allowing them to specify
  a full path to a rotated file.

* Wed Feb 26 2003 Konstantin Riabitsev <icon@phy.duke.edu> 0.8.10-1
- Ported some modules from DULog.

* Mon Feb 10 2003 Konstantin Riabitsev <icon@phy.duke.edu> 0.8.9-1
- Several fixes in fine_locate routines causing it not to break
  on logs with non-consecutive entries and live logs.

* Fri Feb 07 2003 Konstantin Riabitsev <icon@phy.duke.edu> 0.8.7-1
- More fixes for the memory-friendly grep.

* Tue Jan 28 2003 Konstantin Riabitsev <icon@phy.duke.edu> 0.8.6-1
- Lots and lots of memory optimizations (chunked reads throughout)
- Entities replaced in get_html_report
- memory-friendly fgrep calls

* Mon Jan 27 2003 Konstantin Riabitsev <icon@phy.duke.edu> 0.8.5-1
- Big rewrite of logfile handling routines. This works much-much-much
  better!
- A useful usage().
- Lots of bugfixes.

* Sat Jan 18 2003 Konstantin Riabitsev <icon@phy.duke.edu> 0.8-1
- First attempt at building a semi-usable epylog. It even works.
  Sometimes. :)
- Removed DULog-related changelogs.
