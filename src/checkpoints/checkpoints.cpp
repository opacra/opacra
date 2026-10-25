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

#include "checkpoints.h"
#include "coin_network.h"

#include "common/dns_utils.h"
#include "string_tools.h"
#include "storages/portable_storage_template_helper.h" // epee json include
#include "serialization/keyvalue_serialization.h"
#include <boost/system/error_code.hpp>
#include <boost/filesystem.hpp>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <vector>

using namespace epee;

#undef MONERO_DEFAULT_LOG_CATEGORY
#define MONERO_DEFAULT_LOG_CATEGORY "checkpoints"

namespace cryptonote
{
  /**
   * @brief struct for loading a checkpoint from json
   */
  struct t_hashline
  {
    uint64_t height; //!< the height of the checkpoint
    std::string hash; //!< the hash for the checkpoint
        BEGIN_KV_SERIALIZE_MAP()
          KV_SERIALIZE(height)
          KV_SERIALIZE(hash)
        END_KV_SERIALIZE_MAP()
  };

  /**
   * @brief struct for loading many checkpoints from json
   */
  struct t_hash_json {
    std::vector<t_hashline> hashlines; //!< the checkpoint lines from the file
        BEGIN_KV_SERIALIZE_MAP()
          KV_SERIALIZE(hashlines)
        END_KV_SERIALIZE_MAP()
  };

  //---------------------------------------------------------------------------
  checkpoints::checkpoints()
  {
  }
  //---------------------------------------------------------------------------
  bool checkpoints::add_checkpoint(uint64_t height, const std::string& hash_str, const std::string& difficulty_str)
  {
    crypto::hash h = crypto::null_hash;
    bool r = epee::string_tools::hex_to_pod(hash_str, h);
    CHECK_AND_ASSERT_MES(r, false, "Failed to parse checkpoint hash string into binary representation!");

    // return false if adding at a height we already have AND the hash is different
    if (m_base_points.count(height))
    {
      CHECK_AND_ASSERT_MES(h == m_base_points[height], false, "Checkpoint at given height already exists, and hash for new checkpoint was different!");
    }
    m_base_points[height] = h;
    rebuild_points();
    if (!difficulty_str.empty())
    {
      try
      {
        difficulty_type difficulty(difficulty_str);
        if (m_difficulty_points.count(height))
        {
          CHECK_AND_ASSERT_MES(difficulty == m_difficulty_points[height], false, "Difficulty checkpoint at given height already exists, and difficulty for new checkpoint was different!");
        }
        m_difficulty_points[height] = difficulty;
      }
      catch (...)
      {
        LOG_ERROR("Failed to parse difficulty checkpoint: " << difficulty_str);
        return false;
      }
    }
    return true;
  }
  //---------------------------------------------------------------------------
  void checkpoints::rebuild_points()
  {
    // a hard-coded or JSON checkpoint wins over a DNS one at the same height
    m_points = m_base_points;
    for (const auto &pt : m_dns_points)
      m_points.emplace(pt.first, pt.second);
  }
  //---------------------------------------------------------------------------
  bool checkpoints::set_dns_points(const std::map<uint64_t, crypto::hash>& points)
  {
    for (const auto &pt : points)
    {
      const auto it = m_base_points.find(pt.first);
      if (it != m_base_points.end() && it->second != pt.second)
      {
        MERROR("DNS checkpoint at block " << pt.first << " (" << pt.second << ") conflicts with this node's own checkpoint ("
            << it->second << ")");
        return false;
      }
    }
    m_dns_points = points;
    rebuild_points();
    return true;
  }
  //---------------------------------------------------------------------------
  const std::map<uint64_t, crypto::hash>& checkpoints::get_dns_points() const
  {
    return m_dns_points;
  }
  //---------------------------------------------------------------------------
  bool checkpoints::is_in_checkpoint_zone(uint64_t height) const
  {
    return !m_points.empty() && (height <= (--m_points.end())->first);
  }
  //---------------------------------------------------------------------------
  bool checkpoints::check_block(uint64_t height, const crypto::hash& h, bool& is_a_checkpoint) const
  {
    auto it = m_points.find(height);
    is_a_checkpoint = it != m_points.end();
    if(!is_a_checkpoint)
      return true;

    if(it->second == h)
    {
      MINFO("CHECKPOINT PASSED FOR HEIGHT " << height << " " << h);
      return true;
    }else
    {
      MWARNING("CHECKPOINT FAILED FOR HEIGHT " << height << ". EXPECTED HASH: " << it->second << ", FETCHED HASH: " << h);
      return false;
    }
  }
  //---------------------------------------------------------------------------
  bool checkpoints::check_block(uint64_t height, const crypto::hash& h) const
  {
    bool ignored;
    return check_block(height, h, ignored);
  }
  //---------------------------------------------------------------------------
  //FIXME: is this the desired behavior?
  bool checkpoints::is_alternative_block_allowed(uint64_t blockchain_height, uint64_t block_height) const
  {
    if (0 == block_height)
      return false;

    auto it = m_points.upper_bound(blockchain_height);
    // Is blockchain_height before the first checkpoint?
    if (it == m_points.begin())
      return true;

    --it;
    uint64_t checkpoint_height = it->first;
    return checkpoint_height < block_height;
  }
  //---------------------------------------------------------------------------
  uint64_t checkpoints::get_max_height() const
  {
    if (m_points.empty())
      return 0;
    return m_points.rbegin()->first;
  }
  //---------------------------------------------------------------------------
  uint64_t checkpoints::get_nearest_checkpoint_height(uint64_t block_height) const
  {
    if (m_points.empty())
      return 0;

    auto it = m_points.lower_bound(block_height);
    if (it == m_points.begin())
      return 0;

    --it;
    return it->first;
  }
  //---------------------------------------------------------------------------
  const std::map<uint64_t, crypto::hash>& checkpoints::get_points() const
  {
    return m_points;
  }
  //---------------------------------------------------------------------------
  const std::map<uint64_t, difficulty_type>& checkpoints::get_difficulty_points() const
  {
    return m_difficulty_points;
  }

