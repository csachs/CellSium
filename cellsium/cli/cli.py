"""CLI entrypoint."""
import logging
import sys
from argparse import ArgumentParser, Namespace
from typing import Callable, Iterable, Optional

from tunable import TunableSelectable

from ..output import all as output_all
from ..random import RRF
from . import render, simulate, training

_ = output_all

log = logging.getLogger(__name__)


def parse_arguments_and_init(
    args: Iterable[str],
    parser_callback: Optional[Callable[[ArgumentParser], None]] = None,
) -> Namespace:
    """
    Basic setup (i.e. logging) and argument parsing.

    :param args: Arguments
    :param parser_callback: Additional callback to configure the argument parser
    :return: Parsed arguments
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)-15s.%(msecs)03d %(name)s %(levelname)s %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    parser = ArgumentParser()

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

    TunableSelectable.setup_and_parse(parser, args=args)

    if parser_callback:
        parser_callback(parser)

    parsed_args = parser.parse_args(args=args)

    if parsed_args.quiet:
        log.setLevel(logging.WARNING)
    elif parsed_args.verbose == 1:
        log.setLevel(logging.INFO)
    elif parsed_args.verbose > 1:
        log.setLevel(logging.DEBUG)

    return parsed_args


subcommands = {simulate, render, training}
subcommand_default = simulate


def main(args: Optional[Iterable[str]] = None) -> Optional[int]:
    """
    Main entrypoint of the script, will redirect to various sub-scripts.

    :param args: arguments, if not specified will be taken from sys.argv
    :return: The return code of the individual subcommand
    """
    if args is None:
        args = sys.argv[1:]

    if not args:
        subcommand = subcommand_default
    else:
        subcommands_dict = {
            subcommand.__name__.split('.')[-1]: subcommand for subcommand in subcommands
        }
        first_arg = args[0]
        if first_arg in subcommands_dict:
            subcommand = subcommands_dict[first_arg]
            del args[0]
        else:
            subcommand = subcommand_default

    subcommand_argparser = getattr(subcommand, 'subcommand_argparser', None)

    parsed_args = parse_arguments_and_init(
        args=args, parser_callback=subcommand_argparser
    )

    seed = RRF.seed()
    log.info("Seeding with %s" % (seed,))

    return subcommand.subcommand_main(args=parsed_args)
