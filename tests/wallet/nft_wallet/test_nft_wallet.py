import asyncio
from typing import Any

import pytest
from clvm_tools.binutils import disassemble

from chia.consensus.block_rewards import calculate_base_farmer_reward, calculate_pool_reward
from chia.full_node.mempool_manager import MempoolManager
from chia.rpc.wallet_rpc_api import WalletRpcApi
from chia.simulator.full_node_simulator import FullNodeSimulator
from chia.simulator.simulator_protocol import FarmNewBlockProtocol
from chia.types.blockchain_format.program import Program
from chia.types.blockchain_format.sized_bytes import bytes32
from chia.types.peer_info import PeerInfo
from chia.util.byte_types import hexstr_to_bytes
from chia.util.ints import uint16, uint32, uint64
from chia.wallet.did_wallet.did_wallet import DIDWallet
from chia.wallet.nft_wallet.nft_wallet import NFTWallet
from chia.wallet.util.compute_memos import compute_memos
from chia.wallet.util.wallet_types import WalletType
from tests.time_out_assert import time_out_assert, time_out_assert_not_none


async def tx_in_pool(mempool: MempoolManager, tx_id: bytes32) -> bool:
    tx = mempool.get_spendbundle(tx_id)
    if tx is None:
        return False
    return True


@pytest.mark.parametrize(
    "trusted",
    [True, False],
)
@pytest.mark.asyncio
async def test_nft_wallet_creation_automatically(two_wallet_nodes: Any, trusted: Any) -> None:
    num_blocks = 5
    full_nodes, wallets = two_wallet_nodes
    full_node_api = full_nodes[0]
    full_node_server = full_node_api.server
    wallet_node_0, server_0 = wallets[0]
    wallet_node_1, server_1 = wallets[1]
    wallet_0 = wallet_node_0.wallet_state_manager.main_wallet
    wallet_1 = wallet_node_1.wallet_state_manager.main_wallet

    ph = await wallet_0.get_new_puzzlehash()
    ph1 = await wallet_1.get_new_puzzlehash()

    if trusted:
        wallet_node_0.config["trusted_peers"] = {
            full_node_api.full_node.server.node_id.hex(): full_node_api.full_node.server.node_id.hex()
        }
        wallet_node_1.config["trusted_peers"] = {
            full_node_api.full_node.server.node_id.hex(): full_node_api.full_node.server.node_id.hex()
        }
    else:
        wallet_node_0.config["trusted_peers"] = {}
        wallet_node_1.config["trusted_peers"] = {}

    await server_0.start_client(PeerInfo("localhost", uint16(full_node_server._port)), None)
    await server_1.start_client(PeerInfo("localhost", uint16(full_node_server._port)), None)

    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph))

    funds = sum(
        [calculate_pool_reward(uint32(i)) + calculate_base_farmer_reward(uint32(i)) for i in range(1, num_blocks - 1)]
    )

    await time_out_assert(10, wallet_0.get_unconfirmed_balance, funds)
    await time_out_assert(10, wallet_0.get_confirmed_balance, funds)
    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph1))

    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph))

    await time_out_assert(15, wallet_0.get_pending_change_balance, 0)
    nft_wallet_0 = await NFTWallet.create_new_nft_wallet(
        wallet_node_0.wallet_state_manager, wallet_0, name="NFT WALLET 1"
    )
    metadata = Program.to(
        [
            ("u", ["https://www.chia.net/img/branding/chia-logo.svg"]),
            ("h", "0xD4584AD463139FA8C0D9F68F4B59F185"),
        ]
    )

    sb = await nft_wallet_0.generate_new_nft(metadata)
    assert sb
    await time_out_assert_not_none(15, full_node_api.full_node.mempool_manager.get_spendbundle, sb.name())

    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph1))

    await time_out_assert(15, len, 1, nft_wallet_0.nft_wallet_info.my_nft_coins)
    coins = nft_wallet_0.nft_wallet_info.my_nft_coins
    assert len(coins) == 1, "nft not generated"

    sb = await nft_wallet_0.transfer_nft(coins[0], ph1)
    assert sb is not None
    await time_out_assert_not_none(15, full_node_api.full_node.mempool_manager.get_spendbundle, sb.name())
    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph1))
    await time_out_assert(15, len, 2, wallet_node_1.wallet_state_manager.wallets)
    # Get the new NFT wallet
    nft_wallets = await wallet_node_1.wallet_state_manager.get_all_wallet_info_entries(WalletType.NFT)
    assert len(nft_wallets) == 1
    nft_wallet_1: NFTWallet = wallet_node_1.wallet_state_manager.wallets[nft_wallets[0].id]
    await time_out_assert(15, len, 1, nft_wallet_1.nft_wallet_info.my_nft_coins)
    coins = nft_wallet_0.nft_wallet_info.my_nft_coins
    assert len(coins) == 0
    coins = nft_wallet_1.nft_wallet_info.my_nft_coins
    assert len(coins) == 1


