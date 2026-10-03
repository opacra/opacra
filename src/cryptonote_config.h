// Copyright (c) 2014-2022, The Monero Project
// 
// All rights reserved.
// 
// Redistribution and use in source and binary forms, with or without modification, are
// permitted provided that the following conditions are met:
// 
// 1. Redistributions of source code must retain the above copyright notice, this list of
//    conditions and the following disclaimer.
// 
// 2. Redistributions in binary form must reproduce the above copyright notice, this list
//    of conditions and the following disclaimer in the documentation and/or other
//    materials provided with the distribution.
// 
// 3. Neither the name of the copyright holder nor the names of its contributors may be
//    used to endorse or promote products derived from this software without specific
//    prior written permission.
// 
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
// EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
// MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL
// THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
// SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
// PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
// INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
// STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF
// THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
// 
// Parts of this file are originally copyright (c) 2012-2013 The Cryptonote developers

#pragma once

#include <cstdint>
#include <stdexcept>
#include <string>
#include <boost/uuid/uuid.hpp>

#define CRYPTONOTE_DNS_TIMEOUT_MS                       20000

#define CRYPTONOTE_MAX_BLOCK_NUMBER                     500000000
#define CRYPTONOTE_MAX_TX_SIZE                          1000000
#define CRYPTONOTE_MAX_TX_PER_BLOCK                     0x10000000
#define CRYPTONOTE_PUBLIC_ADDRESS_TEXTBLOB_VER          0
#define CRYPTONOTE_MINED_MONEY_UNLOCK_WINDOW            60
#define CURRENT_TRANSACTION_VERSION                     2
#define CURRENT_BLOCK_MAJOR_VERSION                     1
#define CURRENT_BLOCK_MINOR_VERSION                     0
// ---------------------------------------------------------------------------
// Opacra consensus parameters (differences from Monero are marked "Opacra:")
// ---------------------------------------------------------------------------
#define COIN_NAME                                       "Opacra"
#define COIN_TICKER                                     "OPCA"

// Opacra: blocks may be at most 3 minutes (6 block targets) ahead of a node's clock
// (Monero: 2 h).  LWMA treats a backwards step after a forward-dated block as a 1 s
// solve time, so a loose limit lets a few miners inflate difficulty; 180 s keeps
// the effect small.  Nodes should run NTP; a block that is only "too new" for
// this node's clock is rejected without penalising the peer that relayed it.
#define CRYPTONOTE_BLOCK_FUTURE_TIME_LIMIT              (60*3)

#define CRYPTONOTE_DEFAULT_TX_SPENDABLE_AGE             10  // 10 blocks = 5 minutes at 30 s

// Opacra: median-time-past window of 11 blocks (Monero: 60), as recommended for LWMA
#define BLOCKCHAIN_TIMESTAMP_CHECK_WINDOW               11

// Opacra emission: smooth curve over a 10,000,000 OPCA main supply, then a
// permanent tail emission.  reward = (MONEY_SUPPLY - generated) >> 22 per block,
// never less than TAIL_EMISSION_REWARD.  With 30 s blocks, half of the main
// supply is emitted in ~2.8 years; the tail starts after ~15 years.
#define MONEY_SUPPLY                                    ((uint64_t)10000000 * (uint64_t)1000000000000) // 10M OPCA in atomic units
#define EMISSION_SPEED_FACTOR_PER_BLOCK                 (22)
#define TAIL_EMISSION_REWARD                            ((uint64_t)50000000000) // 0.05 OPCA per block (~52,600 OPCA/year)
// Opacra launch slow start: block rewards ramp up linearly from 0 over the first
// SLOW_START_BLOCKS blocks (~7 days), so nobody can capture a large share of
// coins before the wider community has joined mining.
#define SLOW_START_BLOCKS                               ((uint64_t)20160)

