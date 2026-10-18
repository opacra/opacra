// Copyright (c) 2026, The Opacra Project
// Portions Copyright (c) 2014-2022, The Monero Project
//
// Redistribution and use in source and binary forms, with or without modification, are
// permitted under the terms of the BSD-3-Clause license found in the LICENSE file.
//
// ---------------------------------------------------------------------------------------
// LAUNCH-TIME NETWORK ENDPOINTS
//
// Everything a node contacts on its own lives here, so that no Opacra node ever talks to
// Monero infrastructure (seed nodes, MoneroPulse DNS, getmonero.org downloads).
// Fill these in before building release binaries (see docs/LAUNCH_CHECKLIST.md).
// Empty lists simply disable the feature; nodes can always be pointed at peers with
// --add-peer / --add-priority-node / --seed-node on the command line.
// ---------------------------------------------------------------------------------------

#pragma once

#include <cstdint>
#include <string>
#include <vector>
#include "cryptonote_config.h"

namespace coin_network
{
  // Hard-coded fallback seed nodes, "ip:port".  Put 3+ geographically separate VPSes here.
  inline std::vector<std::string> ip_seed_nodes(cryptonote::network_type nettype)
  {
    switch (nettype)
    {
      case cryptonote::MAINNET:
        return {
          "169.58.62.247:29960",   // seed 1 (Contabo, Hub Europe)
          "13.140.226.160:29960",  // seed 2 (Contabo, US East), ordered 18 Oct 2026
        };
      case cryptonote::TESTNET:
        return {
          "169.58.62.247:29970",   // testnet seed 1 (Contabo, EU), live since 4 Oct 2026
          "13.140.226.160:29970",  // testnet seed 2 (Contabo, US East), live since 18 Oct 2026
        };
      case cryptonote::STAGENET:
        return {};
      default:
        return {};
    }
  }

  // DNS names whose A records list seed node IPs (mainnet only).  e.g. "seeds.opacra.org"
  inline std::vector<std::string> dns_seed_domains()
  {
    return {};
  }

  // Tor / I2P seed nodes ("xxxx.onion:29963", "xxxx.b32.i2p")
  inline std::vector<std::string> tor_seed_nodes() { return {}; }
  inline std::vector<std::string> i2p_seed_nodes() { return {}; }

  // DNSSEC-signed TXT records "height:hash" used for emergency checkpoints (MoneroPulse-style).
  // A checkpoint counts only when every domain listed publishes exactly the same set of records
  // and each answer passes DNSSEC validation (tools::dns_utils::load_txt_records_from_dns needs
  // agreement from more than half of the domains, and with two that means both). The domains
  // are on two separate zones (opacra.org, opacra.com) in a dedicated, 2FA-protected registrar
  // account. Ordinary nodes only warn when their chain disagrees with a DNS checkpoint; nodes
  // started with --enforce-dns-checkpointing (seeds, exchanges) refuse to reorganise below it.
  inline std::vector<std::string> checkpoint_dns_domains(cryptonote::network_type nettype)
  {
    switch (nettype)
    {
      case cryptonote::MAINNET:  return {"checkpoints.opacra.org", "checkpoints.opacra.com"};
      case cryptonote::TESTNET:  return {"testpoints.opacra.org", "testpoints.opacra.com"};
      case cryptonote::STAGENET: return {};
      default:                   return {};
    }
  }

  // How often a running node re-reads the DNS checkpoints, in seconds. Monero uses an hour;
  // Opacra's 30-second blocks make an hour 120 blocks, so emergency checkpoints are read every
  // 5 minutes. Two small TXT lookups per node every 5 minutes are negligible.
  constexpr int64_t dns_checkpoint_refresh_seconds = 300;

  // DNSSEC-signed TXT records announcing releases "<software>:<buildtag>:<version>:<sha256>"
  inline std::vector<std::string> update_dns_domains() { return {}; }

  // Base URLs used by --check-updates=download (must end with '/')
  inline std::string download_base_url_user() { return "https://downloads.opacra.org/"; }
  inline std::string download_base_url_auto() { return "https://updates.opacra.org/"; }

  // DNSSEC-signed TXT records listing IPs/subnets to ban (mainnet only)
  inline std::vector<std::string> blocklist_dns_domains() { return {}; }

  // A DNSSEC-signed name used to test whether the local resolver validates DNSSEC
  inline const char *dnssec_probe_hostname() { return "ietf.org"; }
}