@pytest.mark.parametrize(
    "trusted",
    [True, False],
)
@pytest.mark.asyncio
async def test_nft_wallet_creation_and_transfer(two_wallet_nodes: Any, trusted: Any) -> None:
    num_blocks = 2
    full_nodes, wallets = two_wallet_nodes
    full_node_api: FullNodeSimulator = full_nodes[0]
    full_node_server = full_node_api.server
    wallet_node_0, server_0 = wallets[0]
    wallet_node_1, server_1 = wallets[1]
    wallet_0 = wallet_node_0.wallet_state_manager.main_wallet
    wallet_1 = wallet_node_1.wallet_state_manager.main_wallet

    ph = await wallet_0.get_new_puzzlehash()
    ph1 = await wallet_1.get_new_puzzlehash()

    if trusted:
        wallet_node_0.config["trusted_peers"] = {
            full_node_api.full_node.server.node_id.hex(): full_node_api.full_node.server.node_id.hex()
        }
        wallet_node_1.config["trusted_peers"] = {
            full_node_api.full_node.server.node_id.hex(): full_node_api.full_node.server.node_id.hex()
        }
    else:
        wallet_node_0.config["trusted_peers"] = {}
        wallet_node_1.config["trusted_peers"] = {}

    await server_0.start_client(PeerInfo("localhost", uint16(full_node_server._port)), None)
    await server_1.start_client(PeerInfo("localhost", uint16(full_node_server._port)), None)

    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph))

    funds = sum(
        [calculate_pool_reward(uint32(i)) + calculate_base_farmer_reward(uint32(i)) for i in range(1, num_blocks - 1)]
    )

    await time_out_assert(10, wallet_0.get_unconfirmed_balance, funds)
    await time_out_assert(10, wallet_0.get_confirmed_balance, funds)
    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph1))

    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph))

    await time_out_assert(15, wallet_0.get_pending_change_balance, 0)
    nft_wallet_0 = await NFTWallet.create_new_nft_wallet(
        wallet_node_0.wallet_state_manager, wallet_0, name="NFT WALLET 1"
    )
    metadata = Program.to(
        [
            ("u", ["https://www.chia.net/img/branding/chia-logo.svg"]),
            ("h", "0xD4584AD463139FA8C0D9F68F4B59F185"),
        ]
    )

    await time_out_assert(10, wallet_0.get_unconfirmed_balance, 2000000000000)
    await time_out_assert(10, wallet_0.get_confirmed_balance, 2000000000000)
    sb = await nft_wallet_0.generate_new_nft(metadata)
    assert sb
    # ensure hints are generated
    assert compute_memos(sb)
    await time_out_assert_not_none(15, full_node_api.full_node.mempool_manager.get_spendbundle, sb.name())

    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph))

    await time_out_assert(10, len, 1, nft_wallet_0.nft_wallet_info.my_nft_coins)
    metadata = Program.to(
        [
            ("u", ["https://www.test.net/logo.svg"]),
            ("h", "0xD4584AD463139FA8C0D9F68F4B59F181"),
        ]
    )

    await time_out_assert(10, wallet_0.get_unconfirmed_balance, 4000000000000 - 1)
    await time_out_assert(10, wallet_0.get_confirmed_balance, 4000000000000 - 1)
    sb = await nft_wallet_0.generate_new_nft(metadata)
    assert sb
    # ensure hints are generated
    assert compute_memos(sb)
    await time_out_assert_not_none(10, full_node_api.full_node.mempool_manager.get_spendbundle, sb.name())

    await time_out_assert(30, wallet_node_0.wallet_state_manager.lock.locked, False)
    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph1))
    await time_out_assert(15, len, 2, nft_wallet_0.nft_wallet_info.my_nft_coins)
    coins = nft_wallet_0.nft_wallet_info.my_nft_coins
    assert len(coins) == 2, "nft not generated"

    await time_out_assert(15, wallet_0.get_pending_change_balance, 0)
    nft_wallet_1 = await NFTWallet.create_new_nft_wallet(
        wallet_node_1.wallet_state_manager, wallet_1, name="NFT WALLET 2"
    )
    sb = await nft_wallet_0.transfer_nft(coins[1], ph1)

    assert sb is not None
    # ensure hints are generated
    assert compute_memos(sb)

    await time_out_assert_not_none(15, full_node_api.full_node.mempool_manager.get_spendbundle, sb.name())

    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph1))
    await time_out_assert(15, len, 1, nft_wallet_0.nft_wallet_info.my_nft_coins)
    await time_out_assert(15, len, 1, nft_wallet_1.nft_wallet_info.my_nft_coins)
    coins = nft_wallet_1.nft_wallet_info.my_nft_coins
    assert len(coins) == 1

    await time_out_assert(15, wallet_1.get_pending_change_balance, 0)
    # Send it back to original owner
    nsb = await nft_wallet_1.transfer_nft(coins[0], ph)
    assert nsb is not None

    await time_out_assert_not_none(15, full_node_api.full_node.mempool_manager.get_spendbundle, nsb.name())
    # ensure hints are generated
    assert compute_memos(nsb)

    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph1))
    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph))

    await time_out_assert(30, wallet_node_0.wallet_state_manager.lock.locked, False)
    await time_out_assert(15, len, 2, nft_wallet_0.nft_wallet_info.my_nft_coins)
    await time_out_assert(15, len, 0, nft_wallet_1.nft_wallet_info.my_nft_coins)


