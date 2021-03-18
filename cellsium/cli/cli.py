import argparse
import logging
import sys

from tunable import TunableSelectable

from ..random import RRF
from . import render, simulate, training

log = logging.getLogger(__name__)


def parse_arguments_and_init(parser_callback=None):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)-15s.%(msecs)03d %(name)s %(levelname)s %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    parser = argparse.ArgumentParser()

    parser.add_argument('-o', '--output-file', dest='output', default=None)
    parser.add_argument(
        '-w', '--overwrite', dest='overwrite', default=False, action='store_true'
    )
    parser.add_argument(
        '-p', '--prefix', dest='prefix', default=False, action='store_true'
    )
    verbose_group = parser.add_mutually_exclusive_group()
    verbose_group.add_argument(
        '-q', '--quiet', dest='quiet', default=False, action='store_true'
    )
    verbose_group.add_argument(
        '-v', '--verbose', dest='verbose', default=1, action='count'
    )

    TunableSelectable.setup_and_parse(parser)

    if parser_callback:
        parser_callback(parser)

    args = parser.parse_args()

    if args.quiet:
        log.setLevel(logging.WARNING)
    elif args.verbose == 1:
        log.setLevel(logging.INFO)
    else:
        # possibly switch on more debug settings
        log.setLevel(logging.DEBUG)

    return args


subcommands = {simulate, render, training}
subcommand_default = simulate


def main():
    if len(sys.argv) == 1:
        subcommand = subcommand_default
    else:
        subcommands_dict = {
            subcommand.__name__.split('.')[-1]: subcommand for subcommand in subcommands
        }
        first_arg = sys.argv[1]
        if first_arg in subcommands_dict:
            subcommand = subcommands_dict[first_arg]
            del sys.argv[1]
        else:
            subcommand = subcommand_default

    subcommand_argparser = getattr(subcommand, 'subcommand_argparser', None)

    args = parse_arguments_and_init(parser_callback=subcommand_argparser)

    seed = RRF.seed()
    log.info("Seeding with %s" % (seed,))

    return subcommand.subcommand_main(args=args)
