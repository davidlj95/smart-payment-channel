# Bidirectional Payment Channel application
## Goal
The goal of this application was to prove with an implemented _proof-of-concept_ how Bitcoin bidirectional payment channels can be implemented using the idea proposed by _Christian Decker_ and _Roger Wattenhofer_ [1] of linking two unidirectional payment channels and use an _invalidation tree_ to enable channel resets. The technical proposal and explanation can be found in the [project whitepaper](../whitepaper/whitepaper.pdf) and in the [project presentation slides](,,/presentation/presentation.pdf)
> [1] C. Decker and R. Wattenhofer, [“A fast and scalable payment network with bitcoin duplex micropayment channels”](http://www.tik.ee.ethz.ch/file/716b955c130e6c703fac336ea17b1670/duplex-micropayment-channels.pdf) in Symposium on Self-Stabilizing Systems, pp. 3-18, Springer, 2015
## Features
### What the software _can_ do
The software can create transactions to create and operate our implementation of the Decker's bidirectional payment channels proposal with the following features:
 - __Create transaction sets__: the application does not communicate with other nodes running this application. Just generates transactions necessary for the channel creation. It is for this reason that needs both parties private keys (it is not yet intended for final use, but for proving the channel implementation is possible)
 - __Command-line arguments__: the application is operated using a CLI that requires basically two elements (and also accepts additional arguments for advanced uses):
   - __Operation__: What operation to perform to generate a set of transactions (`fund, pay, reset, close`)
   - __Channel state__: Because the application does not store any information, all information needed to fund the channel is also needed to operate it after main channel structure has been created. Therefore it requires basic arguments that are mandatory for all channel operations (`--priv-keys, --utxo-ids, --utxo-nums, --expiry-time, --funds, --expiry-time`).
### What the software _can not_ do
Currently the software has the following limitations:
 - __Does not allow communications__
    - ___No protocol is followed___: All transactions are generated instantly with both supposed users private keys. No secure protocol is followed to enable real trustless payment channel operation. It is a _proof-of-concept_
    - ___Does not communicate with your wallet___: you must specify which inputs do you want to fund the channel and be sure of their value in order for the software to work. You must also provide private keys to sign those inputs. It does not accept more than one input per user neither.
    - ___Does not communicate with Bitcoin network___: all transactions generated must be broadcasted using a Bitcoin client, like `bitcoin-cli sendrawtransaction` method
 - __Does not allow change outputs__: all balance from the UTXOs specified will be used to fund the channel, no refund outputs will be added. If the value is greater than the funds, the difference will be sumed to the defined fees.
 - __Does not create multiple branches in the invalidation tree__: as it is just a _proof-of-concept_, no functionality is coded to enable multiple branches of the invalidation tree (the _n_ parameter in [Decker's whitepaper](http://www.tik.ee.ethz.ch/file/716b955c130e6c703fac336ea17b1670/duplex-micropayment-channels.pdf))
## How to use it
Here a guide on how to use the software manually with the current limitations. __We suppose we have access to a [`Bitcoin Core` wallet](https://bitcoin.org/en/full-node)__ operating on the Bitcoin's `testnet` network, that allows us to export private keys and list the wallet transactions and also access the __bitcoin-cli__ client. In order to test the channel faster, you can enable [`-regtest` mode](https://bitcoin.org/en/developer-examples#regtest-mode).

In order to provide a practical guide, we will create a bidirectional payment channel using our application to enable payments between Alice and Bob (two virtual users we both control)

### Preparation
#### Creating the channel inputs
In order to just have 2 inputs in the funding transaction, we must first fund two new Bitcoin P2PKH adresses with the funds for Alice and Bob.

> Previously to this step we have created two accounts, one for Alice and one for Bob in order to be the more realistic as possible when creating this guide
>
> This can done having a default wallet with some amount of bitcoins (maybe obtained from [a faucet](https://testnet.manu.backend.hamburg/faucet))
> The command to move some amount of bitcoins from the default account to an account (and create that account if does not exist) is
> ```bash
> user@bitcoin:~$ bitcoin-cli move "" alice 1.5
> ```
> To move 1.5 BTCs from default account to Alice's account. The same command allows to create Bob's account or increase any of both accounts.
> Creating accounts is necessary in order to have several different addresses to receive and send funds to.

So we must obtain a new Alice's address and a new Bob's address. We can do it with the command:
```bash
user@bitcoin:~$ bitcoin-cli getaccountaddress alice
```
It will output a new address for Alice's account. Like we can see in the following screenshot
<center>
<img src="img/00_alice_address.png"/>
<small><i>Figure 1. Alice address generation</i></small>
</center>

We repeat the same steps but with Bob to obtain a Bob's address to fund.

> __IMPORTANT__: Take note of the addresses for Alice and Bob

Now we fund this address with the exact amount of bitcoins we want Alice to fund the payment channel, sending some funds Alice owns to this new address. In this example, we want Alice to fund the channel with 1 tBTC.
```bash
user@bitcoin:~$ bitcoin-cli sendfrom alice mh9ghQVpa3dDiZ1NJ4JZWqrNLirZG2P8RH 1
```
> Replace the address in the example by the address obtained from previous command

If the transaction was succesfully created and broadcasted, its `txId` will appear in the command line as a result as we can see in the next figure
<center>
<img src="img/01_alice_moves.png"/>
<small><i>Figure 2. Alice funds the address</i></small>
</center>

We do the same to get an address for Bob and fund Bob's address.

> __IMPORTANT__: Take note of the `txId` output from the command for Alice and Bob

After that, we can check in an [online block explorer](https://www.blocktrail.com/tBTC) when our transactions are confirmed by searching the obtained `txId`. We will see also which output number sends funds to the address we specified (starting to count from 0)
<center>
<img src="img/02_alice_tx_online.png"/>
<small><i>Figure 3. Checking if a transaction has been confirmed and its output number</i></small>
</center>

In our example, the output number is 0. We repeat this previous steps to get the output number of Bob's transaction.

> __IMPORTANT__: Take note of the output number that funds the address, counting from zero for both Alice and Bob's `txIds`

> We can also check it using the `bitcoin-cli listtransactions` command and looking at the confirmations number for the transaction. It also provides details about the transaction
> <center>
> ![alice_tx_cli](img/03_alice_tx_cli.png)
> <small><i>Figure 4. Checking if a transaction has been confirmed using  `bitcoin-cli`</i></small>
> </center>

Summarizing, we need __for both Alice and Bob__:
 - __The address__ generated with funds to fund the channel from
 - __The _txId___ that moves funds to her / his address
 - __The _output number___ that sends funds to the address
#### Obtaining private keys
Now we need to spend this funds payed to those addresses by performing a digital signature, so we need the corresponding private keys for each of the addresses. We can obtain the private keys using `bitcoin-cli`. In order to avoid copying and pasting the private key, we will store keys in files.

```bash
user@bitcoin:~$ bitcoin-cli dumpprivkey mh9ghQVpa3dDiZ1NJ4JZWqrNLirZG2P8RH > alice.key
```

Note that we specify Alice's address to obtain Alice's private key. We do the same to obtain Bob's private key.

### Using the application
> __Required environment__
> Remember to have [Python 3.6](https://www.python.org/) and have installed the dependencies ([`python-bitcoinlib`](https://github.com/petertodd/python-bitcoinlib) and [`pybitcointools`](https://github.com/vbuterin/pybitcointools)) before running the software. Dependencies can be installed with [`pip`](https://pypi.python.org/pypi/pip)

We now have everything to start using the application and create our payment channels. We can start by calling main module `src` using a terminal located in the project's source code roots' folder and requesting for help with the `-h` argument

```bash
user@bitcoin:~$ python -m src -h
```

It will show us basic application usage help and all arguments that can handle
<center>
<img src="img/04_usage.png"/>
<small><i>Figure 5. Application's help and usage message</i></small>
</center>

From now on, we can request an operation and the software will go asking for arguments until all necessary arguments are filled.

#### Creating the channel
To create the channel structure, we need to specify the following operation and arguments

```bash
user@bitcoin:~$ python -m src \
--priv-keys $(cat alice.key) $(cat bob.key) \
--utxo-ids 1ea738d159141bc65e8c2409a31d4ab174c684a9382b33be689c5038cb839347 \
d291aa5e80ec5f454d95b11946202bf501d54bb3c2bbd6584cafc31415b6c492 \
--utxo-nums 1 1 --funds 1 1 --expiry-time 1151554 \
--tree-depth 1 fund
```
This means, we have to specify:
 - __Private keys__: in WIF format, for Alice and Bob, in this order. We obtained them in the previous steps (and are now passing them as an argument first reading the private keys' file contents)
 - __UTXOs__: so Alice and Bob can fund the channel. We have to specify them with `--utxo-ids` and specify the previous input ids to spent for Alice and Bob in the right order. Also we have to specify `--utxo-nums` to specify the output numbers for both Alice and Bob.
 - __Funds__: amount of bitcoins each user will fund the channel with, in order (first Alice, then Bob). Must coincide with the UTXOs value, as will not be checked when generating all transactions.
 - __Expiry time__: Time to lock the refund transactions in order to recover funds if a party did not cooperate. Specified as a block number if number is `< 500000000` or as timestamp if greater. See [BIP-65](https://github.com/bitcoin/bips/blob/master/bip-0065.mediawiki) for more information.
 - __Tree depth__: number of invalidation non-leaf nodes to create. Default is 1 if not specified

This is the master command we need to use as a base to create all the channel basic structure. We'll change it and extend it to perform resets, payments and eventually closure transactions.

The output, if all parameters are correct is something like the following figure:

<center>
<img src="img/05_channel_txs.png"/>
<small><i>Figure 6. Generated channel transactions</i></small>
</center>

Where all transactions to fund the channel and have the basic invalidation tree appear in hexadecimal format. You can add `--verbose` to the application's arguments to show a human-readable version of them:

<center>
<img src="img/06_tx_verbose.png"/>
<small><i>Figure 7. Example of a verbose transaction (funding)</i></small>
</center>

You can see how in the previous figure the funding transaction refers to the previous inputs to the passed `txIds` and `output nums`. The same we created when preparing the channel.

The output, as it can also be seen has less value than 2 BTC, the sum of the inputs amounts, as 0.002 BTC fees have been automatically applied. You can change the fees to apply in each generated transaction with the `--fees` parameter.

> __IMPORTANT__:
> Make sure to do not change any of the parameters explained until now when paying or performing other operations, as the channel the operations may not operate over the same channel generated.

##### Broadcasting the funding transaction
To begin operating the channel, we can just broadcast the funding transaction by copying the hexadecimal representation of the funding transaction and sending it using the `bitcoin-cli` client:
<center>
<img src="img/07_send_funding.png"/>
<small><i>Figure 8. Broadcasting the funding transaction</i></small>
</center>

As you can see in the figure, as a result, the `txId` of the funding transaction will be returned if no errors happen.

#### Operating the channel
In order to operate the channel once we have the main structure and  broadcasted the funding transaction, we have to change slightly the previous generation or funding command:

```bash
user@bitcoin:~$ python -m src \
--priv-keys $(cat alice.key) $(cat bob.key) \
--utxo-ids 1ea738d159141bc65e8c2409a31d4ab174c684a9382b33be689c5038cb839347 \
d291aa5e80ec5f454d95b11946202bf501d54bb3c2bbd6584cafc31415b6c492 \
--utxo-nums 1 1 --funds 1 1 --expiry-time 1151554 \
--tree-depth 1
```

We must replace `fund` with another operation, but leave all the other arguments equal in order to operate the funded channel and not a different one. __We will call this command the _master command___

In order to perform operations, we have to add to the _master command_ an operation and its arguments

##### Payment transactions
The operation for creating payment transactions is `pay`. And the arguments are `--to destination amount`. For example, to pay 0.5 tBTC to Bob:
```bash
user@bitcoin:~$ $MASTER_COMMAND pay --to bob 0.5
```
This will output all structure transactions and the payment transaction at the end. Remember to always pay incremental amounts. If need to reset the channel to perform more payments, use the `reset` operation

> If the channel has been reset and you need to create a payment transaction, you need to specify how many resets have been performed using the `--reset` argument and the balances of the last reset with `--balances`. By default, we suppose no resets have been performed. See next section for more information.

##### Reset transactions
The operation for creating a new reset is `reset`. And the arguments are `--reset counter` specifying how many resets have been performed in the past and `--balances alice bob`. For example, to create the first reset and set a balance of 0.5 tBTC for Alice and 1.5 tBTC for Bob:
```bash
user@bitcoin:~$ $MASTER_COMMAND reset --reset 0 --balances 0.5 1.5
```
You will have to use this arguments within the master command after a reset has been performed in order to create valid payment transactions as seen before.

To create the second reset, we would have to specify `--reset 1` and the balances of the reset.

##### Closure transactions
We can create closure transactions simulating a graceful closure where both parties agree on the channel final balance with the operation `close`. We specify the final balances with the same `--balances` argument we used in the reset operation.

For example, to create a closure transaction with final balances of 1.5 tBTC for Alice and 0.5 tBTC for Bob:

```bash
user@bitcoin:~$ $MASTER_COMMAND close --balances 0.5 1.5
```

At the end of the output, the closure transaction will appear.