// Opacra development fund: 5% of every block subsidy (the newly created coins, not
// transaction fees), from block 1 onwards with no end date, including tail emission.
// Paid as the last coinbase output to config::DEV_FUND_ADDRESS (per network) with a
// per-height key R_f carried as the coinbase's second transaction public key (see
// get_dev_fund_tx_key), so every node can check it and nobody can choose or reuse it.
// The fund's view key is published (config::DEV_FUND_VIEW_KEY) so anyone can audit the
// fund's income. Miners receive the other 95% plus all fees.
#define OPACRA_DEV_FUND_PERCENT                         5

// Opacra: block-size rules scaled to 30 s blocks so they match Monero per unit of real
// time (Monero: 300 kB per 2-minute block, 100-block and 100,000-block median windows).
// 75 kB every 30 s gives the same penalty-free room per minute (~40 typical transactions
// per block before blocks grow with demand), the same spam cost relative to the block
// reward, and the same time horizons: 3.3 hours short-term, 139 days long-term.
// Transactions may use at most half the minimum block weight (~36.9 kB, ~50 inputs);
// wallets split larger spends automatically.
#define CRYPTONOTE_REWARD_BLOCKS_WINDOW                 400
#define CRYPTONOTE_BLOCK_GRANTED_FULL_REWARD_ZONE_V2    60000 //size of block (bytes) after which reward for block calculated using block size
#define CRYPTONOTE_BLOCK_GRANTED_FULL_REWARD_ZONE_V1    20000 //size of block (bytes) after which reward for block calculated using block size - before first fork
#define CRYPTONOTE_BLOCK_GRANTED_FULL_REWARD_ZONE_V5    75000 //size of block (bytes) after which reward for block calculated using block size - second change, from v5 (Opacra: Monero 300000 / 4)
#define CRYPTONOTE_LONG_TERM_BLOCK_WEIGHT_WINDOW_SIZE   400000 // size in blocks of the long term block weight median window (Opacra: 139 days, as Monero's 100000 x 2 min)
#define CRYPTONOTE_SHORT_TERM_BLOCK_WEIGHT_SURGE_FACTOR 50
#define CRYPTONOTE_COINBASE_BLOB_RESERVED_SIZE          600
#define CRYPTONOTE_DISPLAY_DECIMAL_POINT                12
// COIN - number of smallest units in one coin
#define COIN                                            ((uint64_t)1000000000000) // pow(10, 12)

#define FEE_PER_KB_OLD                                  ((uint64_t)10000000000) // pow(10, 10)
#define FEE_PER_KB                                      ((uint64_t)2000000000) // 2 * pow(10, 9)
#define FEE_PER_BYTE                                    ((uint64_t)300000)
#define DYNAMIC_FEE_PER_KB_BASE_FEE                     ((uint64_t)2000000000) // 2 * pow(10,9)
#define DYNAMIC_FEE_PER_KB_BASE_BLOCK_REWARD            ((uint64_t)10000000000000) // 10 * pow(10,12)
#define DYNAMIC_FEE_PER_KB_BASE_FEE_V5                  ((uint64_t)2000000000 * (uint64_t)CRYPTONOTE_BLOCK_GRANTED_FULL_REWARD_ZONE_V2 / CRYPTONOTE_BLOCK_GRANTED_FULL_REWARD_ZONE_V5)
#define DYNAMIC_FEE_REFERENCE_TRANSACTION_WEIGHT         ((uint64_t)3000)

#define ORPHANED_BLOCKS_MAX_COUNT                       100


// Opacra: 30-second blocks for every block version
#define DIFFICULTY_TARGET_V2                            30  // seconds
#define DIFFICULTY_TARGET_V1                            30  // seconds
// Opacra: LWMA-1 difficulty (zawy12) instead of Monero's sorted/cut window.
// N = 60 blocks (30 minutes); the algorithm reads the last N+1 blocks.  A short
// window reacts within ~60 blocks to hash-rate jumps (rented or profit-switching
// hash power), which is the main difficulty risk for a young PoW chain.
#define DIFFICULTY_WINDOW                               60  // blocks (LWMA N)
#define DIFFICULTY_LAG                                  0   // unused with LWMA
#define DIFFICULTY_CUT                                  0   // unused with LWMA
#define DIFFICULTY_BLOCKS_COUNT                         (DIFFICULTY_WINDOW + 1)
// Until the chain has this many blocks (after genesis) difficulty is fixed at
// DIFFICULTY_STARTUP_GUESS; LWMA then adapts with the blocks available.
#define DIFFICULTY_STARTUP_BLOCKS                       12
#define DIFFICULTY_STARTUP_GUESS                        10000