@pytest.mark.parametrize(
    "trusted",
    [True, False],
)
@pytest.mark.asyncio
async def test_nft_wallet_rpc_creation_and_list(two_wallet_nodes: Any, trusted: Any) -> None:
    num_blocks = 5
    full_nodes, wallets = two_wallet_nodes
    full_node_api = full_nodes[0]
    full_node_server = full_node_api.server
    wallet_node_0, server_0 = wallets[0]
    wallet_node_1, server_1 = wallets[1]
    wallet_0 = wallet_node_0.wallet_state_manager.main_wallet
    wallet_1 = wallet_node_1.wallet_state_manager.main_wallet

    ph = await wallet_0.get_new_puzzlehash()
    _ = await wallet_1.get_new_puzzlehash()

    if trusted:
        wallet_node_0.config["trusted_peers"] = {
            full_node_api.full_node.server.node_id.hex(): full_node_api.full_node.server.node_id.hex()
        }
        wallet_node_1.config["trusted_peers"] = {
            full_node_api.full_node.server.node_id.hex(): full_node_api.full_node.server.node_id.hex()
        }
    else:
        wallet_node_0.config["trusted_peers"] = {}
        wallet_node_1.config["trusted_peers"] = {}

    await server_0.start_client(PeerInfo("localhost", uint16(full_node_server._port)), None)
    await server_1.start_client(PeerInfo("localhost", uint16(full_node_server._port)), None)

    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph))
    funds = sum(
        [calculate_pool_reward(uint32(i)) + calculate_base_farmer_reward(uint32(i)) for i in range(1, num_blocks - 1)]
    )

    await time_out_assert(10, wallet_0.get_unconfirmed_balance, funds)
    await time_out_assert(10, wallet_0.get_confirmed_balance, funds)
    api_0 = WalletRpcApi(wallet_node_0)
    nft_wallet_0 = await api_0.create_new_wallet(dict(wallet_type="nft_wallet", name="NFT WALLET 1"))
    assert isinstance(nft_wallet_0, dict)
    assert nft_wallet_0.get("success")
    nft_wallet_0_id = nft_wallet_0["wallet_id"]

    tr1 = await api_0.nft_mint_nft(
        {
            "wallet_id": nft_wallet_0_id,
            "artist_address": ph,
            "hash": "0xD4584AD463139FA8C0D9F68F4B59F185",
            "uris": ["https://www.chia.net/img/branding/chia-logo.svg"],
        }
    )

    assert isinstance(tr1, dict)
    assert tr1.get("success")
    sb = tr1["spend_bundle"]

    await time_out_assert_not_none(15, full_node_api.full_node.mempool_manager.get_spendbundle, sb.name())
    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph))

    time_left = 5.0
    while time_left > 0:
        coins_response = await api_0.nft_get_nfts(dict(wallet_id=nft_wallet_0_id))
        if len(coins_response.get("nft_list", [])) > 0:
            break
        await asyncio.sleep(0.5)
        time_left -= 0.5
    else:
        raise AssertionError("NFT not minted")
    await time_out_assert(15, wallet_1.get_pending_change_balance, 0)
    tr2 = await api_0.nft_mint_nft(
        {
            "wallet_id": nft_wallet_0_id,
            "artist_address": ph,
            "hash": "0xD4584AD463139FA8C0D9F68F4B59F184",
            "uris": ["https://chialisp.com/img/logo.svg"],
        }
    )
    assert isinstance(tr2, dict)
    assert tr2.get("success")
    sb = tr2["spend_bundle"]
    await time_out_assert_not_none(15, full_node_api.full_node.mempool_manager.get_spendbundle, sb.name())
    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph))
    time_left = 5.0
    while time_left > 0:
        coins_response = await api_0.nft_get_nfts(dict(wallet_id=nft_wallet_0_id))
        try:
            assert isinstance(coins_response, dict)
            assert coins_response.get("success")
            coins = coins_response["nft_list"]
            assert len(coins) == 2
            uris = []
            for coin in coins:
                assert not coin.supports_did
                uris.append(coin.data_uris[0])
                assert coin.mint_height > 0
            assert len(uris) == 2
            assert "https://chialisp.com/img/logo.svg" in uris
            assert bytes32.fromhex(coins[1].to_json_dict()["nft_coin_id"][2:]) in [x.name() for x in sb.additions()]
        except AssertionError:
            if time_left < 1:
                raise
        await asyncio.sleep(0.5)
        time_left -= 0.5


