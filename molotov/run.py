import os
import sys
import argparse
import platform

from importlib import import_module
from importlib.util import spec_from_file_location, module_from_spec

from molotov.runner import Runner
from molotov.api import get_scenarios, get_scenario
from molotov import __version__
from molotov.util import expand_options, OptionError, printable_error
from molotov.sharedconsole import SharedConsole


PYPY = platform.python_implementation() == 'PyPy'


def _parser():
    parser = argparse.ArgumentParser(description='Load test.')

    parser.add_argument('scenario', default="loadtest.py",
                        help="path or module name that contains scenarii",
                        nargs="?")

    parser.add_argument('-s', '--single-mode', default=None, type=str,
                        help="Name of a single scenario to run once.")

    parser.add_argument('--config', default=None, type=str,
                        help='Point to a JSON config file.')

    parser.add_argument('--version', action='store_true', default=False,
                        help='Displays version and exits.')

    parser.add_argument('--debug', action='store_true', default=False,
                        help='Run the event loop in debug mode.')

    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help=('Verbosity level. -v will display '
                              'tracebacks. -vv requests and responses.'))

    parser.add_argument('-w', '--workers', help='Number of workers',
                        type=int, default=1)

    parser.add_argument('--ramp-up', help='Ramp-up time in seconds',
                        type=float, default=0.)

    parser.add_argument('--sizing', help='Autosizing', action='store_true',
                        default=False)

    parser.add_argument('--sizing-tolerance', help='Sizing tolerance',
                        type=float, default=5.)

    parser.add_argument('--delay', help='Delay between each worker run',
                        type=float, default=0.)

    parser.add_argument('--console-update',
                        help='Delay between each console update',
                        type=float, default=0.2)

    parser.add_argument('-p', '--processes', help='Number of processes',
                        type=int, default=1)

    parser.add_argument('-d', '--duration', help='Duration in seconds',
                        type=int, default=86400)

    parser.add_argument('-r', '--max-runs', help='Maximum runs per worker',
                        type=int, default=None)

    parser.add_argument('-q', '--quiet', action='store_true', default=False,
                        help='Quiet')

    parser.add_argument('-x', '--exception', action='store_true',
                        default=False,
                        help='Stop on first failure.')

    parser.add_argument('-f', '--fail', type=int, default=None,
                        help='Number of failures required to fail')

    parser.add_argument('-c', '--console', action='store_true',
                        default=True,
                        help='Use simple console for feedback')

    parser.add_argument('--statsd', help='Activates statsd',
                        action='store_true', default=False)

    parser.add_argument('--statsd-address', help='Statsd Address',
                        type=str, default="udp://127.0.0.1:8125")

    parser.add_argument('--uvloop', help='Use uvloop', default=False,
                        action='store_true')

    parser.add_argument('--use-extension',
                        help='Imports a module containing Molotov extensions',
                        default=None, type=str, nargs='+')

    return parser


def main(args=None):
    if args is None:
        parser = _parser()
        args = parser.parse_args()

    if args.version:
        print(__version__)
        sys.exit(0)

    if args.config:
        if args.scenario == 'loadtest.py':
            args.scenario = 'test'

        try:
            expand_options(args.config, args.scenario, args)
        except OptionError as e:
            print(str(e))
            sys.exit(0)

    if args.uvloop:
        if PYPY:
            print("You can't use uvloop with PyPy")     # pragma: no cover
            sys.exit(0)                                 # pragma: no cover

        try:
            import uvloop
        except ImportError:
            print('You need to install uvloop when using --uvloop')
            sys.exit(0)

        import asyncio
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    if args.sizing:
        # sizing is just ramping up workers indefinitely until
        # something things break. If the user has not set the values,
        # we do it here with 5 minutes and 500 workers
        if args.ramp_up == 0.:
            args.ramp_up = 300
        if args.workers == 1:
            args.workers = 500

    return run(args)


_SIZING = """\

Sizing is over!

Error Ratio %(RATIO).2f %% obtained with %(WORKER)d workers.

OVERALL: SUCCESSES: %(OK)d | FAILURES: %(FAILED)d
LAST MINUTE: SUCCESSES: %(MINUTE_OK)d | FAILURES: %(MINUTE_FAILED)d
"""

HELLO = '**** Molotov v%s. Happy breaking! ****' % __version__


def run(args):
    args.shared_console = SharedConsole(interval=args.console_update)

    if not args.quiet:
        print(HELLO)

    if args.use_extension:
        for extension in args.use_extension:
            if not args.quiet:
                print("Loading extension %r" % extension)
            if os.path.exists(extension):
                spec = spec_from_file_location("extension", extension)
                module = module_from_spec(spec)
                spec.loader.exec_module(module)
            else:
                try:
                    import_module(extension)
                except (ImportError, ValueError) as e:
                    print('Cannot import %r' % extension)
                    print('\n'.join(printable_error(e)))
                    sys.exit(1)

    if os.path.exists(args.scenario):
        spec = spec_from_file_location("loadtest", args.scenario)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        try:
            import_module(args.scenario)
        except (ImportError, ValueError) as e:
            print('Cannot import %r' % args.scenario)
            print('\n'.join(printable_error(e)))
            sys.exit(1)

    if len(get_scenarios()) == 0:
        print('You need at least one scenario. No scenario was found.')
        print('A scenario with a weight of 0 is ignored')
        sys.exit(1)

    if args.verbose > 0 and args.quiet:
        print("You can't use -q and -v at the same time")
        sys.exit(1)

    if args.single_mode:
        if get_scenario(args.single_mode) is None:
            print("Can't find %r in registered scenarii" % args.single_mode)
            sys.exit(1)

    res = Runner(args)()

    def _dict(counters):
        res = {}
        for k, v in counters.items():
            if k == 'RATIO':
                res[k] = float(v.value) / 100.
            else:
                res[k] = v.value
        return res

    res = _dict(res)

    if not args.quiet:
        if args.sizing:
            if res['REACHED'] == 1:
                print(_SIZING % res)
            else:
                print('Sizing was not finished. (interrupted)')
        else:
            print('SUCCESSES: %(OK)d | FAILURES: %(FAILED)d\r' % res)
        print('*** Bye ***')
        if args.fail is not None and res['FAILED'] >= args.fail:
            sys.exit(1)