// Opacra: side-chain blocks must have a difficulty of at least 1/4 of the main chain's
// next difficulty, once both are past the first two LWMA windows (122 blocks, ~1 hour).
// Stops attackers from walking a side chain's difficulty down to nothing (see
// alt_difficulty_acceptable() in difficulty.cpp). There is no limit on reorg depth.
#define OPACRA_ALT_MIN_DIFFICULTY_DIVISOR               4
#define OPACRA_ALT_MIN_DIFFICULTY_FROM_HEIGHT           (2 * DIFFICULTY_BLOCKS_COUNT)


#define CRYPTONOTE_LOCKED_TX_ALLOWED_DELTA_SECONDS_V1   DIFFICULTY_TARGET_V1 * CRYPTONOTE_LOCKED_TX_ALLOWED_DELTA_BLOCKS
#define CRYPTONOTE_LOCKED_TX_ALLOWED_DELTA_SECONDS_V2   DIFFICULTY_TARGET_V2 * CRYPTONOTE_LOCKED_TX_ALLOWED_DELTA_BLOCKS
#define CRYPTONOTE_LOCKED_TX_ALLOWED_DELTA_BLOCKS       1


#define DIFFICULTY_BLOCKS_ESTIMATE_TIMESPAN             DIFFICULTY_TARGET_V1 //just alias; used by tests


#define BLOCKS_IDS_SYNCHRONIZING_DEFAULT_COUNT          10000  //by default, blocks ids count in synchronizing
#define BLOCKS_IDS_SYNCHRONIZING_MAX_COUNT              25000  //max blocks ids count in synchronizing
#define BLOCKS_SYNCHRONIZING_DEFAULT_COUNT_PRE_V4       100    //by default, blocks count in blocks downloading
#define BLOCKS_SYNCHRONIZING_DEFAULT_COUNT              20     //by default, blocks count in blocks downloading
#define BLOCKS_SYNCHRONIZING_MAX_COUNT                  2048   //must be a power of 2, greater than 128, equal to SEEDHASH_EPOCH_BLOCKS

#define CRYPTONOTE_MEMPOOL_TX_LIVETIME                    (86400*3) //seconds, three days
#define CRYPTONOTE_MEMPOOL_TX_FROM_ALT_BLOCK_LIVETIME     604800 //seconds, one week


#define CRYPTONOTE_DANDELIONPP_STEMS              2 // number of outgoing stem connections per epoch
#define CRYPTONOTE_DANDELIONPP_FLUFF_PROBABILITY 20 // out of 100
#define CRYPTONOTE_DANDELIONPP_MIN_EPOCH         10 // minutes
#define CRYPTONOTE_DANDELIONPP_EPOCH_RANGE       30 // seconds
#define CRYPTONOTE_DANDELIONPP_FLUSH_AVERAGE      5 // seconds average for poisson distributed fluff flush
#define CRYPTONOTE_DANDELIONPP_EMBARGO_AVERAGE   39 // seconds (see tx_pool.cpp for more info)

// see src/cryptonote_protocol/levin_notify.cpp
#define CRYPTONOTE_NOISE_MIN_EPOCH                      5      // minutes
#define CRYPTONOTE_NOISE_EPOCH_RANGE                    30     // seconds
#define CRYPTONOTE_NOISE_MIN_DELAY                      10     // seconds
#define CRYPTONOTE_NOISE_DELAY_RANGE                    5      // seconds
#define CRYPTONOTE_NOISE_BYTES                          3*1024 // 3 KiB
#define CRYPTONOTE_NOISE_CHANNELS                       2      // Max outgoing connections per zone used for noise/covert sending

