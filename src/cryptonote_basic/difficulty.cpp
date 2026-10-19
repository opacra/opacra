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

#include <algorithm>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>

#include "int-util.h"
#include "misc_log_ex.h"
#include "crypto/hash.h"
#include "cryptonote_config.h"
#include "difficulty.h"

#undef MONERO_DEFAULT_LOG_CATEGORY
#define MONERO_DEFAULT_LOG_CATEGORY "difficulty"

namespace cryptonote {

  using std::size_t;
  using std::uint64_t;
  using std::vector;

#if defined(__x86_64__)
  static inline void mul(uint64_t a, uint64_t b, uint64_t &low, uint64_t &high) {
    low = mul128(a, b, &high);
  }

#else

  static inline void mul(uint64_t a, uint64_t b, uint64_t &low, uint64_t &high) {
    // __int128 isn't part of the standard, so the previous function wasn't portable. mul128() in Windows is fine,
    // but this portable function should be used elsewhere. Credit for this function goes to latexi95.

    uint64_t aLow = a & 0xFFFFFFFF;
    uint64_t aHigh = a >> 32;
    uint64_t bLow = b & 0xFFFFFFFF;
    uint64_t bHigh = b >> 32;

    uint64_t res = aLow * bLow;
    uint64_t lowRes1 = res & 0xFFFFFFFF;
    uint64_t carry = res >> 32;

    res = aHigh * bLow + carry;
    uint64_t highResHigh1 = res >> 32;
    uint64_t highResLow1 = res & 0xFFFFFFFF;

    res = aLow * bHigh;
    uint64_t lowRes2 = res & 0xFFFFFFFF;
    carry = res >> 32;

    res = aHigh * bHigh + carry;
    uint64_t highResHigh2 = res >> 32;
    uint64_t highResLow2 = res & 0xFFFFFFFF;

    //Addition

    uint64_t r = highResLow1 + lowRes2;
    carry = r >> 32;
    low = (r << 32) | lowRes1;
    r = highResHigh1 + highResLow2 + carry;
    uint64_t d3 = r & 0xFFFFFFFF;
    carry = r >> 32;
    r = highResHigh2 + carry;
    high = d3 | (r << 32);
  }

#endif

  static inline bool cadd(uint64_t a, uint64_t b) {
    return a + b < a;
  }

  static inline bool cadc(uint64_t a, uint64_t b, bool c) {
    return a + b < a || (c && a + b == (uint64_t) -1);
  }

  bool check_hash_64(const crypto::hash &hash, uint64_t difficulty) {
    uint64_t low, high, top, cur;
    // First check the highest word, this will most likely fail for a random hash.
    mul(swap64le(((const uint64_t *) &hash)[3]), difficulty, top, high);
    if (high != 0) {
      return false;
    }
    mul(swap64le(((const uint64_t *) &hash)[0]), difficulty, low, cur);
    mul(swap64le(((const uint64_t *) &hash)[1]), difficulty, low, high);
    bool carry = cadd(cur, low);
    cur = high;
    mul(swap64le(((const uint64_t *) &hash)[2]), difficulty, low, high);
    carry = cadc(cur, low, carry);
    carry = cadc(high, top, carry);
    return !carry;
  }

  uint64_t next_difficulty_64(std::vector<std::uint64_t> timestamps, std::vector<uint64_t> cumulative_difficulties, size_t target_seconds) {
    // Opacra: kept for API compatibility (tests/tools); uses the same LWMA-1 rule
    std::vector<difficulty_type> wide(cumulative_difficulties.begin(), cumulative_difficulties.end());
    const difficulty_type d = next_difficulty(std::move(timestamps), std::move(wide), target_seconds);
    if (d > std::numeric_limits<uint64_t>::max())
      return 0;
    return d.convert_to<uint64_t>();
  }

#if defined(_MSC_VER)
#ifdef max
#undef max
#endif
#endif

  const difficulty_type max64bit(std::numeric_limits<std::uint64_t>::max());
  const boost::multiprecision::uint256_t max128bit(std::numeric_limits<boost::multiprecision::uint128_t>::max());
  const boost::multiprecision::uint512_t max256bit(std::numeric_limits<boost::multiprecision::uint256_t>::max());

#define FORCE_FULL_128_BITS

