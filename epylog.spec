# $Id$

%define _vardir  %{_localstatedir}/lib
%define _pydir   %{_libdir}/python2.2/site-packages
%define _perldir %{_libdir}/perl5/site_perl

Summary: New logs analyzer and parser.
Name: epylog
Version: 0.9.3
Release: 1
License: GPL
Group: Applications/System
Source: http://linux.duke.edu/projects/epylog/download/%{name}-%{version}.tar.gz
Packager: Konstantin Riabitsev <icon@phy.duke.edu>
Vendor: Duke University
BuildRoot: %{_tmppath}/%{name}-%{version}-root
BuildArch: noarch
BuildPrereq: perl, python, gzip, sed
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
%configure \
    --with-python=/usr/bin/python2 \
    --with-lynx=/usr/bin/links
##
# Fix version.
#
%{__perl} -pi -e \
    "s/^VERSION\s*=\s*.*/VERSION = '%{name}-%{version}-%{release}'/g" \
    py/epylog/__init__.py

%build
%{__make}

%install
%{__rm} -rf %{buildroot}
%{__make} install DESTDIR=%{buildroot}
##
# Remove docs
#
%{__rm} -rf %{buildroot}%{_defaultdocdir}
##
# Gzip up manpages
#
find %{buildroot}%{_mandir} -type f -exec %{__gzip} {} \;
##
# Move docs to doc
mv AUTHORS ChangeLog INSTALL LICENSE README doc/

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
* Thu May  1 2003 Konstantin Riabitsev <icon@phy.duke.edu> 0.9.3-1
- Now using autoconf to do the building.
- Added qmail support in mail module.

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