// Both below are in seconds. The idea is to delay forwarding from i2p/tor
// to ipv4/6, such that 2+ incoming connections _could_ have sent the tx
#define CRYPTONOTE_FORWARD_DELAY_BASE (CRYPTONOTE_NOISE_MIN_DELAY + CRYPTONOTE_NOISE_DELAY_RANGE)
#define CRYPTONOTE_FORWARD_DELAY_AVERAGE (CRYPTONOTE_FORWARD_DELAY_BASE + (CRYPTONOTE_FORWARD_DELAY_BASE / 2))

#define CRYPTONOTE_MAX_FRAGMENTS                        20 // ~20 * NOISE_BYTES max payload size for covert/noise send

#define COMMAND_RPC_GET_BLOCKS_FAST_MAX_BLOCK_COUNT     1000
#define COMMAND_RPC_GET_BLOCKS_FAST_MAX_TX_COUNT        20000
#define DEFAULT_RPC_MAX_CONNECTIONS_PER_PUBLIC_IP       3
#define DEFAULT_RPC_MAX_CONNECTIONS_PER_PRIVATE_IP      25
#define DEFAULT_RPC_MAX_CONNECTIONS                     100
#define DEFAULT_RPC_SOFT_LIMIT_SIZE                     25 * 1024 * 1024 // 25 MiB
#define MAX_RPC_CONTENT_LENGTH                          1048576 // 1 MB

#define P2P_LOCAL_WHITE_PEERLIST_LIMIT                  1000
#define P2P_LOCAL_GRAY_PEERLIST_LIMIT                   5000

#define P2P_DEFAULT_CONNECTIONS_COUNT                   12
#define P2P_DEFAULT_HANDSHAKE_INTERVAL                  60           //secondes
#define P2P_DEFAULT_PACKET_MAX_SIZE                     50000000     //50000000 bytes maximum packet size
#define P2P_DEFAULT_PEERS_IN_HANDSHAKE                  250
#define P2P_MAX_PEERS_IN_HANDSHAKE                      250
#define P2P_DEFAULT_CONNECTION_TIMEOUT                  5000       //5 seconds
#define P2P_DEFAULT_SOCKS_CONNECT_TIMEOUT               45         // seconds
#define P2P_DEFAULT_PING_CONNECTION_TIMEOUT             2000       //2 seconds
#define P2P_DEFAULT_INVOKE_TIMEOUT                      60*2*1000  //2 minutes
#define P2P_DEFAULT_HANDSHAKE_INVOKE_TIMEOUT            5000       //5 seconds
#define P2P_DEFAULT_WHITELIST_CONNECTIONS_PERCENT       70
#define P2P_DEFAULT_ANCHOR_CONNECTIONS_COUNT            2
#define P2P_DEFAULT_SYNC_SEARCH_CONNECTIONS_COUNT       2
#define P2P_DEFAULT_LIMIT_RATE_UP                       8192       // kB/s
#define P2P_DEFAULT_LIMIT_RATE_DOWN                     32768       // kB/s

#define P2P_FAILED_ADDR_FORGET_SECONDS                  (60*60)     //1 hour
#define P2P_IP_BLOCKTIME                                (60*60*24)  //24 hour
#define P2P_IP_FAILS_BEFORE_BLOCK                       10
#define P2P_IDLE_CONNECTION_KILL_INTERVAL               (5*60) //5 minutes

#define P2P_SUPPORT_FLAG_FLUFFY_BLOCKS                  0x01
#define P2P_SUPPORT_FLAGS                               P2P_SUPPORT_FLAG_FLUFFY_BLOCKS

#define RPC_IP_FAILS_BEFORE_BLOCK                       3

#define CRYPTONOTE_NAME                         "opacra"
#define CRYPTONOTE_BLOCKCHAINDATA_FILENAME      "data.mdb"
#define CRYPTONOTE_BLOCKCHAINDATA_LOCK_FILENAME "lock.mdb"
#define P2P_NET_DATA_FILENAME                   "p2pstate.bin"
#define RPC_PAYMENTS_DATA_FILENAME              "rpcpayments.bin"
#define MINER_CONFIG_FILE_NAME                  "miner_conf.json"

#define THREAD_STACK_SIZE                       5 * 1024 * 1024