@pytest.mark.parametrize(
    "trusted",
    [True, False],
)
@pytest.mark.asyncio
async def test_nft_wallet_rpc_update_metadata(two_wallet_nodes: Any, trusted: Any) -> None:
    num_blocks = 3
    full_nodes, wallets = two_wallet_nodes
    full_node_api = full_nodes[0]
    full_node_server = full_node_api.server
    wallet_node_0, server_0 = wallets[0]
    wallet_node_1, server_1 = wallets[1]
    wallet_0 = wallet_node_0.wallet_state_manager.main_wallet
    wallet_1 = wallet_node_1.wallet_state_manager.main_wallet

    ph = await wallet_0.get_new_puzzlehash()
    _ = await wallet_1.get_new_puzzlehash()

    if trusted:
        wallet_node_0.config["trusted_peers"] = {
            full_node_api.full_node.server.node_id.hex(): full_node_api.full_node.server.node_id.hex()
        }
        wallet_node_1.config["trusted_peers"] = {
            full_node_api.full_node.server.node_id.hex(): full_node_api.full_node.server.node_id.hex()
        }
    else:
        wallet_node_0.config["trusted_peers"] = {}
        wallet_node_1.config["trusted_peers"] = {}

    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph))

    await server_0.start_client(PeerInfo("localhost", uint16(full_node_server._port)), None)
    await server_1.start_client(PeerInfo("localhost", uint16(full_node_server._port)), None)

    funds = sum(
        [calculate_pool_reward(uint32(i)) + calculate_base_farmer_reward(uint32(i)) for i in range(1, num_blocks - 1)]
    )

    await time_out_assert(10, wallet_0.get_unconfirmed_balance, funds)
    await time_out_assert(10, wallet_0.get_confirmed_balance, funds)

    api_0 = WalletRpcApi(wallet_node_0)
    await time_out_assert(10, wallet_node_0.wallet_state_manager.synced, True)
    await time_out_assert(10, wallet_node_1.wallet_state_manager.synced, True)
    nft_wallet_0 = await api_0.create_new_wallet(dict(wallet_type="nft_wallet", name="NFT WALLET 1"))
    assert isinstance(nft_wallet_0, dict)
    assert nft_wallet_0.get("success")
    nft_wallet_0_id = nft_wallet_0["wallet_id"]

    # mint NFT
    resp = await api_0.nft_mint_nft(
        {
            "wallet_id": nft_wallet_0_id,
            "artist_address": ph,
            "hash": "0xD4584AD463139FA8C0D9F68F4B59F185",
            "uris": ["https://www.chia.net/img/branding/chia-logo.svg"],
        }
    )

    assert resp.get("success")
    sb = resp["spend_bundle"]

    await time_out_assert_not_none(15, full_node_api.full_node.mempool_manager.get_spendbundle, sb.name())
    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph))
    time_left = 5.0
    coins_response = {}
    while time_left > 0:
        coins_response = await api_0.nft_get_nfts(dict(wallet_id=nft_wallet_0_id))
        if coins_response.get("nft_list"):
            break
        await asyncio.sleep(0.5)
        time_left -= 0.5
    assert coins_response["nft_list"], isinstance(coins_response, dict)
    assert coins_response.get("success")
    coins = coins_response["nft_list"]
    coin = coins[0].to_json_dict()
    assert coin["mint_height"] > 0
    assert coin["data_hash"] == "0xd4584ad463139fa8c0d9f68f4b59f185"
    assert coin["chain_info"] == disassemble(
        Program.to(
            [
                ("u", ["https://www.chia.net/img/branding/chia-logo.svg"]),
                ("h", hexstr_to_bytes("0xD4584AD463139FA8C0D9F68F4B59F185")),
                ("mu", []),
                ("mh", hexstr_to_bytes("00")),
                ("lu", []),
                ("lh", hexstr_to_bytes("00")),
                ("sn", uint64(1)),
                ("st", uint64(1)),
            ]
        )
    )
    nft_coin_id = coin["nft_coin_id"]
    await time_out_assert(15, wallet_0.get_pending_change_balance, 0)
    # add another URI
    tr1 = await api_0.nft_add_uri(
        {"wallet_id": nft_wallet_0_id, "nft_coin_id": nft_coin_id, "uri": "http://metadata", "key": "mu"}
    )

    assert isinstance(tr1, dict)
    assert tr1.get("success")
    coins_response = await api_0.nft_get_nfts(dict(wallet_id=nft_wallet_0_id))
    assert coins_response["nft_list"][0].pending_transaction
    sb = tr1["spend_bundle"]
    await time_out_assert_not_none(15, full_node_api.full_node.mempool_manager.get_spendbundle, sb.name())
    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph))
    # check that new URI was added
    time_left = 5.0
    while time_left > 0:
        coins_response = await api_0.nft_get_nfts(dict(wallet_id=nft_wallet_0_id))
        try:
            assert isinstance(coins_response, dict)
            assert coins_response.get("success")
            coins = coins_response["nft_list"]
            assert len(coins) == 1
            coin = coins[0].to_json_dict()
            assert coin["mint_height"] > 0
            uris = coin["data_uris"]
            assert len(uris) == 1
            assert "https://www.chia.net/img/branding/chia-logo.svg" in uris
            assert len(coin["metadata_uris"]) == 1
            assert "http://metadata" == coin["metadata_uris"][0]
            assert len(coin["license_uris"]) == 0
        except AssertionError:
            if time_left < 1:
                raise
        await asyncio.sleep(0.5)
        time_left -= 0.5

    # add yet another URI
    await time_out_assert(15, wallet_0.get_pending_change_balance, 0)
    nft_coin_id = coin["nft_coin_id"]
    tr1 = await api_0.nft_add_uri(
        {
            "wallet_id": nft_wallet_0_id,
            "nft_coin_id": nft_coin_id,
            "uri": "http://data",
            "key": "u",
        }
    )

    assert isinstance(tr1, dict)
    assert tr1.get("success")
    sb = tr1["spend_bundle"]
    await time_out_assert_not_none(15, full_node_api.full_node.mempool_manager.get_spendbundle, sb.name())
    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph))
    time_left = 5.0
    while time_left > 0:
        coins_response = await api_0.nft_get_nfts(dict(wallet_id=nft_wallet_0_id))
        try:
            assert isinstance(coins_response, dict)
            assert coins_response.get("success")
            coins = coins_response["nft_list"]
            assert len(coins) == 1
            coin = coins[0].to_json_dict()
            assert coin["mint_height"] > 0
            uris = coin["data_uris"]
            assert len(uris) == 2
            assert len(coin["metadata_uris"]) == 1
            assert "http://data" == coin["data_uris"][0]
        except AssertionError:
            if time_left < 1:
                raise
        await asyncio.sleep(0.5)
        time_left -= 0.5