  bool checkpoints::check_for_conflicts(const checkpoints& other) const
  {
    for (auto& pt : other.get_points())
    {
      if (m_points.count(pt.first))
      {
        CHECK_AND_ASSERT_MES(pt.second == m_points.at(pt.first), false, "Checkpoint at given height already exists, and hash for new checkpoint was different!");
      }
    }
    return true;
  }

  bool checkpoints::init_default_checkpoints(network_type nettype)
  {
    // Opacra: checkpoints are added here as the chain grows (one every few thousand
    // blocks, plus the genesis hash once it is final).  Format:
    //   ADD_CHECKPOINT2(height, "block hash", "cumulative difficulty as hex");
    // Get the values from a synced node:  print_block <height>  (daemon console)
    // or the helper script contrib/launch/make_checkpoint.sh.
    if (nettype == TESTNET)
    {
      ADD_CHECKPOINT2(0, "6a34e62860464e20baca5655351ee2e605e64a5cd1ad3e48751223a44c547a19", "0x1");
      // testnet 3: checkpoints are added once its genesis is final and the chain has grown
      return true;
    }
    if (nettype == STAGENET)
    {
      return true;
    }
    if (nettype == MAINNET)
    {
      // mainnet: the genesis hash is added on launch day (contrib/coin-identity/make_genesis.py)
      return true;
    }
    return true;
  }