#define HF_VERSION_DYNAMIC_FEE                  4
#define HF_VERSION_MIN_MIXIN_4                  6
#define HF_VERSION_MIN_MIXIN_6                  7
#define HF_VERSION_MIN_MIXIN_10                 8
#define HF_VERSION_MIN_MIXIN_15                 15
#define HF_VERSION_ENFORCE_RCT                  6
#define HF_VERSION_PER_BYTE_FEE                 8
#define HF_VERSION_SMALLER_BP                   10
#define HF_VERSION_LONG_TERM_BLOCK_WEIGHT       10
#define HF_VERSION_MIN_2_OUTPUTS                12
#define HF_VERSION_MIN_V2_COINBASE_TX           12
#define HF_VERSION_SAME_MIXIN                   12
#define HF_VERSION_REJECT_SIGS_IN_COINBASE      12
#define HF_VERSION_ENFORCE_MIN_AGE              12
#define HF_VERSION_EFFECTIVE_SHORT_TERM_MEDIAN_IN_PENALTY 12
#define HF_VERSION_EXACT_COINBASE               13
#define HF_VERSION_CLSAG                        13
#define HF_VERSION_DETERMINISTIC_UNLOCK_TIME    13
#define HF_VERSION_BULLETPROOF_PLUS             15
#define HF_VERSION_VIEW_TAGS                    15
#define HF_VERSION_2021_SCALING                 15

#define PER_KB_FEE_QUANTIZATION_DECIMALS        8
#define CRYPTONOTE_SCALING_2021_FEE_ROUNDING_PLACES 2

#define HASH_OF_HASHES_STEP                     512

#define DEFAULT_TXPOOL_MAX_WEIGHT               648000000ull // 3 days of full 75 kB blocks every 30 s, in bytes

#define BULLETPROOF_MAX_OUTPUTS                 16
#define BULLETPROOF_PLUS_MAX_OUTPUTS            16

#define CRYPTONOTE_PRUNING_STRIPE_SIZE          4096 // the smaller, the smoother the increase
#define CRYPTONOTE_PRUNING_LOG_STRIPES          3 // the higher, the more space saved
#define CRYPTONOTE_PRUNING_TIP_BLOCKS           5500 // the smaller, the more space saved

#define RPC_CREDITS_PER_HASH_SCALE ((float)(1<<24))

#define DNS_BLOCKLIST_LIFETIME (86400 * 8)

//The limit is enough for the mandatory transaction content with 16 outputs (547 bytes),
//a custom tag (1 byte) and up to 32 bytes of custom data for each recipient.
// (1+32) + (1+1+16*32) + (1+16*32) = 1060
#define MAX_TX_EXTRA_SIZE                       1060

// New constants are intended to go here
namespace config
{
  uint64_t const DEFAULT_FEE_ATOMIC_XMR_PER_KB = 500; // Just a placeholder!  Change me!
  uint8_t const FEE_CALCULATION_MAX_RETRIES = 10;
  uint64_t const DEFAULT_DUST_THRESHOLD = ((uint64_t)2000000000); // 2 * pow(10, 9)
  uint64_t const BASE_REWARD_CLAMP_THRESHOLD = ((uint64_t)100000000); // pow(10, 8)

