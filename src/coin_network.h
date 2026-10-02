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
          // "203.0.113.10:29960",   // seed-1 (example - replace)
          // "198.51.100.20:29960",  // seed-2 (example - replace)
        };
      case cryptonote::TESTNET:
        return {};
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

  // DNSSEC-signed TXT records "height:hash" used for emergency checkpoints.
  // Leave empty until you control DNSSEC-enabled domains.
  inline std::vector<std::string> checkpoint_dns_domains(cryptonote::network_type nettype)
  {
    switch (nettype)
    {
      case cryptonote::MAINNET:  return {};
      case cryptonote::TESTNET:  return {};
      case cryptonote::STAGENET: return {};
      default:                   return {};
    }
  }

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
