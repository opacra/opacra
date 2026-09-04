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

#include "cryptonote_basic.h"
#include "crypto/crypto.h"
#include "crypto/hash.h"


namespace cryptonote {
  /************************************************************************/
  /*                                                                      */
  /************************************************************************/

#pragma pack(push, 1)
  struct public_address_outer_blob
  {
    uint8_t m_ver;
    account_public_address m_address;
    uint8_t check_sum;
  };
  struct public_integrated_address_outer_blob
  {
    uint8_t m_ver;
    account_public_address m_address;
    crypto::hash8 payment_id;
    uint8_t check_sum;
  };
#pragma pack (pop)

  namespace
  {
    inline std::string return_first_address(const std::string &url, const std::vector<std::string> &addresses, bool dnssec_valid)
    {
      if (addresses.empty())
        return {};
      return addresses[0];
    }
  }

  struct address_parse_info
  {
    account_public_address address;
    bool is_subaddress;
    bool has_payment_id;
    crypto::hash8 payment_id;
  };

  /************************************************************************/
  /* Cryptonote helper functions                                          */
  /************************************************************************/
  size_t get_min_block_weight(uint8_t version);
  size_t get_max_tx_size();
  bool get_block_reward(size_t median_weight, size_t current_block_weight, uint64_t already_generated_coins, uint64_t &reward, uint8_t version);
  // Opacra: reward for a block at a given height. Consensus code (coinbase construction and
  // validation) uses this function, so a height-dependent rule can be added in one place.
  bool get_block_reward_at_height(size_t median_weight, size_t current_block_weight, uint64_t already_generated_coins, uint64_t &reward, uint8_t version, uint64_t height);

  // Opacra development fund (see OPACRA_DEV_FUND_PERCENT in cryptonote_config.h).
  // Share of a block's subsidy (not fees) owed to the fund; 0 for the genesis block.
  uint64_t get_dev_fund_share(uint64_t block_subsidy, uint64_t height);
  // The fund's standard address and its public view secret key for a network (FAKECHAIN
  // uses mainnet's). False if either is malformed or they don't belong together.
  bool get_dev_fund_keys(network_type nettype, account_public_address &address, crypto::secret_key &view_secret_key);
  bool get_dev_fund_address(network_type nettype, account_public_address &address);
  // The fund output's own transaction key for a block:
  //   r_f = Hs("OpacraDevFund" || height || prev_id) from get_dev_fund_prev_id_binding_height()
  //   (block 1 on every network), R_f = r_f*G.
  // It goes into the coinbase as a second transaction public key (after the extra nonce),
  // so the fund's one-time key is unique per block and fixed by consensus: no miner can
  // choose it, reuse it or burn it, and nobody can know it before the previous block exists.
  uint64_t get_dev_fund_prev_id_binding_height(network_type nettype);
  void get_dev_fund_tx_key(network_type nettype, uint64_t height, const crypto::hash &prev_id, crypto::secret_key &tx_key, crypto::public_key &tx_pub_key);
  // The one-time key and view tag the fund's output must have at coinbase output index
  // `output_index` in the block at `height` whose previous block is `prev_id`.
  bool get_dev_fund_output(network_type nettype, uint64_t height, const crypto::hash &prev_id, size_t output_index, crypto::public_key &output_key, crypto::view_tag &view_tag);
  uint8_t get_account_address_checksum(const public_address_outer_blob& bl);
  uint8_t get_account_integrated_address_checksum(const public_integrated_address_outer_blob& bl);

  std::string get_account_address_as_str(
      network_type nettype
    , bool subaddress
    , const account_public_address& adr
    );

  std::string get_account_integrated_address_as_str(
      network_type nettype
    , const account_public_address& adr
    , const crypto::hash8& payment_id
    );

  bool get_account_address_from_str(
      address_parse_info& info
    , network_type nettype
    , const std::string& str
    );

  bool get_account_address_from_str_or_url(
      address_parse_info& info
    , network_type nettype
    , const std::string& str_or_url
    , std::function<std::string(const std::string&, const std::vector<std::string>&, bool)> dns_confirm = return_first_address
    );

  bool operator ==(const cryptonote::transaction& a, const cryptonote::transaction& b);
  bool operator ==(const cryptonote::block& a, const cryptonote::block& b);
}

bool parse_hash256(const std::string &str_hash, crypto::hash& hash);

