# $Id$

%{!?_pyver:%define _pyver 2.2}

%define _python  %{_bindir}/python%{_pyver}
%define _vardir  %{_localstatedir}/lib
%define _pydir   %{_libdir}/python%{_pyver}/site-packages
%define _perldir %{_libdir}/perl5/site_perl

#------------------------------------------------------------------------------

Summary:        New logs analyzer and parser.
Name:           epylog
Version:        1.0
Release:        0.%{_pyver}
Epoch:          0
License:        GPL
Group:          Applications/System
Source:         http://linux.duke.edu/projects/epylog/download/%{name}-%{version}.tar.gz
URL:            http://linux.duke.edu/projects/epylog/
BuildRoot:      %{_tmppath}/%{name}-%{version}-root
BuildArch:      noarch
BuildPrereq:    perl, %{_python}, gzip, sed
Requires:       %{_python}, libxml2-python
Obsoletes:      dulog

%description
Epylog is a new log notifier and parser which runs periodically out of
cron, looks at your logs, processes the entries in order to present
them in a more comprehensive format, and then provides you with the
output. It is written specifically with large network clusters in mind
where a lot of machines (around 50 and upwards) log to the same
loghost using syslog or syslog-ng.

#------------------------------------------------------------------------------

%package perl
Summary:        Perl module for writing external Epylog modules
Group:          Development/Libraries
Requires:       epylog, perl >= 5.6
Provides:       perl(epylog)

%description perl
This package provides a perl module for epylog. It is useful for
writing epylog modules that use external module API. No modules shipping
with epylog by default use that API, so install this only if you are using
external perl modules, or intend to write some of your own.

#------------------------------------------------------------------------------

%prep
%setup -q
%configure \
    --with-python=%{_python} \
    --with-lynx=/usr/bin/links
##
# Fix version.
#
%{__perl} -pi -e \
    "s/^VERSION\s*=\s*.*/VERSION = '%{name}-%{version}-%{release}'/g" \
    py/epylog/__init__.py

#------------------------------------------------------------------------------

%build
%{__make}

#------------------------------------------------------------------------------

%install
%{__rm} -rf %{buildroot}
%{__make} install DESTDIR=%{buildroot}
##
# Remove installed docs
#
%{__rm} -rf %{buildroot}%{_defaultdocdir}
##
# Gzip up manpages
#
%{__gzip} %{buildroot}%{_mandir}/man*/*
##
# Move docs to doc
#
%{__mv} AUTHORS ChangeLog INSTALL LICENSE README doc/

#------------------------------------------------------------------------------

%clean
%{__rm} -rf %{buildroot}

#------------------------------------------------------------------------------

%files
%defattr(-,root,root)
%dir %{_vardir}/%{name}
%dir %{_datadir}/%{name}
%{_datadir}/%{name}/modules/*
%{_pydir}/%{name}
%{_sbindir}/%{name}
%{_sysconfdir}/cron.daily/%{name}.cron
%{_mandir}/man5/*
%{_mandir}/man8/*
%config(noreplace) %{_sysconfdir}/%{name}
%doc doc/*

#------------------------------------------------------------------------------

%files perl
%defattr(-,root,root)
%{_perldir}/%{name}.pm
%{_mandir}/man3/*

#------------------------------------------------------------------------------

%changelog
* Fri Apr 09 2004 Konstantin Ryabitsev <icon@linux.duke.edu> 1.0
- Version 1.0
- Do not depend on elinks to make things simpler

* Mon Feb 09 2004 Konstantin Ryabitsev <icon@linux.duke.edu> 0.9.7-1
- Version 0.9.7
- Depend on python version.

* Mon Sep 22 2003 Konstantin Ryabitsev <icon@linux.duke.edu> 0.9.6-1
- Version 0.9.6

* Wed Jul 23 2003 Konstantin Ryabitsev <icon@linux.duke.edu> 0.9.5-1
- Version 0.9.5

* Tue May 20 2003 Konstantin Ryabitsev <icon@linux.duke.edu> 0.9.4-1
- Specfile cleanups to make it more easily adaptable for Linux@DUKE.
- Fix for bug 38 (incorrect offsets were causing backtrace)
- Normalized logger calls (bug 9)
- Enhancements to mail and packets modules

* Thu May  1 2003 Konstantin Ryabitsev <icon@linux.duke.edu> 0.9.3-1
- Now using autoconf to do the building.
- Added qmail support in mail module.
- Split perl module into a separate package.

* Tue Apr 29 2003 Konstantin Ryabitsev <icon@linux.duke.edu> 0.9.2-1
- Notices module reworked to support custom notifications.
- Weeder module now supports 'ALL' for enable
- Some changes to epylog core to return matched regex as part of linemap.

* Fri Apr 25 2003 Konstantin Ryabitsev <icon@linux.duke.edu> 0.9.1-1
- Some bugfixes after running pychecker
- Added doc/INSTALL for people not running RPM.

* Thu Apr 18 2003 Konstantin Ryabitsev <icon@linux.duke.edu> 0.9.0-1
- A significant rewrite of module handlers.

* Wed Mar 13 2003 Konstantin Ryabitsev <icon@linux.duke.edu> 0.8.14-1
- Fixes for html email sending
- Option to send via sendmail vs. smtplib
- Multiple mailto addresses now handled correctly
- Small bugfixes.

* Mon Mar 03 2003 Konstantin Ryabitsev <icon@linux.duke.edu> 0.8.13-1
- Two new features for module configs: you can now specify the priority
  and extra options for modules.

* Fri Feb 28 2003 Konstantin Ryabitsev <icon@linux.duke.edu> 0.8.12-1
- Two small bugfixes which prevented some modules from ever being 
  executed when the last log was 0 length.

* Thu Feb 27 2003 Konstantin Ryabitsev <icon@linux.duke.edu> 0.8.11-1
- Small changes to logrotation modules, allowing them to specify
  a full path to a rotated file.

* Wed Feb 26 2003 Konstantin Ryabitsev <icon@linux.duke.edu> 0.8.10-1
- Ported some modules from DULog.

* Mon Feb 10 2003 Konstantin Ryabitsev <icon@linux.duke.edu> 0.8.9-1
- Several fixes in fine_locate routines causing it not to break
  on logs with non-consecutive entries and live logs.

* Fri Feb 07 2003 Konstantin Ryabitsev <icon@linux.duke.edu> 0.8.7-1
- More fixes for the memory-friendly grep.

* Tue Jan 28 2003 Konstantin Ryabitsev <icon@linux.duke.edu> 0.8.6-1
- Lots and lots of memory optimizations (chunked reads throughout)
- Entities replaced in get_html_report
- memory-friendly fgrep calls

* Mon Jan 27 2003 Konstantin Ryabitsev <icon@linux.duke.edu> 0.8.5-1
- Big rewrite of logfile handling routines. This works much-much-much
  better!
- A useful usage().
- Lots of bugfixes.

* Sat Jan 18 2003 Konstantin Ryabitsev <icon@linux.duke.edu> 0.8-1
- First attempt at building a semi-usable epylog. It even works.
  Sometimes. :)
- Removed DULog-related changelogs.
