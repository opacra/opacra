// Copyright (c) 2026, The Opacra Project
// BSD-3-Clause, see LICENSE.
//
// Difficulty fuzz harness: runs the node's real next_difficulty() on cases read from
// stdin and prints one result per line, so contrib/sim/difficulty_fuzz.py can compare it
// with the independent Python model (contrib/sim/opacra_params.py).
//
// Input, one case per line:  <target> <n> <t_1> ... <t_n> <c_1> ... <c_n>
//   (timestamps, then cumulative difficulties as decimal integers up to 2^128-1)
// Output, one line per case: the next difficulty as a decimal integer.
//   make opacra_difficulty_fuzz && python3 contrib/sim/difficulty_fuzz.py

#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include "cryptonote_basic/difficulty.h"

using cryptonote::difficulty_type;

int main()
{
  std::ios::sync_with_stdio(false);
  std::string line;
  while (std::getline(std::cin, line))
  {
    if (line.empty())
      continue;
    std::istringstream in(line);
    uint64_t target = 0;
    size_t n = 0;
    if (!(in >> target >> n))
    {
      std::cout << "PARSE_ERROR\n";
      continue;
    }
    std::vector<std::uint64_t> timestamps(n);
    std::vector<difficulty_type> cumulative(n);
    for (size_t i = 0; i < n; ++i)
      in >> timestamps[i];
    for (size_t i = 0; i < n; ++i)
    {
      std::string s;
      in >> s;
      cumulative[i] = difficulty_type(s);
    }
    if (!in)
    {
      std::cout << "PARSE_ERROR\n";
      continue;
    }
    const difficulty_type d = cryptonote::next_difficulty(timestamps, cumulative, target);
    std::cout << d << '\n';
  }
  return 0;
}
