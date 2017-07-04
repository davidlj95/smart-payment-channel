import argparse
import ast
from .constants import LOG_DEFAULT, LOGS, ACTIONS, TREE_DEPTH_DEFAULT, \
                       FEE_DEFAULT, TIMELOCK_INCREMENT_DEFAULT, RESET_DEFAULT


# helping methods
def evalTF(string):
    return ast.literal_eval(string.title())


# Default parser
DEFAULT_PARSER = argparse.ArgumentParser(
    # prog = 'iec.py'
    # usage = (generated by default)
    description="""Bidirectional Payment Channels [Decker's implementation]""",
    epilog="<> with ♥ by davidlj95 @ dEIC.UAB.cat",
    add_help=True,
    allow_abbrev=True
)
DEFAULT_PARSER.add_argument(
    "-v", "--version",
    action="version",
    version="v0.12"
)
DEFAULT_PARSER.add_argument(
    "-l", "--log-level",
    metavar="level",
    action="store",
    help="""specifies the level of events to log. Events upper from that level
    will be displayed. Default is %s""" % (LOG_DEFAULT),
    type=str,
    choices=LOGS,
    default=LOG_DEFAULT
)
# Generic params
DEFAULT_PARSER.add_argument(
    "operation",
    action="store",
    help="sets the operation to perform to operate a bidirectional payment " +
         "channel",
    type=str,
    choices=ACTIONS
)
DEFAULT_PARSER.add_argument(
    "--fees",
    action="store",
    help="sets the fees to specify in each transaction",
    type=float,
    default=FEE_DEFAULT
)
# Funding parameters
DEFAULT_PARSER.add_argument(
    "-d", "--tree-depth",
    action="store",
    help="sets the initial invalidation tree depth when funding a channel",
    type=int,
    default=TREE_DEPTH_DEFAULT
)
DEFAULT_PARSER.add_argument(
    "-f", "--funds",
    action="store",
    nargs=2,
    help="sets the amount of funds that each party will dedicate to their " +
         "unidirectional channel to pay the other party",
    type=float
)
DEFAULT_PARSER.add_argument(
    "--utxo-ids",
    action="store",
    nargs=2,
    help="sets the list of utxo previous tx ids to use to fund the channel. " +
         "Specify them in order (first Alice, then Bob)",
)
DEFAULT_PARSER.add_argument(
    "--utxo-nums",
    action="store",
    nargs=2,
    help="sets the list of utxo previous ouput numbers to use to fund the "
         "channel. Specify them in order (first Alice, then Bob)",
)
DEFAULT_PARSER.add_argument(
    "--priv-keys",
    action="store",
    nargs=2,
    help="specifies a WIF encoded private key to use for signing transactions",
    type=str
)
DEFAULT_PARSER.add_argument(
    "--expiry-time",
    action="store",
    help="sets the expiry time of the payment channel. Read BIP-65 for " +
         "the number format's specification",
    type=int
)
DEFAULT_PARSER.add_argument(
    "--locktime-increment",
    action="store",
    help="number to use as a secure locktime between tx confirmations",
    type=int,
    default=TIMELOCK_INCREMENT_DEFAULT
)
# Reset
DEFAULT_PARSER.add_argument(
    "-r", "--reset",
    action="store",
    help="number of times the channel has been previously reset",
    type=int,
    default=None
)
DEFAULT_PARSER.add_argument(
    "-b", "--balances",
    action="store",
    nargs=2,
    help="the balance to update the channel reset with",
    type=float,
    default=[]
)
DEFAULT_PARSER.add_argument(
    "--to",
    action="store",
    nargs=2,
    help="specifies in a payment operation who to pay (Alice or Bob) and the "
         "amount to pay (example --to alice 5 for bob to pay 5 btc to alice)",
    type=str
)
DEFAULT_PARSER.add_argument(
    "--verbose",
    action="store_true",
    help="prints not just the hexadecimal transactions but also their content "
         "in human readable mode"
)