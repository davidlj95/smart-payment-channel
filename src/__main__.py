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
    if args.operation == "fund" or args.operation == "reset":
        if args.operation == "reset":
            # Check reset counter is set
            LOGGER.info("<Reset operation>")
            if args.reset < 0:
                LOGGER.error("Reset counter must be specified and >= 0")
                sys.exit(1)
            # Check new balances
            if len(args.balances) != 2:
                LOGGER.error("New channel balances must be specified")
                sys.exit(1)
        else:
            LOGGER.info("<Funding operation>")
        LOGGER.info("Creating funding transaction and first branches")
        # Funds reading
        LOGGER.info("Setting funds amount")
        if len(args.funds) == 0:
            LOGGER.error("No funds specified")
            sys.exit(1)
        funds = []
        for fund in args.funds:
            if fund <= 0:
                LOGGER.error("Negative or 0 value funds are not valid")
                sys.exit(1)
            funds.append(fund)
        total_funds = sum(funds)
        LOGGER.info(" - Total funds are %f", total_funds)
        # Balances
        balances = funds
        if args.operation == "reset":
            balances = []
            for balance in args.balances:
                if balance <= 0:
                    LOGGER.error("Negative or 0 value balances are not valid")
                    sys.exit(1)
                balances.append(balance)
            total_balances = sum(balances)
            LOGGER.info(" - Total balances are %f", total_balances)
            if total_balances != total_funds:
                LOGGER.error("Total balances do not match specified funds")
                sys.exit(1)
        # Public keys parsing
        LOGGER.info("Reading public keys")
        pub_keys = []
        for pub_key in args.pub_keys:
            # Convert to bytes
            try:
                pub_key_bytes = bytes.fromhex(pub_key)
            except Exception as e:
                LOGGER.error(
                    "Public keys are not in hexadecimal format: %s", str(e))
                sys.exit(1)
            pub_keys.append(pub_key_bytes)
            # TODO: Validate pub_key format
        if len(pub_keys) == 0:
            LOGGER.error("No public keys were specified")
            sys.exit(1)
        elif len(pub_keys) < 2:
            LOGGER.error("Two public keys have to be specified")
            sys.exit(1)
        elif len(pub_keys) > 2:
            LOGGER.warning("Just two public keys will be used")
        # Opt-in atomic multiparty transactions redeem scripts
        LOGGER.info(
            "Creating opt-in multisig chain (depth is %d)" % args.tree_depth)
        optin_redeem_scripts = []
        p2sh_addresses = []
        for i in range(args.tree_depth+3):
            redeem_script = MultiSigRedeemScript(2, 2, get_op_code_n(i))
            for pub_key in pub_keys:
                redeem_script.add_public_key(pub_key)
            optin_redeem_scripts.append(redeem_script)
            address = P2SHAddress(redeem_script)
            p2sh_addresses.append(address)
            LOGGER.info(" - P2SH_%d Address: %s", i, address.encode())
            LOGGER.info(" - Latest 2 P2SH addresses are the ones used for " +
                        "   setting the payment channels in leaf node")
        # Funding transaction
        LOGGER.info("Creating funding transaction")
        LOGGER.info(" - Reading UTXO to spend funds")
        # # UTXO
        if len(args.utxo) != 2:
            if len(args.utxo) == 0:
                LOGGER.error("No UTXO specified")
            else:
                LOGGER.error("Invalid UTXO, must contain two elements: " +
                             "<txId> <output_num>")
            sys.exit(1)
        # # # UTXO id
        utxo_txid = args.utxo[0]
        try:
            utxo_txid = bytes.fromhex(utxo_txid)
        except Exception as e:
            LOGGER.error("Invalid UTXO txId hex format: %s", str(e))
            sys.exit(1)
        # # # UTXO num
        utxo_num = args.utxo[1]
        try:
            utxo_num = int(utxo_num)
        except Exception as e:
            LOGGER.error("Invalid UTXO output number: %s", str(e))
            sys.exit(1)
        # # Private key
        LOGGER.info(" - Reading private key")
        if args.priv_key is None:
            LOGGER.error("No private key specified")
            sys.exit(1)
        try:
            priv_key = WIFAddress.decode(args.priv_key)
        except Exception as e:
            LOGGER.error("Unable to decode private key: %s", str(e))
            sys.exit(1)
        # # Creation
        funding_tx = SignableTx(
            outputs=[
                TxOutput(
                    btc=total_funds - args.fees,
                    script=p2sh_addresses[0].script
                )]
        )
        LOGGER.info(" - Funding transaction generated:")
        funding_tx.add_input(
            TxInput(
                utxo_id=utxo_txid,
                utxo_n=utxo_num,
                script=P2PKHScriptSig()
            )
        )
        # # Signature
        funding_tx.inputs[0].script.sign(
            key=priv_key.private_key
        )
        print(funding_tx.serialize().hex())
        # Read expiry time
        if args.expiry_time is None:
            LOGGER.error("Expiry time must be specified")
            sys.exit(1)
        elif args.expiry_time <= 0:
            LOGGER.error("Expiry time must be > 0")
            sys.exit(1)
        locktime = args.expiry_time - args.locktime_increment
        # Branch transaction
        LOGGER.info("Creating first tree branch")
        LOGGER.info(" - Locktime initially set to %d", locktime)
        tree_branch = []
        previous_tx = funding_tx
        for i in range(args.tree_depth):
            tree_tx = SignableTx(
                inputs=[
                    TxInput(
                        utxo_id=previous_tx.id,
                        utxo_n=0,
                        script=P2SHScriptSig(
                            optin_redeem_scripts[i],
                            optin_redeem_scripts[i].pay_script
                        )
                    )],
                outputs=[
                    TxOutput(
                        btc=total_funds - args.fees*(i+2),
                        script=p2sh_addresses[i+1].script
                    )],
                locktime=locktime
            )
            # Sign our part
            tree_tx.inputs[0].script.payment_script.add_signature(
                tree_tx.sign(priv_key.private_key, 0, optin_redeem_scripts[i])
            )
            # Show it
            LOGGER.info(" - [%d] Signed tree branch transaction", i+1)
            print(tree_tx.serialize().hex())
            # Append
            tree_branch.append(tree_tx)
            # Continue branch
            previous_tx = tree_tx
            locktime -= args.locktime_increment
        LOGGER.info(" - Created %d tree branch transactions", len(tree_branch))
        # Payment transaction
        LOGGER.info("Creating leaf transaction")
        if args.operation == "reset":
            LOGGER.info(
                " - Applying a lower locktime (%d resets made)", args.reset+1)
            locktime = locktime - args.locktime_increment*(args.reset+1)
        leaf_tx = SignableTx(
            inputs=[
                TxInput(
                    utxo_id=previous_tx.id,
                    utxo_n=0,
                    script=P2SHScriptSig(
                        optin_redeem_scripts[args.tree_depth],
                        optin_redeem_scripts[args.tree_depth].pay_script
                    )
                )],
            outputs=[
                TxOutput(
                    btc=funds[0] - args.fees*(args.tree_depth+1.5),
                    script=p2sh_addresses[args.tree_depth+1].script
                ),
                TxOutput(
                    btc=funds[1] - args.fees*(args.tree_depth+1.5),
                    script=p2sh_addresses[args.tree_depth+2].script
                )],
            locktime=locktime
            )
        # Sign our part
        leaf_tx.inputs[0].script.payment_script.add_signature(
            leaf_tx.sign(priv_key.private_key, 0,
                         optin_redeem_scripts[args.tree_depth])
        )
        LOGGER.info(" - Signed leaf transaction with micropayment channels")
        print(leaf_tx.serialize().hex())
        # Refund transaction
        LOGGER.info("Creating refund transaction")
        refund_tx = SignableTx(
            inputs=[
                TxInput(
                    utxo_id=funding_tx.id,
                    utxo_n=0,
                    script=P2SHScriptSig(
                        optin_redeem_scripts[0],
                        optin_redeem_scripts[0].pay_script
                    )
                )],
            outputs=[
                TxOutput(
                    btc=balances[0] - args.fees*2,
                    script=P2PKHAddress(pub_keys[0]).script
                ),
                TxOutput(
                    btc=balances[1] - args.fees*2,
                    script=P2PKHAddress(pub_keys[1]).script
                )],
            locktime=args.expiry_time
        )
        LOGGER.info(" - Refund signed transaction generated")
        print(refund_tx.serialize().hex())
    elif args.operation == "pay":
        LOGGER.info("Creating a payment transaction")
    LOGGER.info("Goodbye")
