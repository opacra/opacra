// Copyright (c) 2026, The Opacra Project
// BSD-3-Clause, see LICENSE.
//
// Regression tests for the consensus rules Opacra changed relative to Monero:
// per-block emission and tail, launch slow start (reward ramp and block-weight cap),
// LWMA-1 difficulty, and the compact hard-fork tables.  No test framework needed:
//   make opacra_consensus_tests && ./bin/opacra_consensus_tests   (exit code 0 = pass)

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <sstream>
#include <string>
#include <vector>

#include "cryptonote_config.h"
#include "cryptonote_basic/cryptonote_basic_impl.h"
#include "cryptonote_basic/difficulty.h"
#include "hardforks/hardforks.h"
#include "cryptonote_core/cryptonote_tx_utils.h"
#include "cryptonote_basic/cryptonote_format_utils.h"
#include "string_tools.h"
#include "int-util.h"

using cryptonote::difficulty_type;

static int failures = 0, checks = 0;

template <typename T>
static std::string str(const T &v) { std::ostringstream o; o << v; return o.str(); }

#define EXPECT(cond) do { ++checks; if (!(cond)) { std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); ++failures; } } while (0)
#define EXPECT_EQ(a, b) do { ++checks; const auto _a = (a); const auto _b = (b); if (!(_a == _b)) { \
  std::printf("FAIL %s:%d: %s == %s  (%s vs %s)\n", __FILE__, __LINE__, #a, #b, str(_a).c_str(), str(_b).c_str()); ++failures; } } while (0)

static const uint64_t FULL = 2384185791015ull;       // 10^19 >> 22
static const uint64_t PENALISED = 1788139343261ull;  // FULL at 1.5x the median: floor(floor(FULL*150000*450000/300000)/300000)

static void test_emission()
{
  uint64_t r = 0;
  EXPECT(cryptonote::get_block_reward(0, 0, 0, r, 16));
  EXPECT_EQ(r, FULL);
  EXPECT_EQ(r, MONEY_SUPPLY >> EMISSION_SPEED_FACTOR_PER_BLOCK);
  // genesis (v1) uses the same per-block rule
  EXPECT(cryptonote::get_block_reward(0, 0, 0, r, 1));
  EXPECT_EQ(r, FULL);
  // one block later the remaining supply is smaller, so is the reward
  EXPECT(cryptonote::get_block_reward(0, 0, FULL, r, 16));
  EXPECT_EQ(r, (MONEY_SUPPLY - FULL) >> 22);
  // tail emission when the curve falls below 0.05 OPCA, and at / past the cap
  EXPECT(cryptonote::get_block_reward(0, 0, MONEY_SUPPLY - (TAIL_EMISSION_REWARD << 22) + 1, r, 16));
  EXPECT_EQ(r, TAIL_EMISSION_REWARD);
  EXPECT(cryptonote::get_block_reward(0, 0, MONEY_SUPPLY, r, 16));
  EXPECT_EQ(r, TAIL_EMISSION_REWARD);
  EXPECT(cryptonote::get_block_reward(0, 0, MONEY_SUPPLY + 12345, r, 16)); // defensive: no underflow
  EXPECT_EQ(r, TAIL_EMISSION_REWARD);
  // the daemon's generated-coins total keeps counting past MONEY_SUPPLY (tail emission)
  EXPECT(cryptonote::get_block_reward(0, 0, MONEY_SUPPLY + MONEY_SUPPLY / 2, r, 16)); // (2x would overflow uint64)
  EXPECT_EQ(r, TAIL_EMISSION_REWARD);
  EXPECT(cryptonote::get_block_reward(0, 0, UINT64_MAX, r, 16));
  EXPECT_EQ(r, TAIL_EMISSION_REWARD);
  // Monero's size penalty still applies: 1.5x the median loses a quarter of the reward
  EXPECT(cryptonote::get_block_reward(300000, 450000, 0, r, 16));
  EXPECT_EQ(r, PENALISED);
  EXPECT(!cryptonote::get_block_reward(300000, 600001, 0, r, 16)); // over 2x median: invalid
}

static void test_slow_start()
{
  EXPECT_EQ(cryptonote::apply_slow_start(FULL, 0), FULL);                 // genesis exempt
  EXPECT_EQ(cryptonote::apply_slow_start(FULL, 1), FULL / SLOW_START_BLOCKS);
  EXPECT_EQ(cryptonote::apply_slow_start(FULL, SLOW_START_BLOCKS / 2), FULL / 2);
  EXPECT_EQ(cryptonote::apply_slow_start(FULL, SLOW_START_BLOCKS - 1), (uint64_t)((unsigned __int128)FULL * (SLOW_START_BLOCKS - 1) / SLOW_START_BLOCKS));
  EXPECT_EQ(cryptonote::apply_slow_start(FULL, SLOW_START_BLOCKS), FULL);
  EXPECT_EQ(cryptonote::apply_slow_start(FULL, 5000000), FULL);
  EXPECT_EQ(cryptonote::apply_slow_start(~0ull, 20159), (uint64_t)((unsigned __int128)(~0ull) * 20159 / SLOW_START_BLOCKS)); // no overflow

  uint64_t r = 0;
  // during the ramp: at or below the effective median is fine, above it is refused
  EXPECT(cryptonote::get_block_reward_at_height(300000, 300000, FULL, r, 16, 100));
  EXPECT_EQ(r, cryptonote::apply_slow_start((MONEY_SUPPLY - FULL) >> 22, 100));
  EXPECT(!cryptonote::get_block_reward_at_height(300000, 300001, FULL, r, 16, 100));
  EXPECT(!cryptonote::get_block_reward_at_height(0, 75001, FULL, r, 16, SLOW_START_BLOCKS - 1)); // median floored at 75 kB
  EXPECT(cryptonote::get_block_reward_at_height(0, 75000, FULL, r, 16, SLOW_START_BLOCKS - 1));
  // block-size rules scaled to 30 s blocks (Monero's values per unit of time)
  EXPECT_EQ(cryptonote::get_min_block_weight(16), size_t(75000));
  EXPECT_EQ(CRYPTONOTE_REWARD_BLOCKS_WINDOW * DIFFICULTY_TARGET_V2, 100 * 120);
  EXPECT_EQ(CRYPTONOTE_LONG_TERM_BLOCK_WEIGHT_WINDOW_SIZE * DIFFICULTY_TARGET_V2, 100000 * 120);
  EXPECT_EQ(CRYPTONOTE_BLOCK_GRANTED_FULL_REWARD_ZONE_V5 * 120 / DIFFICULTY_TARGET_V2, 300000);
  // below the old 300 kB floor but above the new one: allowed only with the penalty after the ramp
  EXPECT(cryptonote::get_block_reward_at_height(0, 112500, 0, r, 16, SLOW_START_BLOCKS));
  EXPECT_EQ(r, (uint64_t)(((unsigned __int128)FULL * 37500 * 112500 / 75000) / 75000));
  // after the ramp Monero's penalty zone opens again
  EXPECT(cryptonote::get_block_reward_at_height(300000, 450000, 0, r, 16, SLOW_START_BLOCKS));
  EXPECT_EQ(r, PENALISED);
  // the ramp's size cap does not apply to genesis (v1: 20 kB median floor, so 30 kB is in
  // Monero's penalty zone, which is allowed there but refused at heights inside the ramp)
  EXPECT(cryptonote::get_block_reward_at_height(0, 30000, 0, r, 1, 0));
  EXPECT(!cryptonote::get_block_reward_at_height(0, 30000, 0, r, 1, 1));
}

static difficulty_type lwma(const std::vector<uint64_t> &ts, const std::vector<difficulty_type> &cd)
{
  return cryptonote::next_difficulty(ts, cd, DIFFICULTY_TARGET_V2);
}

static void series(size_t n, uint64_t spacing, difficulty_type d, std::vector<uint64_t> &ts, std::vector<difficulty_type> &cd)
{
  ts.clear(); cd.clear();
  difficulty_type cum = 1;
  for (size_t i = 0; i < n; ++i) { ts.push_back(1000000 + i * spacing); cum += d; cd.push_back(cum); }
}

static void test_lwma()
{
  std::vector<uint64_t> ts; std::vector<difficulty_type> cd;
  EXPECT_EQ(lwma(ts, cd), difficulty_type(1));                           // heights 0 and 1
  series(DIFFICULTY_STARTUP_BLOCKS - 1, 30, 5, ts, cd);
  EXPECT_EQ(lwma(ts, cd), difficulty_type(DIFFICULTY_STARTUP_GUESS));    // startup guess
  // steady state: blocks exactly on target -> 0.99 x difficulty (LWMA-1's bias correction)
  series(DIFFICULTY_WINDOW + 1, 30, 100000, ts, cd);
  EXPECT_EQ(lwma(ts, cd), difficulty_type(99000));
  // twice as slow -> half the difficulty
  series(DIFFICULTY_WINDOW + 1, 60, 100000, ts, cd);
  EXPECT_EQ(lwma(ts, cd), difficulty_type(49500));
  // all timestamps equal -> bounded by the minimum weighted solve time (~10x)
  series(DIFFICULTY_WINDOW + 1, 0, 100000, ts, cd);
  EXPECT_EQ(lwma(ts, cd), difficulty_type(1006500));
  // only the last N+1 blocks count
  std::vector<uint64_t> ts2; std::vector<difficulty_type> cd2;
  series(300, 30, 100000, ts2, cd2);
  for (size_t i = 0; i < 100; ++i) ts2.at(i) = 7;                        // garbage outside the window
  EXPECT_EQ(lwma(ts2, cd2), difficulty_type(99000));
  // out-of-order timestamps never break it
  series(DIFFICULTY_WINDOW + 1, 30, 100000, ts, cd);
  ts.at(30) = ts.at(29) + 100000;                                        // far-future block in the middle
  const difficulty_type d = lwma(ts, cd);
  EXPECT(d >= 1);
  EXPECT(d > difficulty_type(99000));   // later honest blocks count as 1 s: difficulty rises, not falls
  // the 64-bit wrapper agrees with the wide version
  std::vector<uint64_t> cd64;
  series(DIFFICULTY_WINDOW + 1, 31, 123456, ts, cd);
  for (const auto &c: cd) cd64.push_back(c.convert_to<uint64_t>());
  EXPECT_EQ(difficulty_type(cryptonote::next_difficulty_64(ts, cd64, DIFFICULTY_TARGET_V2)), lwma(ts, cd));
}

// Side chain forked from a mature main chain at difficulty D0. Each new side block is
// stamped `claim` seconds after the previous one, as long as that stays within real
// time (fork time + `available` seconds + the future limit). Returns how many side
// blocks the difficulty floor lets through and the lowest difficulty among them.
static void side_chain_attack(uint64_t claim, uint64_t available, size_t &accepted, difficulty_type &lowest)
{
  const difficulty_type D0 = 150000000;
  std::vector<uint64_t> ts; std::vector<difficulty_type> cd;
  series(DIFFICULTY_WINDOW + 1, 30, D0, ts, cd);          // main chain history up to the fork
  const uint64_t main_height = 100000;                     // mature main chain
  const difficulty_type main_next = lwma(ts, cd);
  const uint64_t fork_time = ts.back();
  accepted = 0; lowest = main_next;
  for (size_t i = 0; i < 2000; ++i)
  {
    const difficulty_type d = lwma(ts, cd);
    if (!cryptonote::alt_difficulty_acceptable(main_height - 50 + i, main_height, d, main_next))
      break;
    ++accepted;
    if (d < lowest) lowest = d;
    uint64_t t = ts.back() + claim;
    if (t > fork_time + available + CRYPTONOTE_BLOCK_FUTURE_TIME_LIMIT)
      t = ts.back() + 1;                                   // out of claimable time
    ts.push_back(t); cd.push_back(cd.back() + d);
  }
}

static void test_alt_difficulty_floor()
{
  using cryptonote::alt_difficulty_acceptable;
  const difficulty_type main_next = 1000000;
  const uint64_t from = OPACRA_ALT_MIN_DIFFICULTY_FROM_HEIGHT;
  EXPECT_EQ(from, uint64_t(122));
  // the floor is 1/4 of the main chain's next difficulty
  EXPECT(alt_difficulty_acceptable(5000, 5000, 250000, main_next));
  EXPECT(!alt_difficulty_acceptable(5000, 5000, 249999, main_next));
  EXPECT(alt_difficulty_acceptable(5000, 5000, 9000000, main_next));   // harder side chains always fine
  // security audit: once the main chain is past its first hour the floor applies at every
  // height, including side blocks near genesis (block 1 has difficulty 1; a side chain
  // forked from genesis walks down to ~16 by height 121)
  EXPECT(!alt_difficulty_acceptable(1, 5000, 1, main_next));
  EXPECT(!alt_difficulty_acceptable(from - 1, 5000, 16, main_next));
  EXPECT(!alt_difficulty_acceptable(12, 5000, 10000, main_next));
  EXPECT(!alt_difficulty_acceptable(from, from, 1, main_next));
  // first hour (main chain below 122 blocks): block 1 now costs the startup guess (except on
  // the public testnet, which is past its first hour), so an honest race for block 1 can be
  // settled at any time in the first hour, and a difficulty-1 block never gets in...
  EXPECT(alt_difficulty_acceptable(1, 2, DIFFICULTY_STARTUP_GUESS, DIFFICULTY_STARTUP_GUESS));
  EXPECT(alt_difficulty_acceptable(1, from - 1, DIFFICULTY_STARTUP_GUESS, main_next));
  EXPECT(!alt_difficulty_acceptable(1, 2, 1, DIFFICULTY_STARTUP_GUESS));
  // ...and the floor is 1/4 of min(main reference, startup guess), which honest blocks meet
  // even right after LWMA takes over from the startup guess (here a 10x jump to 99,000)
  EXPECT(alt_difficulty_acceptable(12, 13, DIFFICULTY_STARTUP_GUESS, 99000));
  EXPECT(alt_difficulty_acceptable(50, 60, 2500, main_next));
  EXPECT(!alt_difficulty_acceptable(50, 60, 2499, main_next));
  EXPECT(alt_difficulty_acceptable(50, 60, 300, 1200));          // very low launch hash rate
  EXPECT(!alt_difficulty_acceptable(50, 60, 299, 1200));

  // an honest competing side chain (blocks on target) is never refused
  size_t accepted; difficulty_type lowest;
  side_chain_attack(30, 1000000000, accepted, lowest);
  EXPECT_EQ(accepted, size_t(2000));
  // attack: claim the maximum 6T per block from a fork with unlimited claimable time
  // (e.g. a fork from long ago). Without the floor the difficulty falls to 1; with it,
  // the side chain is cut off and no accepted block is cheaper than 1/4 of the main chain.
  side_chain_attack(6 * DIFFICULTY_TARGET_V2, 1000000000, accepted, lowest);
  std::printf("side-chain attack at 6T per block: %zu blocks accepted before the floor, lowest difficulty %s (main chain ~148500000)\n",
              accepted, str(lowest).c_str());
  EXPECT(accepted < 200);
  EXPECT(lowest >= difficulty_type(150000000) * 99 / 100 / 4);

  // security audit: side chain forked from genesis (timestamp 0), stamped 6T apart, with the
  // real LWMA. Before the fix every block up to height 121 was accepted for ever at a cost of
  // 1 hash (height 1) down to 16 hashes (height 121).
  for (const uint64_t main_height: {uint64_t(5000), uint64_t(100)})
  {
    const difficulty_type main_now = main_height == 5000 ? difficulty_type(1000000) : difficulty_type(DIFFICULTY_STARTUP_GUESS);
    std::vector<uint64_t> gts; std::vector<difficulty_type> gcd;
    size_t got = 0; difficulty_type cheapest = 0; bool first = true;
    for (uint64_t h = 1; h < from; ++h)
    {
      const difficulty_type d = lwma(gts, gcd);
      if (cryptonote::alt_difficulty_acceptable(h, main_height, d, main_now))
      {
        ++got;
        if (first || d < cheapest) cheapest = d;
        first = false;
      }
      gts.push_back(h * 6 * DIFFICULTY_TARGET_V2);
      gcd.push_back((gcd.empty() ? difficulty_type(0) : gcd.back()) + d);
    }
    std::printf("side chain from genesis, main chain at %llu blocks: %zu of %llu side blocks accepted, cheapest %s\n",
                (unsigned long long)main_height, got, (unsigned long long)(from - 1), str(cheapest).c_str());
    if (main_height == 5000)
      EXPECT_EQ(got, size_t(0));
    else
      EXPECT(got == 0 || cheapest >= difficulty_type(DIFFICULTY_STARTUP_GUESS / 4));
  }

  // security audit: eclipse + inflated difficulty. An attacker feeds an eclipsed node fake
  // 1-second blocks until its next difficulty is 4x the honest one; compared with that next
  // difficulty alone, the honest chain's blocks fall below the floor and the node would
  // refuse them for ever. Blockchain::get_alt_floor_reference() uses the lowest main-chain
  // difficulty of the last 720 blocks instead, which still includes the honest blocks.
  {
    std::vector<uint64_t> its; std::vector<difficulty_type> icd;
    series(DIFFICULTY_WINDOW + 1, DIFFICULTY_TARGET_V2, 1000000, its, icd);
    const difficulty_type honest_next = lwma(its, icd);
    difficulty_type lowest_recent = honest_next;
    size_t fake = 0;
    while (lwma(its, icd) < honest_next * 4)
    {
      const difficulty_type d = lwma(its, icd);
      if (d < lowest_recent) lowest_recent = d;
      its.push_back(its.back() + 1); icd.push_back(icd.back() + d);
      ++fake;
    }
    const difficulty_type inflated_next = lwma(its, icd);
    std::printf("eclipse inflation: %zu fake blocks push the next difficulty from %s to %s\n", fake, str(honest_next).c_str(), str(inflated_next).c_str());
    EXPECT(!alt_difficulty_acceptable(5000, 5100, honest_next, inflated_next));
    EXPECT(alt_difficulty_acceptable(5000, 5100, honest_next, std::min(inflated_next, lowest_recent)));
  }
}

static void test_dev_fund()
{
  using namespace cryptonote;
  // 5% of the subsidy, none for genesis, floor division, no overflow
  EXPECT_EQ(get_dev_fund_share(FULL, 0), uint64_t(0));
  EXPECT_EQ(get_dev_fund_share(FULL, 1), FULL * 5 / 100);
  EXPECT_EQ(get_dev_fund_share(TAIL_EMISSION_REWARD, 50000000), uint64_t(2500000000));   // 0.0025 OPCA of the tail
  EXPECT_EQ(get_dev_fund_share(19, 7), uint64_t(0));
  EXPECT_EQ(get_dev_fund_share(UINT64_MAX, 7), (uint64_t)((unsigned __int128)UINT64_MAX * 5 / 100));

  // every network has a valid standard fund address; regtest uses mainnet's
  account_public_address main_addr, test_addr, stage_addr, fake_addr;
  EXPECT(get_dev_fund_address(MAINNET, main_addr));
  EXPECT(get_dev_fund_address(TESTNET, test_addr));
  EXPECT(get_dev_fund_address(STAGENET, stage_addr));
  EXPECT(get_dev_fund_address(FAKECHAIN, fake_addr));
  EXPECT(main_addr == fake_addr);
  EXPECT(!(main_addr == test_addr));

  // the published view key belongs to each network's fund address
  crypto::secret_key fund_view;
  account_public_address keys_addr;
  EXPECT(get_dev_fund_keys(MAINNET, keys_addr, fund_view));
  EXPECT(keys_addr == main_addr);
  crypto::secret_key other_view;
  EXPECT(get_dev_fund_keys(TESTNET, keys_addr, other_view));
  EXPECT(keys_addr == test_addr);
  EXPECT(get_dev_fund_keys(STAGENET, keys_addr, other_view));
  EXPECT(keys_addr == stage_addr);

  // the fund's transaction key is fixed by the height and the previous block, and different
  // for every height and every previous block (security audit: nobody can know it before
  // the previous block exists, so nobody can plant a decoy with the same one-time key)
  crypto::hash prev = crypto::cn_fast_hash("prev", 4), other_prev = crypto::cn_fast_hash("other", 5);
  crypto::secret_key fr1, fr2;
  crypto::public_key fR1, fR2, fR3, fR4;
  EXPECT_EQ(get_dev_fund_prev_id_binding_height(MAINNET), uint64_t(1));
  EXPECT_EQ(get_dev_fund_prev_id_binding_height(FAKECHAIN), uint64_t(1));
  EXPECT_EQ(get_dev_fund_prev_id_binding_height(TESTNET), uint64_t(30000));
  get_dev_fund_tx_key(MAINNET, 100, prev, fr1, fR1);
  get_dev_fund_tx_key(MAINNET, 100, prev, fr2, fR2);
  EXPECT(fR1 == fR2);
  get_dev_fund_tx_key(MAINNET, 101, prev, fr2, fR3);
  EXPECT(!(fR1 == fR3));
  get_dev_fund_tx_key(MAINNET, 100, other_prev, fr2, fR4);
  EXPECT(!(fR1 == fR4));
  // the public testnet keeps the old per-height key below 30,000 (its existing blocks stay
  // valid) and binds the previous block from 30,000
  get_dev_fund_tx_key(TESTNET, 29999, prev, fr2, fR3);
  get_dev_fund_tx_key(TESTNET, 29999, other_prev, fr2, fR4);
  EXPECT(fR3 == fR4);
  get_dev_fund_tx_key(TESTNET, 30000, prev, fr2, fR3);
  get_dev_fund_tx_key(TESTNET, 30000, other_prev, fr2, fR4);
  EXPECT(!(fR3 == fR4));
  {
    // below the switch the key is exactly the original Hs("OpacraDevFund" || height)
    char legacy[13 + 8];
    memcpy(legacy, "OpacraDevFund", 13);
    const uint64_t h = SWAP64LE(uint64_t(29999));
    memcpy(legacy + 13, &h, 8);
    crypto::secret_key lr; crypto::public_key lR;
    crypto::hash_to_scalar(legacy, sizeof(legacy), lr);
    crypto::secret_key_to_public_key(lr, lR);
    get_dev_fund_tx_key(TESTNET, 29999, prev, fr2, fR3);
    EXPECT(lR == fR3);
  }

  // a coinbase at height 100: miner output first (paid with the coinbase's random key),
  // fund output last with 5% of the subsidy (paid with R_f, the second tx public key)
  keypair miner_spend = keypair::generate(hw::get_device("default"));
  keypair miner_view = keypair::generate(hw::get_device("default"));
  account_public_address miner{miner_spend.pub, miner_view.pub};
  transaction tx, tx2;
  const uint64_t fee = 123456789;
  EXPECT(construct_miner_tx(100, 0, FULL, 0, fee, miner, tx, blobdata(), 1, 16, MAINNET, prev));
  uint64_t subsidy = 0;
  EXPECT(get_block_reward_at_height(0, 0, FULL, subsidy, 16, 100));
  EXPECT_EQ(tx.vout.size(), size_t(2));
  EXPECT_EQ(tx.vout[1].amount, get_dev_fund_share(subsidy, 100));
  EXPECT_EQ(tx.vout[0].amount, subsidy - get_dev_fund_share(subsidy, 100) + fee);
  EXPECT(get_additional_tx_pub_keys_from_extra(tx).empty());
  const crypto::public_key main_pub = get_tx_pub_key_from_extra(tx, 0);
  EXPECT(get_tx_pub_key_from_extra(tx, 1) == fR1);              // R_f follows the miner's key
  EXPECT(!(main_pub == fR1));
  crypto::public_key k1, k2, out_key;
  crypto::view_tag t1, t2;
  EXPECT(get_dev_fund_output(MAINNET, 100, prev, 1, k1, t1));
  EXPECT(get_output_public_key(tx.vout[1], out_key));
  EXPECT(out_key == k1);
  EXPECT(get_output_view_tag(tx.vout[1]) && *get_output_view_tag(tx.vout[1]) == t1);
  EXPECT(get_dev_fund_output(MAINNET, 100, prev, 0, k2, t2));
  EXPECT(!(k1 == k2));                                           // index matters
  // the fund output for a block is the same in every coinbase (nobody can choose it),
  // and different at every height (no two blocks share a fund key)
  EXPECT(construct_miner_tx(100, 0, FULL, 0, fee, miner, tx2, blobdata(), 1, 16, MAINNET, prev));
  crypto::public_key out_key2;
  EXPECT(get_output_public_key(tx2.vout[1], out_key2));
  EXPECT(out_key == out_key2);
  EXPECT(get_dev_fund_output(MAINNET, 101, prev, 1, k2, t2));
  EXPECT(!(k1 == k2));

  // the fund's wallet finds its output with the view key through R_f (wallet scanning maths)
  crypto::key_derivation d;
  crypto::public_key found;
  EXPECT(crypto::generate_key_derivation(fR1, fund_view, d));
  EXPECT(crypto::derive_public_key(d, 1, main_addr.m_spend_public_key, found));
  EXPECT(found == out_key);
  // ...and the miner's wallet still finds the miner output through the main key
  EXPECT(crypto::generate_key_derivation(main_pub, miner_view.sec, d));
  EXPECT(crypto::derive_public_key(d, 0, miner.m_spend_public_key, found));
  EXPECT(get_output_public_key(tx.vout[0], out_key));
  EXPECT(found == out_key);
  // ...and the miner's view key does not see the fund output
  EXPECT(crypto::derive_public_key(d, 1, miner.m_spend_public_key, found));
  EXPECT(get_output_public_key(tx.vout[1], out_key));
  EXPECT(!(found == out_key));

  // genesis-style coinbase (height 0) has no fund output
  transaction g;
  EXPECT(construct_miner_tx(0, 0, 0, 0, 0, miner, g, blobdata(), 1, 1, MAINNET));
  EXPECT_EQ(g.vout.size(), size_t(1));
}

static void test_hardforks_and_identity()
{
  EXPECT_EQ(num_mainnet_hard_forks, (size_t)2);
  EXPECT_EQ((int)mainnet_hard_forks[0].version, 1);
  EXPECT_EQ(mainnet_hard_forks[0].height, (uint64_t)0);
  EXPECT_EQ((int)mainnet_hard_forks[1].version, 16);
  EXPECT_EQ(mainnet_hard_forks[1].height, (uint64_t)1);
  EXPECT_EQ(mainnet_hard_fork_version_1_till, (uint64_t)0);
  EXPECT_EQ(num_testnet_hard_forks, (size_t)2);
  EXPECT_EQ(num_stagenet_hard_forks, (size_t)2);

  const cryptonote::network_type nets[] = { cryptonote::MAINNET, cryptonote::TESTNET, cryptonote::STAGENET };
  std::vector<uint64_t> prefixes;
  for (auto n: nets)
  {
    const auto &c = cryptonote::get_config(n);
    prefixes.push_back(c.CRYPTONOTE_PUBLIC_ADDRESS_BASE58_PREFIX);
    prefixes.push_back(c.CRYPTONOTE_PUBLIC_INTEGRATED_ADDRESS_BASE58_PREFIX);
    prefixes.push_back(c.CRYPTONOTE_PUBLIC_SUBADDRESS_BASE58_PREFIX);
  }
  for (size_t i = 0; i < prefixes.size(); ++i)
    for (size_t j = i + 1; j < prefixes.size(); ++j)
      EXPECT(prefixes[i] != prefixes[j]);
  EXPECT_EQ(DIFFICULTY_TARGET_V1, 30);
  EXPECT_EQ(DIFFICULTY_TARGET_V2, 30);
}

int main()
{
  test_emission();
  test_slow_start();
  test_lwma();
  test_alt_difficulty_floor();
  test_dev_fund();
  test_hardforks_and_identity();
  std::printf("%d checks, %d failures\n", checks, failures);
  return failures == 0 ? 0 : 1;
}
