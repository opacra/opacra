// Copyright (c) 2026, The Tacita Project
// BSD-3-Clause, see LICENSE.
//
// Regression tests for the consensus rules Tacita changed relative to Monero:
// per-block emission and tail, launch slow start (reward ramp and block-weight cap),
// LWMA-1 difficulty, and the compact hard-fork tables.  No test framework needed:
//   make tacita_consensus_tests && ./bin/tacita_consensus_tests   (exit code 0 = pass)

#include <cstdio>
#include <sstream>
#include <string>
#include <vector>

#include "cryptonote_config.h"
#include "cryptonote_basic/cryptonote_basic_impl.h"
#include "cryptonote_basic/difficulty.h"
#include "hardforks/hardforks.h"

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
  // tail emission when the curve falls below 0.05 TCA, and at / past the cap
  EXPECT(cryptonote::get_block_reward(0, 0, MONEY_SUPPLY - (TAIL_EMISSION_REWARD << 22) + 1, r, 16));
  EXPECT_EQ(r, TAIL_EMISSION_REWARD);
  EXPECT(cryptonote::get_block_reward(0, 0, MONEY_SUPPLY, r, 16));
  EXPECT_EQ(r, TAIL_EMISSION_REWARD);
  EXPECT(cryptonote::get_block_reward(0, 0, MONEY_SUPPLY + 12345, r, 16)); // defensive: no underflow
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
  EXPECT(!cryptonote::get_block_reward_at_height(0, 300001, FULL, r, 16, SLOW_START_BLOCKS - 1)); // median floored at 300 kB
  EXPECT(cryptonote::get_block_reward_at_height(0, 299999, FULL, r, 16, SLOW_START_BLOCKS - 1));
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
  test_hardforks_and_identity();
  std::printf("%d checks, %d failures\n", checks, failures);
  return failures == 0 ? 0 : 1;
}