  bool checkpoints::load_checkpoints_from_json(const std::string &json_hashfile_fullpath)
  {
    boost::system::error_code errcode;
    if (! (boost::filesystem::exists(json_hashfile_fullpath, errcode)))
    {
      LOG_PRINT_L1("Blockchain checkpoints file not found");
      return true;
    }

    LOG_PRINT_L1("Adding checkpoints from blockchain hashfile");

    // Opacra: compared with the permanent checkpoints only (a DNS checkpoint is not permanent)
    uint64_t prev_max_height = m_base_points.empty() ? 0 : m_base_points.rbegin()->first;
    LOG_PRINT_L1("Hard-coded max checkpoint height is " << prev_max_height);
    t_hash_json hashes;
    if (!epee::serialization::load_t_from_json_file(hashes, json_hashfile_fullpath))
    {
      MERROR("Error loading checkpoints from " << json_hashfile_fullpath);
      return false;
    }
    for (std::vector<t_hashline>::const_iterator it = hashes.hashlines.begin(); it != hashes.hashlines.end(); )
    {
      uint64_t height;
      height = it->height;
      if (height <= prev_max_height) {
	LOG_PRINT_L1("ignoring checkpoint height " << height);
      } else {
	std::string blockhash = it->hash;
	LOG_PRINT_L1("Adding checkpoint height " << height << ", hash=" << blockhash);
	ADD_CHECKPOINT(height, blockhash);
      }
      ++it;
    }

    return true;
  }

  std::string test_dns_records_file(network_type nettype)
  {
    if (nettype == MAINNET)
      return "";
    const char *f = std::getenv("OPACRA_TEST_DNS_CHECKPOINTS");
    return f ? std::string(f) : std::string();
  }

  bool checkpoints::load_checkpoints_from_dns(network_type nettype)
  {
    std::vector<std::string> records;

    const std::string test_file = test_dns_records_file(nettype);
    if (!test_file.empty())
    {
      // tests only (never mainnet): the file's lines stand in for the agreed DNS records; a
      // missing or empty file is the same as DNS being unreadable
      static bool logged = false;
      if (!logged)
        MCLOG_RED(el::Level::Warning, "global", "TEST MODE: reading DNS checkpoint records from " << test_file << " instead of DNS");
      logged = true;
      std::ifstream in(test_file);
      std::string line;
      while (std::getline(in, line))
      {
        while (!line.empty() && (line.back() == '\r' || line.back() == ' '))
          line.pop_back();
        if (!line.empty())
          records.push_back(line);
      }
      if (records.empty())
        return true;
    }
    else
    {
    // Opacra: DNS checkpoint domains are configured in coin_network.h
    const std::vector<std::string> dns_urls = coin_network::checkpoint_dns_domains(nettype);
    if (dns_urls.empty())
      return true;

    if (!tools::dns_utils::load_txt_records_from_dns(records, dns_urls))
      return true; // why true ?
    }

    for (const auto& record : records)
    {
      auto pos = record.find(":");
      if (pos != std::string::npos)
      {
        // Opacra (25 Oct 2026 review): "serial:N" is the records' version number, not a
        // checkpoint (older nodes skip it: "serial" doesn't parse as a height)
        if (record.compare(0, pos, "serial") == 0)
        {
          uint64_t serial = 0;
          std::stringstream ss(record.substr(pos + 1));
          if (ss >> serial && ss.eof())
            m_dns_serial = std::max(m_dns_serial, serial);
          continue;
        }

        uint64_t height;
        crypto::hash hash;

        // parse the first part as uint64_t,
        // if this fails move on to the next record
        std::stringstream ss(record.substr(0, pos));
        if (!(ss >> height))
        {
    continue;
        }

        // parse the second part as crypto::hash,
        // if this fails move on to the next record
        std::string hashStr = record.substr(pos + 1);
        if (!epee::string_tools::hex_to_pod(hashStr, hash))
        {
    continue;
        }

        ADD_CHECKPOINT(height, hashStr);
      }
    }
    return true;
  }

  bool checkpoints::load_new_checkpoints(const std::string &json_hashfile_fullpath, network_type nettype, bool dns)
  {
    bool result;

    result = load_checkpoints_from_json(json_hashfile_fullpath);
    if (dns)
    {
      result &= load_checkpoints_from_dns(nettype);
    }

    return result;
  }
}
