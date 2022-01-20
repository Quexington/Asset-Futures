import pytest
import datetime
import sys
sys.path.append("..")

from cdv.test import setup as setup_test
from cdv.test import block_time, CoinWrapper

from chia.util.ints import uint32, uint64
from chia.types.blockchain_format.program import Program
from chia.types.condition_opcodes import ConditionOpcode
from chia.types.spend_bundle import SpendBundle

from drivers.lineage_proof import LineageProof
from drivers.cat_utils import (
    SpendableCAT,
    CAT_MOD,
    unsigned_spend_bundle_for_spendable_cats,
)
from drivers.futures_drivers import (
    LAUNCHER_MOD,
    create_funds_puzzle,
    create_futures_tail,
    create_launcher_solution,
    create_tail_condition,
    redeem_cat,
)


class TestFuturesLifecycle:
    @pytest.fixture(scope="function")
    async def setup(self):
        network, alice, bob = await setup_test()
        await network.farm_block()
        yield network, alice, bob

    @pytest.mark.asyncio
    async def test_lifecycle(self, setup):
        network, alice, bob = setup
        try:
            # Get our alice wallet some money
            await network.farm_block(farmer=alice)

            # This retrieves us a coin that is at least 1 XCH + 1000 mojos.
            funding_coin = await alice.choose_coin(1000000001000)

            #This is the spend of the piggy bank coin.  We use the driver code to create the solution.
            to_launcher_spend = await alice.spend_coin(
                funding_coin,
                pushtx=False,
                custom_conditions=[[ConditionOpcode.CREATE_COIN, LAUNCHER_MOD.get_tree_hash(), 1000000001000]],
            )

            # Gather the launcher addition
            launcher_coin = [c for c in to_launcher_spend.additions() if c.puzzle_hash == LAUNCHER_MOD.get_tree_hash()][0]

            # Generate that spend
            unlock_time = uint32(network.sim.timestamp + 200)
            launcher_spend = await alice.spend_coin(
                CoinWrapper(launcher_coin.parent_coin_info, launcher_coin.puzzle_hash, launcher_coin.amount, LAUNCHER_MOD),
                pushtx=False,
                args=create_launcher_solution(launcher_coin, unlock_time, 1000000000000, Program.to(1)),
            )

            # Aggregate them to make sure they are spent together
            combined_spend = SpendBundle.aggregate([to_launcher_spend, launcher_spend])
            result = await network.push_tx(combined_spend)
            assert "error" not in result

            # Gather the coins
            funds_coin = [c for c in combined_spend.additions() if c.amount == 1000000000000][0]
            cat_coin = [c for c in combined_spend.additions() if c.amount == 1000][0]

            # Spend the CAT
            tail = create_futures_tail(launcher_coin.name(), unlock_time)
            spendable_cat = SpendableCAT(
                coin=cat_coin,
                limitations_program_hash=tail.get_tree_hash(),
                inner_puzzle=Program.to(1),
                inner_solution=[[51, Program.to(1).get_tree_hash(), cat_coin.amount], create_tail_condition(tail)],
            )
            cat_spend = unsigned_spend_bundle_for_spendable_cats(CAT_MOD, [spendable_cat])
            result = await network.push_tx(cat_spend)
            assert "error" not in result

            # Gather the cat again
            new_cat_coin = [c for c in cat_spend.additions() if c.amount == 1000][0]

            # Generate the redemption spend
            redemption_spend = redeem_cat(
                new_cat_coin,
                cat_coin,
                funds_coin,
                tail,
                LineageProof(cat_coin.parent_coin_info, Program.to(1).get_tree_hash(), cat_coin.amount),
                create_funds_puzzle(launcher_coin.name(), unlock_time),
                Program.to(1),
                Program.to([[51, Program.to(1).get_tree_hash(), cat_coin.amount - 500], create_tail_condition(tail)]),
                500,
            )
            result = await network.push_tx(redemption_spend)
            assert "error" in result
            assert "ASSERT_SECONDS_ABSOLUTE_FAILED" in result["error"]

            network.sim.pass_time(uint64(300))
            await network.farm_block(farmer=bob)

            result = await network.push_tx(redemption_spend)
            assert "error" not in result

        finally:
            await network.close()
