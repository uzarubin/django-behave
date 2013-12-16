"""Django test runner which uses behave for BDD tests.
"""

import unittest
from pdb import set_trace
from os.path import dirname, abspath, basename, join, isdir

from django.test.simple import DjangoTestSuiteRunner, reorder_suite
from django.test import LiveServerTestCase
from django.db.models import get_app, get_apps
from django.db.models.loading import AppCache

from behave.configuration import Configuration, ConfigError
from behave.runner import Runner
from behave.parser import ParserError
from behave.formatter.ansi_escapes import escapes

from selenium import webdriver

import sys


def get_app_dir(app_module):
    app_dir = dirname(app_module.__file__)
    if basename(app_dir) == 'models':
        app_dir = abspath(join(app_dir, '..'))
    return app_dir


def get_features(app_module):
    app_dir = get_app_dir(app_module)
    features_dir = abspath(join(app_dir, 'features'))
    if isdir(features_dir):
        return features_dir
    else:
        return None


class DjangoBehaveTestCase(LiveServerTestCase):
    def __init__(self, **kwargs):
        self.features_dir = kwargs.pop('features_dir')
        super(DjangoBehaveTestCase, self).__init__(**kwargs)
        unittest.TestCase.__init__(self)

    def get_features_dir(self):
        if isinstance(self.features_dir, basestring):
            return [self.features_dir]
        return self.features_dir

    def setUp(self):
        self.setupBehave()

    def setupBehave(self):
        # sys.argv kludge
        # need to understand how to do this better
        # temporarily lose all the options etc
        # else behave will complain
        old_argv = sys.argv
        sys.argv = old_argv[:2]
        self.behave_config = Configuration()
        sys.argv = old_argv
        # end of sys.argv kludge

        self.behave_config.server_url = self.live_server_url  # property of LiveServerTestCase
        self.behave_config.paths = self.get_features_dir()
        self.behave_config.format = ['pretty']
        # disable these in case you want to add set_trace in the tests you're developing
        self.behave_config.stdout_capture = False
        self.behave_config.stderr_capture = False

    def runTest(self, result=None):
        # run behave on a single directory

        # from behave/__main__.py
        #stream = self.behave_config.output
        runner = Runner(self.behave_config)
        try:
            failed = runner.run()
        except ParserError, e:
            sys.exit(str(e))
        except ConfigError, e:
            sys.exit(str(e))

        if self.behave_config.show_snippets and runner.undefined:
            msg = u"\nYou can implement step definitions for undefined steps with "
            msg += u"these snippets:\n\n"
            printed = set()

            if sys.version_info[0] == 3:
                string_prefix = "('"
            else:
                string_prefix = u"(u'"

            for step in set(runner.undefined):
                if step in printed:
                    continue
                printed.add(step)

                msg += u"@" + step.step_type + string_prefix + step.name + u"')\n"
                msg += u"def impl(context):\n"
                msg += u"    assert False\n\n"

            sys.stderr.write(escapes['undefined'] + msg + escapes['reset'])
            sys.stderr.flush()

        if failed:
            sys.exit(1)
        # end of from behave/__main__.py


class DjangoBehaveTestSuiteRunner(DjangoTestSuiteRunner):
    def make_bdd_test_suite(self, features_dir):
        return DjangoBehaveTestCase(features_dir=features_dir)

    def build_suite(self, test_labels, extra_tests=None, **kwargs):
        # build standard Django test suite
        suite = unittest.TestSuite()

        #
        # Run Normal Django Test Suite
        #
        std_test_suite = super(DjangoBehaveTestSuiteRunner,self).build_suite(test_labels,**kwargs)
        suite.addTest(std_test_suite)

        #
        # Add BDD tests to it
        #

        # always get all features for given apps (for convenience)
        for label in test_labels:
            if '.' in label:
                print "Ignoring label with dot in: " % label
                continue
            app = get_app(label)

            # Check to see if a separate 'features' module exists,
            # parallel to the models module
            features_dir = get_features(app)
            if features_dir is not None:
                # build a test suite for this directory
                suite.addTest(self.make_bdd_test_suite(features_dir))

        return reorder_suite(suite, (LiveServerTestCase,))


class DjangoBehaveOnlyFeatures(DjangoBehaveTestSuiteRunner):

    def make_bdd_test_suite(self, features_dir):
        return DjangoBehaveTestCase(features_dir=features_dir)

    def build_suite(self, test_labels, extra_tests=None, **kwargs):
        cache = AppCache()

        get_app = cache.get_app
        get_apps = cache.get_apps

        suite = unittest.TestSuite()

        #get all features for given apps
        if test_labels:
            for label in test_labels:
                if '.' in label:
                    print 'Ignoring label with dot in: ' % label
                    continue
                app = get_app(label)

                features_dir = get_features(app)
                if features_dir is not None:
                    suite.addTest(self.make_bdd_test_suite(features_dir))
        else:
            for app in get_apps():
                features_dir = get_features(app)
                if features_dir is not None:
                    suite.addTest(self.make_bdd_test_suite(features_dir))

        return reorder_suite(suite, (LiveServerTestCase,))
# eof:
