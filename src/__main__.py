#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BTC Payment Channels application.

This software allows to create a payment channel between two
parties by generating transactions with special scripts using the Bitcoin
scripting language.

The software just creates the transactions from the keys introduced and does
not check their validity against the blockchain. Use it at your own risk.
"""
# Libraries
# # Built-in
import os
import platform
import logging
import sys
# # App
from .core import log
from .bitcoin import MultiSigRedeemScript, ScriptNum, get_op_code_n, \
                     SignableTx, TxOutput, P2SHAddress, P2PKHScriptSig, \
                     TxInput, WIFAddress, P2SHScriptSig, P2PKHAddress
from .cli.arguments.parser import DEFAULT_PARSER
from .cli.arguments.constants import LOGS_LEVELS, LOGS

# Constants
LOGGER = logging.getLogger(__name__)
LOCKTIME_THRESHOLD = 500000000
LOCKTIME_INCREMENT_MIN_BLOCK = 3
LOCKTIME_INCREMENT_MIN_TIMESTAMP = 600

# Variables
args = None


# Functions
def parseArguments(parser, args=None):
    """
    Parse arguments.

    Takes the system arguments vector and tries to parse the arguments in it
    given the argument parser specified and returns the namespace generated.

    Args:
        parser(object): 	the ArgumentParser object to use to
                            parse the arguments.
        args(array):        arguments to parse (default is sys.argv)
    Returns:
        A namespace with the parsed arguments and its values
    """
    return parser.parse_args(args)


def read_private_keys(wif_strings):
    """
    Given the argument parser object, reads and returns the private key objects
    if found or exits if not

    Arguments:
        wif_strings (list): list of WIF addresses strings
    """
    # No private keys
    if wif_strings is None:
        LOGGER.error("No private keys were specified. " +
                     "We need both Alice and Bob private keys"
                     "Specify them with --priv-keys")
        sys.exit(1)
    priv_keys = []
    # Read all private keys
    for priv_key in wif_strings:
        # Convert to WIF
        try:
            priv_key_obj = WIFAddress.decode(priv_key)
        except Exception as e:
            LOGGER.error(
                "Private key can not be parsed: %s", str(e))
            sys.exit(1)
        priv_keys.append(priv_key_obj)
    # Check correct number passed
    if len(priv_keys) == 0:
        LOGGER.error("No private keys were specified. " +
                     "We need both Alice and Bob private keys")
        sys.exit(1)
    elif len(priv_keys) < 2:
        LOGGER.error("Two private keys (Alice and Bob's) have to be specified")
        sys.exit(1)
    elif len(priv_keys) > 2:
        LOGGER.warning("Just two private keys will be used (%d found)",
                       len(priv_keys))
    # Information
    LOGGER.info(" - Read %d private keys", len(priv_keys))
    return priv_keys


def read_inputs(prev_txids, num_outputs):
    """
    Given a list of previous transaction ids and a list of respective output
    numbers, returns transaction input objects created with those information.

    If no information is found, exits the application
    """
    # Read inputs (previous ouputs)
    if prev_txids is None or num_outputs is None:
        LOGGER.error("You must specify the UTXOs to fund the channel. "
                     "Both Alice's and Bob's. " +
                     "Specify --utxo-ids and --utxo-nums")
        sys.exit(1)
    # # UTXO id
    utxo_txids = []
    for txid in prev_txids:
        try:
            txid_bytes = bytes.fromhex(txid)
        except Exception as e:
            LOGGER.error("Invalid UTXO txId hex format: %s", str(e))
            sys.exit(1)
        utxo_txids.append(txid_bytes)
    # # UTXO num
    utxo_nums = []
    for utxo_num in num_outputs:
        try:
            utxo_num = int(utxo_num)
        except Exception as e:
            LOGGER.error("Invalid UTXO output number: %s", str(e))
            sys.exit(1)
        utxo_nums.append(utxo_num)
    # Verify number of ids and outputs nums
    if len(utxo_txids) != len(utxo_nums):
        LOGGER.error("Same number of UTXO txId and UTXO output numbers " +
                     "must be specified")
        sys.exit(1)
    if len(utxo_txids) != len(utxo_nums) != 2:
        LOGGER.error("Two utxo txIds and output numbers must be specified " +
                     "(Alice and Bob's, in order)")
    # Create input objects
    tx_inputs = []
    for i in range(2):
        tx_inputs.append(TxInput(utxo_txids[i], utxo_nums[i],
                                 P2PKHScriptSig()))
    LOGGER.info(" - Read %d inputs (outputs to spend)", len(tx_inputs))
    return tx_inputs


def read_funds(funds):
    """
    Given a list of strings containing the funds desired for each party,
    returns a list of floats with that funds

    If not enough funds specified or conversion errors happen, application
    exits
    """
    # No funds
    if funds is None:
        LOGGER.error("No funds specified. Both Alice and Bob funds must " +
                     "be specified. " +
                     "Specify them with --funds")
        sys.exit(1)
    # Not enough
    if len(funds) < 2:
        LOGGER.error("Two funds must be specified. Alice and Bob's"
                     "Specify them with --funds")
        sys.exit(1)
    elif len(funds) > 2:
        LOGGER.warning("Just two funds will be used")
    # Done
    LOGGER.info(" - Funds set (Alice: %f | Bob: %f)", funds[0], funds[1])
    return funds


def read_expiry_time(expiry_time):
    """
    Checks and reads the expiry time passed from the CLI argument

    If not valid, exits
    """
    # No expiry time
    if expiry_time is None:
        LOGGER.error("No expiry time for the channel specified. "
                     "Specify it with --expiry-time. See BIP-65 for format")
        sys.exit(1)
    # Check block or timestamp
    if expiry_time <= 0:
        LOGGER.error("Please set a valid expiry time (>0)"
                     "Specify it with --expiry-time. See BIP-65 for format")
        sys.exit(1)
    LOGGER.info(" - Channel expiry time set to %d (%s)",
                expiry_time,
                "block num" if expiry_time < LOCKTIME_THRESHOLD
                else "timestamp")
    return expiry_time


def read_locktime_increment(locktime_increment, expiry_time):
    """
    Reads the locktime increment parameter and validates it to see if is
    specified in same units (block num, timestamp) than the expiry time

    If fails to parse or validate, exits the app
    """
    # No locktime increment
    if locktime_increment is None:
        LOGGER.error("No locktime increment for the channel specified. "
                     "Specify it with --locktime-increment. "
                     "See BIP-65 for format")
        sys.exit(1)
    # Check coherence
    locktime_in_blocks = expiry_time < LOCKTIME_THRESHOLD
    if locktime_in_blocks:
        # Check minimum block number set
        if locktime_increment < LOCKTIME_INCREMENT_MIN_BLOCK:
            LOGGER.error("In order to prevent attacks, when using expiry time "
                         "block numbers, locktime increment must be at least "
                         "%d (was set to %d). Change it with "
                         "--locktime-increment",
                         LOCKTIME_INCREMENT_MIN_BLOCK, locktime_increment)
            sys.exit(1)
    else:
        # Check minimum timestamp increment set
        if locktime_increment < LOCKTIME_INCREMENT_MIN_TIMESTAMP:
            LOGGER.error("In order to prevent attacks, when using expiry time "
                         "with timestamps, locktime increment must be at "
                         "least %d (was set to %d). Change it with "
                         "--locktime-increment",
                         LOCKTIME_INCREMENT_MIN_TIMESTAMP, locktime_increment)
            sys.exit(1)
    LOGGER.info(" - Channel invalidation tree locktime increment set to %d"
                " (%s)",
                locktime_increment,
                "blocks" if expiry_time < LOCKTIME_THRESHOLD
                else "seconds")
    return locktime_increment


def read_fees(fees):
    """
    Sets the fees to use for transactions or exits if invalid number set
    """
    # No Fees
    if fees is None:
        LOGGER.error("Fees were not set. Specify them with --fees")
        sys.exit(1)
    # Negative fees
    if fees < 0:
        LOGGER.error("Can't use negative fees. Change them with --fees")
        sys.exit(1)
    # No fees
    if fees == 0:
        LOGGER.warning("Transactions will not have fees for miners!")
    LOGGER.info(" - Transaction fees set to %f tBTC", fees)
    return fees


def read_tree_depth(tree_depth):
    """
    Reads the tree depth to set in the channel invalidation tree
    (number of tree nodes)

    Exits if invalid tree depths
    """
    # No depth
    if tree_depth is None or tree_depth == 0:
        LOGGER.error("Tree depth must be at least 1 to enable resetting. "
                     "Specify tree depth with --tree-depth")
        sys.exit(1)
    LOGGER.info(" - Tree depth set to %d (will create those number of tree "
                " nodes)", tree_depth)
    return tree_depth


def read_balances(balances, funds):
    """
    Given a list of strings containing the balances desired for each party,
    at the current channel moment, returns a list of floats with that balances

    Checks also against initial funds to see if balances are possible

    If not enough balances specified or conversion errors happen, application
    exits
    """
    # No funds
    if balances is None:
        LOGGER.error("No balances specified. Both Alice and Bob balances "
                     "at the current moment must be specified. ",
                     "Specify them with --balances")
        sys.exit(1)
    # Not enough
    if len(balances) < 2:
        LOGGER.error("Two balances must be specified, Alice and Bob's. "
                     "Specify them with --balances")
        sys.exit(1)
    elif len(balances) > 2:
        LOGGER.warning("Just two balances will be used")
    # Check them against funds
    if sum(balances) > sum(funds):
        LOGGER.error("Sum of current balances must be lower / equal to "
                     "sum of initial channel funds. "
                     "Specify them with --balances")
        sys.exit(1)
    # Done
    LOGGER.info(" - New balances set (Alice: %f | Bob: %f)",
                balances[0], balances[1])
    return balances


def read_reset(reset):
    """
    Reads the reset argument to know how many times the channel was reseted
    before

    If fails to parse, exits the app
    """
    if reset is None:
        LOGGER.error("Reset counter was not specified. Please specify the "
                     "number of times the channel was reset to create next "
                     "reset with --reset argument (example --reset 0 for "
                     "first reset)")
        sys.exit(1)
    if reset < 0:
        LOGGER.error("Reset counter has to be positive or 0 (>= 0)"
                     "Change it with --reset argument")
        sys.exit(1)
    LOGGER.info(" - Channel has been reseted %d times", reset)
    return reset


def read_pay(pay, balances):
    """
    Reads a list of strings containing first the destinatary of the payment
    transaction to generate and second the amount to pay to it

    If can't read or finds invalid information, exits the app
    """
    if pay is None or len(pay) != 2:
        LOGGER.error("Payment destination not set or invalid. Set it with "
                     "the --to argument specifying both destinatary and "
                     "amount (ie: --to alice 1.2 or --to bob 0.5)")
        sys.exit(1)
    destination, amount = pay
    destination = destination.lower()
    # Check destination
    if destination != "alice" and destination != "bob":
        LOGGER.error("First argument of the payment destination must be ",
                     "Alice or Bob (alice for first input / priv_key). "
                     "Example: --to alice 1.0")
        sys.exit(1)
    destination = 0 if destination == "alice" else 1
    # Check amount
    try:
        amount = float(amount)
    except Exception as e:
        LOGGER.error("Second argument of the payment destination must be "
                     "an amount specified as a float number in BTC. "
                     "Example: --to bob 2.3")
        LOGGER.error("Conversion error: %s", str(e))
        sys.exit(1)
    # Check balances
    if amount > balances[1-destination]:  # Check if other party has balance
        LOGGER.error("%s has not enough balance in %s channel to pay %f "
                     "BTC", "Bob" if destination == 0 else "Alice",
                     "his" if destination == 0 else "her")
        sys.exit(1)
    LOGGER.info(" - Paying %f BTC to %s", amount, "Alice" if destination == 0
                else "Bob")
    return destination, amount


if __name__ == "__main__":
    # Prepare coding
    if platform.system() == "Windows":
        os.system("chcp 65001")
    args = parseArguments(DEFAULT_PARSER)
    # Switching log level
    root_logger = logging.getLogger()
    root_logger.setLevel(LOGS_LEVELS[LOGS.index(args.log_level)])
    # Welcome
    LOGGER.info("Bidirectional Payment Channel [Decker's implementation]")
    if args.operation == "fund":
        LOGGER.info("<OPERATION: Channel creation>")
    elif args.operation == "pay":
        LOGGER.info("<OPERATION: Channel payment>")
    elif args.operation == "reset":
        LOGGER.info("<OPERATION: Channel resetting>")
    elif args.operation == "close":
        LOGGER.info("<OPERATION: Channel closure>")
    else:
        LOGGER.error("Unrecognized operation %s", args.operation)
        LOGGER.info("Available operations are fund, reset, payment, closure")
        sys.exit(1)
    # Arguments needed
    # # Common
    LOGGER.info("[STEP 1] Reading funding arguments")
    LOGGER.info("Don't worry, if something is missing, we'll tell you")
    priv_keys = read_private_keys(args.priv_keys)
    pub_keys = [key.public_key for key in priv_keys]
    tx_inputs = read_inputs(args.utxo_ids, args.utxo_nums)
    funds = read_funds(args.funds)
    total_funds = sum(funds)
    expiry_time = read_expiry_time(args.expiry_time)
    locktime_increment = read_locktime_increment(args.locktime_increment,
                                                 expiry_time)
    fees = read_fees(args.fees)
    tree_depth = read_tree_depth(args.tree_depth)
    balances = funds
    # # Specific operation arguments
    reset = None
    origin = None
    destination = None
    if args.operation == "reset" \
       or (args.operation == "pay" and args.reset is not None):
        LOGGER.info("Balances will be used to recreate the resets number")
        reset = read_reset(args.reset)
        balances = read_balances(args.balances, funds)
    if args.operation == "pay":
        # Reset counter
        if args.reset is None:
            LOGGER.warning(" - No reset counter set. You are creating a "
                           "payment in a channel not reseted yet")
            LOGGER.warning(" - We ignore balances argument then")
        # Read destination and amount
        destination, amount = read_pay(args.to, balances)
        origin = 1 - destination
    if args.operation == "close":
        # Set closure transaction balances
        LOGGER.info("Balances will be used to generate a closure transaction")
        balances = read_balances(args.balances, funds)
    LOGGER.info("All arguments parsed successfully")
    # Chain of P2SH (invalidation tree P2SH addresses, outputs)
    LOGGER.info("[STEP 2] Creating smart contracts")
    LOGGER.info("         -- P2SH Smart Contracts count --")
    LOGGER.info("          Fund contracts:       %02d", 1)
    LOGGER.info("          Tree nodes contracts: %02d", tree_depth)
    LOGGER.info("          Tree leafs contracts: %02d", 2)
    LOGGER.info("         --------------------------")
    LOGGER.info("          TOTAL contracts:      %02d", tree_depth + 3)
    # Lists of scripts and addresses
    redeem_scripts = []
    p2sh_addresses = []
    # Create them
    LOGGER.info("P2SH addresses list:")
    for i in range(tree_depth+3):
        # Multisig redeem script + variation
        redeem_script = MultiSigRedeemScript(2, 2)
        for pub_key in pub_keys:
            redeem_script.add_public_key(pub_key)
        redeem_scripts.append(redeem_script)
        # Create address
        address = P2SHAddress(redeem_script)
        p2sh_addresses.append(address)
        # Print info
        LOGGER.info(" - P2SH_%d Address: %s", i, address.encode())
        if i == 0:
            LOGGER.info("     Content: funding multisig contract")
        elif i <= tree_depth:
            LOGGER.info("     Content: tree node multisig contract")
        elif i == tree_depth + 1:
            LOGGER.info("     Content: Alice -> Bob channel "
                        "multisig contract")
        else:
            LOGGER.info("     Content: Bob -> Alice channel "
                        "multisig contract")
    # Funding transaction
    LOGGER.info("[STEP 3] Funding transaction")
    LOGGER.info(" - Creating transaction...")
    funding_tx = SignableTx(
        inputs=tx_inputs,
        outputs=[
            TxOutput(
                btc=total_funds - fees,
                script=p2sh_addresses[0].script
            )]
    )
    LOGGER.info(" - Signing transaction...")
    # # Signature
    for i in range(2):
        funding_tx.inputs[i].script.sign(
            key=priv_keys[i].private_key
        )
    LOGGER.info(" - Done!")
    # Tree nodes
    LOGGER.info("[STEP 4] Creating tree nodes")
    locktime = expiry_time - locktime_increment
    LOGGER.info("Locktime initially set to %d", locktime)
    tree_branch = []
    previous_tx = funding_tx
    # Create nodes' txs
    for i in range(tree_depth):
        tree_tx = SignableTx(
            inputs=[
                TxInput(
                    utxo_id=previous_tx.id,
                    utxo_n=0,
                    script=P2SHScriptSig(
                        redeem_scripts[i],
                        redeem_scripts[i].pay_script
                    )
                )],
            outputs=[
                TxOutput(
                    btc=total_funds - fees*(i+2),
                    script=p2sh_addresses[i+1].script
                )],
            locktime=locktime
        )
        LOGGER.info(" - [%d] Created tree node transaction", i+1)
        # Sign our part
        for j in range(2):
            tree_tx.inputs[0].script.payment_script.add_signature(
                tree_tx.sign(
                    priv_keys[j].private_key, 0, redeem_scripts[i])
            )
        # Show it
        LOGGER.info(" - [%d] Signed tree node transaction", i+1)
        # Append
        tree_branch.append(tree_tx)
        # Continue branch
        previous_tx = tree_tx
    LOGGER.info("Created %d tree nodes transactions", len(tree_branch))
    # Payment transaction
    LOGGER.info("[STEP 5] Leaf transaction")
    # # Reset last status
    if args.operation == "reset":
        # # Bare reset operation
        reset += 1
        LOGGER.info(
            " - Adding a new reset (%d resets totally)", reset)
    if args.operation == "reset" \
       or (args.operation == "pay" and reset is not None):
        # # Take in account a previous reset
        LOGGER.info(
            " - Applying a lower locktime (%d resets made)", reset)
        locktime = locktime - locktime_increment*reset
    LOGGER.info(" - Leaf locktime set to %d", locktime)
    # # Create leaf_tx
    LOGGER.info(" - Creating leaf transaction...")
    leaf_tx = SignableTx(
        inputs=[
            TxInput(
                utxo_id=previous_tx.id,
                utxo_n=0,
                script=P2SHScriptSig(
                    redeem_scripts[tree_depth],
                    redeem_scripts[tree_depth].pay_script
                )
            )],
        outputs=[
            TxOutput(
                btc=balances[0] - fees*(tree_depth+0.5),
                script=p2sh_addresses[tree_depth+1].script
            ),
            TxOutput(
                btc=balances[1] - fees*(tree_depth+0.5),
                script=p2sh_addresses[tree_depth+2].script
            )],
        locktime=locktime
    )
    # # Sign it
    LOGGER.info(" - Signing leaf transaction")
    for i in range(2):
        leaf_tx.inputs[0].script.payment_script.add_signature(
            leaf_tx.sign(priv_keys[i].private_key, 0,
                         redeem_scripts[tree_depth])
        )
    LOGGER.info(" - Done!")
    # Refund transaction
    LOGGER.info("[STEP 6] Refund transaction")
    LOGGER.info(" - Creating refund transaction...")
    refund_tx = SignableTx(
        inputs=[
            TxInput(
                utxo_id=funding_tx.id,
                utxo_n=0,
                script=P2SHScriptSig(
                    redeem_scripts[0],
                    redeem_scripts[0].pay_script
                )
            )],
        outputs=[
            TxOutput(
                btc=funds[0] - fees,
                script=P2PKHAddress(pub_keys[0]).script
            ),
            TxOutput(
                btc=funds[1] - fees,
                script=P2PKHAddress(pub_keys[1]).script
            )],
        locktime=expiry_time
    )
    LOGGER.info(" - Signing refund transaction...")
    for i in range(2):
        refund_tx.inputs[0].script.payment_script.add_signature(
            refund_tx.sign(priv_keys[i].private_key, 0,
                           redeem_scripts[0])
        )
    LOGGER.info(" - Done!")
    # Closure transaction
    if args.operation == "close":
        LOGGER.info("[STEP 7] Closure transaction")
        LOGGER.info("Final balances are:")
        LOGGER.info(" -> Alice: %f BTC", balances[0])
        LOGGER.info(" -> Bob: %f BTC", balances[1])
        LOGGER.info(" - Creating closure transaction...")
        closure_tx = SignableTx(
            inputs=[
                TxInput(
                    utxo_id=funding_tx.id,
                    utxo_n=0,
                    script=P2SHScriptSig(
                        redeem_scripts[0],
                        redeem_scripts[0].pay_script
                    )
                )],
            outputs=[
                TxOutput(
                    btc=balances[0] - fees,
                    script=P2PKHAddress(pub_keys[0]).script
                ),
                TxOutput(
                    btc=balances[1] - fees,
                    script=P2PKHAddress(pub_keys[1]).script
                )],
            locktime=0
        )
        LOGGER.info(" - Signing closure transaction...")
        for i in range(2):
            closure_tx.inputs[0].script.payment_script.add_signature(
                closure_tx.sign(priv_keys[i].private_key, 0,
                                redeem_scripts[0])
            )
        LOGGER.info(" - Done!")
    # Payment transaction
    if args.operation == "pay":
        LOGGER.info("[STEP 7] Payment transaction")
        LOGGER.info(" - Creating payment transaction...")
        pay_tx = SignableTx(
            inputs=[
                TxInput(
                    utxo_id=leaf_tx.id,
                    utxo_n=origin,
                    script=P2SHScriptSig(
                        redeem_scripts[tree_depth + origin + 1],
                        redeem_scripts[tree_depth + origin + 1].pay_script
                    )
                )],
            outputs=[
                TxOutput(
                    btc=amount - fees*(tree_depth+1.5),
                    script=P2PKHAddress(pub_keys[destination]).script
                )]
        )
        LOGGER.info(" - Signing payment transaction...")
        for i in range(2):
            pay_tx.inputs[0].script.payment_script.add_signature(
                pay_tx.sign(priv_keys[i].private_key, 0,
                            redeem_scripts[tree_depth + origin + 1])
            )
        LOGGER.info(" - Done!")
    # Payment operation
    LOGGER.info("[SUMMARY]")
    LOGGER.info(" -> Funding tx:")
    LOGGER.info("    %s", funding_tx.serialize().hex())
    if args.verbose:
        LOGGER.info(" -> Funding tx (human-readable)")
        print(funding_tx)
    LOGGER.info(" -> Invalidation tree nodes txs:")
    for i in range(len(tree_branch)):
        LOGGER.info(" ---> Node [%d]", i+1)
        LOGGER.info("      %s", tree_branch[i].serialize().hex())
        if args.verbose:
            LOGGER.info(" ---> Node [%d] (human-readable)", i+1)
            print(tree_branch[i])
    LOGGER.info(" -> Leaf tree node tx:")
    LOGGER.info("    %s", leaf_tx.serialize().hex())
    if args.verbose:
        LOGGER.info(" -> Leaf tx (human-readable)")
        print(leaf_tx)
    LOGGER.info(" -> Refund tx:")
    LOGGER.info("    %s", refund_tx.serialize().hex())
    if args.verbose:
        LOGGER.info(" -> Refund tx (human-readable)")
        print(refund_tx)
    if args.operation == "pay":
        LOGGER.info(" -> Payment transaction (%f from %s to %s)",
                    amount, "Alice" if origin == 0 else "Bob",
                    "Alice" if destination == 0 else "Bob")
        LOGGER.info("    %s", pay_tx.serialize().hex())
        if args.verbose:
            LOGGER.info(" -> Pay tx (human-readable)")
            print(pay_tx)
    if args.operation == "close":
        LOGGER.info(" -> Closure transaction")
        LOGGER.info("    %s", closure_tx.serialize().hex())
        if args.verbose:
            LOGGER.info(" -> Closure tx (human-readable)")
            print(closure_tx)
    LOGGER.info("Goodbye :)")