  bool check_hash_128(const crypto::hash &hash, difficulty_type difficulty) {
#ifndef FORCE_FULL_128_BITS
    // fast check
    if (difficulty >= max64bit && ((const uint64_t *) &hash)[3] > 0)
      return false;
#endif
    // usual slow check
    boost::multiprecision::uint512_t hashVal = 0;
#ifdef FORCE_FULL_128_BITS
    for(int i = 0; i < 4; i++) { // highest word is zero
#else
    for(int i = 1; i < 4; i++) { // highest word is zero
#endif
      hashVal <<= 64;
      hashVal |= swap64le(((const uint64_t *) &hash)[3 - i]);
    }
    return hashVal * difficulty <= max256bit;
  }

  bool check_hash(const crypto::hash &hash, difficulty_type difficulty) {
    if (difficulty <= max64bit) // if can convert to small difficulty - do it
      return check_hash_64(hash, difficulty.convert_to<std::uint64_t>());
    else
      return check_hash_128(hash, difficulty);
  }

  // Opacra: LWMA-1 difficulty algorithm
  // Copyright (c) 2017-2019 Zawy (zawy12), MIT License
  // https://github.com/zawy12/difficulty-algorithms/issues/3
  //
  // Linearly weighted moving average of solve times over the last N blocks: the most
  // recent block has weight N, the oldest weight 1.  It reacts to hashrate changes
  // within a few blocks while staying stable, which matters for a young PoW chain with
  // fast (30 s) blocks.  Integer arithmetic only, so every node computes the same value.
  //
  // Inputs are the timestamps and cumulative difficulties of the most recent blocks in
  // chain order (oldest first), genesis excluded.  Only the last N+1 entries are used.
  // Opacra: LWMA lets a side chain's difficulty fall as fast as its timestamps claim
  // slow blocks, and with no checkpoints a side chain may fork from far back, where
  // hours of "slow" timestamps are allowed. That let an attacker walk a side chain's
  // difficulty down to almost nothing and flood nodes with free blocks. A side chain
  // that has to compete with ours never needs a much lower difficulty than ours, so a
  // floor of 1/4 of the main chain's difficulty stops the flood without limiting reorg
  // depth. It starts once the main chain has two full LWMA windows (about an hour), so
  // launch-day swings from the startup guess cannot split nodes.
  //
  // Security audit (October 2026): the first version exempted side blocks below height
  // 122 forever. Block 1 then had difficulty 1 and a side chain forked from genesis (timestamp
  // 0) can claim days of slow blocks, so side blocks at heights 1-121 cost 1-10,000
  // hashes for as long as the chain exists, and anyone could flood any node with them.
  // Now the exemption depends only on the main chain's age:
  //  - In the first hour (main chain below 122 blocks) the floor is 1/4 of the smaller of
  //    the main chain's reference difficulty and the startup guess, which honest blocks
  //    always meet, even when LWMA jumps after the startup guess. Block 1 costs the startup
  //    guess too on every network (Blockchain::get_difficulty_for_next_block), so no height
  //    is free.
  //  - After that every side block, at any height, needs 1/4 of the main chain's reference
  //    difficulty (Blockchain::get_alt_floor_reference). Trade-off: a launch partition that
  //    splits within the first 12 blocks and lasts beyond the first hour cannot merge by
  //    itself (nodes on the losing side need pop_blocks); see docs/SECURITY_AUDIT_2026-10.md.
  bool alt_difficulty_acceptable(uint64_t alt_height, uint64_t main_chain_height, const difficulty_type &alt_difficulty, const difficulty_type &main_reference_difficulty)
  {
    (void)alt_height;
    if (main_chain_height < OPACRA_ALT_MIN_DIFFICULTY_FROM_HEIGHT)
    {
      const difficulty_type reference = std::min(main_reference_difficulty, difficulty_type(DIFFICULTY_STARTUP_GUESS));
      return alt_difficulty >= reference / OPACRA_ALT_MIN_DIFFICULTY_DIVISOR;
    }
    return alt_difficulty >= main_reference_difficulty / OPACRA_ALT_MIN_DIFFICULTY_DIVISOR;
  }

  difficulty_type next_difficulty(std::vector<uint64_t> timestamps, std::vector<difficulty_type> cumulative_difficulties, size_t target_seconds) {
    CHECK_AND_ASSERT_THROW_MES(timestamps.size() == cumulative_difficulties.size(), "LWMA: timestamps/difficulties size mismatch");

    const size_t window = DIFFICULTY_WINDOW + 1;
    if (timestamps.size() > window)
    {
      timestamps.erase(timestamps.begin(), timestamps.end() - window);
      cumulative_difficulties.erase(cumulative_difficulties.begin(), cumulative_difficulties.end() - window);
    }

    const size_t length = timestamps.size();
    // No previous blocks (only genesis asks this): difficulty 1, as in Monero. Block 1 gets the
    // startup guess from Blockchain::get_difficulty_for_next_block.
    if (length == 0)
      return 1;
    // Startup: a fixed, deliberately low guess until a few blocks exist.
    if (length < DIFFICULTY_STARTUP_BLOCKS)
      return DIFFICULTY_STARTUP_GUESS;

    const uint64_t T = target_seconds;
    const uint64_t N = length - 1;  // number of solve times available (<= DIFFICULTY_WINDOW)

    // Weighted sum of solve times.  Out-of-sequence timestamps are treated as a 1 second
    // solve time and every solve time is capped at 6*T, which bounds the effect of any
    // single manipulated timestamp.
    uint64_t L = 0;
    uint64_t previous_timestamp = timestamps[0];
    for (uint64_t i = 1; i <= N; ++i)
    {
      const uint64_t this_timestamp = timestamps[i] > previous_timestamp ? timestamps[i] : previous_timestamp + 1;
      L += i * std::min<uint64_t>(6 * T, this_timestamp - previous_timestamp);
      previous_timestamp = this_timestamp;
    }
    // Keep the result bounded when blocks arrive (nearly) instantly
    const uint64_t L_min = N * N * T / 20;
    if (L < L_min)
      L = L_min;

    // next_D = avg_D * T * (N(N+1)/2) / L * 0.99, with avg_D = total_work / N
    //        = total_work * T * (N+1) * 99 / (200 * L)
    const difficulty_type total_work = cumulative_difficulties[N] - cumulative_difficulties[0];
    const boost::multiprecision::uint256_t numerator = boost::multiprecision::uint256_t(total_work) * T * (N + 1) * 99;
    const boost::multiprecision::uint256_t denominator = boost::multiprecision::uint256_t(200) * L;
    boost::multiprecision::uint256_t next_d = numerator / denominator;
    if (next_d < 1)
      next_d = 1;
    if (next_d > max128bit)
      return 0; // blockchain reports "difficulty overhead"; unreachable in practice
    return next_d.convert_to<difficulty_type>();
  }

  std::string hex(difficulty_type v)
  {
    static const char chars[] = "0123456789abcdef";
    std::string s;
    while (v > 0)
    {
      s.push_back(chars[(v & 0xf).convert_to<unsigned>()]);
      v >>= 4;
    }
    if (s.empty())
      s += "0";
    std::reverse(s.begin(), s.end());
    return "0x" + s;
  }

}