  // Opacra mainnet identity (regenerate with contrib/coin-identity/coinid.py before launch)
  uint64_t const CRYPTONOTE_PUBLIC_ADDRESS_BASE58_PREFIX = 30598;            // addresses start with "Pa"
  uint64_t const CRYPTONOTE_PUBLIC_INTEGRATED_ADDRESS_BASE58_PREFIX = 24839; // integrated addresses start with "Pi"
  uint64_t const CRYPTONOTE_PUBLIC_SUBADDRESS_BASE58_PREFIX = 22408;         // subaddresses start with "Ps"
  uint16_t const P2P_DEFAULT_PORT = 29960;
  uint16_t const RPC_DEFAULT_PORT = 29961;
  uint16_t const ZMQ_RPC_DEFAULT_PORT = 29962;
  boost::uuids::uuid const NETWORK_ID = { {
      0xBC, 0x2D, 0x89, 0x3E, 0x96, 0xB8, 0xF6, 0x91, 0x19, 0x9F, 0x37, 0x3C, 0xE5, 0xBC, 0x47, 0x18
    } };
  // Genesis coinbase: reward = MONEY_SUPPLY >> EMISSION_SPEED_FACTOR_PER_BLOCK, paid to an
  // unspendable key; tx extra carries the message
  // "Opacra mainnet genesis | 2026-10-02 | Private by default, auditable by choice."
  std::string const GENESIS_TX = "013c01ff0001a7a4b0e4b145029f76646388993c91ca84209b815bff6467bc631500f3a86c2aa332572de9d94d7101aa0a93586b60454f425d180db01995ed2e688be793cbef62f08e324821400609024e4f7061637261206d61696e6e65742067656e65736973207c20323032362d31302d3032207c20507269766174652062792064656661756c742c20617564697461626c652062792063686f6963652e";
  uint32_t const GENESIS_NONCE = 10000;
  // Development fund: receives OPACRA_DEV_FUND_PERCENT of every block subsidy. Must be a
  // standard address. The project's offline mainnet fund wallet (created 3 Oct 2026).
  std::string const DEV_FUND_ADDRESS = "Pa2TDAomGjCM7y1s2S2APLcrGqhkddoyRgsx2Miqu2eRJKLcayF84VPea6SMcSDnxeg78smaG9fBeTpVj5EL1wbU81m8HT6rPW";
  // The fund's secret view key is public on purpose: anyone can import it into a
  // view-only wallet to audit every payment the fund receives. Nodes check at startup
  // that it belongs to DEV_FUND_ADDRESS.
  std::string const DEV_FUND_VIEW_KEY = "69416fd0f64a86d2f3053d9ec1ed072daa83e8970d5fb7c63ab81657834a0101";

