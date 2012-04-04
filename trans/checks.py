# -*- coding: UTF-8 -*-
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
import re

PYTHON_PRINTF_MATCH = re.compile('''
        %(                          # initial %
              (?:\((?P<key>\w+)\))?    # Python style variables, like %(var)s
        (?P<fullvar>
            [+#-]*                  # flags
            (?:\d+)?                # width
            (?:\.\d+)?              # precision
            (hh\|h\|l\|ll)?         # length formatting
            (?P<type>[\w%]))        # type (%s, %d, etc.)
        )''', re.VERBOSE)


PHP_PRINTF_MATCH = re.compile('''
        %(                          # initial %
              (?:(?P<ord>\d+)\$)?   # variable order, like %1$s
        (?P<fullvar>
            [+#-]*                  # flags
            (?:\d+)?                # width
            (?:\.\d+)?              # precision
            (hh\|h\|l\|ll)?         # length formatting
            (?P<type>[\w%]))        # type (%s, %d, etc.)
        )''', re.VERBOSE)


C_PRINTF_MATCH = re.compile('''
        %(                          # initial %
        (?P<fullvar>
            [+#-]*                  # flags
            (?:\d+)?                # width
            (?:\.\d+)?              # precision
            (hh\|h\|l\|ll)?         # length formatting
            (?P<type>[\w%]))        # type (%s, %d, etc.)
        )''', re.VERBOSE)

# We ignore some words which are usually not translated
SAME_BLACKLIST = frozenset((
    'bluetooth',
    'bzip2',
    'csv',
    'cvs',
    'data',
    'dm',
    'e-mail',
    'eib',
    'email',
    'esperanto',
    'export',
    'firmware',
    'fulltext',
    'gib',
    'git',
    'gzip',
    'id',
    'irc',
    'irda',
    'imei',
    'import',
    'kib',
    'km',
    'latex',
    'mib',
    'mm',
    'n/a',
    'name',
    'ok',
    'open document',
    'pdf',
    'pib',
    'port',
    'rss',
    'server',
    'sim',
    'smsc',
    'software',
    'sql',
    'status',
    'text',
    'tib',
    'vcalendar',
    'vcard',
    'version',
    'web',
    'wiki',
    'www',
    'xml',
    'zip',
    ))

DEFAULT_CHECK_LIST = (
    'trans.checks.SameCheck',
    'trans.checks.BeginNewlineCheck',
    'trans.checks.EndNewlineCheck',
    'trans.checks.EndSpaceCheck',
    'trans.checks.EndStopCheck',
    'trans.checks.EndColonCheck',
    'trans.checks.EndQuestionCheck',
    'trans.checks.EndExclamationCheck',
    'trans.checks.PythonFormatCheck',
    'trans.checks.PHPFormatCheck',
    'trans.checks.CFormatCheck',
    'trans.checks.PluralsCheck',
    'trans.checks.ConsistencyCheck',
)

class Check(object):
    '''
    Basic class for checks.
    '''
    check_id = ''
    name = ''
    description = ''

    def check(self, sources, targets, flags, language, unit):
        '''
        Checks single unit, handling plurals.
        '''
        # Check singular
        if self.check_single(sources[0], targets[0], flags, language, unit):
            return True
        # Do we have more to check?
        if len(sources) == 1:
            return False
        # Check plurals against plural from source
        for target in targets[1:]:
            if self.check_single(sources[1], target, flags, language, unit):
                return True
        # Check did not fire
        return False

    def check_single(self, source, target, flags, language, unit):
        '''
        Check for single phrase, not dealing with plurals.
        '''
        return False

    def check_chars(self, source, target, pos, chars):
        '''
        Generic checker for chars presence.
        '''
        if len(target) == 0:
            return False
        s = source[pos]
        t = target[pos]
        return (s in chars and t not in chars) or (s not in chars and t in chars)

    def check_format_strings(self, source, target, regex):
        '''
        Generic checker for format strings.
        '''
        if len(target) == 0:
            return False
        src_matches = set([x[0] for x in regex.findall(source)])
        tgt_matches = set([x[0] for x in regex.findall(target)])
        # We ignore %% as this is really not relevant. However it needs
        # to be matched to prevent handling %%s as %s.
        if '%' in src_matches:
            src_matches.remove('%')
        if '%' in tgt_matches:
            tgt_matches.remove('%')

        if src_matches != tgt_matches:
            return True

        return False

    def is_language(self, language, vals):
        '''
        Detects whether language is in given list, ignores language
        variants.
        '''
        return language.code.split('_')[0] in vals