@pytest.mark.parametrize(
    "trusted",
    [True, False],
)
@pytest.mark.asyncio
async def test_nft_with_did_wallet_creation(two_wallet_nodes: Any, trusted: Any) -> None:
    num_blocks = 3
    full_nodes, wallets = two_wallet_nodes
    full_node_api: FullNodeSimulator = full_nodes[0]
    full_node_server = full_node_api.server
    wallet_node_0, server_0 = wallets[0]
    wallet_node_1, server_1 = wallets[1]
    wallet_0 = wallet_node_0.wallet_state_manager.main_wallet
    api_0 = WalletRpcApi(wallet_node_0)
    ph = await wallet_0.get_new_puzzlehash()

    if trusted:
        wallet_node_0.config["trusted_peers"] = {
            full_node_api.full_node.server.node_id.hex(): full_node_api.full_node.server.node_id.hex()
        }
        wallet_node_1.config["trusted_peers"] = {
            full_node_api.full_node.server.node_id.hex(): full_node_api.full_node.server.node_id.hex()
        }
    else:
        wallet_node_0.config["trusted_peers"] = {}
        wallet_node_1.config["trusted_peers"] = {}

    await server_0.start_client(PeerInfo("localhost", uint16(full_node_server._port)), None)
    await server_1.start_client(PeerInfo("localhost", uint16(full_node_server._port)), None)

    for _ in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph))

    funds = sum(
        [calculate_pool_reward(uint32(i)) + calculate_base_farmer_reward(uint32(i)) for i in range(1, num_blocks - 1)]
    )

    await time_out_assert(10, wallet_0.get_unconfirmed_balance, funds)
    await time_out_assert(10, wallet_0.get_confirmed_balance, funds)
    did_wallet: DIDWallet = await DIDWallet.create_new_did_wallet(
        wallet_node_0.wallet_state_manager, wallet_0, uint64(1)
    )
    spend_bundle_list = await wallet_node_0.wallet_state_manager.tx_store.get_unconfirmed_for_wallet(wallet_0.id())

    spend_bundle = spend_bundle_list[0].spend_bundle
    await time_out_assert_not_none(5, full_node_api.full_node.mempool_manager.get_spendbundle, spend_bundle.name())

    for _ in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph))
    await time_out_assert(15, wallet_0.get_pending_change_balance, 0)
    hex_did_id = did_wallet.get_my_DID()

    res = await api_0.create_new_wallet(dict(wallet_type="nft_wallet", name="NFT WALLET 1", did_id=hex_did_id))
    assert isinstance(res, dict)
    assert res.get("success")
    nft_wallet_0_id = res["wallet_id"]

    # this shouldn't work
    res = await api_0.create_new_wallet(dict(wallet_type="nft_wallet", name="NFT WALLET 1", did_id=hex_did_id))
    assert isinstance(res, dict)
    assert res.get("success")
    assert res["wallet_id"] == nft_wallet_0_id
    # now create NFT wallet with P2 standard puzzle for inner puzzle
    res = await api_0.create_new_wallet(dict(wallet_type="nft_wallet", name="NFT WALLET 0"))
    assert isinstance(res, dict)
    assert res.get("success")
    nft_wallet_p2_puzzle = res["wallet_id"]
    assert nft_wallet_p2_puzzle != nft_wallet_0_id
    await time_out_assert(10, wallet_0.get_unconfirmed_balance, 5999999999999)
    await time_out_assert(10, wallet_0.get_confirmed_balance, 5999999999999)
    # Create a NFT with DID
    resp = await api_0.nft_mint_nft(
        {
            "wallet_id": nft_wallet_0_id,
            "hash": "0xD4584AD463139FA8C0D9F68F4B59F185",
            "uris": ["https://www.chia.net/img/branding/chia-logo.svg"],
        }
    )
    assert resp.get("success")
    sb = resp["spend_bundle"]

    # ensure hints are generated
    assert compute_memos(sb)
    await time_out_assert_not_none(5, full_node_api.full_node.mempool_manager.get_spendbundle, sb.name())

    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph))

    await time_out_assert(10, wallet_0.get_unconfirmed_balance, 7999999999999 - 1)
    await time_out_assert(10, wallet_0.get_confirmed_balance, 7999999999999 - 1)
    # Create a NFT without DID, this will go the unassigned NFT wallet
    resp = await api_0.nft_mint_nft(
        {
            "wallet_id": nft_wallet_0_id,
            "did_id": "",
            "hash": "0xD4584AD463139FA8C0D9F68F4B59F181",
            "uris": ["https://url1"],
        }
    )
    assert resp.get("success")
    sb = resp["spend_bundle"]

    # ensure hints are generated
    assert compute_memos(sb)
    await time_out_assert_not_none(5, full_node_api.full_node.mempool_manager.get_spendbundle, sb.name())

    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph))
    await time_out_assert(10, wallet_0.get_unconfirmed_balance, 13999999999998 - 1)
    await time_out_assert(10, wallet_0.get_confirmed_balance, 13999999999998 - 1)
    # Check DID NFT
    time_left = 5.0
    coins_response = {}
    while time_left > 0:
        coins_response = await api_0.nft_get_nfts(dict(wallet_id=nft_wallet_0_id))
        if coins_response.get("nft_list"):
            break
        await asyncio.sleep(0.5)
        time_left -= 0.5
    assert coins_response["nft_list"], isinstance(coins_response, dict)
    assert coins_response.get("success")
    coins = coins_response["nft_list"]
    assert len(coins) == 1
    did_nft = coins[0].to_json_dict()
    assert did_nft["mint_height"] > 0
    assert did_nft["supports_did"]
    assert did_nft["data_uris"][0] == "https://www.chia.net/img/branding/chia-logo.svg"
    assert did_nft["data_hash"] == "0xD4584AD463139FA8C0D9F68F4B59F185".lower()
    assert did_nft["owner_did"][2:] == hex_did_id
    assert did_nft["owner_pubkey"] is not None
    # Check unassigned NFT
    nft_wallets = await wallet_node_0.wallet_state_manager.get_all_wallet_info_entries(WalletType.NFT)
    assert len(nft_wallets) == 2
    coins_response = await api_0.nft_get_nfts(dict(wallet_id=nft_wallet_p2_puzzle))
    assert coins_response["nft_list"], isinstance(coins_response, dict)
    assert coins_response.get("success")
    coins = coins_response["nft_list"]
    assert len(coins) == 1
    non_did_nft = coins[0].to_json_dict()
    assert non_did_nft["mint_height"] > 0
    assert non_did_nft["supports_did"]
    assert non_did_nft["data_uris"][0] == "https://url1"
    assert non_did_nft["data_hash"] == "0xD4584AD463139FA8C0D9F68F4B59F181".lower()
    assert non_did_nft["owner_did"] is None
    assert non_did_nft["owner_pubkey"] is not None