  // Hash domain separators
  const char HASH_KEY_BULLETPROOF_EXPONENT[] = "bulletproof";
  const char HASH_KEY_BULLETPROOF_PLUS_EXPONENT[] = "bulletproof_plus";
  const char HASH_KEY_BULLETPROOF_PLUS_TRANSCRIPT[] = "bulletproof_plus_transcript";
  const char HASH_KEY_RINGDB[] = "ringdsb";
  const char HASH_KEY_SUBADDRESS[] = "SubAddr";
  const unsigned char HASH_KEY_ENCRYPTED_PAYMENT_ID = 0x8d;
  const unsigned char HASH_KEY_WALLET = 0x8c;
  const unsigned char HASH_KEY_WALLET_CACHE = 0x8d;
  const unsigned char HASH_KEY_BACKGROUND_CACHE = 0x8e;
  const unsigned char HASH_KEY_BACKGROUND_KEYS_FILE = 0x8f;
  const unsigned char HASH_KEY_RPC_PAYMENT_NONCE = 0x58;
  const unsigned char HASH_KEY_MEMORY = 'k';
  const unsigned char HASH_KEY_MULTISIG[] = {'M', 'u', 'l', 't' , 'i', 's', 'i', 'g', 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
  const unsigned char HASH_KEY_MULTISIG_KEY_AGGREGATION[] = "Multisig_key_agg";
  const unsigned char HASH_KEY_CLSAG_ROUND_MULTISIG[] = "CLSAG_round_ms_merge_factor";
  const unsigned char HASH_KEY_TXPROOF_V2[] = "TXPROOF_V2";
  const unsigned char HASH_KEY_CLSAG_ROUND[] = "CLSAG_round";
  const unsigned char HASH_KEY_CLSAG_AGG_0[] = "CLSAG_agg_0";
  const unsigned char HASH_KEY_CLSAG_AGG_1[] = "CLSAG_agg_1";
  const char HASH_KEY_MESSAGE_SIGNING[] = "OpacraMessageSignature"; // Opacra: own domain, no cross-chain replay
  const unsigned char HASH_KEY_MM_SLOT = 'm';
  const constexpr char HASH_KEY_MULTISIG_TX_PRIVKEYS_SEED[] = "multisig_tx_privkeys_seed";
  const constexpr char HASH_KEY_MULTISIG_TX_PRIVKEYS[] = "multisig_tx_privkeys";
  const constexpr char HASH_KEY_TXHASH_AND_MIXRING[] = "txhash_and_mixring";

  // Multisig
  const uint32_t MULTISIG_MAX_SIGNERS{16};

  namespace testnet
  {
    uint64_t const CRYPTONOTE_PUBLIC_ADDRESS_BASE58_PREFIX = 8479;             // "Te"
    uint64_t const CRYPTONOTE_PUBLIC_INTEGRATED_ADDRESS_BASE58_PREFIX = 11935; // "Tf"
    uint64_t const CRYPTONOTE_PUBLIC_SUBADDRESS_BASE58_PREFIX = 15263;         // "Tg"
    uint16_t const P2P_DEFAULT_PORT = 29970;
    uint16_t const RPC_DEFAULT_PORT = 29971;
    uint16_t const ZMQ_RPC_DEFAULT_PORT = 29972;
    boost::uuids::uuid const NETWORK_ID = { {
        0x8F, 0xB1, 0x39, 0x6E, 0xD4, 0x92, 0xE2, 0xE5, 0xC9, 0x68, 0x25, 0x15, 0x17, 0x0B, 0x5F, 0x91
      } };
    std::string const GENESIS_TX = "013c01ff0001a7a4b0e4b145029f2f9831645742126ae225f9660bf52079f95792919a2a6a8bd9acb57eaf6f514601c3f0f15ec3eb910212e78b99ff0a0a701fb9d578e7942ee4f30956786de8604902234f706163726120746573746e65742067656e65736973207c20323032362d31302d3032";
    uint32_t const GENESIS_NONCE = 10001;
    // Development fund: receives OPACRA_DEV_FUND_PERCENT of every block subsidy. Must be a
    // standard address. The project's offline testnet fund wallet (created 3 Oct 2026).
    std::string const DEV_FUND_ADDRESS = "Te1fW4xtitRA7yzFYdkToMJYcxgYdt4BzWswBjAX3HS4CUMFmMEcWScL6QMhoYfYLs4yCR9Cma9Qv31e3eLCF7Du33Wb2ABRJ";
    // The fund's secret view key is public on purpose: anyone can import it into a
    // view-only wallet to audit every payment the fund receives. Nodes check at startup
    // that it belongs to DEV_FUND_ADDRESS.
    std::string const DEV_FUND_VIEW_KEY = "cdf9882d2797df566b2974ee5cc5873c2c97da0addeb8a47018df536858c6f0b";
  }

  namespace stagenet
  {
    uint64_t const CRYPTONOTE_PUBLIC_ADDRESS_BASE58_PREFIX = 28440;            // "Sa"
    uint64_t const CRYPTONOTE_PUBLIC_INTEGRATED_ADDRESS_BASE58_PREFIX = 22809; // "Si"
    uint64_t const CRYPTONOTE_PUBLIC_SUBADDRESS_BASE58_PREFIX = 20378;         // "Ss"
    uint16_t const P2P_DEFAULT_PORT = 29980;
    uint16_t const RPC_DEFAULT_PORT = 29981;
    uint16_t const ZMQ_RPC_DEFAULT_PORT = 29982;
    boost::uuids::uuid const NETWORK_ID = { {
        0x0F, 0x57, 0xC4, 0xD1, 0xD3, 0x44, 0x63, 0xD1, 0x3D, 0x6F, 0xFD, 0x9D, 0xD5, 0xF2, 0x40, 0x42
      } };
    std::string const GENESIS_TX = "013c01ff0001a7a4b0e4b14502f7fcb1005aa2e46c3e4626b211d76d3cf0d12ff3dafdbc7b4c7c4506c524c4294701332eb62e164cd880959de076bf659ba3b9cb01e6a941ecde1a8a7d21fe178c8f02244f70616372612073746167656e65742067656e65736973207c20323032362d31302d3032";
    uint32_t const GENESIS_NONCE = 10002;
    // Development fund: receives OPACRA_DEV_FUND_PERCENT of every block subsidy. Must be a
    // standard address. PLACEHOLDER (development identity): replace with the project's
    // offline fund wallet before the public testnet / mainnet.
    std::string const DEV_FUND_ADDRESS = "Sa1CJsHUjXFaNSytLRr2h1U3wRxcZi36eimPkSUJ87AuaAEwhhg9UoLh9dYcHczjj97HNVLEGCcwdQ2drVLvk25X7BnkNKWE8F";
    // The fund's secret view key is public on purpose: anyone can import it into a
    // view-only wallet to audit every payment the fund receives. Nodes check at startup
    // that it belongs to DEV_FUND_ADDRESS.
    std::string const DEV_FUND_VIEW_KEY = "1acfcf08c41616dcf9a14247edf520a4e16430ed4525f544476f2e711bd7600f";
  }
}

namespace cryptonote
{
  enum network_type : uint8_t
  {
    MAINNET = 0,
    TESTNET,
    STAGENET,
    FAKECHAIN,
    UNDEFINED = 255
  };
  struct config_t
  {
    uint64_t const CRYPTONOTE_PUBLIC_ADDRESS_BASE58_PREFIX;
    uint64_t const CRYPTONOTE_PUBLIC_INTEGRATED_ADDRESS_BASE58_PREFIX;
    uint64_t const CRYPTONOTE_PUBLIC_SUBADDRESS_BASE58_PREFIX;
    uint16_t const P2P_DEFAULT_PORT;
    uint16_t const RPC_DEFAULT_PORT;
    uint16_t const ZMQ_RPC_DEFAULT_PORT;
    boost::uuids::uuid const NETWORK_ID;
    std::string const GENESIS_TX;
    uint32_t const GENESIS_NONCE;
  };
  inline const config_t& get_config(network_type nettype)
  {
    static const config_t mainnet = {
      ::config::CRYPTONOTE_PUBLIC_ADDRESS_BASE58_PREFIX,
      ::config::CRYPTONOTE_PUBLIC_INTEGRATED_ADDRESS_BASE58_PREFIX,
      ::config::CRYPTONOTE_PUBLIC_SUBADDRESS_BASE58_PREFIX,
      ::config::P2P_DEFAULT_PORT,
      ::config::RPC_DEFAULT_PORT,
      ::config::ZMQ_RPC_DEFAULT_PORT,
      ::config::NETWORK_ID,
      ::config::GENESIS_TX,
      ::config::GENESIS_NONCE
    };
    static const config_t testnet = {
      ::config::testnet::CRYPTONOTE_PUBLIC_ADDRESS_BASE58_PREFIX,
      ::config::testnet::CRYPTONOTE_PUBLIC_INTEGRATED_ADDRESS_BASE58_PREFIX,
      ::config::testnet::CRYPTONOTE_PUBLIC_SUBADDRESS_BASE58_PREFIX,
      ::config::testnet::P2P_DEFAULT_PORT,
      ::config::testnet::RPC_DEFAULT_PORT,
      ::config::testnet::ZMQ_RPC_DEFAULT_PORT,
      ::config::testnet::NETWORK_ID,
      ::config::testnet::GENESIS_TX,
      ::config::testnet::GENESIS_NONCE
    };
    static const config_t stagenet = {
      ::config::stagenet::CRYPTONOTE_PUBLIC_ADDRESS_BASE58_PREFIX,
      ::config::stagenet::CRYPTONOTE_PUBLIC_INTEGRATED_ADDRESS_BASE58_PREFIX,
      ::config::stagenet::CRYPTONOTE_PUBLIC_SUBADDRESS_BASE58_PREFIX,
      ::config::stagenet::P2P_DEFAULT_PORT,
      ::config::stagenet::RPC_DEFAULT_PORT,
      ::config::stagenet::ZMQ_RPC_DEFAULT_PORT,
      ::config::stagenet::NETWORK_ID,
      ::config::stagenet::GENESIS_TX,
      ::config::stagenet::GENESIS_NONCE
    };
    switch (nettype)
    {
      case MAINNET: return mainnet;
      case TESTNET: return testnet;
      case STAGENET: return stagenet;
      case FAKECHAIN: return mainnet;
      default: throw std::runtime_error("Invalid network type");
    }
  };
}