class SameCheck(Check):
    '''
    Check for not translated entries.
    '''
    check_id = 'same'
    name = _('Not translated')
    description = _('Source and translated strings are same')

    def check_single(self, source, target, flags, language, unit):
        # One letter things are usually labels or decimal/thousand separators
        if len(source) == 1 and len(target) == 1:
            return False

        # English variants will have most things not translated
        if self.is_language(language, ['en']):
            return False

        # Probably shortcut
        if source.isupper() and target.isupper():
            return False

        # Ignore words which are often same in foreigh language
        if source.lower() in SAME_BLACKLIST or source.lower().strip('&: ') in SAME_BLACKLIST:
            return False

        return (source == target)

class BeginNewlineCheck(Check):
    '''
    Checks for newlines at beginning.
    '''
    check_id = 'begin_newline'
    name = _('Starting newline')
    description = _('Source and translated do not both start with a newline')

    def check_single(self, source, target, flags, language, unit):
        return self.check_chars(source, target, 0, ['\n'])

class EndNewlineCheck(Check):
    '''
    Checks for newlines at end.
    '''
    check_id = 'end_newline'
    name = _('Trailing newline')
    description = _('Source and translated do not both end with a newline')

    def check_single(self, source, target, flags, language, unit):
        return self.check_chars(source, target, -1, ['\n'])

class EndSpaceCheck(Check):
    '''
    Whitespace check
    '''
    check_id = 'end_space'
    name = _('Trailing space')
    description = _('Source and translated do not both end with a space')

    def check_single(self, source, target, flags, language, unit):
        # One letter things are usually decimal/thousand separators
        if len(source) == 1 and len(target) <= 1:
            return False
        if self.is_language(language, ['fr', 'br']):
            if len(target) == 0:
                return False
            if source[-1] in [':', '!', '?'] and target[-1] == ' ':
                return False
        return self.check_chars(source, target, -1, [' '])

class EndStopCheck(Check):
    '''
    Check for final stop
    '''
    check_id = 'end_stop'
    name = _('Trailing stop')
    description = _('Source and translated do not both end with a full stop')

    def check_single(self, source, target, flags, language, unit):
        if len(source) == 1 and len(target) == 1:
            return False
        return self.check_chars(source, target, -1, [u'.', u'。', u'।', u'۔'])


class EndColonCheck(Check):
    '''
    Check for final colon
    '''
    check_id = 'end_colon'
    name = _('Trailing colon')
    description = _('Source and translated do not both end with a colon or colon is not correctly spaced')

    def check_single(self, source, target, flags, language, unit):
        if self.is_language(language, ['fr', 'br']):
            if len(target) == 0:
                return False
            if source[-1] == ':':
                if target[-3:] not in [' : ', '&nbsp;: ', u' : ']:
                    return True
            return False
        if self.is_language(language, ['ja']):
            # Japanese sentence might need to end with full stop
            # in case it's used before list.
            if source[-1] == ':':
                return self.check_chars(source, target, -1, [u':', u'：', u'.', u'。'])
            return False
        return self.check_chars(source, target, -1, [u':', u'：'])


