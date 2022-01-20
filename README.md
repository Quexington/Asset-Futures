# Asset-Futures
Some Chialisp for issuing and claiming on chain futures

This is something I whipped together for issuing futures for on chain assets as CATs.  Basically there are three puzzles:
* A launcher puzzle which will lock up the desired asset in the futures puzzle and create a CAT at a mojo ratio of 1/1 billion.  This ratio is crucial for the futures puzzle to work.  This launcher puzzle is not actually necessary except for your own peace of mind that everything is being done correctly, and potentially for on-chain verifiability.
* A CAT TAIL that is esentially a single-time issuance CAT, except that it can be melted if it asserts an announcement from the futures puzzle that it is releasing the correct amount of asset.
* A "futures" puzzle that locks up a coin until a certain time, and after that can be claimed with an announcement from the CAT that was issued as a tradable represention of itself.

Things that could be better:
* Currently there's no truth inherent in the puzzles.  Someone could lie about the backing when giving you a CAT that is supposed to be redeemable, and likewise a contract can not have enough CATs to fully redeem it, since it does not verify that they were created in the launcher at all.