@pytest.mark.parametrize(
    "trusted",
    [True, False],
)
@pytest.mark.asyncio
async def test_nft_rpc_mint(two_wallet_nodes: Any, trusted: Any) -> None:
    num_blocks = 3
    full_nodes, wallets = two_wallet_nodes
    full_node_api: FullNodeSimulator = full_nodes[0]
    full_node_server = full_node_api.server
    wallet_node_0, server_0 = wallets[0]
    wallet_node_1, server_1 = wallets[1]
    wallet_0 = wallet_node_0.wallet_state_manager.main_wallet
    wallet_1 = wallet_node_1.wallet_state_manager.main_wallet
    api_0 = WalletRpcApi(wallet_node_0)
    ph = await wallet_0.get_new_puzzlehash()
    ph1 = await wallet_1.get_new_puzzlehash()

    if trusted:
        wallet_node_0.config["trusted_peers"] = {
            full_node_api.full_node.server.node_id.hex(): full_node_api.full_node.server.node_id.hex()
        }
        wallet_node_1.config["trusted_peers"] = {
            full_node_api.full_node.server.node_id.hex(): full_node_api.full_node.server.node_id.hex()
        }
    else:
        wallet_node_0.config["trusted_peers"] = {}
        wallet_node_1.config["trusted_peers"] = {}

    await server_0.start_client(PeerInfo("localhost", uint16(full_node_server._port)), None)
    await server_1.start_client(PeerInfo("localhost", uint16(full_node_server._port)), None)

    for _ in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph))

    funds = sum(
        [calculate_pool_reward(uint32(i)) + calculate_base_farmer_reward(uint32(i)) for i in range(1, num_blocks - 1)]
    )

    await time_out_assert(10, wallet_0.get_unconfirmed_balance, funds)
    await time_out_assert(10, wallet_0.get_confirmed_balance, funds)
    did_wallet: DIDWallet = await DIDWallet.create_new_did_wallet(
        wallet_node_0.wallet_state_manager, wallet_0, uint64(1)
    )
    spend_bundle_list = await wallet_node_0.wallet_state_manager.tx_store.get_unconfirmed_for_wallet(wallet_0.id())

    spend_bundle = spend_bundle_list[0].spend_bundle
    await time_out_assert_not_none(5, full_node_api.full_node.mempool_manager.get_spendbundle, spend_bundle.name())

    for _ in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph))
    await time_out_assert(15, wallet_0.get_pending_change_balance, 0)
    hex_did_id = did_wallet.get_my_DID()

    res = await api_0.create_new_wallet(dict(wallet_type="nft_wallet", name="NFT WALLET 1", did_id=hex_did_id))
    assert isinstance(res, dict)
    assert res.get("success")
    nft_wallet_0_id = res["wallet_id"]

    await time_out_assert(10, wallet_0.get_unconfirmed_balance, 5999999999999)
    await time_out_assert(10, wallet_0.get_confirmed_balance, 5999999999999)
    # Create a NFT with DID
    royalty_address = ph1
    data_hash_param = "0xD4584AD463139FA8C0D9F68F4B59F185"
    license_uris = ["http://mylicenseuri"]
    license_hash = "0xcafef00d"
    meta_uris = ["http://metauri"]
    meta_hash = "0xdeadbeef"
    royalty_percentage = 200
    sn = 10
    st = 100
    resp = await api_0.nft_mint_nft(
        {
            "wallet_id": nft_wallet_0_id,
            "hash": data_hash_param,
            "uris": ["https://www.chia.net/img/branding/chia-logo.svg"],
            "license_uris": license_uris,
            "license_hash": license_hash,
            "meta_hash": meta_hash,
            "series_number": sn,
            "series_total": st,
            "meta_uris": meta_uris,
            "royalty_address": royalty_address,
            "target_address": ph,
            "royalty_percentage": royalty_percentage,
        }
    )
    assert resp.get("success")
    sb = resp["spend_bundle"]

    # ensure hints are generated
    assert compute_memos(sb)
    await time_out_assert_not_none(5, full_node_api.full_node.mempool_manager.get_spendbundle, sb.name())

    for i in range(1, num_blocks):
        await full_node_api.farm_new_transaction_block(FarmNewBlockProtocol(ph))
    await time_out_assert(10, wallet_0.get_unconfirmed_balance, 9999999999998)
    await time_out_assert(10, wallet_0.get_confirmed_balance, 9999999999998)
    time_left = 5.0
    coins_response = {}
    while time_left > 0:
        coins_response = await api_0.nft_get_nfts(dict(wallet_id=nft_wallet_0_id))
        if coins_response.get("nft_list"):
            break
        await asyncio.sleep(0.5)
        time_left -= 0.5
    assert coins_response["nft_list"], isinstance(coins_response, dict)
    assert coins_response.get("success")
    coins = coins_response["nft_list"]
    assert len(coins) == 1
    did_nft = coins[0]
    assert did_nft.royalty_puzzle_hash == royalty_address
    assert did_nft.data_hash == bytes.fromhex(data_hash_param[2:])
    assert did_nft.metadata_hash == bytes.fromhex(meta_hash[2:])
    assert did_nft.metadata_uris == meta_uris
    assert did_nft.license_uris == license_uris
    assert did_nft.license_hash == bytes.fromhex(license_hash[2:])
    assert did_nft.series_total == st
    assert did_nft.series_number == sn
    assert did_nft.royalty_percentage == royalty_percentage