class EndQuestionCheck(Check):
    '''
    Check for final question mark
    '''
    check_id = 'end_question'
    name = _('Trailing question')
    description = _('Source and translated do not both end with a question mark or it is not correctly spaced')

    def check_single(self, source, target, flags, language, unit):
        if self.is_language(language, ['fr', 'br']):
            if len(target) == 0:
                return False
            if source[-1] == '?':
                if target[-2:] not in [' ?', '&nbsp;?', u' ?']:
                    return True
            return False
        return self.check_chars(source, target, -1, [u'?', u'՞', u'؟', u'⸮', u'？', u'፧', u'꘏', u'⳺'])

class EndExclamationCheck(Check):
    '''
    Check for final exclamation mark
    '''
    check_id = 'end_exclamation'
    name = _('Trailing exclamation')
    description = _('Source and translated do not both end with an exclamation mark or it is not correctly spaced')

    def check_single(self, source, target, flags, language, unit):
        if self.is_language(language, ['fr', 'br']):
            if len(target) == 0:
                return False
            if source[-1] == '!':
                if target[-2:] not in [' !', '&nbsp;!', u' !']:
                    return True
            return False
        return self.check_chars(source, target, -1, [u'!', u'！', u'՜', u'᥄', u'႟', u'߹'])

# For now all format string checks use generic implementation, but
# it should be switched to language specific

class PythonFormatCheck(Check):
    '''
    Check for Python format string
    '''
    check_id = 'python_format'
    name = _('Python format')
    description = _('Format string does not match source')

    def check_single(self, source, target, flags, language, unit):
        if not 'python-format' in flags:
            return False
        return self.check_format_strings(source, target, PYTHON_PRINTF_MATCH)

class PHPFormatCheck(Check):
    '''
    Check for PHP format string
    '''
    check_id = 'php_format'
    name = _('PHP format')
    description = _('Format string does not match source')

    def check_single(self, source, target, flags, language, unit):
        if not 'php-format' in flags:
            return False
        return self.check_format_strings(source, target, PHP_PRINTF_MATCH)

class CFormatCheck(Check):
    '''
    Check for C format string
    '''
    check_id = 'c_format'
    name = _('C format')
    description = _('Format string does not match source')

    def check_single(self, source, target, flags, language, unit):
        if not 'c-format' in flags:
            return False
        return self.check_format_strings(source, target, C_PRINTF_MATCH)


class PluralsCheck(Check):
    '''
    Check for incomplete plural forms
    '''
    check_id = 'plurals'
    name = _('Missing plurals')
    description = _('Some plural forms are not translated')

    def check(self, sources, targets, flags, language, unit):
        # Is this plural?
        if len(sources) == 1:
            return False
        # Is at least something translated?
        if targets == len(targets) * ['']:
            return False
        # Check for empty translation
        return ('' in targets)

class ConsistencyCheck(Check):
    '''
    Check for inconsistent translations
    '''
    check_id = 'inconsistent'
    name = _('Inconsistent')
    description = _('This message has more than one translation in this project')

    def check(self, sources, targets, flags, language, unit):
        from trans.models import Unit
        related = Unit.objects.filter(
            translation__language = language,
            translation__subproject__project = unit.translation.subproject.project,
            checksum = unit.checksum
            ).exclude(
            id = unit.id
            )
        for unit2 in related.iterator():
            if unit2.target != unit.target:
                return True

        return False


# Initialize checks list
CHECKS = {}
for path in getattr(settings, 'CHECK_LIST', DEFAULT_CHECK_LIST):
    i = path.rfind('.')
    module, attr = path[:i], path[i+1:]
    try:
        mod = __import__(module, {}, {}, [attr])
    except ImportError, e:
        raise ImproperlyConfigured('Error importing translation check module %s: "%s"' % (module, e))
    try:
        cls = getattr(mod, attr)
    except AttributeError:
        raise ImproperlyConfigured('Module "%s" does not define a "%s" callable check' % (module, attr))
    CHECKS[cls.check_id] = cls()


