from pathlib import Path
from typing import List, Optional, Tuple
from blspy import G2Element

from chia.types.blockchain_format.coin import Coin
from chia.types.blockchain_format.sized_bytes import bytes32
from chia.types.blockchain_format.program import Program
from chia.types.spend_bundle import SpendBundle
from chia.types.coin_spend import CoinSpend
from chia.types.condition_opcodes import ConditionOpcode
from chia.util.ints import uint32, uint64
from chia.util.hash import std_hash

from clvm.casts import int_to_bytes

import cdv.clibs as std_lib
from cdv.util.load_clvm import load_clvm

from drivers.cat_utils import SpendableCAT, unsigned_spend_bundle_for_spendable_cats, CAT_MOD
from drivers.lineage_proof import LineageProof

clibs_path: Path = Path(std_lib.__file__).parent
LAUNCHER_MOD: Program = load_clvm("future_launcher.clsp", "clsp", search_paths=[clibs_path])
FUTURE_TAIL: Program = load_clvm("futures_tail.clsp", "clsp", search_paths=[clibs_path])
FUTURE_MOD: Program = load_clvm("future.clsp", "clsp", search_paths=[clibs_path])

# Create the program that locks the funds until a specified date
def create_funds_puzzle(launcher_id: bytes32, unlock_time: uint32) -> Program:
    return FUTURE_MOD.curry(
        FUTURE_MOD.get_tree_hash(),
        CAT_MOD.get_tree_hash(),
        FUTURE_TAIL.get_tree_hash(),
        launcher_id,
        unlock_time,
    )

# Create the TAIL program to use within the CAT
def create_futures_tail(launcher_id: bytes32, unlock_time: uint32) -> Program:
    return FUTURE_TAIL.curry(
        launcher_id,
        create_funds_puzzle(launcher_id, unlock_time).get_tree_hash(),
    )

# Create the solution to launch a future
def create_launcher_solution(launcher: Coin, unlock_time: uint32, amount: uint64, cat_inner_puzzle: Program) -> Program:
    return Program.to(
        [
            amount,
            create_funds_puzzle(launcher.name(), unlock_time).get_tree_hash(),
            CAT_MOD.curry(
                CAT_MOD.get_tree_hash(),
                create_futures_tail(launcher.name(), unlock_time).get_tree_hash(),
                cat_inner_puzzle,
            ).get_tree_hash(),
        ]
    )

# Create the condition that triggers and solves the CAT TAIL
def create_tail_condition(tail: Program) -> Program:
    return Program.to([51, 0, -113, tail, Program.to([])])

# Generate a solution to contribute to a piggybank
def redeem_cat(
    cat_coin: Coin,
    cat_parent: Coin,
    funds_coin: Coin,
    tail: Program,
    lineage_proof: LineageProof,
    funds_puzzle: Program,
    cat_inner_puzzle: Program,
    cat_inner_solution: Program,
    redeem_amount: uint64,
) -> SpendBundle:
    spendable_cat = SpendableCAT(
        coin=cat_coin,
        limitations_program_hash=tail.get_tree_hash(),
        inner_puzzle=cat_inner_puzzle,
        inner_solution=cat_inner_solution,
        lineage_proof=lineage_proof,
        extra_delta=redeem_amount * -1,
    )
    spend_bundle = unsigned_spend_bundle_for_spendable_cats(CAT_MOD, [spendable_cat])
    funds_coin_spend = CoinSpend(
        funds_coin,
        funds_puzzle,
        Program.to([cat_inner_puzzle.get_tree_hash(), redeem_amount * 1000000000, funds_coin.amount]),
    )
    return SpendBundle.aggregate([spend_bundle, SpendBundle([funds_coin_spend], G2Element())])
